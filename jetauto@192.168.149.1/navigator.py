#!/usr/bin/env python3
"""
Autonomous navigation. go_to(location_name) drives the robot to a saved
location from locations.json using move_base (the same system you use by
clicking "2D Nav Goal" in RViz), driven from code via actionlib.

Locations are recorded once (RUNBOOK step B) into ~/locations.json with keys:
    medicine_shelf, bed1, bed2, bed3

The move_base action name is AUTO-DETECTED: some JetAuto setups run it at
/move_base, namespaced ones at /jetauto_1/move_base.
"""
import json
import math
import sys

import rospy
import actionlib
from actionlib_msgs.msg import GoalStatus
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import Quaternion

import config

_client = None          # cached action client (creating one is expensive)
_client_name = None


def load_locations():
    with open(config.LOCATIONS_FILE, "r") as f:
        return json.load(f)


def angle_to_quaternion(angle):
    """Convert a flat-floor yaw angle (radians) into a ROS quaternion."""
    return Quaternion(x=0.0, y=0.0,
                      z=math.sin(angle / 2.0),
                      w=math.cos(angle / 2.0))


def _find_move_base_name():
    """Return the move_base action name that actually exists on this robot."""
    try:
        published = [t for t, _ in rospy.get_published_topics()]
    except Exception:
        published = []
    for ns in config.NAMESPACE_CANDIDATES:
        name = (ns + "/move_base").lstrip("/") if ns else "move_base"
        if "/" + name + "/status" in published:
            return name
    return None


def _get_client(log):
    """Connect (once) to the move_base action server. Returns client or None."""
    global _client, _client_name
    if _client is not None:
        return _client
    name = _find_move_base_name()
    if name is None:
        # Not visible in published topics — try the plain name anyway.
        name = "move_base"
        log("move_base not found in topic list; trying '%s' directly" % name)
    client = actionlib.SimpleActionClient(name, MoveBaseAction)
    log("connecting to move_base action server '%s'..." % name)
    if not client.wait_for_server(rospy.Duration(config.NAV_SERVER_WAIT_SEC)):
        log("ERROR: move_base server '%s' not available. Is the navigation "
            "launch running? (roslaunch jetauto_navigation navigation.launch "
            "map:=... )" % name)
        return None
    _client, _client_name = client, name
    return _client


def go_to(location_name, log=print):
    """Drive to a named saved location. Returns True on arrival, else False."""
    try:
        locations = load_locations()
    except Exception as e:
        log("ERROR: cannot read %s (%s). Record locations first (RUNBOOK "
            "step B)." % (config.LOCATIONS_FILE, e))
        return False
    if location_name not in locations:
        log("ERROR: unknown location '%s' (have: %s)"
            % (location_name, ", ".join(sorted(locations))))
        return False
    loc = locations[location_name]

    client = _get_client(log)
    if client is None:
        return False

    goal = MoveBaseGoal()
    goal.target_pose.header.frame_id = "map"
    goal.target_pose.header.stamp = rospy.Time.now()
    goal.target_pose.pose.position.x = float(loc["x"])
    goal.target_pose.pose.position.y = float(loc["y"])
    goal.target_pose.pose.orientation = angle_to_quaternion(float(loc["angle"]))

    log("navigating to '%s' (x=%.2f, y=%.2f, angle=%.2f)"
        % (location_name, loc["x"], loc["y"], loc["angle"]))
    client.send_goal(goal)

    finished = client.wait_for_result(rospy.Duration(config.NAV_TIMEOUT_SEC))
    if not finished:
        client.cancel_goal()
        log("ERROR: timed out (%ds) reaching '%s'"
            % (config.NAV_TIMEOUT_SEC, location_name))
        return False

    if client.get_state() == GoalStatus.SUCCEEDED:
        log("arrived at '%s'" % location_name)
        return True
    log("ERROR: failed to reach '%s' (move_base state=%s)"
        % (location_name, client.get_state()))
    return False


if __name__ == "__main__":
    rospy.init_node("navigator_node", anonymous=True)
    if len(sys.argv) < 2:
        print("Usage: python3 navigator.py <medicine_shelf|bed1|bed2|bed3>")
        sys.exit(1)
    ok = go_to(sys.argv[1])
    sys.exit(0 if ok else 1)
