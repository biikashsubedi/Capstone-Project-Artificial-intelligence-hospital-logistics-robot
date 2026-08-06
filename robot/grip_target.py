#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Where the gripper actually grabs — measured, not assumed.

The arm camera does not look straight down the gripper's throat, so a medicine
sitting in the MIDDLE of the image is usually NOT where the fingers close.
This module stores the real grab point (measured once) and reads the gripper
joint to tell whether it is holding something.

Set it by sending the command:
    calibrate med1
with the medicine placed exactly where the arm picks it reliably.

Stored in ~/grip_target.json:
    {"x": 0.18, "y": 0.42, "empty_pos": -0.31}
"""
import json

import config


def load():
    """Return {'x','y','area','empty_pos','calibrated'} — saved or fallback."""
    data = {"x": config.GRIP_TARGET_X,
            "y": config.GRIP_TARGET_Y,
            "area": config.GRIP_TARGET_AREA,
            "empty_pos": config.GRIP_EMPTY_POS,
            "grab_z": config.GRAB_Z,      # metres ahead, from the depth camera
            "grab_x": config.GRAB_X}      # metres sideways
    try:
        with open(config.GRIP_TARGET_FILE, "r") as f:
            saved = json.load(f)
        for k in ("x", "y", "area", "empty_pos", "grab_z", "grab_x"):
            if k in saved:
                data[k] = saved[k]
        data["calibrated"] = True
    except Exception:
        data["calibrated"] = False
    return data


def save(x=None, y=None, area=None, empty_pos=None, grab_z=None, grab_x=None):
    """Update only the values given; anything omitted keeps its old value."""
    old = load()
    data = {}
    for key, val in (("x", x), ("y", y), ("area", area),
                     ("empty_pos", empty_pos),
                     ("grab_z", grab_z), ("grab_x", grab_x)):
        chosen = old.get(key) if val is None else val
        if chosen is not None:
            data[key] = round(float(chosen), 5)
    with open(config.GRIP_TARGET_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def read_gripper_position():
    """Current gripper joint angle (radians), or None if unreadable."""
    try:
        import rospy
        from sensor_msgs.msg import JointState
        msg = rospy.wait_for_message("/joint_states", JointState, timeout=2.0)
        for name, pos in zip(msg.name, msg.position):
            if name == config.GRIP_JOINT_NAME:
                return float(pos)
    except Exception:
        pass
    return None


def is_holding(log=print):
    """True if the gripper seems to have something in it.

    Compares the closed gripper angle against the calibrated 'closed on
    nothing' angle: if a box blocks the fingers, they stop short of empty.
    Returns None when it cannot tell (not calibrated / joint unreadable).
    """
    if not config.GRIP_VERIFY:
        return None
    target = load()
    empty = target.get("empty_pos")
    if empty is None:
        log("grip check skipped — no empty-gripper reading calibrated yet")
        return None
    pos = read_gripper_position()
    if pos is None:
        log("grip check skipped — could not read %s" % config.GRIP_JOINT_NAME)
        return None
    # On this robot /joint_states reports the gripper as a constant 0.000 — it
    # never moves — so the reading carries no information. Saying "EMPTY" from
    # that would abort every single pick, including successful ones.
    if abs(pos) < 1e-6 and abs(empty) < 1e-6:
        log("grip check unavailable: %s never changes (always %+.3f) on this "
            "robot, so a pick cannot be confirmed from the joint. Judge it by "
            "eye instead." % (config.GRIP_JOINT_NAME, pos))
        return None

    diff = abs(pos - empty)
    # A stale or nonsense 'empty' reading makes every pick look successful.
    # The gripper joint only spans a small range, so a huge difference means
    # the reference is wrong, not that we are holding something.
    if diff > config.GRIP_MAX_SANE_DIFF:
        log("grip check UNRELIABLE: %s reads %+.3f but 'empty' was recorded as "
            "%+.3f (difference %.3f is impossible). Re-record it with: "
            "the arm_test tool in dev/robot-tools"
            % (config.GRIP_JOINT_NAME, pos, empty, diff))
        return None
    holding = diff > config.GRIP_HOLD_MARGIN
    log("grip check: %s = %+.3f rad, empty = %+.3f, difference %.3f -> %s"
        % (config.GRIP_JOINT_NAME, pos, empty, diff,
           "HOLDING the box" if holding else "EMPTY"))
    return holding
