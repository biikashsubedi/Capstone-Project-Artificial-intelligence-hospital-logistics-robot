#!/usr/bin/env python3
"""
Arm pick-and-drop using fixed, pre-recorded servo positions.

The JetAuto Pro arm uses Hiwonder BUS SERVOS commanded in PULSES (0..1000)
via the standard topic  .../servo_controllers/port_id_1/multi_id_pos_dur
(message type hiwonder_servo_msgs/MultiRawIdPosDur). This is the same
interface every Hiwonder JetAuto example script uses.

Positions live in ~/arm_positions.json, recorded once with arm_recorder.py.
Format — each named pose is a list of [servo_id, pulse] pairs:

    {
      "look":          [[2, 500], [3, 80], [4, 825], [5, 500]],
      "med1_approach": [[2, 500], [3, 200], [4, 700], [5, 500]],
      ...
    }

pick(med):  open gripper -> approach -> grip -> close -> lift -> carry
drop():     drop_approach -> release(open gripper) -> carry

If anything about the servo interface differs on your robot, run
    python3 arm_probe.py
and adjust config.py from what it reports.
"""
import json
import time

import rospy

import config

# ── message / helper imports (JetAuto standard, with fallback) ──────────────
try:
    from hiwonder_servo_msgs.msg import MultiRawIdPosDur, RawIdPosDur
    HAS_SERVO_MSGS = True
except ImportError:
    HAS_SERVO_MSGS = False

_pub = None


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
    if not HAS_SERVO_MSGS:
        raise RuntimeError(
            "hiwonder_servo_msgs not importable — source the JetAuto "
            "workspace first:  source ~/jetauto_ws/devel/setup.bash")
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
    dur_ms = int(duration * 1000)
    msg = MultiRawIdPosDur(id_pos_dur_list=[
        RawIdPosDur(int(sid), int(pulse), dur_ms)
        for sid, pulse in id_pulse_pairs])
    _get_pub().publish(msg)


def set_gripper(open_gripper=True, duration=0.6):
    pulse = (config.GRIPPER_OPEN_PULSE if open_gripper
             else config.GRIPPER_CLOSED_PULSE)
    send_arm_command([(config.GRIPPER_SERVO_ID, pulse)], duration)


def _move(positions, name, duration):
    if name not in positions:
        raise KeyError(
            "arm position '%s' missing from %s — record it with "
            "arm_recorder.py" % (name, config.ARM_POSITIONS_FILE))
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
