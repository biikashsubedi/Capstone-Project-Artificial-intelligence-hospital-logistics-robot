"""
Mac-side medicine detection using the custom-trained YOLO model (best.pt).

Runs FULLY OFFLINE (ultralytics + torch on this Mac) — no internet needed, so
it works on the robot's hotspot. The GUI uses it two ways:
  1. Live overlay: detect() on each displayed camera frame, draw boxes.
  2. Delivery confirmation: the robot (at the shelf) asks the Mac over the
     socket "DETECT med1"; the GUI answers with check_medicine().

Model classes (from best.pt): acetaminophen, allergy_relief, ibuprofen.
Command tokens (med1/med2/med3) are mapped via config/config_data.json.
"""
import json
import threading
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).parent


def _load_model_config():
    with open(BASE_DIR / "config" / "config_data.json", "r", encoding="utf-8") as f:
        cfg = json.load(f).get("model", {})
    return {
        "path": str(BASE_DIR / cfg.get("path", "best.pt")),
        "confidence": float(cfg.get("confidence", 0.6)),
        "class_map": cfg.get("class_map", {}),
    }


class MedicineDetector:
    """Thread-safe wrapper around the YOLO model. Loads lazily on first use."""

    def __init__(self):
        self.cfg = _load_model_config()
        self._model = None
        self._lock = threading.Lock()   # ultralytics predict isn't re-entrant
        self.load_error = None

    # ── model loading ──────────────────────────────────────────────────────
    def ensure_loaded(self):
        """Load the model (slow, once). Returns True if usable."""
        if self._model is not None:
            return True
        if self.load_error is not None:
            return False
        try:
            from ultralytics import YOLO
            with self._lock:
                if self._model is None:
                    self._model = YOLO(self.cfg["path"])
            return True
        except Exception as e:  # missing package, missing best.pt, etc.
            self.load_error = str(e)
            return False

    # ── detection ──────────────────────────────────────────────────────────
    def detect(self, pil_image, conf=None):
        """Run the model on a PIL image.

        Returns a list of (class_name, confidence, (x1, y1, x2, y2)) in the
        image's pixel coordinates, sorted by confidence descending.
        """
        if not self.ensure_loaded():
            return []
        conf = self.cfg["confidence"] if conf is None else conf
        frame = np.asarray(pil_image.convert("RGB"))[:, :, ::-1]  # RGB -> BGR
        with self._lock:
            results = self._model.predict(frame, conf=conf, verbose=False)
        dets = []
        r = results[0]
        names = r.names
        if r.boxes is not None:
            for box in r.boxes:
                cls_name = names[int(box.cls[0])]
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
                dets.append((cls_name, confidence, (x1, y1, x2, y2)))
        dets.sort(key=lambda d: d[1], reverse=True)
        return dets

    def check_medicine(self, med_token, pil_image):
        """Answer 'is medX visible?'. Returns confidence (float) or None.

        med_token is a command token (med1/med2/med3); it's translated to the
        model's class name via the config class_map.
        """
        hit = self.find_medicine(med_token, pil_image)
        return hit[0] if hit else None

    def find_medicine(self, med_token, pil_image):
        """Like check_medicine but also reports where and how big it looks.

        Returns (confidence, area_fraction, offset_x, offset_y) or None:
          area_fraction  the box's share of the whole frame (bigger = closer)
          offset_x       -1.0 (far left) .. +1.0 (far right);  0 = mid-frame
          offset_y       -1.0 (top)      .. +1.0 (bottom);     0 = mid-frame
        The robot compares these against its CALIBRATED grip point (which is
        usually not the middle of the image) to line the gripper up.
        """
        target = self.cfg["class_map"].get(med_token, med_token).lower()
        width = float(pil_image.width) or 1.0
        height = float(pil_image.height) or 1.0
        frame_area = width * height

        def norm_x(px):
            return (px - width / 2.0) / (width / 2.0)

        def norm_y(py):
            return (py - height / 2.0) / (height / 2.0)

        for cls_name, confidence, (x1, y1, x2, y2) in self.detect(pil_image):
            if cls_name.lower() == target:
                box_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                return (confidence, box_area / frame_area,
                        norm_x(cx), norm_y(cy),
                        # the box edges too, so the robot can check whether the
                        # gripper's grab point falls INSIDE the medicine
                        norm_x(x1), norm_y(y1), norm_x(x2), norm_y(y2))
        return None

    def label_for(self, cls_name):
        """Pretty display name: allergy_relief -> Allergy Relief."""
        return cls_name.replace("_", " ").title()


if __name__ == "__main__":
    # Self-test: load model, run on a blank frame (expects no detections).
    from PIL import Image

    det = MedicineDetector()
    ok = det.ensure_loaded()
    print("model loaded:", ok, det.load_error or "")
    blank = Image.new("RGB", (640, 480), (30, 30, 30))
    print("detections on blank frame:", det.detect(blank))
    print("check med1 on blank:", det.check_medicine("med1", blank))
