# -*- coding: utf-8 -*-
"""
Central configuration for the AI Nurse Robot delivery system (robot side).

Every robot-side script imports its settings from here, so all the
"values that must match your physical setup" live in ONE place.
Edit this file on the robot after copying the `robot/` folder over.
"""
import os
import sys

# ── Make ROS packages importable even without `source setup.bash` ──────────
# A fresh SSH session doesn't inherit the workspace, which used to make
# hiwonder_servo_msgs / sensor_msgs fail. Add the usual locations ourselves
# so every script works in any terminal.
_HOME = os.path.expanduser("~")
for _p in (
        os.path.join(_HOME, "jetauto_ws/devel/lib/python3/dist-packages"),
        os.path.join(_HOME, "jetauto_ws/devel/lib/python2.7/dist-packages"),
        "/opt/ros/melodic/lib/python3/dist-packages",
        "/opt/ros/melodic/lib/python2.7/dist-packages",
        "/home/jetauto/jetauto_software/jetauto_arm_pc",
):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)

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
# on-robot vision fallback.
CAMERA_TOPIC = "/usb_cam/image_raw"

# Bus-servo command topic for the arm (Hiwonder standard interface).
# Auto-detection in arm_control.py searches subscribers for this suffix.
SERVO_TOPIC_SUFFIX = "servo_controllers/port_id_1/multi_id_pos_dur"

# ── Arm servos (Hiwonder bus servos, positions are PULSES 0..1000) ─────────
# Servo IDs on the JetAuto Pro arm. Gripper is usually ID 1.
# Verified against the robot's own servo manager parameters.
GRIPPER_SERVO_ID = 1
GRIPPER_OPEN_PULSE = 200      # jaws open
GRIPPER_CLOSED_PULSE = 550    # jaws closed (snug, not straining)
GRIPPER_MOVE_SEC = 1.0        # how long the jaws take to travel

# joint_states name -> bus servo ID.
#
#
# CONFIRMED from the robot's own hiwonder_servo_manager parameters:
#   joint1_controller -> servo id 5     joint3_controller -> servo id 3
#   joint2_controller -> servo id 4     joint4_controller -> servo id 2
#   r_joint_controller (gripper) -> servo id 1
JOINT_TO_SERVO = {
    "joint1": 5,
    "joint2": 4,
    "joint3": 3,
    "joint4": 2,
}
GRIPPER_JOINT_NAME = "r_joint"

# The place_* action groups swing the arm over the drop point AND fold it
# back again, all in one blocking call — and they never open the gripper.
# So the release is fired on a timer partway through the action, while the
# arm is still extended over the bed.
#   too early -> box drops short of the bed  -> raise this
#   too late  -> box lands at the robot      -> lower this
# The log prints how long the action actually took, so you can tune it.
PLACE_OPEN_GRIPPER = True
PLACE_RELEASE_AT_SEC = 2.0

# ── File locations on the robot ────────────────────────────────────────────
HOME = os.path.expanduser("~")
LOCATIONS_FILE = os.path.join(HOME, "locations.json")
ARM_POSITIONS_FILE = os.path.join(HOME, "arm_positions.json")

# ── Command vocabulary ─────────────────────────────────────────────────────
VALID_MEDICINES = ["med1", "med2", "med3"]
VALID_BEDS = ["bed1", "bed2"]

# ── Navigation ─────────────────────────────────────────────────────────────
NAV_TIMEOUT_SEC = 90          # give a slow careful robot time to arrive

# ── Hiwonder ACTION GROUPS (pre-recorded arm sequences shipped with JetAuto)
# Found in automatic_pick.py — these are complete, tested pick/place motions.
ARM_PC_PATH = "/home/jetauto/jetauto_software/jetauto_arm_pc"

# Action group names vary by image version. These are tried IN ORDER and the
# first one that actually exists (.d6a file present) is used.
#   navigation_pick / navigation_place -> used by automatic_pick.py on this robot
#   pick / place_right / place_center  -> names in Hiwonder's arm-control docs
ACTION_PICK_CANDIDATES = ["navigation_pick", "pick"]
ACTION_PLACE_CANDIDATES = ["place_right", "navigation_place",
                           "place_center", "place"]
ACTION_HOME_CANDIDATES = ["navigation_pick_init", "pick_init", "init"]

