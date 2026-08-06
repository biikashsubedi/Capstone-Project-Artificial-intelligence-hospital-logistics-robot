#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arm pick-and-drop using fixed, pre-recorded servo positions.

The JetAuto Pro arm uses Hiwonder BUS SERVOS commanded in PULSES (0..1000)
via the standard topic  .../servo_controllers/port_id_1/multi_id_pos_dur
(message type hiwonder_servo_msgs/MultiRawIdPosDur). This is the same
interface every Hiwonder JetAuto example script uses.

Positions live in ~/arm_positions.json (recorded with the arm_recorder
tool in dev/robot-tools).
Format — each named pose is a list of [servo_id, pulse] pairs:

    {
      "look":          [[2, 500], [3, 80], [4, 825], [5, 500]],
      "med1_approach": [[2, 500], [3, 200], [4, 700], [5, 500]],
      ...
    }

pick(med):  open gripper -> approach -> grip -> close -> lift -> carry
drop():     drop_approach -> release(open gripper) -> carry

If anything about the servo interface differs on your robot, run
    the arm_probe tool in dev/robot-tools
and adjust config.py from what it reports.
"""
import json
import os
import sys
import time

import rospy

import config

# ── message imports (JetAuto standard, several known package names) ─────────
MultiRawIdPosDur = None
RawIdPosDur = None
HAS_SERVO_MSGS = False
SERVO_MSG_ERROR = "no servo message package found"

for _pkg in ("hiwonder_servo_msgs.msg",
             "hiwonder_servo_controllers.msg",
             "jetauto_servo_msgs.msg",
             "ros_robot_controller_msgs.msg"):
    try:
        _mod = __import__(_pkg, fromlist=["MultiRawIdPosDur", "RawIdPosDur"])
        MultiRawIdPosDur = getattr(_mod, "MultiRawIdPosDur")
        RawIdPosDur = getattr(_mod, "RawIdPosDur")
        HAS_SERVO_MSGS = True
        SERVO_MSG_ERROR = None
        break
    except (ImportError, AttributeError) as _e:
        SERVO_MSG_ERROR = str(_e)

SERVO_SETUP_HELP = (
    "hiwonder_servo_msgs is not importable, so the arm cannot be commanded.\n"
    "    Fix: source the JetAuto workspace in THIS terminal, then re-run:\n"
    "        source ~/jetauto_ws/devel/setup.bash\n"
    "    Check it worked:\n"
    "        python3 -c \"import hiwonder_servo_msgs; print('ok')\"\n"
    "    (config.py also adds the usual paths automatically — if this still\n"
    "     fails, use the arm_probe tool in dev/robot-tools.)\n"
    "    last import error: %s" % SERVO_MSG_ERROR)


def require_servo_msgs():
    """Raise a clear, actionable error if the servo messages are missing."""
    if not HAS_SERVO_MSGS:
        raise RuntimeError(SERVO_SETUP_HELP)


_pub = None

# ── Hiwonder action groups (pre-recorded arm sequences) ────────────────────
# automatic_pick.py uses these; they are complete, tested pick/place motions,
# so we prefer them over hand-recorded poses.
_controller = None
ACTION_GROUPS_ERROR = None

try:
    if config.ARM_PC_PATH not in sys.path:
        sys.path.append(config.ARM_PC_PATH)
    import action_group_controller as _controller     # noqa: E402
    HAS_ACTION_GROUPS = True
except Exception as _e:
    HAS_ACTION_GROUPS = False
    ACTION_GROUPS_ERROR = str(_e)

# Official Hiwonder helper for driving bus servos (same call automatic_pick uses)
try:
    from hiwonder_servo_controllers import bus_servo_control as _bus
    HAS_BUS_HELPER = True
except Exception:
    _bus = None
    HAS_BUS_HELPER = False


def list_action_groups():
    """Names of the .d6a action groups installed on this robot."""
    names = set()
    for root in (os.path.join(config.ARM_PC_PATH, "ActionGroups"),
                 config.ARM_PC_PATH):
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.endswith(".d6a"):
                    names.add(f[:-4])
    return sorted(names)


def resolve_action(candidates, log=print):
    """First candidate that exists on this robot (falls back to candidates[0])."""
    available = list_action_groups()
    if available:
        for name in candidates:
            if name in available:
                return name
        log("WARNING: none of %s found; available: %s"
            % (candidates, ", ".join(available) or "(none)"))
    return candidates[0]


def run_action(name, log=print):
    """Play a Hiwonder action group (e.g. 'navigation_pick'). Blocks."""
    if not HAS_ACTION_GROUPS:
        raise RuntimeError(
            "action groups unavailable (%s) — is %s present?"
            % (ACTION_GROUPS_ERROR, config.ARM_PC_PATH))
    log("running action group '%s'" % name)
    _controller.runAction(name)
    log("action '%s' finished" % name)


def ready_pose(log=print):
    """Move to Hiwonder's documented ready-to-pick pose (gripper open)."""
    log("arm -> ready pose")
    send_servos(config.READY_POSE, config.READY_POSE_MS)
    time.sleep(config.READY_POSE_MS / 1000.0 + 0.3)


