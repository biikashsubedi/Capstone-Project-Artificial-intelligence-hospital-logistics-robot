#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple timed base motion (no map needed).

Publishes geometry_msgs/Twist on the JetAuto's velocity topic for a fixed
duration, then ALWAYS sends a stop. The topic is auto-detected (Lab 5: the
physical JetAuto listens on .../jetauto_controller/cmd_vel).

Standalone tests (robot on the floor, wheels clear!):
    python3 motion.py forward 1.0      # creep forward for 1 second
    python3 motion.py backward 1.0
    python3 motion.py stop
"""
import time

import rospy
from geometry_msgs.msg import Twist

import config

_pub = None
_topic = None


def _find_cmd_vel_topic():
    """Prefer the hardware controller topic; fall back to plain cmd_vel."""
    try:
        master = rospy.get_master()
        _, subs, _ = master.getSystemState()[2]
        subscribed = [t for t, _n in subs]
    except Exception:
        subscribed = []
    for suffix in ["jetauto_controller/cmd_vel", "/cmd_vel"]:
        for topic in subscribed:
            if topic.endswith(suffix) and "move_base" not in topic:
                return topic
    return "/jetauto_controller/cmd_vel"     # labs' documented default


def _get_pub(log=print):
    global _pub, _topic
    if _pub is None:
        _topic = _find_cmd_vel_topic()
        _pub = rospy.Publisher(_topic, Twist, queue_size=1)
        rospy.sleep(0.4)                     # let the publisher register
        log("motion: commanding wheels on %s" % _topic)
    return _pub


def stop(log=print):
    _get_pub(log).publish(Twist())


def drive(linear_x, duration, log=print, linear_y=0.0):
    """Drive for `duration` seconds, then stop.

    linear_x: forward (+) / backward (-) in m/s
    linear_y: mecanum strafe — left (+) / right (-) in m/s
    """
    pub = _get_pub(log)
    msg = Twist()
    msg.linear.x = float(linear_x)
    msg.linear.y = float(linear_y)
    end = time.time() + float(duration)
    try:
        while time.time() < end and not rospy.is_shutdown():
            pub.publish(msg)
            time.sleep(0.1)
    finally:
        pub.publish(Twist())                 # ALWAYS stop, even on Ctrl-C
        time.sleep(0.1)
        pub.publish(Twist())


if __name__ == "__main__":
    import sys
    rospy.init_node("motion_test", anonymous=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stop"
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    if cmd == "forward":
        drive(config.FETCH_SPEED, secs)
    elif cmd == "backward":
        drive(-config.FETCH_SPEED, secs)
    elif cmd == "right":
        drive(0.0, secs, linear_y=-config.FETCH_SPEED)   # mecanum strafe
    elif cmd == "left":
        drive(0.0, secs, linear_y=config.FETCH_SPEED)
    else:
        stop()
    print("done")
