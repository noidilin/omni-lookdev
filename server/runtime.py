from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import numpy as np

from .asset_catalog import AssetCatalog
from .camera_controller import OrbitCamera
from .config import LOOKDEV_ASSET_PRIM, OV_CAMERA_PRIM, OV_RENDER_PRODUCT, ServerConfig
from .input_router import InputRouter
from .message_router import MessageRouter
from .render_settings import DEBUG_AOV_NAMES, aov_options_payload
from .scene_loader import STUDIO_CAMERA_XFORM, make_lookdev_composite
from .selection_controller import SelectionController
from .settings_store import SettingsStore
from .stage_queries import StageQueryCache


class RuntimeNotAvailable(RuntimeError):
    pass


class LookdevRuntime:
    def __init__(self, config: ServerConfig):
        os.environ.setdefault("OVRTX_SKIP_USD_CHECK", "1")
        self.config = config
        self.settings = SettingsStore(config.settings_path)
        self.assets = AssetCatalog(config.asset_root)
        self.camera = OrbitCamera(config.width, config.height)
        self.selection = SelectionController()
        self.queries = StageQueryCache()
        self.commands: queue.Queue[dict[str, Any]] = queue.Queue()
        self.ready = threading.Event()
        self.shutdown_requested = threading.Event()
        self.client_connected = False
        self.current_asset_path: Path | None = None
        self.current_composite_path: Path | None = None
        self.input_router = InputRouter(self)
        self.message_router = MessageRouter(self)
        self.renderer = None
        self.stream = None
        self.ovrtx = None
        self.ovstream = None
        self.wp = None
        self._aov_converter = None
        self._last_frame = None
        stored_aov = str(self.settings.render_settings().get("aov", "LdrColor"))
        self._active_aov = stored_aov if stored_aov in DEBUG_AOV_NAMES else "LdrColor"
        self._available_aovs = {"LdrColor"}
        self._last_aov_error = ""
        self._stream_uses_tensor_input = False
        self._last_stream_error = ""
        self.stage_version = 0
        self.stage_lock = threading.Lock()
        self.loading_stage = threading.Event()
        self._active_camera_prim = OV_CAMERA_PRIM
        self._camera_dirty = False
        self._camera_interaction_active = False
        self._last_video_frame = None
        self._reload_sequence = 0
        self._reloaded_asset_references: dict[str, tuple[Path, str]] = {}

    def enqueue(self, command: dict[str, Any]) -> None:
        self.commands.put(command)

    def start(self) -> None:
        self._import_runtime()
        self._start_health_server()
        self._construct_renderer()
        self._load_stage(self.assets.first_asset())
        self._start_stream_server()
        self._render_loop()

    def send(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.stream is None or not getattr(self.stream, "is_client_connected", False):
            return
        try:
            message = {"event_type": event_type, "payload": payload}
            self.stream.send_message(
                json.dumps(
                    {
                        "messageRecipient": "app",
                        "messageType": "json",
                        "data": json.dumps(message, default=str),
                    }
                )
            )
        except Exception:
            pass

    def available_aovs(self) -> list[str]:
        return [name for name in DEBUG_AOV_NAMES if name in self._available_aovs] or ["LdrColor"]

    def active_aov_state(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "active": self._active_aov,
            "available": self.available_aovs(),
            "options": aov_options_payload(),
        }
        if extra:
            payload.update(extra)
        return payload

    def send_aov_state(self, extra: dict[str, Any] | None = None) -> None:
        available = self.available_aovs()
        self.send("activeAOVState", self.active_aov_state(extra))
        self.send("availableAOVsResult", {"aovs": available, "available": available, "options": aov_options_payload()})

    def set_active_aov(self, requested: str) -> bool:
        if requested not in DEBUG_AOV_NAMES:
            return False
        if requested not in self._available_aovs:
            return False
        self._active_aov = requested
        self.settings.render_settings()["aov"] = requested
        self.settings.save()
        return True

    def _import_runtime(self) -> None:
        try:
            import ovrtx
            import ovstream
            import warp as wp
        except ImportError as exc:
            raise RuntimeNotAvailable(
                "Missing ovrtx/ovstream runtime. Run `mise run setup:server:win` on native Windows "
                "or `mise run setup:server` on a supported Linux RTX host."
            ) from exc
        from .aov_conversion import AOVFrameConverter

        self.ovrtx = ovrtx
        self.ovstream = ovstream
        self.wp = wp
        self._aov_converter = AOVFrameConverter()

    def _construct_renderer(self) -> None:
        ovrtx = self.ovrtx
        config = ovrtx.RendererConfig(sync_mode=True, selection_outline_enabled=True, selection_outline_width=4)
        self.renderer = ovrtx.Renderer(config=config)
        if hasattr(self.renderer, "set_selection_group_styles"):
            style = ovrtx.SelectionGroupStyle(outline_color=(1.0, 0.62, 0.14, 1.0), fill_color=(0.0, 0.0, 0.0, 0.0))
            self.renderer.set_selection_group_styles({1: style})

    def _start_stream_server(self) -> None:
        ovstream = self.ovstream
        ovstream.initialize(log_fn=lambda level, channel, msg, ts: print(f"[{level.name}] {channel}: {msg}"))
        self.stream = ovstream.Server(ovstream.ServerType.WEBRTC)
        self.stream.on_connection = self.message_router.on_connection
        self.stream.on_message = self.message_router.on_message
        self.stream.on_input = lambda event: self.input_router.on_input(event, ovstream)
        config = ovstream.ServerConfig(width=self.config.width, height=self.config.height, target_fps=self.config.fps)
        config.webrtc_signal_port = self.config.signaling_port
        config.webrtc_public_ip = self.config.public_ip
        if hasattr(ovstream, "VideoInput"):
            if hasattr(ovstream.VideoFrame, "from_dlpack") and hasattr(ovstream.VideoInput, "TENSOR"):
                config.video_input = ovstream.VideoInput.TENSOR
                self._stream_uses_tensor_input = True
            else:
                config.video_input = ovstream.VideoInput.CUDA
        self.stream.start(config)

    def _load_stage(self, asset_path: Path | None, *, reload_current: bool = False) -> None:
        previous_asset_path = self.current_asset_path
        previous_composite_path = self.current_composite_path
        previous_queries = self.queries
        previous_stage_version = self.stage_version
        previous_selected_paths = list(self.selection.selected_paths)
        previous_pickable_paths = set(self.selection.pickable_paths)
        cache_bust_token = self._next_reload_token(asset_path) if reload_current and asset_path is not None else None
        cache_bust_asset_stage = None
        if reload_current and asset_path is not None and cache_bust_token is not None:
            cache_bust_asset_stage = self._cache_bust_asset_snapshot(asset_path, cache_bust_token)
        asset_reference_stage = cache_bust_asset_stage
        if not reload_current and asset_path is not None:
            asset_reference_stage, cache_bust_token = self._reloaded_asset_reference(asset_path)
        next_queries = StageQueryCache()
        with self.stage_lock:
            composite_path = make_lookdev_composite(
                self.config.studio_stage,
                asset_path,
                self.config.generated_dir,
                self.config.width,
                self.config.height,
                self.settings.render_settings(),
                cache_bust_token=cache_bust_token,
                asset_reference_stage=asset_reference_stage,
            )
            try:
                self.renderer.open_usd(str(composite_path))
                stage_ready = self._refresh_queries_after_load(
                    asset_path,
                    composite_path,
                    next_queries,
                    stream_warmup_frames=not reload_current,
                )
                if reload_current and not stage_ready:
                    detail = next_queries.last_error or f"Reloaded stage did not include {LOOKDEV_ASSET_PRIM}"
                    raise RuntimeError(detail)
            except Exception:
                if reload_current:
                    self.current_asset_path = previous_asset_path
                    self.current_composite_path = previous_composite_path
                    self.queries = previous_queries
                    self.stage_version = previous_stage_version
                    self.selection.selected_paths = previous_selected_paths
                    self.selection.pickable_paths = previous_pickable_paths
                    if previous_composite_path is not None:
                        try:
                            self.renderer.open_usd(str(previous_composite_path))
                            self._refresh_queries_after_load(
                                previous_asset_path,
                                previous_composite_path,
                                previous_queries,
                                stream_warmup_frames=False,
                            )
                        except Exception as rollback_exc:
                            self.send(
                                "viewerError",
                                {"code": "stage_reload_rollback_failed", "message": str(rollback_exc)},
                            )
                    if cache_bust_asset_stage is not None:
                        self._delete_reload_asset_snapshot(cache_bust_asset_stage)
                raise
            self.selection.clear()
            self.current_asset_path = asset_path
            self.current_composite_path = composite_path
            self.queries = next_queries
            self.stage_version += 1
            self._active_camera_prim = OV_CAMERA_PRIM
            self._camera_dirty = False
            self._camera_interaction_active = False
            self.camera.cancel_interaction()
            self.camera.set_from_xform(STUDIO_CAMERA_XFORM)
            if cache_bust_asset_stage is not None and asset_path is not None and cache_bust_token is not None:
                self._reloaded_asset_references[self._path_key(asset_path)] = (cache_bust_asset_stage, cache_bust_token)
                self._cleanup_reload_asset_snapshots(asset_path, keep=cache_bust_asset_stage)
        self.send(
            "openStageResult",
            {
                "url": str(asset_path or ""),
                "result": "success",
                "root_prim_path": self.queries.root_prim_path,
                "stage_version": self.stage_version,
                "mode": "lookdev_asset",
            },
        )
        if not stage_ready:
            detail = self.queries.last_error or f"Loaded stage but renderer queries did not include {LOOKDEV_ASSET_PRIM}"
            self.send(
                "viewerError",
                {
                    "code": "stage_query_stale",
                    "message": detail,
                },
            )
        self.send("stageSelectionChanged", self.selection.payload())
        self.send_aov_state()
        if reload_current:
            self.send(
                "assetReloadResult",
                {
                    "result": "success",
                    "stage_version": self.stage_version,
                    "url": str(asset_path or ""),
                },
            )

    def _load_stage_async(self, asset_path: Path | None, *, reload_current: bool = False) -> None:
        try:
            self._load_stage(asset_path, reload_current=reload_current)
        except Exception as exc:
            if reload_current:
                self.send(
                    "assetReloadResult",
                    {
                        "result": "error",
                        "message": str(exc),
                        "stage_version": self.stage_version,
                        "url": str(self.current_asset_path) if self.current_asset_path else "",
                    },
                )
            else:
                self.send("viewerError", {"code": "stage_load_failed", "message": str(exc)})
        finally:
            self.loading_stage.clear()

    def _send_current_stage(self) -> None:
        self.send(
            "openStageResult",
            {
                "url": str(self.current_asset_path) if self.current_asset_path else "",
                "result": "success",
                "root_prim_path": self.queries.root_prim_path,
                "stage_version": self.stage_version,
                "mode": "lookdev_asset",
            },
        )
        self.send(
            "getChildrenResult",
            {
                "prim_path": self.queries.root_prim_path,
                "children": self.queries.get_children(self.queries.root_prim_path),
                "stage_version": self.stage_version,
            },
        )
        self.send_aov_state()

    def _render_loop(self) -> None:
        frame_interval = 1.0 / max(1, self.config.fps)
        while not self.shutdown_requested.is_set():
            start = time.monotonic()
            self._drain_commands()
            if not self.stage_lock.acquire(blocking=False):
                self._stream_last_video_frame()
                elapsed = time.monotonic() - start
                time.sleep(max(0.0, frame_interval - elapsed))
                continue
            try:
                if self._camera_dirty:
                    self._write_camera()
                products = self.renderer.step(render_products={OV_RENDER_PRODUCT}, delta_time=frame_interval)
                self._handle_render_products(products)
            except Exception as exc:
                self.send("viewerError", {"code": "render_step_failed", "message": str(exc)})
            finally:
                self.stage_lock.release()
            elapsed = time.monotonic() - start
            time.sleep(max(0.0, frame_interval - elapsed))

    def _handle_render_products(self, products) -> None:
        if hasattr(products, "__enter__"):
            with products as ctx:
                self._handle_frame(ctx[OV_RENDER_PRODUCT].frames[0])
            return
        self._handle_frame(products[OV_RENDER_PRODUCT].frames[0])

    def _handle_frame(self, frame) -> None:
        self._last_frame = frame
        self._update_available_aovs(getattr(frame, "render_vars", {}), notify=True)
        if not self.ready.is_set():
            print(f"First ovrtx frame ready: {self.config.width}x{self.config.height}")
            self.ready.set()
        self._stream_frame(frame)

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                return
            try:
                self._handle_command(command)
            except Exception as exc:
                self.send("viewerError", {"code": "command_failed", "message": str(exc), "command": command.get("type")})

    def _handle_command(self, command: dict[str, Any]) -> None:
        kind = command.get("type")
        if kind == "load_asset":
            asset_path = self.assets.resolve(str(command.get("path") or ""))
            if self.current_asset_path and self._same_path(asset_path, self.current_asset_path):
                self._send_current_stage()
            elif self.loading_stage.is_set():
                self.send("viewerError", {"code": "stage_load_in_progress", "message": "A stage load is already in progress."})
            else:
                self.loading_stage.set()
                threading.Thread(target=self._load_stage_async, args=(asset_path,), daemon=True).start()
        elif kind == "reload_asset":
            if self.current_asset_path is None:
                self.send(
                    "assetReloadResult",
                    {"result": "error", "message": "No asset is currently loaded.", "stage_version": self.stage_version},
                )
            elif self.loading_stage.is_set():
                self.send(
                    "assetReloadResult",
                    {
                        "result": "error",
                        "message": "A stage load is already in progress.",
                        "stage_version": self.stage_version,
                    },
                )
            else:
                self.loading_stage.set()
                threading.Thread(
                    target=self._load_stage_async,
                    args=(self.current_asset_path,),
                    kwargs={"reload_current": True},
                    daemon=True,
                ).start()
        elif kind == "cancel_interaction":
            self.camera.cancel_interaction()
            self._camera_interaction_active = False
        elif kind == "camera_down":
            self.camera.on_mouse_button_down(command["x"], command["y"], command["button"])
            self._camera_interaction_active = True
        elif kind == "camera_up":
            self.camera.on_mouse_button_up(command["x"], command["y"], command["button"])
            self._camera_interaction_active = False
        elif kind == "camera_move":
            self.camera.on_mouse_move(command["x"], command["y"])
            if self._camera_interaction_active:
                self._camera_dirty = True
        elif kind == "camera_scroll":
            self.camera.on_scroll(command["delta"])
            self._camera_dirty = True
        elif kind == "fit_camera":
            self._fit_camera()
        elif kind == "select":
            self._select(command.get("paths", []))
        elif kind == "make_pickable":
            self.selection.set_pickable(command.get("paths", []))
            self._write_pickable(command.get("paths", []), True)
        elif kind == "render_setting_changed":
            key = command.get("key")
            if key == "aov":
                requested = str(command.get("value") or self.settings.render_settings().get("aov", "LdrColor"))
                self.set_active_aov(requested)

    def _fit_camera(self) -> None:
        center, size = self.queries.estimated_content_bounds() or ((0.0, 1.0, 0.0), (4.0, 3.0, 4.0))
        self.camera.fit_bounds(center, size)
        self._camera_dirty = True
        self.send("cameraStateChanged", self.camera.state_payload())

    def _refresh_queries_after_load(
        self,
        asset_path: Path | None,
        composite_path: Path | None = None,
        queries: StageQueryCache | None = None,
        *,
        stream_warmup_frames: bool = True,
    ) -> bool:
        query_cache = queries or self.queries
        expected_path = LOOKDEV_ASSET_PRIM if asset_path is not None else ""
        frame_interval = 1.0 / max(1, self.config.fps)
        for attempt in range(12):
            query_cache.refresh_from_renderer(self.renderer)
            if not expected_path or expected_path in query_cache.paths:
                return True
            try:
                products = self.renderer.step(render_products={OV_RENDER_PRODUCT}, delta_time=frame_interval)
                if stream_warmup_frames:
                    self._handle_render_products(products)
            except Exception as exc:
                if attempt == 11:
                    self.send("viewerError", {"code": "stage_warmup_failed", "message": str(exc)})
            time.sleep(0.05)
        query_cache.refresh_from_renderer(self.renderer)
        fallback_path = composite_path or self.current_composite_path
        if expected_path and expected_path not in query_cache.paths and fallback_path is not None:
            if query_cache.refresh_from_usd_file(fallback_path):
                return expected_path in query_cache.paths
        return not expected_path or expected_path in query_cache.paths

    def _write_camera(self) -> None:
        matrix = np.ascontiguousarray(self.camera.get_camera_xform(), dtype=np.float64)
        if not np.isfinite(matrix).all():
            return
        self.renderer.write_attribute(
            prim_paths=[self._active_camera_prim],
            attribute_name="omni:xform",
            tensor=matrix.reshape(1, 4, 4),
            semantic=self.ovrtx.Semantic.XFORM_MAT4x4,
            prim_mode=self.ovrtx.PrimMode.CREATE_NEW,
        )
        self._camera_dirty = False

    def _write_pickable(self, paths: list[str], enabled: bool) -> None:
        if not paths:
            return
        attr = getattr(self.ovrtx, "OVRTX_ATTR_NAME_PICKABLE", "omni:pickable")
        self.renderer.write_attribute(prim_paths=paths, attribute_name=attr, tensor=np.full((len(paths),), 1 if enabled else 0, dtype=np.uint8))

    def _select(self, paths: list[str]) -> None:
        previous = set(self.selection.selected_paths)
        current = set(self.selection.select(paths))
        writes = {path: 0 for path in previous - current}
        writes.update({path: 1 for path in current})
        if writes:
            attr = getattr(self.ovrtx, "OVRTX_ATTR_NAME_SELECTION_OUTLINE_GROUP", "omni:selectionOutlineGroup")
            ordered = list(writes)
            self.renderer.write_attribute(
                prim_paths=ordered,
                attribute_name=attr,
                tensor=np.asarray([writes[path] for path in ordered], dtype=np.uint8),
            )
        self.send("stageSelectionChanged", self.selection.payload())

    def _stream_frame(self, frame) -> None:
        if self.stream is None:
            return
        render_vars = getattr(frame, "render_vars", {})
        if self._aov_converter is None:
            return
        source = self._active_aov if self._active_aov in self._available_aovs else "LdrColor"
        candidates = [source]
        if source != "LdrColor":
            candidates.append("LdrColor")
        for candidate in candidates:
            try:
                copied = self._aov_converter.copy_to_stream_buffer(render_vars, candidate, self.ovrtx.Device.CUDA)
                if not copied or self._aov_converter.stream_buffer is None:
                    raise RuntimeError(f"Unable to convert {candidate} to BGRA8")
                stream_buffer = self._aov_converter.stream_buffer
                if self._stream_uses_tensor_input:
                    dlpack_source = stream_buffer.__dlpack__() if hasattr(stream_buffer, "__dlpack__") else stream_buffer
                    video_frame = self.ovstream.VideoFrame.from_dlpack(dlpack_source)
                else:
                    video_frame = self.ovstream.VideoFrame.from_cuda_array(stream_buffer)
                self.stream.stream_video(video_frame)
                self._last_video_frame = video_frame
                if candidate != source:
                    self._report_aov_error(f"stream_video fell back from {source} to {candidate}")
                self._last_stream_error = ""
                return
            except Exception as exc:
                message = str(exc)
                if message != self._last_stream_error:
                    print(f"stream_video failed for {candidate}: {message}")
                    self._last_stream_error = message
        self._stream_last_video_frame()

    def _update_available_aovs(self, render_vars: Any, notify: bool = False) -> None:
        if self._aov_converter is None:
            available = ["LdrColor"]
        else:
            available = self._aov_converter.available_from(render_vars)
        next_available = set(available)
        changed = next_available != self._available_aovs
        self._available_aovs = next_available
        if self._active_aov not in self._available_aovs:
            previous = self._active_aov
            self._active_aov = "LdrColor"
            self.settings.render_settings()["aov"] = "LdrColor"
            self.settings.save()
            changed = True
            self._report_aov_error(f"AOV {previous} is unavailable for the current render product; reverted to Beauty.")
        if notify and changed:
            self.send_aov_state()

    def _report_aov_error(self, message: str) -> None:
        if message == self._last_aov_error:
            return
        self._last_aov_error = message
        print(message)
        self.send("activeAOVState", self.active_aov_state({"result": "error", "reason": message}))

    def _stream_last_video_frame(self) -> None:
        if self.stream is None or self._last_video_frame is None:
            return
        try:
            self.stream.stream_video(self._last_video_frame)
        except Exception:
            pass

    @staticmethod
    def _same_path(left: Path, right: Path) -> bool:
        return LookdevRuntime._path_key(left) == LookdevRuntime._path_key(right)

    @staticmethod
    def _path_key(path: Path) -> str:
        return os.path.normcase(os.path.abspath(path))

    def _reloaded_asset_reference(self, asset_path: Path) -> tuple[Path | None, str | None]:
        key = self._path_key(asset_path)
        reference = self._reloaded_asset_references.get(key)
        if reference is None:
            return None, None
        snapshot, token = reference
        if snapshot.exists():
            return snapshot, token
        self._reloaded_asset_references.pop(key, None)
        return None, None

    def _next_reload_token(self, asset_path: Path) -> str:
        self._reload_sequence += 1
        try:
            stat = asset_path.stat()
            metadata = f"mtime={stat.st_mtime_ns}:size={stat.st_size}"
        except OSError as exc:
            metadata = f"stat_error={type(exc).__name__}"
        return f"path={asset_path.resolve()}:metadata={metadata}:seq={self._reload_sequence}"

    def _cache_bust_asset_snapshot(self, asset_path: Path, cache_bust_token: str) -> Path:
        resolved = asset_path.resolve()
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", resolved.stem).strip("._") or "asset"
        path_digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:12]
        token_digest = hashlib.sha1(cache_bust_token.encode("utf-8")).hexdigest()[:12]
        snapshot = resolved.with_name(f"._lookdev_reload_{stem}_{path_digest}_{token_digest}{resolved.suffix}")
        shutil.copy2(resolved, snapshot)
        return snapshot

    def _cleanup_reload_asset_snapshots(self, asset_path: Path, *, keep: Path) -> None:
        resolved = asset_path.resolve()
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", resolved.stem).strip("._") or "asset"
        path_digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:12]
        pattern = f"._lookdev_reload_{stem}_{path_digest}_*{resolved.suffix}"
        for candidate in resolved.parent.glob(pattern):
            if candidate.resolve() == keep.resolve():
                continue
            self._delete_reload_asset_snapshot(candidate)

    @staticmethod
    def _delete_reload_asset_snapshot(snapshot: Path) -> None:
        try:
            snapshot.unlink()
        except FileNotFoundError:
            return
        except OSError:
            return

    def _start_health_server(self) -> None:
        ready = self.ready

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/healthz":
                    self.send_response(404)
                    self.end_headers()
                    return
                if ready.is_set():
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"ok")
                else:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b"not ready")

            def log_message(self, *_args):
                return

        httpd = HTTPServer(("0.0.0.0", self.config.health_port), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