# Back-compat single names (used only if candidate resolution finds nothing)
ACTION_PICK = "navigation_pick"
ACTION_PLACE = "navigation_place"

# Hiwonder's "ready to pick" pose, straight from automatic_pick.py.
# (servo 1 = gripper OPEN at 200)
READY_POSE = ((1, 200), (2, 215), (3, 15), (4, 700), (5, 500))
READY_POSE_MS = 2000

# ── DEMO mission (the simple one: pick → ride 2 s → drop on the right) ─────
# Every command from the GUI runs this same sequence.
DEMO_POSES_FILE = os.path.join(HOME, "demo_poses.json")
DEMO_DRIVE_SEC = 2.0          # how long to ride after picking
DEMO_DRIVE_SPEED = 0.10       # m/s — slow and safe
DEMO_STRAFE_SEC = 0.0         # optional mecanum strafe right before dropping
DEMO_STRAFE_SPEED = 0.10
DEMO_ARM_SEC = 2.0            # seconds per arm move (slow = safe)
DEMO_GRIP_PAUSE = 1.0         # settle time after opening/closing the gripper

# Fallback arm poses, used only if the action groups are unavailable.
# Stored in DEMO_POSES_FILE as lists of [servo_id, pulse] pairs.
DEMO_POSE_NAMES = ["home", "approach", "grip", "lift", "drop_right"]

# ── ROOM LAYOUT (74 cm x 100 cm mat, no map needed) ───────────────────────
#
#      BED 1 (top-left)                 BED 2 (top-right)
#                    \                 /
#                     \   [ ROBOT ]   /      <- home / centre,
#                      \   facing    /          faces the medicine table
#                            v
#                      MEDICINE TABLE (bottom)
#
# Waypoints are offsets from home, in the ROBOT'S OWN frame:
#   forward +  = toward the medicine table (the way the robot faces)
#   forward -  = backwards, toward the beds
#   left    +  = strafe to the robot's LEFT  (= top-right of the mat)
#   left    -  = strafe to the robot's RIGHT (= top-left of the mat)
#
# These are the only numbers that depend on the physical setup; measure them
# with the waypoint_test tool in dev/robot-tools if the layout changes.
WAYPOINTS = {
    "home":     {"forward": 0.00, "left": 0.00},
    "medicine": {"forward": 0.30, "left": 0.00},   # forward to the medicines
    "bed1":     {"forward": -0.32, "left": -0.22},  # back + right = top-LEFT
    "bed2":     {"forward": -0.32, "left": 0.22},   # back + left  = top-RIGHT
}

# ── HOW THE ROBOT TRAVELS ──────────────────────────────────────────────────
#   "odom" = closed-loop odometry moves using WAYPOINTS above.
#            No map needed. Best for this small mat.
#   "map"  = full SLAM + move_base navigation using ~/locations.json.
#            Needs the map built (Lab 6) and poses recorded (Lab 7).
#            Knows where it is, avoids obstacles, recovers if bumped.
#   "marker" = LOOK for printed ArUco markers: rotate until the marker for
#            that place is in view, centre it, drive up to it. No map, and
#            it self-corrects because it keeps checking what it sees.
NAV_MODE = "marker"

# ── ArUco landmark navigation ─────────────────────────────────────────────
# Print the markers from the Mac's markers/ folder (~15 cm wide) and stand
# one at each place, facing the middle of the mat.
MARKER_DICT = "DICT_4X4_50"
MARKER_IDS = {
    "medicine": 0,
    "bed1": 1,
    "bed2": 2,
    "home": 3,
}
# Camera used to look for markers (forward-facing mast camera first).
NAV_CAMERA_CANDIDATES = [
    "/jetauto_1/camera/rgb/image_raw", "/astra_cam/rgb/image_raw",
    "/camera/rgb/image_raw", "/jetauto_1/usb_cam/image_raw", "/usb_cam/image_raw",
]
MARKER_SEARCH_SPEED = 0.55    # rad/s while rotating to search
MARKER_SEARCH_STEP = 0.40     # seconds of rotation per search step
MARKER_SEARCH_STEPS = 24      # enough steps to cover a full turn
MARKER_SETTLE = 0.20          # pause after moving, so the image is sharp
MARKER_CENTRE_TOL = 0.12      # |offset| below this counts as centred
MARKER_CENTRE_GAIN = 1.1      # how hard to turn toward an off-centre marker
MARKER_CENTRE_TRIES = 8
MARKER_APPROACH_SPEED = 0.16  # m/s while driving toward a marker
MARKER_APPROACH_STEP = 0.45    # seconds of driving per approach step (when near)
MARKER_APPROACH_STEP_FAR = 1.5  # longer steps while still far away = faster
MARKER_FAR_RATIO = 0.5        # "far" = marker smaller than half the target size
MARKER_APPROACH_STEPS = 45    # generous — centring no longer eats the budget
MARKER_STALL_STEPS = 6        # give up if the marker stops growing for this many
MARKER_NEAR_AREA = 0.045      # marker fills this share of frame = close enough

