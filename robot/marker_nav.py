#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Landmark navigation with ArUco markers — the robot LOOKS for where to go.

Put a printed ArUco marker at each place (see markers/ on the Mac):
    ID 0 = medicine table      ID 2 = bed 2
    ID 1 = bed 1               ID 3 = home / centre

Then, for any place:
    1. rotate on the spot until that marker comes into view
    2. turn to centre it in the camera
    3. drive forward until it is close enough
    4. stop

Detection runs HERE on the robot (OpenCV only, no model needed), so the
control loop is fast and does not depend on the WiFi link. The Mac's YOLO
model is still what identifies WHICH medicine to pick.

Test it standalone:
    python3 marker_test.py see          # what markers can the camera see?
    python3 marker_test.py find 1       # rotate until bed 1 is found
    python3 marker_test.py goto 0       # find and approach the medicine table
"""
import math
import time

import rospy
from sensor_msgs.msg import Image

import config
import motion

try:
    import cv2
    import numpy as np
    HAS_CV = True
except ImportError:
    HAS_CV = False

_detector = None
_dict = None
last_error = None      # why the most recent goto() failed (for good messages)

# How long the robot drove FORWARD while approaching each place, in seconds at
# MARKER_APPROACH_SPEED. Retracing that exact amount is faster and far more
# reliable than hunting for the home marker again — which is easy to lose once
# the robot is right up against the medicine table.
_drive_seconds = {}


def travelled(place):
    """Seconds of forward driving recorded on the last trip to `place`."""
    return _drive_seconds.get(place, 0.0)


def retrace(place, log=print):
    """Reverse exactly the distance driven to reach `place`.

    Same speed, same time, opposite direction — so the robot lands back where
    it set off from without needing to see anything.
    """
    secs = _drive_seconds.get(place, 0.0)
    if secs <= 0.0:
        log("nothing recorded for the trip to %s — cannot retrace" % place)
        return False
    log("retracing the trip to %s: reversing %.1f s (%.0f cm)"
        % (place, secs, secs * config.MARKER_APPROACH_SPEED * 100))
    remaining = secs
    while remaining > 0.01 and not rospy.is_shutdown():
        chunk = min(remaining, 3.0)          # keep each command short and safe
        motion.drive(-config.MARKER_APPROACH_SPEED, chunk, log=log)
        remaining -= chunk
    motion.stop(log=log)
    _drive_seconds[place] = 0.0              # consumed
    log("back at the position we started from")
    return True


def _get_detector():
    """Build the ArUco detector, handling both old and new OpenCV APIs."""
    global _detector, _dict
    if _detector is not None or _dict is not None:
        return _detector, _dict
    if not HAS_CV:
        raise RuntimeError("OpenCV not available on the robot")
    if not hasattr(cv2, "aruco"):
        raise RuntimeError(
            "cv2.aruco missing — install it with:\n"
            "    pip3 install opencv-contrib-python")
    name = getattr(cv2.aruco, config.MARKER_DICT, cv2.aruco.DICT_4X4_50)
    if hasattr(cv2.aruco, "getPredefinedDictionary"):
        _dict = cv2.aruco.getPredefinedDictionary(name)
    else:                                    # very old OpenCV
        _dict = cv2.aruco.Dictionary_get(name)
    if hasattr(cv2.aruco, "ArucoDetector"):  # OpenCV >= 4.7
        _detector = cv2.aruco.ArucoDetector(_dict, cv2.aruco.DetectorParameters())
    return _detector, _dict


def _grab_frame():
    """One BGR frame from the navigation camera. None if unavailable."""
    for topic in config.NAV_CAMERA_CANDIDATES:
        try:
            msg = rospy.wait_for_message(topic, Image, timeout=2.0)
        except Exception:
            continue
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8)
            if msg.encoding in ("rgb8", "bgr8"):
                img = arr.reshape(msg.height, msg.width, 3)
                if msg.encoding == "rgb8":
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                return img
            if msg.encoding == "mono8":
                return cv2.cvtColor(arr.reshape(msg.height, msg.width),
                                    cv2.COLOR_GRAY2BGR)
        except Exception:
            continue
    return None


def detect(frame=None):
    """Detect markers. Returns {id: {'cx','cy','area','offset','width'}}.

    offset is -1.0 (far left of the image) .. +1.0 (far right); 0 = centred.
    area is the marker's share of the frame (bigger = closer).
    """
    if frame is None:
        frame = _grab_frame()
    if frame is None:
        return {}
    det, dic = _get_detector()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if det is not None:
        corners, ids, _ = det.detectMarkers(gray)
    else:
        corners, ids, _ = cv2.aruco.detectMarkers(gray, dic)
    out = {}
    if ids is None:
        return out
    h, w = gray.shape[:2]
    for c, i in zip(corners, ids.ravel()):
        pts = c.reshape(4, 2)
        cx, cy = float(pts[:, 0].mean()), float(pts[:, 1].mean())
        area = float(cv2.contourArea(pts.astype(np.float32))) / float(w * h)
        out[int(i)] = {
            "cx": cx, "cy": cy, "area": area,
            "offset": (cx - w / 2.0) / (w / 2.0),
            "width": float(pts[:, 0].max() - pts[:, 0].min()),
        }
    return out


def _spin(direction, log):
    """Rotate in place for one search step."""
    pub = motion._get_pub(log)
    from geometry_msgs.msg import Twist
    msg = Twist()
    msg.angular.z = config.MARKER_SEARCH_SPEED * direction
    end = time.time() + config.MARKER_SEARCH_STEP
    while time.time() < end and not rospy.is_shutdown():
        pub.publish(msg)
        time.sleep(0.05)
    motion.stop(log=log)
    time.sleep(config.MARKER_SETTLE)


def search(marker_id, log=print, direction=1):
    """Rotate on the spot until `marker_id` is visible. Returns info or None."""
    log("searching for marker %d (rotating)..." % marker_id)
    for step in range(1, config.MARKER_SEARCH_STEPS + 1):
        found = detect()
        if marker_id in found:
            info = found[marker_id]
            log("marker %d found (offset %+.2f, size %.1f%%)"
                % (marker_id, info["offset"], info["area"] * 100))
            return info
        if found:
            log("  step %d: see markers %s — not the one"
                % (step, sorted(found)))
        else:
            log("  step %d/%d: nothing in view"
                % (step, config.MARKER_SEARCH_STEPS))
        _spin(direction, log)
    log("marker %d not found after a full search" % marker_id)
    return None


def centre(marker_id, log=print):
    """Turn until the marker sits in the middle of the frame."""
    for _ in range(config.MARKER_CENTRE_TRIES):
        found = detect()
        if marker_id not in found:
            return False
        off = found[marker_id]["offset"]
        if abs(off) <= config.MARKER_CENTRE_TOL:
            log("marker %d centred" % marker_id)
            return True
        # turn toward the marker; speed proportional to how far off it is
        from geometry_msgs.msg import Twist
        pub = motion._get_pub(log)
        msg = Twist()
        turn = -config.MARKER_CENTRE_GAIN * off
        msg.angular.z = max(-config.MARKER_SEARCH_SPEED,
                            min(config.MARKER_SEARCH_SPEED, turn))
        end = time.time() + 0.25
        while time.time() < end:
            pub.publish(msg)
            time.sleep(0.05)
        motion.stop(log=log)
        time.sleep(config.MARKER_SETTLE)
    return True


def approach(marker_id, target_area=None, log=print):
    """Drive forward (re-centring as it goes) until the marker looks close.

    Steps are long while the marker is still small and shorten near the end,
    so approaches are quick without overshooting. Re-centring does NOT use up
    the step budget — only actual driving does.
    """
    target_area = target_area or config.MARKER_NEAR_AREA
    steps_driven = 0
    driven_seconds = 0.0
    best_area = 0.0
    stalled = 0
    while steps_driven < config.MARKER_APPROACH_STEPS:
        found = detect()
        if marker_id not in found:
            log("lost marker %d while approaching — re-searching" % marker_id)
            if search(marker_id, log=log) is None:
                return False, driven_seconds
            continue
        info = found[marker_id]
        area = info["area"]
        if area >= target_area:
            log("arrived at marker %d (size %.1f%%)" % (marker_id, area * 100))
            return True, driven_seconds
        if abs(info["offset"]) > config.MARKER_CENTRE_TOL:
            centre(marker_id, log=log)      # free — doesn't cost a step
            continue

        # Give up early if we're pushing but the marker isn't getting bigger
        # (wall, obstacle, or wheels slipping) instead of grinding to the cap.
        if area > best_area * 1.02:
            best_area = area
            stalled = 0
        else:
            stalled += 1
            if stalled >= config.MARKER_STALL_STEPS:
                log("marker %d stopped getting closer (stuck at %.1f%%) — "
                    "is something in the way?" % (marker_id, area * 100))
                return False, driven_seconds

        far = area < target_area * config.MARKER_FAR_RATIO
        drive_for = (config.MARKER_APPROACH_STEP_FAR if far
                     else config.MARKER_APPROACH_STEP)
        log("  approaching marker %d (size %.1f%% of %.1f%%)%s"
            % (marker_id, area * 100, target_area * 100, "  [fast]" if far else ""))
        motion.drive(config.MARKER_APPROACH_SPEED, drive_for, log=log)
        driven_seconds += drive_for
        steps_driven += 1
        time.sleep(config.MARKER_SETTLE)

    log("gave up approaching marker %d after %d steps (got to %.1f%% of %.1f%%)"
        % (marker_id, steps_driven, best_area * 100, target_area * 100))
    return False, driven_seconds


def goto(place, log=print):
    """Find and drive to a named place ('medicine', 'bed1', 'bed2', 'home')."""
    if place not in config.MARKER_IDS:
        raise KeyError("no marker configured for '%s' (have: %s)"
                       % (place, ", ".join(sorted(config.MARKER_IDS))))
    global last_error
    marker_id = config.MARKER_IDS[place]
    stop_area = config.MARKER_STOP_AREA.get(place, config.MARKER_NEAR_AREA)
    log("going to %s (marker %d, stop at %.1f%% of frame)"
        % (place, marker_id, stop_area * 100))
    if search(marker_id, log=log) is None:
        last_error = ("Could not locate the %s — check its marker is "
                      "upright, well lit and facing the robot" % place)
        return False
    if not centre(marker_id, log=log):
        last_error = "Lost sight of the %s while turning toward it" % place
        return False
    ok, secs = approach(marker_id, target_area=stop_area, log=log)
    _drive_seconds[place] = secs
    if not ok:
        last_error = ("Located the %s but could not reach it — check the "
                      "path is clear" % place)
        return False
    last_error = None
    return True


if __name__ == "__main__":
    import sys
    rospy.init_node("marker_nav", anonymous=True)
    target = sys.argv[1] if len(sys.argv) > 1 else "medicine"
    print("OK" if goto(target) else "FAILED")
