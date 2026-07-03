"""
Live MJPEG camera viewer for the Tkinter workstation.

Reads an MJPEG stream from the robot's web_video_server
(http://<robot>:8080/stream?topic=<camera_topic>) and renders frames into a
Tk Label. Network + decode work happens on a background thread; only the final
PhotoImage creation/assignment is marshalled back to the Tk main thread.
"""
import io
import threading
import urllib.request

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:  # Pillow not installed — GUI still runs, cameras show a hint
    PIL_AVAILABLE = False


def mjpeg_frames(stream, should_continue, chunk_size=4096):
    """Yield complete JPEG byte blobs from a multipart MJPEG stream."""
    buf = b""
    while should_continue():
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        buf += chunk
        while True:
            start = buf.find(b"\xff\xd8")              # JPEG SOI
            end = buf.find(b"\xff\xd9", start + 2) if start != -1 else -1  # EOI
            if start != -1 and end != -1:
                yield buf[start:end + 2]
                buf = buf[end + 2:]
            else:
                break


class CameraStream:
    def __init__(self, url, label, container=None, default_size=(480, 360), on_status=None):
        self.url = url
        self.label = label
        self.container = container or label   # fit frames to THIS widget's size
        self.default_size = default_size      # used until the tile is laid out
        self.on_status = on_status
        self._running = False
        self._frame_lock = threading.Lock()
        self._latest_image = None    # full-resolution PIL image of newest frame
        self.frame_filter = None     # optional callable(PIL) -> PIL (draw overlays)

    def start(self):
        if not PIL_AVAILABLE:
            self._status("install Pillow")
            return
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._running = False

    # ── internals ──────────────────────────────────────────────────────────
    def _run(self):
        self._status("connecting...")
        try:
            stream = urllib.request.urlopen(self.url, timeout=10)
        except Exception:
            self._status("no signal")
            return
        got_frame = False
        try:
            for jpg in mjpeg_frames(stream, lambda: self._running):
                self._render(jpg)
                got_frame = True
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass
        if self._running:
            self._status("disconnected" if got_frame else "no signal")

    def _render(self, jpg):
        try:
            img = Image.open(io.BytesIO(jpg)).convert("RGB")  # decode off main thread
        except Exception:
            return
        with self._frame_lock:
            self._latest_image = img
        self.label.after(0, lambda im=img: self._apply(im))

    def get_latest_image(self):
        """Newest full-resolution frame as a PIL image (or None). Thread-safe."""
        with self._frame_lock:
            return self._latest_image.copy() if self._latest_image else None

    def _apply(self, img):
        if not self._running:
            return
        if self.frame_filter is not None:
            try:
                img = self.frame_filter(img)   # e.g. draw detection boxes
            except Exception:
                pass
        # Fit to the CONTAINER's size (a fixed, non-propagating frame), not the
        # label — measuring the label would feed its own image size back in and
        # make the picture grow without bound.
        w = self.container.winfo_width()
        h = self.container.winfo_height()
        if w <= 1 or h <= 1:
            w, h = self.default_size
        iw, ih = img.size
        scale = min(w / iw, h / ih)
        img = img.resize((max(1, int(iw * scale)), max(1, int(ih * scale))))
        photo = ImageTk.PhotoImage(img)
        self.label.config(image=photo, text="")
        self.label.image = photo  # keep a reference so it isn't GC'd

    def _status(self, text):
        if self.on_status:
            try:
                self.label.after(0, lambda: self.on_status(text))
            except Exception:
                pass
