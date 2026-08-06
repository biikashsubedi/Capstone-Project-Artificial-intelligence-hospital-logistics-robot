#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Measure WHERE the medicine really is, in metres, using the depth camera.

Instead of guessing from how big something looks, this reads the actual
distance from the Astra depth camera and converts it to a real 3D position:

    Z = depth at the object's pixel          (metres, straight ahead)
    X = (px - cx) * Z / fx                   (metres, + = to the right)
    Y = (py - cy) * Z / fy                   (metres, + = downwards)

Two things make this reliable (both standard practice, see REP-118):
  * /astra_cam/depth_registered/... is aligned to the RGB image, so the
    detection's pixel is the SAME pixel in the depth image;
  * depth is 16-bit millimetres with 0 meaning "no reading", so we sample a
    patch around the point and take the MEDIAN of the valid pixels.

Test it on the robot:
    python3 depth_test.py            # distance at the centre of the view
    python3 depth_test.py 0.1 -0.2   # at a normalised (x, y) in the frame
"""
import rospy

import config

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from sensor_msgs.msg import Image, CameraInfo
    HAS_MSGS = True
except ImportError:
    HAS_MSGS = False

_intrinsics = None      # (fx, fy, cx, cy, width, height)


def get_intrinsics(log=print):
    """Camera intrinsics from camera_info (cached). None if unavailable."""
    global _intrinsics
    if _intrinsics is not None:
        return _intrinsics
    if not HAS_MSGS:
        return None
    for topic in config.DEPTH_INFO_CANDIDATES:
        try:
            msg = rospy.wait_for_message(topic, CameraInfo, timeout=2.0)
        except Exception:
            continue
        k = list(msg.K)
        if len(k) >= 6 and k[0] > 0:
            _intrinsics = (k[0], k[4], k[2], k[5], msg.width, msg.height)
            log("camera intrinsics from %s: fx %.1f fy %.1f cx %.1f cy %.1f"
                % (topic, k[0], k[4], k[2], k[5]))
            return _intrinsics
    log("WARNING: no camera_info found — falling back to an assumed field of "
        "view, so sideways distances will be approximate")
    return None


def _grab_depth_image(log=print):
    """One depth frame as a numpy array of metres (NaN where unknown)."""
    if not (HAS_MSGS and HAS_NUMPY):
        return None
    for topic in config.DEPTH_IMAGE_CANDIDATES:
        try:
            msg = rospy.wait_for_message(topic, Image, timeout=2.0)
        except Exception:
            continue
        try:
            if msg.encoding in ("16UC1", "mono16"):
                arr = np.frombuffer(msg.data, dtype=np.uint16)
                arr = arr.reshape(msg.height, msg.width).astype(np.float32)
                arr[arr == 0] = np.nan          # 0 means "no reading"
                return arr / 1000.0             # millimetres -> metres
            if msg.encoding == "32FC1":
                arr = np.frombuffer(msg.data, dtype=np.float32)
                arr = arr.reshape(msg.height, msg.width).copy()
                arr[arr <= 0] = np.nan
                return arr
            log("depth topic %s has unexpected encoding %s"
                % (topic, msg.encoding))
        except Exception as e:
            log("could not read %s (%s)" % (topic, e))
    return None


def measure(norm_x, norm_y, log=print):
    """Real position of whatever is at normalised frame point (norm_x, norm_y).

    norm_x/-y are -1..+1 as used everywhere else (0,0 = middle of the frame).
    Returns (X, Y, Z) in metres — Z forward, X right, Y down — or None.
    """
    depth = _grab_depth_image(log=log)
    if depth is None:
        log("no depth image available (tried %s)"
            % ", ".join(config.DEPTH_IMAGE_CANDIDATES))
        return None
    h, w = depth.shape[:2]
    px = int((norm_x + 1.0) * w / 2.0)
    py = int((norm_y + 1.0) * h / 2.0)
    px = max(0, min(w - 1, px))
    py = max(0, min(h - 1, py))

    # Median over a patch — single pixels are often invalid or noisy.
    r = config.DEPTH_PATCH
    patch = depth[max(0, py - r):py + r + 1, max(0, px - r):px + r + 1]
    valid = patch[~np.isnan(patch)]
    if valid.size < config.DEPTH_MIN_VALID:
        log("depth at pixel (%d,%d): only %d valid readings — too few"
            % (px, py, valid.size))
        return None
    z = float(np.median(valid))
    if not (config.DEPTH_MIN_M < z < config.DEPTH_MAX_M):
        log("depth %.3f m at (%d,%d) is outside the believable range" % (z, px, py))
        return None

    intr = get_intrinsics(log=log)
    if intr is not None:
        fx, fy, cx, cy, iw, ih = intr
        # camera_info may describe a different resolution than the depth image
        sx, sy = w / float(iw or w), h / float(ih or h)
        fx, fy, cx, cy = fx * sx, fy * sy, cx * sx, cy * sy
        x = (px - cx) * z / fx
        y = (py - cy) * z / fy
    else:
        # No intrinsics: approximate using a nominal horizontal field of view.
        import math
        fov = math.radians(config.DEPTH_FALLBACK_HFOV_DEG)
        fx = (w / 2.0) / math.tan(fov / 2.0)
        x = (px - w / 2.0) * z / fx
        y = (py - h / 2.0) * z / fx
    log("depth at pixel (%d,%d): %.3f m ahead, %+.3f m sideways (%d samples)"
        % (px, py, z, x, valid.size))
    return (x, y, z)


if __name__ == "__main__":
    import sys
    rospy.init_node("depth_sense", anonymous=True)
    nx = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    ny = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    print(measure(nx, ny))
