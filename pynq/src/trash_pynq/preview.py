"""Low-overhead LCD presentation; browser encoding has its own update rate."""
import time
import numpy as np


class PreviewPresenter:
    """Keep static LCD pixels and update just the rotated camera rectangle."""
    def __init__(self, ui, video=None):
        self.ui, self.video = ui, video
        self._state = None
        self._started = time.monotonic()
        self._frames = 0
        self.fps = 0.0

    def present(self, raw, **state):
        frame = self.ui.render(raw, **state)
        key = (state.get('label'), state.get('latency_ms'), state.get('light', False),
               state.get('status', 'Ready'), state.get('saved_count', 0), raw is not None)
        if self.video is not None:
            video = self.video
            if video.display_buffer is None:
                raise RuntimeError('LCD must be started before preview')
            status = video.mmio.read(0x04)
            if status & video.ERROR_MASK:
                raise RuntimeError('LCD VDMA status 0x{:08x}'.format(status))
            if key == self._state and raw is not None:
                # Logical [76:412, 28:364], rotated 180 degrees for this LCD.
                video.display_buffer[68:404, 436:772] = frame[411:75:-1, 363:27:-1]
            else:
                video.display_buffer[:] = frame[::-1, ::-1]
            video.display_buffer.flush()
        self._state = key
        self._frames += 1
        now = time.monotonic()
        if now - self._started >= 1:
            self.fps = self._frames / (now - self._started)
            self._frames, self._started = 0, now
        return frame
