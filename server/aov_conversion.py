from __future__ import annotations

from typing import Any

import warp as wp

from .render_settings import DEBUG_AOV_NAMES


DISPLAY_AOVS = DEBUG_AOV_NAMES


@wp.kernel
def _rgba8_to_bgra(src: wp.array(dtype=wp.uint8, ndim=3), dst: wp.array(dtype=wp.uint8, ndim=3)):
    x, y = wp.tid()
    dst[y, x, 0] = src[y, x, 2]
    dst[y, x, 1] = src[y, x, 1]
    dst[y, x, 2] = src[y, x, 0]
    dst[y, x, 3] = src[y, x, 3]


@wp.kernel
def _rgb8_to_bgra(src: wp.array(dtype=wp.uint8, ndim=3), dst: wp.array(dtype=wp.uint8, ndim=3)):
    x, y = wp.tid()
    dst[y, x, 0] = src[y, x, 2]
    dst[y, x, 1] = src[y, x, 1]
    dst[y, x, 2] = src[y, x, 0]
    dst[y, x, 3] = wp.uint8(255)


@wp.kernel
def _normal_float_to_bgra(src: wp.array(dtype=wp.float32, ndim=3), dst: wp.array(dtype=wp.uint8, ndim=3)):
    x, y = wp.tid()
    nx = wp.clamp(src[y, x, 0] * 0.5 + 0.5, 0.0, 1.0)
    ny = wp.clamp(src[y, x, 1] * 0.5 + 0.5, 0.0, 1.0)
    nz = wp.clamp(src[y, x, 2] * 0.5 + 0.5, 0.0, 1.0)
    dst[y, x, 0] = wp.uint8(nz * 255.0)
    dst[y, x, 1] = wp.uint8(ny * 255.0)
    dst[y, x, 2] = wp.uint8(nx * 255.0)
    dst[y, x, 3] = wp.uint8(255)


@wp.kernel
def _depth_range(src: wp.array(dtype=wp.float32, ndim=3), near_value: wp.array(dtype=wp.float32), far_value: wp.array(dtype=wp.float32)):
    x, y = wp.tid()
    depth = src[y, x, 0]
    if wp.isfinite(depth) and depth > 0.0:
        wp.atomic_min(near_value, 0, depth)
        wp.atomic_max(far_value, 0, depth)


@wp.kernel
def _depth_float_to_bgra(
    src: wp.array(dtype=wp.float32, ndim=3),
    near_value: wp.array(dtype=wp.float32),
    far_value: wp.array(dtype=wp.float32),
    dst: wp.array(dtype=wp.uint8, ndim=3),
):
    x, y = wp.tid()
    depth = src[y, x, 0]
    near_depth = near_value[0]
    far_depth = far_value[0]
    gray = 0.0
    if wp.isfinite(depth) and depth > 0.0 and far_depth > near_depth:
        gray = 1.0 - wp.clamp((depth - near_depth) / (far_depth - near_depth), 0.0, 1.0)
    value = wp.uint8(gray * 255.0)
    dst[y, x, 0] = value
    dst[y, x, 1] = value
    dst[y, x, 2] = value
    dst[y, x, 3] = wp.uint8(255)


class AOVFrameConverter:
    def __init__(self):
        self._stream_buffer: wp.array | None = None
        self._depth_near: wp.array | None = None
        self._depth_far: wp.array | None = None

    @property
    def stream_buffer(self) -> wp.array | None:
        return self._stream_buffer

    def available_from(self, render_vars: Any) -> list[str]:
        if hasattr(render_vars, "keys"):
            names = set(render_vars.keys())
        else:
            names = set(render_vars or [])
        return [name for name in DISPLAY_AOVS if name in names] or ["LdrColor"]

    def copy_to_stream_buffer(self, render_vars: Any, aov_name: str, cuda_device: Any) -> bool:
        if not hasattr(render_vars, "__contains__") or aov_name not in render_vars:
            return False
        with render_vars[aov_name].map(device=cuda_device) as mapped:
            src = self._display_tensor(mapped)
            if src is None:
                return False
            shape = tuple(int(dim) for dim in src.shape)
            if len(shape) != 3 or shape[2] < 1:
                return False
            height, width, channels = shape
            self._ensure_stream_buffer(height, width, src.device)
            if self._stream_buffer is None:
                return False
            dim = (width, height)

            if aov_name == "LdrColor":
                if src.dtype == wp.uint8 and channels >= 4:
                    wp.launch(_rgba8_to_bgra, dim=dim, inputs=[src, self._stream_buffer], device=src.device)
                    return True
                if src.dtype == wp.uint8 and channels == 3:
                    wp.launch(_rgb8_to_bgra, dim=dim, inputs=[src, self._stream_buffer], device=src.device)
                    return True

            if aov_name == "NormalSD":
                normal_src = src.view(wp.float32) if src.dtype == wp.uint32 else src
                if normal_src.dtype == wp.float32 and channels >= 3:
                    wp.launch(_normal_float_to_bgra, dim=dim, inputs=[normal_src, self._stream_buffer], device=src.device)
                    return True

            if aov_name == "DepthSD":
                depth_src = src.view(wp.float32) if src.dtype == wp.uint32 else src
                if depth_src.dtype == wp.float32:
                    self._ensure_depth_stats(src.device)
                    if self._depth_near is None or self._depth_far is None:
                        return False
                    self._depth_near.fill_(1.0e20)
                    self._depth_far.fill_(0.0)
                    wp.launch(_depth_range, dim=dim, inputs=[depth_src, self._depth_near, self._depth_far], device=src.device)
                    wp.launch(
                        _depth_float_to_bgra,
                        dim=dim,
                        inputs=[depth_src, self._depth_near, self._depth_far, self._stream_buffer],
                        device=src.device,
                    )
                    return True
        return False

    def _ensure_stream_buffer(self, height: int, width: int, device: Any) -> None:
        if (
            self._stream_buffer is None
            or self._stream_buffer.shape[0] != height
            or self._stream_buffer.shape[1] != width
        ):
            self._stream_buffer = wp.empty((height, width, 4), dtype=wp.uint8, device=device)

    def _ensure_depth_stats(self, device: Any) -> None:
        if self._depth_near is None:
            self._depth_near = wp.empty(1, dtype=wp.float32, device=device)
        if self._depth_far is None:
            self._depth_far = wp.empty(1, dtype=wp.float32, device=device)

    @staticmethod
    def _display_tensor(mapped: Any) -> wp.array | None:
        try:
            return wp.from_dlpack(mapped)
        except TypeError:
            pass
        for name in ("Color", "color", "data", "Depth", "depth", "Normal", "normal"):
            try:
                return wp.from_dlpack(mapped[name])
            except (KeyError, TypeError):
                continue
        return None
