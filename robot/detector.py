#!/usr/bin/env python3
"""
Medicine detection using your custom-trained Roboflow model (local inference).

Captures one frame from the robot camera, runs the model, and checks whether
the requested medicine is present with sufficient confidence.

IMPORTANT FIX vs. the guidebook:
The guidebook compared the detected class directly against "med1"/"med2"/"med3".
Your actual model outputs real class names ("Acetaminophen", "Allergy Relief",
"Ibuprofen"). We translate the command token -> model class via
config.MEDICINE_CLASS_MAP so detection actually matches.
"""
import sys

import rospy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
from inference import get_model

import config

bridge = CvBridge()
model = get_model(model_id=config.MODEL_ID, api_key=config.ROBOFLOW_API_KEY)


def capture_frame(save_path="/tmp/frame.jpg"):
    """Grab one frame from the camera topic and save it as a jpg."""
    msg = rospy.wait_for_message(config.CAMERA_TOPIC, Image, timeout=5)
    frame = bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
    cv2.imwrite(save_path, frame)
    return save_path


def _iter_predictions(result):
    """Yield (class_name, confidence) handling both object- and dict-style results."""
    preds = getattr(result, "predictions", None)
    if preds is None and isinstance(result, dict):
        preds = result.get("predictions", [])
    for p in (preds or []):
        if isinstance(p, dict):
            name = p.get("class") or p.get("class_name") or ""
            conf = float(p.get("confidence", 0.0))
        else:
            name = getattr(p, "class_name", None) or getattr(p, "class", "") or ""
            conf = float(getattr(p, "confidence", 0.0))
        yield name, conf


def detect_medicine(target_name):
    """Return confidence (float) if target medicine is detected, else None."""
    target_class = config.MEDICINE_CLASS_MAP.get(target_name, target_name).lower()
    frame_path = capture_frame()
    result = model.infer(frame_path)[0]

    for name, conf in _iter_predictions(result):
        print("Detected: %s (%.1f%%)" % (name, conf * 100))
        if name.lower() == target_class and conf >= config.CONFIDENCE_THRESHOLD:
            return conf
    return None


def scan_for_medicine(target_name, max_attempts=None):
    """Retry detection a few times. Returns confidence (float) or None."""
    max_attempts = max_attempts or config.DETECT_ATTEMPTS
    for attempt in range(1, max_attempts + 1):
        print("Attempt %d: looking for %s..." % (attempt, target_name))
        conf = detect_medicine(target_name)
        if conf is not None:
            print("Found %s on attempt %d (%.1f%%)" % (target_name, attempt, conf * 100))
            return conf
        rospy.sleep(1)
    print("Did not find %s after %d attempts" % (target_name, max_attempts))
    return None


if __name__ == "__main__":
    rospy.init_node("detector_node", anonymous=True)
    if len(sys.argv) < 2:
        print("Usage: python3 detector.py <med1|med2|med3>")
        sys.exit(1)
    conf = scan_for_medicine(sys.argv[1])
    print("RESULT:", "FOUND (%.1f%%)" % (conf * 100) if conf is not None else "NOT FOUND")
