#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Use the robot's OWN pick-and-place system instead of re-inventing it.

JetAuto ships with automatic_pick.py, which already does the hard part:
it watches the object through the arm camera, drives the base with PID
control until the object is at the exact spot the gripper reaches, aligns
to the object's angle, and then runs the 'navigation_pick' action group.
Hiwonder wrote and tuned it; it exposes three ROS services:

    /automatic_pick/pick     approach the object and grab it
    /automatic_pick/place    put it down
    /automatic_pick/cancel   stop

Progress is reported on the parameter /automatic_pick/status, which goes
    start_pick -> pick_finish        (and start_place -> place_finish)

START IT FIRST (it is not running by default):
    roslaunch jetauto_example automatic_pick.launch

Then test by hand:
    python3 auto_pick.py pick
    python3 auto_pick.py place
"""
import time

import rospy

import config

try:
    from std_srvs.srv import Trigger
    HAS_TRIGGER = True
except ImportError:
    HAS_TRIGGER = False

PICK_SERVICE = "/automatic_pick/pick"
PLACE_SERVICE = "/automatic_pick/place"
CANCEL_SERVICE = "/automatic_pick/cancel"
STATUS_PARAM = "/automatic_pick/status"


def available(log=print):
    """Is the robot's automatic pick node running?"""
    if not HAS_TRIGGER:
        log("std_srvs not importable — source ~/jetauto_ws/devel/setup.bash")
        return False
    try:
        rospy.wait_for_service(PICK_SERVICE, timeout=2.0)
        return True
    except Exception:
        log("%s not available — start the robot's own pick node first:"
            % PICK_SERVICE)
        log("    roslaunch jetauto_example automatic_pick.launch")
        return False


def _call(service, log):
    proxy = rospy.ServiceProxy(service, Trigger)
    resp = proxy()
    ok = getattr(resp, "success", True)
    log("called %s -> %s" % (service, "ok" if ok else "refused"))
    return ok


def _wait_for(done_status, log, timeout):
    """Poll /automatic_pick/status until it reaches done_status."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline and not rospy.is_shutdown():
        try:
            status = rospy.get_param(STATUS_PARAM, "")
        except Exception:
            status = ""
        if status != last:
            log("  status: %s" % (status or "(none)"))
            last = status
        if status == done_status:
            return True
        time.sleep(0.3)
    log("timed out after %ds waiting for '%s' (last status: %s)"
        % (timeout, done_status, last))
    return False


def pick(log=print, timeout=None):
    """Let the robot find, approach and grab the object in front of it."""
    timeout = timeout or config.AUTO_PICK_TIMEOUT
    if not available(log=log):
        return False
    log("handing over to the robot's own pick routine "
        "(it will drive itself into position)...")
    if not _call(PICK_SERVICE, log):
        return False
    ok = _wait_for("pick_finish", log, timeout)
    if ok:
        log("the robot reports the pick finished")
    else:
        cancel(log=log)
    return ok


def place(log=print, timeout=None):
    """Let the robot put the object down using its own place routine."""
    timeout = timeout or config.AUTO_PICK_TIMEOUT
    if not available(log=log):
        return False
    if not _call(PLACE_SERVICE, log):
        return False
    ok = _wait_for("place_finish", log, timeout)
    if not ok:
        cancel(log=log)
    return ok


def cancel(log=print):
    try:
        _call(CANCEL_SERVICE, log)
    except Exception as e:
        log("cancel failed: %s" % e)


if __name__ == "__main__":
    import sys
    rospy.init_node("auto_pick_test", anonymous=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pick"
    if cmd == "pick":
        print("OK" if pick() else "FAILED")
    elif cmd == "place":
        print("OK" if place() else "FAILED")
    elif cmd == "cancel":
        cancel()
    else:
        print(__doc__)