def send_servos(id_pulse_pairs, duration_ms=1000):
    """Drive bus servos: ((id, pulse), ...) over duration_ms milliseconds.

    Uses Hiwonder's own bus_servo_control helper when available (identical to
    what automatic_pick.py does), else publishes the message directly.
    """
    if HAS_BUS_HELPER:
        _bus.set_servos(_get_pub(), int(duration_ms),
                        tuple((int(i), int(p)) for i, p in id_pulse_pairs))
        return
    send_arm_command(id_pulse_pairs, duration_ms / 1000.0)


def _find_servo_topic():
    """Find the bus-servo command topic (subscribed by the servo driver)."""
    suffix = config.SERVO_TOPIC_SUFFIX
    try:
        master = rospy.get_master()
        _, subs, _ = master.getSystemState()[2]
    except Exception:
        subs = []
    for topic, _nodes in subs:
        if topic.endswith(suffix):
            return topic
    # Not found dynamically — build from namespace candidates.
    for ns in config.NAMESPACE_CANDIDATES:
        if ns:
            return "/%s/%s" % (ns, suffix)
    return "/" + suffix


def _get_pub():
    global _pub
    if _pub is not None:
        return _pub
    require_servo_msgs()
    topic = _find_servo_topic()
    _pub = rospy.Publisher(topic, MultiRawIdPosDur, queue_size=1)
    rospy.sleep(0.4)          # let the publisher register with the driver
    print("[arm] commanding servos on %s" % topic)
    return _pub


def load_positions():
    with open(config.ARM_POSITIONS_FILE, "r") as f:
        return json.load(f)


def send_arm_command(id_pulse_pairs, duration=1.0):
    """Move bus servos: [(id, pulse), ...] over `duration` seconds."""
    require_servo_msgs()          # check BEFORE building the message
    dur_ms = int(duration * 1000)
    msg = MultiRawIdPosDur(id_pos_dur_list=[
        RawIdPosDur(int(sid), int(pulse), dur_ms)
        for sid, pulse in id_pulse_pairs])
    _get_pub().publish(msg)


def set_gripper(open_gripper=True, duration=None, log=print):
    """Open or close the gripper.

    Goes through send_servos() so it uses Hiwonder's own bus_servo_control
    helper — the same call their action groups use. Publishing the message
    directly worked only sometimes, which is why releases were being missed.
    """
    pulse = (config.GRIPPER_OPEN_PULSE if open_gripper
             else config.GRIPPER_CLOSED_PULSE)
    ms = int((duration if duration is not None
              else config.GRIPPER_MOVE_SEC) * 1000)
    log("gripper -> %s (servo %d to %d over %d ms)"
        % ("OPEN" if open_gripper else "CLOSE",
           config.GRIPPER_SERVO_ID, pulse, ms))
    send_servos(((config.GRIPPER_SERVO_ID, pulse),), ms)
    time.sleep(ms / 1000.0 + 0.3)


def _move(positions, name, duration):
    if name not in positions:
        raise KeyError(
            "arm position '%s' missing from %s — record it with "
            "the arm_recorder tool in dev/robot-tools"
            % (name, config.ARM_POSITIONS_FILE))
    send_arm_command(positions[name], duration)
    time.sleep(duration + 0.3)


def look(log=print):
    """Aim the arm camera at the shelf (optional pose used before detection)."""
    positions = load_positions()
    if "look" in positions:
        log("arm: moving to look position")
        _move(positions, "look", 1.5)


def pick(medicine_name, log=print):
    positions = load_positions()
    log("arm: opening gripper")
    set_gripper(open_gripper=True)
    time.sleep(0.8)
    log("arm: approaching %s" % medicine_name)
    _move(positions, medicine_name + "_approach", 1.5)
    log("arm: lowering to grip")
    _move(positions, medicine_name + "_grip", 1.0)
    log("arm: closing gripper")
    set_gripper(open_gripper=False)
    time.sleep(0.8)
    log("arm: lifting")
    _move(positions, medicine_name + "_lift", 1.0)
    log("arm: folding to carry position")
    _move(positions, "carry", 1.5)
    log("picked %s" % medicine_name)


def drop(log=print):
    positions = load_positions()
    log("arm: extending to drop position")
    _move(positions, "drop_approach", 1.5)
    log("arm: releasing item")
    _move(positions, "release", 1.0)
    set_gripper(open_gripper=True)
    time.sleep(0.8)
    log("arm: folding to carry position")
    _move(positions, "carry", 1.5)
    log("item dropped")


if __name__ == "__main__":
    import sys
    rospy.init_node("arm_control_test", anonymous=True)
    if len(sys.argv) >= 2 and sys.argv[1] in config.VALID_MEDICINES:
        pick(sys.argv[1])
    elif len(sys.argv) >= 2 and sys.argv[1] == "drop":
        drop()
    elif len(sys.argv) >= 2 and sys.argv[1] == "look":
        look()
    elif len(sys.argv) >= 2 and sys.argv[1] == "gripper":
        set_gripper(open_gripper=(sys.argv[2] == "open") if len(sys.argv) > 2 else True)
        rospy.sleep(1.0)
    else:
        print("Usage: python3 arm_control.py <med1|med2|med3>  (test pick)")
        print("       python3 arm_control.py drop|look")
        print("       python3 arm_control.py gripper open|close")
