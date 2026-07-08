from __future__ import annotations


DRAG_THRESHOLD_PX = 4.0


def camera_button_from_ovstream(raw_button, ovstream) -> int | None:
    try:
        button = raw_button if isinstance(raw_button, ovstream.MouseButton) else ovstream.MouseButton(raw_button)
    except Exception:
        return None
    if button == ovstream.MouseButton.LEFT:
        return 0
    if button == ovstream.MouseButton.MIDDLE:
        return 1
    if button == ovstream.MouseButton.RIGHT:
        return 2
    return None


def wheel_delta(mouse) -> float:
    return float(getattr(mouse, "scroll_y", 0) or getattr(mouse, "data", 0) or 0)


class InputRouter:
    def __init__(self, runtime):
        self.runtime = runtime
        self.viewport_input_active = True
        self._active_button: int | None = None
        self._press_pos: tuple[float, float] | None = None
        self._dragged = False

    def set_viewport_input_active(self, active: bool) -> None:
        self.viewport_input_active = bool(active)
        if not self.viewport_input_active:
            self.runtime.enqueue({"type": "cancel_interaction"})
            self._active_button = None
            self._press_pos = None
            self._dragged = False

    def on_input(self, event, ovstream) -> None:
        if not self.viewport_input_active:
            self.runtime.enqueue({"type": "cancel_interaction"})
            return
        if event.type != ovstream.InputEventType.MOUSE:
            return
        mouse = event.mouse
        if mouse.type == ovstream.MouseEventType.MOVE:
            x, y = float(mouse.x), float(mouse.y)
            if self._press_pos is not None:
                dx = x - self._press_pos[0]
                dy = y - self._press_pos[1]
                if abs(dx) > DRAG_THRESHOLD_PX or abs(dy) > DRAG_THRESHOLD_PX:
                    self._dragged = True
            self.runtime.enqueue({"type": "camera_move", "x": x, "y": y})
            return
        if mouse.type == ovstream.MouseEventType.WHEEL:
            self.runtime.enqueue({"type": "camera_scroll", "delta": wheel_delta(mouse)})
            return
        if mouse.type != ovstream.MouseEventType.BUTTON:
            return
        button = camera_button_from_ovstream(mouse.data, ovstream)
        if button is None:
            return
        is_down = mouse.button_state == ovstream.KeyState.DOWN
        x, y = float(mouse.x), float(mouse.y)
        if is_down:
            self._active_button = button
            self._press_pos = (x, y)
            self._dragged = False
            self.runtime.enqueue({"type": "camera_down", "x": x, "y": y, "button": button})
            return
        was_click = button == self._active_button and not self._dragged
        self.runtime.enqueue({"type": "camera_up", "x": x, "y": y, "button": button})
        if button == 0 and was_click:
            self.runtime.enqueue({"type": "pick", "x": x, "y": y})
        self._active_button = None
        self._press_pos = None
        self._dragged = False