# Coming back from the medicine table, reverse the exact distance driven out
# rather than hunting for the home marker again. Faster, and it cannot fail
# the way a search can when the home marker is out of view behind the robot.
RETURN_BY_RETRACE = True

# How close to get to EACH place. The robot stops when the marker fills this
# share of the camera frame — bigger number = it drives closer.
#
#   medicine/bed1/bed2 : markers stand AT those places, so drive right up.
#   home               : the marker stands OUTSIDE the mat (the robot has to
#                        park where the marker is NOT), so it stops further
#                        away — that stopping point IS the centre.
#                        Lower this number if it parks too close to the
#                        marker, raise it if it stops short of the centre.
MARKER_STOP_AREA = {
    "medicine": 0.045,
    "bed1": 0.045,
    "bed2": 0.045,
    "home": 0.015,
}

WAYPOINT_SPEED = 0.16           # m/s while travelling between waypoints
WAYPOINT_TOLERANCE = 0.02       # stop within 2 cm of the target distance
WAYPOINT_TIMEOUT_FACTOR = 2.5   # safety: give up after 2.5x the expected time
# This robot namespaces everything under /jetauto_1/ and publishes raw wheel
# odometry on .../odom_raw, with an EKF-filtered version alongside it.
ODOM_TOPIC_CANDIDATES = [
    "/jetauto_1/odom", "/jetauto_1/odom_raw", "/jetauto_1/odometry/filtered",
    "/odom", "/odom_raw",
]

# Which arm action drops onto which bed. The robot still faces the medicine
# table while at a bed, so its RIGHT side points at the top-left of the mat.
DEMO_BED_ACTIONS = {
    "bed1": "place_right",   # top-LEFT of the mat  (robot's right)
    "bed2": "place_left",    # top-RIGHT of the mat (robot's left)
}

# Confirm the medicine with the Mac's YOLO model before picking.
# Set False if you want the demo to pick regardless of what the camera sees.
DEMO_REQUIRE_VISION = True
DEMO_VISION_ATTEMPTS = 4
DEMO_VISION_RETRY_SEC = 0.25  # each check is a round-trip to the Mac's model

# After confirming the medicine, slide sideways (mecanum) until it sits in the
# middle of the arm camera, so the gripper closes on it instead of beside it.
DEMO_ALIGN_MEDICINE = True
DEMO_ALIGN_TOL = 0.10         # |error| this small counts as lined up
DEMO_ALIGN_SPEED = 0.06       # m/s sideways — slow, it's a fine adjustment
DEMO_ALIGN_STEP = 0.30        # seconds of strafing per correction
DEMO_ALIGN_TRIES = 30         # the marker only gets us roughly there; vision
                              # does the rest, so give it room to travel
DEMO_ALIGN_FWD_SPEED = 0.07   # m/s forward/back while correcting distance
DEMO_ALIGN_FWD_STEP = 0.25
DEMO_ALIGN_SETTLE = 0.15      # pause after each nudge (was 0.4 — too slow)

# ── LOCK ON BEFORE GRABBING ───────────────────────────────────────────────
# The rule: the gripper's grab point (the red cross on the arm camera) must
# land INSIDE the detected medicine before the jaws close. The robot keeps
# moving until that is true, then picks.
LOCK_BEFORE_PICK = True
# The cross must line up BOTH ways before the jaws close: sideways AND
# distance. Leaving distance out made the robot "lock on" while the medicine
# was still well above the cross, and grab empty air.
LOCK_CHECK_DISTANCE = True
LOCK_MAX_TRIES = 25
LOCK_INSET = 0.15         # aim for the middle 70% of the box, not its edge
LOCK_SPEED = 0.05         # m/s forward/back while closing in
                          # DO NOT SPEED UP: this is the fine
                          # alignment that makes picks land.
