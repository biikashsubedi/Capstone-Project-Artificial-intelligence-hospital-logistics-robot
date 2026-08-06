#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Odometry-based waypoint movement for a small fixed area (no map needed).

The JetAuto has MECANUM wheels, so it can move forward/back AND strafe
sideways without turning. Every waypoint is therefore just an offset from
the home (centre) position, expressed in the robot's own frame:

    forward  +  = the way the robot faces      (toward the medicine table)
    forward  -  = backwards                    (toward the beds)
    left     +  = strafe to the robot's left
    left     -  = strafe to the robot's right

Movement is closed-loop on /odom: the robot drives until it has actually
travelled the requested distance, so it is far more accurate than timing
and unaffected by battery level. If /odom is unavailable it falls back to
timed motion automatically.

Test each leg on its own with:
    the waypoint_test tool in dev/robot-tools
"""
import math
import time

import rospy
from geometry_msgs.msg import Twist

import config
import motion

try:
    from nav_msgs.msg import Odometry
    HAS_ODOM_MSG = True
except ImportError:
    HAS_ODOM_MSG = False


def _read_odom():
    """Current (x, y) from /odom, or None if unavailable."""
    if not HAS_ODOM_MSG:
        return None
    for topic in config.ODOM_TOPIC_CANDIDATES:
        try:
            msg = rospy.wait_for_message(topic, Odometry, timeout=1.5)
            p = msg.pose.pose.position
            return (p.x, p.y)
        except Exception:
            continue
    return None


def move(forward, left, log=print):
    """Translate by (forward, left) metres in the robot's own frame."""
    dist = math.hypot(forward, left)
    if dist < 0.005:
        return True
    speed = config.WAYPOINT_SPEED
    vx = speed * forward / dist
    vy = speed * left / dist

    start = _read_odom()
    if start is None:
        # No odometry — fall back to timed motion.
        secs = dist / speed
        log("moving %.2f m (timed %.1f s; no odom)" % (dist, secs))
        motion.drive(vx, secs, log=log, linear_y=vy)
        return True

    log("moving %.2f m (forward %+.2f, left %+.2f) with odom feedback"
        % (dist, forward, left))
    pub = motion._get_pub(log)
    msg = Twist()
    msg.linear.x = vx
    msg.linear.y = vy
    deadline = time.time() + dist / speed * config.WAYPOINT_TIMEOUT_FACTOR + 3.0
    travelled = 0.0
    try:
        while not rospy.is_shutdown():
            now = _read_odom()
            if now is not None:
                travelled = math.hypot(now[0] - start[0], now[1] - start[1])
                if travelled >= dist - config.WAYPOINT_TOLERANCE:
                    break
            if time.time() > deadline:
                log("WARNING: move timed out after %.2f m of %.2f m"
                    % (travelled, dist))
                break
            pub.publish(msg)
            time.sleep(0.05)
    finally:
        motion.stop(log=log)
        time.sleep(0.3)
    log("moved %.2f m" % travelled)
    return True


def goto(name, current, log=print):
    """Move from waypoint `current` to waypoint `name`. Returns the new name."""
    wps = config.WAYPOINTS
    if name not in wps:
        raise KeyError("unknown waypoint '%s' (have: %s)"
                       % (name, ", ".join(sorted(wps))))
    if current not in wps:
        current = "home"
    here, there = wps[current], wps[name]
    log("going %s -> %s" % (current, name))
    move(there["forward"] - here["forward"],
         there["left"] - here["left"], log=log)
    return name


if __name__ == "__main__":
    import sys
    rospy.init_node("waypoint_move", anonymous=True)
    target = sys.argv[1] if len(sys.argv) > 1 else "home"
    goto(target, "home")
    print("done")
