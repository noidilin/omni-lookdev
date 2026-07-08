from __future__ import annotations

import json
import os
import queue
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
from .scene_loader import make_lookdev_composite
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
        self._last_frame = None
        self._active_aov = self.settings.render_settings().get("aov", "LdrColor")

    def enqueue(self, command: dict[str, Any]) -> None:
        self.commands.put(command)

    def start(self) -> None:
        self._import_runtime()
        self._start_health_server()
        self._construct_renderer()
        self._load_stage(None)
        self._start_stream_server()
        self._render_loop()

    def send(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.stream is None or not getattr(self.stream, "is_client_connected", False):
            return
        try:
            self.stream.send_message(json.dumps({"event_type": event_type, "payload": payload}, default=str))
        except Exception:
            pass

    def available_aovs(self) -> list[str]:
        return ["LdrColor", "HdrColor", "DepthSD", "NormalSD", "InstanceSegmentationSD", "SemanticSegmentationSD", "DiffuseAlbedoSD"]

    def _import_runtime(self) -> None:
        try:
            import ovrtx
            import ovstream
        except ImportError as exc:
            raise RuntimeNotAvailable(
                "Missing ovrtx/ovstream runtime. Run `mise run setup:server:win` on native Windows "
                "or `mise run setup:server` on a supported Linux RTX host."
            ) from exc
        self.ovrtx = ovrtx
        self.ovstream = ovstream

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
            config.video_input = ovstream.VideoInput.CUDA
        self.stream.start(config)

    def _load_stage(self, asset_path: Path | None) -> None:
        self.selection.clear()
        self.current_asset_path = asset_path
        self.current_composite_path = make_lookdev_composite(
            self.config.studio_stage,
            asset_path,
            self.config.generated_dir,
            self.config.width,
            self.config.height,
            self.settings.render_settings(),
        )
        self.renderer.open_usd(str(self.current_composite_path))
        self.queries.refresh_from_renderer(self.renderer)
        self._fit_camera()
        self.send(
            "openStageResult",
            {
                "url": str(asset_path or ""),
                "result": "success",
                "root_prim_path": self.queries.root_prim_path,
                "mode": "lookdev_asset",
            },
        )
        self.send("stageSelectionChanged", self.selection.payload())

    def _render_loop(self) -> None:
        frame_interval = 1.0 / max(1, self.config.fps)
        while not self.shutdown_requested.is_set():
            start = time.monotonic()
            self._drain_commands()
            self._write_camera()
            try:
                products = self.renderer.step(render_products={OV_RENDER_PRODUCT}, delta_time=frame_interval)
                self._handle_render_products(products)
            except Exception as exc:
                self.send("viewerError", {"code": "render_step_failed", "message": str(exc)})
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
            self._load_stage(self.assets.resolve(str(command.get("path") or "")))
        elif kind == "cancel_interaction":
            self.camera.cancel_interaction()
        elif kind == "camera_down":
            self.camera.on_mouse_button_down(command["x"], command["y"], command["button"])
        elif kind == "camera_up":
            self.camera.on_mouse_button_up(command["x"], command["y"], command["button"])
        elif kind == "camera_move":
            self.camera.on_mouse_move(command["x"], command["y"])
        elif kind == "camera_scroll":
            self.camera.on_scroll(command["delta"])
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
                self._active_aov = self.settings.render_settings().get("aov", "LdrColor")

    def _fit_camera(self) -> None:
        self.camera.fit_bounds((0.0, 1.0, 0.0), (4.0, 3.0, 4.0))
        self.send("cameraStateChanged", self.camera.state_payload())

    def _write_camera(self) -> None:
        matrix = np.ascontiguousarray(self.camera.get_camera_xform(), dtype=np.float64)
        if not np.isfinite(matrix).all():
            return
        self.renderer.write_attribute(
            prim_paths=[OV_CAMERA_PRIM],
            attribute_name="omni:xform",
            tensor=matrix.reshape(1, 4, 4),
            semantic=self.ovrtx.Semantic.XFORM_MAT4x4,
            prim_mode=self.ovrtx.PrimMode.CREATE_NEW,
        )

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
        source = self._active_aov if self._active_aov in render_vars else "LdrColor"
        if source not in render_vars:
            return
        # The production path maps the selected render var on CUDA, converts to
        # persistent BGRA8, then wraps it as ovstream.VideoFrame. The exact helper
        # differs by ovstream wheel revision, so keep this call isolated.
        try:
            mapped = render_vars[source].map(device=self.ovrtx.Device.CUDA)
            video_frame = self.ovstream.VideoFrame.from_cuda_array(mapped)
            self.stream.stream_video(video_frame)
        except Exception:
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