LOCK_STRAFE_SPEED = 0.05  # m/s sideways (same — leave it slow)
LOCK_GAIN = 1.6           # seconds of movement per unit of error
# Sign of the motion applied when the error is POSITIVE.
# linear_y: + is left, - is right.   linear_x: + is forward, - is back.
# Both were set from what the robot actually does, not from assumed geometry:
#   X: sliding toward the side the medicine appears on centres it correctly.
#   Y: the forward/back sense IS inverted on this robot — when the medicine
#      looks below the cross it needs to drive FORWARD, not back (confirmed
#      on the real hardware).
# Sign of the motion when the error is POSITIVE.
# linear_y: + = left, - = right.   linear_x: + = forward.
#
# SIDEWAYS follows the picture, which is what works on this robot:
#     medicine appears LEFT  of the cross  ->  robot slides LEFT
#     medicine appears RIGHT of the cross  ->  robot slides RIGHT
LOCK_X_DIRECTION = -1
# DISTANCE also follows the picture. The arm camera looks forward and down,
# so things further away sit HIGHER in the frame:
#     medicine ABOVE the cross -> it is too FAR   -> drive FORWARD
#     medicine BELOW the cross -> it is too NEAR  -> back off
# err_y is positive when the medicine is BELOW the cross, so that case is the
# one that must reverse:
LOCK_Y_DIRECTION = -1
LOCK_LOST_RETRIES = 3     # re-look this many times before giving up on a frame
LOCK_MIN_STEP = 0.10
LOCK_MAX_STEP = 0.45      # short strafes: a long one can slide the medicine
                          # right out of the camera's view before the next look
LOCK_SETTLE = 0.20
LOCK_REQUIRED = False     # True = refuse to pick unless locked on

# ── HOW TO PICK ───────────────────────────────────────────────────────────
#   "hiwonder" = call the robot's OWN /automatic_pick/pick service. It drives
#                itself into position with PID visual servoing and then runs
#                the pick action group. Their code, already tuned.
#                Needs:  roslaunch jetauto_example automatic_pick.launch
#   "manual"   = our own approach (depth camera / camera aiming) + the bare
#                'navigation_pick' action group. Fallback only.
PICK_MODE = "hiwonder"
AUTO_PICK_TIMEOUT = 90        # seconds to let their routine work

# ── DEPTH CAMERA: measure the real distance to the medicine ───────────────
# The Astra publishes depth ALIGNED to the RGB image, so a detection's pixel
# is the same pixel in the depth image. Depth is 16-bit millimetres, 0 = no
# reading (REP-118), so we take the median of a patch.
DEPTH_IMAGE_CANDIDATES = [
    "/astra_cam/depth_registered/image_raw",   # aligned to RGB — best
    "/astra_cam/depth_registered/hw_registered/image_rect_raw",
    "/astra_cam/depth/image_raw",
    "/camera/depth_registered/image_raw",
]
DEPTH_INFO_CANDIDATES = [
    "/astra_cam/rgb/camera_info",
    "/astra_cam/depth_registered/camera_info",
    "/astra_cam/depth/camera_info",
]
DEPTH_PATCH = 6              # half-size of the sampled patch, in pixels
DEPTH_MIN_VALID = 12         # need at least this many valid pixels to trust it
DEPTH_MIN_M = 0.12           # Astra can't see closer than this
DEPTH_MAX_M = 4.0
DEPTH_FALLBACK_HFOV_DEG = 60.0   # only used if camera_info is missing

# Where the medicine must END UP relative to the camera for the arm to grab
# it — measured in METRES by the depth camera during calibration.
# Recorded by "calibrate depth" with the box on the spot that works.
GRAB_Z = None                # metres straight ahead (None = not measured yet)
GRAB_X = None                # metres sideways (+ = right)
GRAB_TOL_Z = 0.02            # stop when within 2 cm of the right distance
GRAB_TOL_X = 0.02
GRAB_APPROACH_SPEED = 0.07   # m/s while closing the measured gap
GRAB_STRAFE_SPEED = 0.06
GRAB_MAX_MOVES = 12

