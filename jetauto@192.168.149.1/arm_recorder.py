#!/usr/bin/env python3
"""
Interactive arm-position recorder — run ONCE on the robot to create
~/arm_positions.json for arm_control.py.

How it works
------------
For each named pose, you physically put the arm where you want it (using the
Hiwonder phone app's arm control, the WonderPi 'teach' mode, or by gently
moving it if torque is off), then press ENTER here. The recorder reads the
current joint angles from /joint_states and converts them to servo pulses
(Hiwonder bus servos: 0..1000 pulses over 240 degrees, centre 500).

If /joint_states isn't available, it falls back to letting you type pulses
manually.

Poses recorded (in this order):
  look            arm aimed so the USB camera sees the shelf
  med1_approach   gripper OPEN, hovering just in front of/above med1
  med1_grip       lowered so the gripper surrounds med1
  med1_lift       med1 lifted slightly off the shelf
  med2_approach / med2_grip / med2_lift
  med3_approach / med3_grip / med3_lift
  carry           arm folded safely against the body for driving
  drop_approach   arm extended over the bed drop spot
  release         where the gripper opens to release the item
"""
import json
import math

import rospy
from sensor_msgs.msg import JointState

import config

POSES = [
    ("look", "Aim the arm so its camera clearly sees the medicine shelf"),
    ("med1_approach", "Gripper OPEN, hovering at med1, ready to descend"),
    ("med1_grip", "Lowered so the open gripper surrounds med1"),
    ("med1_lift", "med1 raised a few cm off the shelf"),
    ("med2_approach", "Gripper OPEN, hovering at med2"),
    ("med2_grip", "Lowered so the open gripper surrounds med2"),
    ("med2_lift", "med2 raised a few cm off the shelf"),
    ("med3_approach", "Gripper OPEN, hovering at med3"),
    ("med3_grip", "Lowered so the open gripper surrounds med3"),
    ("med3_lift", "med3 raised a few cm off the shelf"),
    ("carry", "Arm folded compactly against the robot body (safe to drive)"),
    ("drop_approach", "Arm extended over the bed's drop spot"),
    ("release", "Position where opening the gripper drops the item on the bed"),
]

RAD_TO_PULSE = 1000.0 / math.radians(240.0)   # Hiwonder: 240 deg == 1000 pulses


def read_current_pulses():
    """Read /joint_states once and convert mapped joints to (id, pulse)."""
    topics = [t for t, _ in rospy.get_published_topics()]
    js_topic = None
    for cand in ["/joint_states"] + ["/%s/joint_states" % ns
                                     for ns in config.NAMESPACE_CANDIDATES if ns]:
        if cand in topics:
            js_topic = cand
            break
    if js_topic is None:
        return None
    msg = rospy.wait_for_message(js_topic, JointState, timeout=3)
    pairs = []
    for name, pos in zip(msg.name, msg.position):
        if name in config.JOINT_TO_SERVO:
            pulse = int(round(500 + pos * RAD_TO_PULSE))
            pulse = max(0, min(1000, pulse))
            pairs.append([config.JOINT_TO_SERVO[name], pulse])
    pairs.sort()
    return pairs if pairs else None


def manual_entry():
    print("  Manual entry — type servo_id:pulse pairs separated by spaces")
    print("  e.g.  2:500 3:80 4:825 5:500")
    while True:
        raw = input("  pulses> ").strip()
        try:
            pairs = []
            for token in raw.split():
                sid, pulse = token.split(":")
                pairs.append([int(sid), int(pulse)])
            if pairs:
                return pairs
        except ValueError:
            pass
        print("  Could not parse — try again (format  id:pulse id:pulse ...)")


def main():
    rospy.init_node("arm_recorder", anonymous=True)
    print(__doc__)
    recorded = {}
    try:
        with open(config.ARM_POSITIONS_FILE) as f:
            recorded = json.load(f)
        print("Loaded existing %s — poses you skip keep their old values.\n"
              % config.ARM_POSITIONS_FILE)
    except Exception:
        pass

    for name, hint in POSES:
        existing = " (already recorded — ENTER to redo, 's' to keep)" \
                   if name in recorded else ""
        print("\n=== %s ===\n    %s%s" % (name, hint, existing))
        choice = input("Position the arm now, then press ENTER "
                       "(or 's' to skip): ").strip().lower()
        if choice == "s":
            continue
        pairs = read_current_pulses()
        if pairs is None:
            print("  (could not read /joint_states — falling back to manual)")
            pairs = manual_entry()
        recorded[name] = pairs
        print("  recorded %s = %s" % (name, pairs))

    with open(config.ARM_POSITIONS_FILE, "w") as f:
        json.dump(recorded, f, indent=2)
    print("\nSaved %d poses to %s" % (len(recorded), config.ARM_POSITIONS_FILE))
    print("Now test:  python3 arm_control.py med1   (robot at the shelf!)")


if __name__ == "__main__":
    main()
