from __future__ import annotations

import json
import threading
import time
from typing import Any

from .render_settings import CAPABILITIES, aov_options_payload, capabilities_payload, coerce_setting


class MessageRouter:
    def __init__(self, runtime):
        self.runtime = runtime

    def on_connection(self, connected: bool) -> None:
        self.runtime.client_connected = bool(connected)
        if connected:
            threading.Thread(target=self._push_initial_state, daemon=True).start()

    def on_message(self, raw: Any) -> None:
        msg = self._decode(raw)
        if not msg:
            return
        event_type = msg.get("event_type")
        payload = msg.get("payload") or {}
        handler = getattr(self, f"_handle_{event_type}", None)
        if handler is None:
            self.runtime.send("viewerError", {"code": "unknown_event", "message": f"Unknown event: {event_type}"})
            return
        handler(payload)

    def _handle_listAssetsRequest(self, _payload: dict) -> None:
        self.runtime.send("listAssetsResult", {"assets": self.runtime.assets.list_assets()})

    def _handle_loadAssetRequest(self, payload: dict) -> None:
        path = str(payload.get("path") or "")
        self.runtime.enqueue({"type": "load_asset", "path": path})

    def _handle_getChildrenRequest(self, payload: dict) -> None:
        prim_path = str(payload.get("prim_path") or self.runtime.queries.root_prim_path)
        self.runtime.send(
            "getChildrenResult",
            {
                "prim_path": prim_path,
                "children": self.runtime.queries.get_children(prim_path),
                "stage_version": self.runtime.stage_version,
            },
        )

    def _handle_getPropertiesRequest(self, payload: dict) -> None:
        prim_path = str(payload.get("prim_path") or "")
        self.runtime.send(
            "getPropertiesResponse",
            {
                "prim_path": prim_path,
                "properties": self.runtime.queries.get_properties(prim_path),
                "truncated": False,
                "stage_version": self.runtime.stage_version,
            },
        )

    def _handle_getPrimCountRequest(self, _payload: dict) -> None:
        self.runtime.send(
            "getPrimCountResult",
            {"count": self.runtime.queries.prim_count(), "stage_version": self.runtime.stage_version},
        )

    def _handle_selectPrimsRequest(self, payload: dict) -> None:
        paths = [str(path) for path in payload.get("paths", []) if path]
        self.runtime.enqueue({"type": "select", "paths": paths})

    def _handle_makePrimsSelectable(self, payload: dict) -> None:
        paths = [str(path) for path in payload.get("paths", []) if path]
        self.runtime.enqueue({"type": "make_pickable", "paths": paths})

    def _handle_setViewportInputActive(self, payload: dict) -> None:
        self.runtime.input_router.set_viewport_input_active(bool(payload.get("active", True)))

    def _handle_getRenderSettingsRequest(self, _payload: dict) -> None:
        self._send_render_settings({"result": "success", "applied": False})

    def _handle_setRenderSettingRequest(self, payload: dict) -> None:
        key = str(payload.get("key") or "")
        if key == "aov":
            self._handle_changeAOVRequest({"aov": payload.get("value")})
            return
        capability = CAPABILITIES.get(key)
        if capability is None or not capability.validated or capability.applies_at == "unsupported":
            self.runtime.send(
                "renderSettingsChanged",
                {
                    "settings": self.runtime.settings.render_settings(),
                    "capabilities": capabilities_payload(),
                    "key": key,
                    "result": "error",
                    "applied": False,
                    "applies_at": "unsupported",
                    "requires_reload": False,
                    "message": f"Unsupported render setting: {key}",
                },
            )
            return
        value = coerce_setting(key, payload.get("value"))
        self.runtime.settings.render_settings()[key] = value
        self.runtime.settings.save()
        self.runtime.enqueue({"type": "render_setting_changed", "key": key})
        self._send_render_settings(
            {
                "key": key,
                "result": "success",
                "applied": capability.applies_at == "immediate",
                "applies_at": capability.applies_at,
                "requires_reload": capability.applies_at == "reload_required",
                "requires_reconnect": capability.applies_at == "reconnect_required",
            }
        )

    def _handle_changeAOVRequest(self, payload: dict) -> None:
        requested = coerce_setting("aov", payload.get("aov") or payload.get("name"))
        if not isinstance(requested, str) or not requested:
            self.runtime.send_aov_state({"result": "error", "reason": "Missing AOV name"})
            return
        previous = self.runtime._active_aov
        if self.runtime.set_active_aov(requested):
            self._send_render_settings(
                {
                    "key": "aov",
                    "result": "success",
                    "applied": True,
                    "applies_at": "immediate",
                    "requires_reload": False,
                    "requires_reconnect": False,
                }
            )
            self.runtime.send_aov_state({"result": "success", "previous": previous, "requested": requested})
            return
        self.runtime.send_aov_state(
            {
                "result": "error",
                "previous": previous,
                "requested": requested,
                "reason": "AOV is not available for the current render product",
            }
        )

    def _handle_getAvailableAOVs(self, _payload: dict) -> None:
        self.runtime.send_aov_state()

    def _handle_fitCameraRequest(self, payload: dict) -> None:
        self.runtime.enqueue({"type": "fit_camera", "path": payload.get("path")})

    def _handle_resetViewRequest(self, _payload: dict) -> None:
        self.runtime.enqueue({"type": "fit_camera"})

    def _send_render_settings(self, extra: dict) -> None:
        self.runtime.send(
            "renderSettingsChanged",
            {
                "settings": self.runtime.settings.render_settings(),
                "capabilities": capabilities_payload(),
                "aov_options": aov_options_payload(),
                **extra,
            },
        )
        self.runtime.send_aov_state()

    def _push_initial_state(self) -> None:
        time.sleep(0.3)
        self.runtime.send(
            "openStageResult",
            {
                "url": str(self.runtime.current_asset_path) if self.runtime.current_asset_path else "",
                "result": "success",
                "root_prim_path": self.runtime.queries.root_prim_path,
                "stage_version": self.runtime.stage_version,
                "mode": "lookdev_asset",
            },
        )
        self.runtime.send(
            "getChildrenResult",
            {
                "prim_path": self.runtime.queries.root_prim_path,
                "children": self.runtime.queries.get_children(self.runtime.queries.root_prim_path),
                "stage_version": self.runtime.stage_version,
            },
        )
        self.runtime.send("listAssetsResult", {"assets": self.runtime.assets.list_assets()})
        self._send_render_settings({"result": "success", "applied": False})
        self.runtime.send("stageSelectionChanged", self.runtime.selection.payload())

    @staticmethod
    def _decode(raw: Any) -> dict[str, Any] | None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        if isinstance(raw, str):
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                return None
        elif isinstance(raw, dict):
            msg = raw
        else:
            return None
        if "messageType" in msg and "data" in msg:
            data = msg["data"]
            if isinstance(data, str):
                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    return None
            elif isinstance(data, dict):
                msg = data
        if not isinstance(msg, dict) or "event_type" not in msg:
            return None
        return msg
