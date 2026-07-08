from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


MIN_DISTANCE = 0.01
MAX_ELEVATION = math.pi / 2 - 0.01


@dataclass
class OrbitCamera:
    width: int
    height: int
    target: np.ndarray = field(default_factory=lambda: np.array([0.0, 1.0, 0.0], dtype=np.float64))
    distance: float = 6.0
    azimuth: float = -math.pi / 4
    elevation: float = math.radians(18.0)
    _last_pos: tuple[float, float] | None = None
    _active_button: int | None = None

    def fit_bounds(self, center: tuple[float, float, float], size: tuple[float, float, float]) -> None:
        max_dim = max(float(size[0]), float(size[1]), float(size[2]), 0.25)
        self.target = np.asarray(center, dtype=np.float64)
        fov = math.radians(45.0)
        self.distance = max_dim / max(0.1, math.sin(fov * 0.5)) * 0.75
        self.azimuth = -math.pi / 4
        self.elevation = math.radians(20.0)
        self._sanitize()

    def cancel_interaction(self) -> None:
        self._last_pos = None
        self._active_button = None

    def snapshot(self) -> dict:
        return {
            "target": self.target.copy(),
            "distance": self.distance,
            "azimuth": self.azimuth,
            "elevation": self.elevation,
        }

    def restore(self, snapshot: dict) -> bool:
        target = np.asarray(snapshot.get("target"), dtype=np.float64)
        distance = float(snapshot.get("distance", float("nan")))
        azimuth = float(snapshot.get("azimuth", float("nan")))
        elevation = float(snapshot.get("elevation", float("nan")))
        if target.shape != (3,) or not np.isfinite(target).all():
            return False
        if not all(math.isfinite(value) for value in (distance, azimuth, elevation)):
            return False
        self.target = target
        self.distance = distance
        self.azimuth = azimuth
        self.elevation = elevation
        self.cancel_interaction()
        self._sanitize()
        return True

    def set_from_xform(self, xform: tuple[tuple[float, ...], ...], distance: float = 6.0) -> bool:
        matrix = np.asarray(xform, dtype=np.float64)
        if matrix.shape != (4, 4) or not np.isfinite(matrix).all():
            return False
        forward = -matrix[2, :3]
        norm = np.linalg.norm(forward)
        if norm < 1e-8:
            return False
        forward = forward / norm
        self.elevation = math.asin(max(-1.0, min(1.0, float(forward[1]))))
        self.azimuth = math.atan2(float(forward[0]), float(forward[2]))
        self.distance = max(MIN_DISTANCE, float(distance))
        self.target = matrix[3, :3] + forward * self.distance
        self.cancel_interaction()
        self._sanitize()
        return True

    def on_mouse_button_down(self, x: float, y: float, button: int) -> None:
        self._active_button = button
        self._last_pos = (x, y)

    def on_mouse_button_up(self, x: float, y: float, button: int) -> None:
        self._active_button = None
        self._last_pos = None

    def on_mouse_move(self, x: float, y: float) -> None:
        if self._last_pos is None or self._active_button is None:
            self._last_pos = (x, y)
            return
        dx = x - self._last_pos[0]
        dy = y - self._last_pos[1]
        self._last_pos = (x, y)
        if self._active_button == 0:
            self.orbit_delta(dx, dy)
        elif self._active_button == 1:
            self.pan_delta(dx, dy)
        elif self._active_button == 2:
            self.dolly_delta(dy)

    def on_scroll(self, delta: float) -> None:
        self.dolly_delta(-delta * 0.2)

    def orbit_delta(self, dx: float, dy: float, scale: float = 1.0) -> None:
        self.azimuth -= float(dx) * 0.006 * scale
        self.elevation += float(dy) * 0.006 * scale
        self._sanitize()

    def pan_delta(self, dx: float, dy: float) -> None:
        right, up, _forward = self._basis()
        pixels = max(1.0, float(min(self.width, self.height)))
        pan_scale = self.distance / pixels
        self.target -= right * float(dx) * pan_scale
        self.target += up * float(dy) * pan_scale
        self._sanitize()

    def dolly_delta(self, dy: float) -> None:
        factor = math.exp(float(dy) * 0.01)
        self.distance *= factor
        self._sanitize()

    def get_camera_xform(self) -> np.ndarray:
        right, up, forward = self._basis()
        eye = self.target - forward * self.distance
        matrix = np.eye(4, dtype=np.float64)
        matrix[0, :3] = right
        matrix[1, :3] = up
        matrix[2, :3] = -forward
        matrix[3, :3] = eye
        return matrix

    def state_payload(self) -> dict:
        return {
            "target": self.target.tolist(),
            "distance": self.distance,
            "azimuth": self.azimuth,
            "elevation": self.elevation,
        }

    def _basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        self._sanitize()
        forward = np.array(
            [
                math.cos(self.elevation) * math.sin(self.azimuth),
                math.sin(self.elevation),
                math.cos(self.elevation) * math.cos(self.azimuth),
            ],
            dtype=np.float64,
        )
        forward /= max(np.linalg.norm(forward), 1e-8)
        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        right = np.cross(forward, world_up)
        if np.linalg.norm(right) < 1e-8:
            right = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        up /= max(np.linalg.norm(up), 1e-8)
        return right, up, forward

    def _sanitize(self) -> None:
        if not math.isfinite(float(self.azimuth)):
            self.azimuth = -math.pi / 4
        if not math.isfinite(float(self.elevation)):
            self.elevation = math.radians(18.0)
        self.elevation = max(-MAX_ELEVATION, min(MAX_ELEVATION, self.elevation))
        if not math.isfinite(float(self.distance)):
            self.distance = 6.0
        self.distance = max(MIN_DISTANCE, float(self.distance))
        target = np.asarray(self.target, dtype=np.float64)
        if target.shape != (3,) or not np.isfinite(target).all():
            target = np.zeros(3, dtype=np.float64)
        self.target = target
