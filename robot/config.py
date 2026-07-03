"""
Central configuration for the AI Nurse Robot delivery system (robot side).

Every robot-side script imports its settings from here, so all the
"values that must match your physical setup" live in ONE place.
Edit this file on the robot after copying the `robot/` folder over.
"""
import os

# ── Network (socket server the Mac connects to) ────────────────────────────
SERVER_HOST = "0.0.0.0"   # bind all interfaces; leave as-is
SERVER_PORT = 5050

# ── ROS namespace ──────────────────────────────────────────────────────────
# This robot reported MASTER=jetauto_1, but its camera topics are NOT
# namespaced (/usb_cam/...). Navigation may live at /move_base or
# /jetauto_1/move_base depending on how the nav stack was launched.
# navigator.py AUTO-DETECTS the right one at runtime; this is the fallback
# order it tries first.
NAMESPACE_CANDIDATES = ["", "jetauto_1"]

# ── ROS interfaces ─────────────────────────────────────────────────────────
# Camera used for medicine detection lives on the MAC side now (the Mac runs
# best.pt on the live /usb_cam stream). This value is only needed if you use
# the optional on-robot detector.py fallback.
CAMERA_TOPIC = "/usb_cam/image_raw"

# Bus-servo command topic for the arm (Hiwonder standard interface).
# Auto-detection in arm_control.py searches subscribers for this suffix.
SERVO_TOPIC_SUFFIX = "servo_controllers/port_id_1/multi_id_pos_dur"

# ── Arm servos (Hiwonder bus servos, positions are PULSES 0..1000) ─────────
# Servo IDs on the JetAuto Pro arm. Gripper is usually ID 1.
# Verify with:  python3 arm_probe.py   and adjust here if different.
GRIPPER_SERVO_ID = 1
GRIPPER_OPEN_PULSE = 200      # tune with arm_recorder.py
GRIPPER_CLOSED_PULSE = 550    # tune with arm_recorder.py (grip snug, not straining)

# joint_states name -> bus servo ID (used by arm_recorder.py to convert the
# live joint angles into pulses). Run arm_probe.py to see the real names and
# fix this mapping if needed.
JOINT_TO_SERVO = {
    "joint1": 2,
    "joint2": 3,
    "joint3": 4,
    "joint4": 5,
}

# ── File locations on the robot ────────────────────────────────────────────
HOME = os.path.expanduser("~")
LOCATIONS_FILE = os.path.join(HOME, "locations.json")
ARM_POSITIONS_FILE = os.path.join(HOME, "arm_positions.json")

# ── Command vocabulary ─────────────────────────────────────────────────────
VALID_MEDICINES = ["med1", "med2", "med3"]
VALID_BEDS = ["bed1", "bed2", "bed3"]

# ── Navigation ─────────────────────────────────────────────────────────────
NAV_TIMEOUT_SEC = 90          # give a slow careful robot time to arrive
NAV_SERVER_WAIT_SEC = 10      # how long to wait for move_base to exist

# ── Detection (delegated to the Mac over the socket) ───────────────────────
DETECT_ATTEMPTS = 5           # how many times to ask the Mac before giving up
DETECT_RETRY_DELAY_SEC = 1.5

# ── Optional on-robot Roboflow fallback (detector.py) ──────────────────────
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "YOUR_API_KEY_HERE")
MODEL_ID = "agent/1"
CONFIDENCE_THRESHOLD = 0.6
MEDICINE_CLASS_MAP = {
    "med1": "acetaminophen",
    "med2": "allergy_relief",
    "med3": "ibuprofen",
}