# ── WHERE THE GRIPPER ACTUALLY GRABS (calibrated) ─────────────────────────
# The gripper does NOT close at the middle of the camera image. These are the
# frame coordinates (-1..+1) where a medicine must appear for the pick to
# succeed. Measure them once — put a box where the arm picks it reliably, then
# from the Mac GUI press "CALIBRATE GRIP" (or send the command "calibrate med1").
# The measured values are written to GRIP_TARGET_FILE and used automatically.
GRIP_TARGET_FILE = os.path.join(HOME, "grip_target.json")

# DEFAULTS STRAIGHT FROM HIWONDER'S OWN automatic_pick.py, which drives the
# SAME 'navigation_pick' action group we use:
#     stop_x = 287, stop_y = 388   (in the 640x480 arm-camera image)
# Normalised to -1..+1 that is x = (287-320)/320, y = (388-240)/240.
# Note how far DOWN the frame it is — the box must be near the bottom of the
# image, nowhere near the middle. Calibration can refine these, but these
# factory values are a good starting point.
GRIP_TARGET_X = -0.103
# Hiwonder's own value is 0.617 (pixel 388), but that drives THIS robot too
# close — the box ends up at the very bottom of the frame and under the
# gripper. Backed off so it stops a couple of inches short.
#   SMALLER y  = box sits HIGHER in the frame = robot stops FURTHER BACK
#   LARGER  y  = box sits LOWER  in the frame = robot drives CLOSER
# Tune it live with the "grip up" / "grip down" commands — no file edits.
GRIP_TARGET_Y = 0.45
GRIP_TARGET_AREA = 0.0        # optional cross-check on distance (0 = unused)
GRIP_NUDGE = 0.05             # how much one "grip up/down/left/right" moves it

# Distance is judged by the box's VERTICAL position, exactly like Hiwonder's
# code: lower in the frame = nearer the robot.
GRIP_ALIGN_DISTANCE = True
# Hiwonder tolerate 10 px, tightening to 5 px for the final approach.
# 10/640 -> 0.031 in x, 10/240 -> 0.042 in y.
GRIP_TOL_X = 0.031
GRIP_TOL_Y = 0.042
# Proportional control: move by (error x gain), clamped — big error, big move;
# small error, small nudge. Fixed-size steps used to overshoot or stall.
GRIP_GAIN_X = 1.4
GRIP_GAIN_Y = 1.2
GRIP_MIN_STEP = 0.08          # seconds — shortest useful nudge
GRIP_MAX_STEP = 1.00          # seconds — longest single correction

# ── DID THE GRIPPER ACTUALLY GET IT? ──────────────────────────────────────
# After closing, read the gripper joint. If it closed all the way it is empty;
# if a box is in the way it stops short. Calibration records the empty value.
GRIP_VERIFY = True
GRIP_JOINT_NAME = "r_joint"
GRIP_EMPTY_POS = None         # radians when closed on nothing (calibrated)
GRIP_HOLD_MARGIN = 0.05       # this much away from "empty" means holding
# The gripper joint only travels a small range. A difference bigger than this
# means the recorded "empty" value is stale/bogus, not that a box is held —
# that false positive made failed picks report success.
GRIP_MAX_SANE_DIFF = 0.60

# ── Fetch mission (creep forward until the medicine is seen, no map) ───────
FETCH_SPEED = 0.10            # m/s — slow, safe creep
FETCH_STEP_SEC = 1.2          # one step ~12 cm, then stop and look
FETCH_MAX_STEPS = 15          # hard cap ≈ 1.8 m of forward travel
FETCH_NEAR_AREA = 0.05        # stop when box fills ≥5% of the frame (tune!)
FETCH_CONFIRM_CHECKS = 2      # consecutive confirmations before picking
FETCH_SETTLE_SEC = 0.5        # pause after each step before looking
NAV_SERVER_WAIT_SEC = 10      # how long to wait for move_base to exist

# ── Detection (delegated to the Mac over the socket) ───────────────────────
DETECT_ATTEMPTS = 5           # how many times to ask the Mac before giving up
DETECT_RETRY_DELAY_SEC = 1.5

# ── Optional on-robot vision fallback ─────────────────────────────────────
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "YOUR_API_KEY_HERE")
MODEL_ID = "agent/1"
CONFIDENCE_THRESHOLD = 0.6
MEDICINE_CLASS_MAP = {
    "med1": "acetaminophen",
    "med2": "allergy_relief",
    "med3": "ibuprofen",
}
