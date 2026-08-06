#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robot-side socket server. Receives a command from the Mac, runs the full
delivery sequence — streaming progress lines and delegating vision checks to
the Mac's YOLO model — then sends the final result.

Protocol: see protocol.py (newline-framed; LOG / DETECT / OK / ERROR).

Run on the robot AFTER the ROS stack is up (see RUNBOOK.md):
    source ~/jetauto_ws/devel/setup.bash
    python3 chat_server.py
"""
import socket
import time

import rospy

from protocol import LineSocket
import delivery
import config

# ── Command routing ────────────────────────────────────────────────────────
# "move medX to bedY" runs the delivery. The other commands are maintenance
# helpers (grip point adjustment and calibration).


def _arm_to_pick_pose(log):
    """Put the arm in the same pose it will be in during a real pick."""
    import arm_control
    try:
        home_action = arm_control.resolve_action(
            config.ACTION_HOME_CANDIDATES, log=log)
        if home_action in arm_control.list_action_groups():
            arm_control.run_action(home_action, log=log)
    except Exception as e:
        log("could not run the init action (%s) — continuing" % e)


def calibrate_grip(medicine, link):
    """PHASE 2 (run second) — measure where the box appears once it is sitting
    exactly where the gripper closed in phase 1.

    This follows Hiwonder's own documented method: let the GRIPPER define the
    grab spot, then look at where that spot falls in the camera image. No
    guessing, no trial and error.
    """
    import grip_target

    log = link.log
    log("CALIBRATION 2/2 — measuring where the box sits in the camera")
    _arm_to_pick_pose(log)

    xs, ys, areas = [], [], []
    for i in range(1, 6):
        found, conf, area, off_x, off_y = link.request_detection(medicine)
        if found:
            xs.append(off_x); ys.append(off_y); areas.append(area)
            log("  sample %d: x %+.3f  y %+.3f  size %.2f%%  (%.0f%%)"
                % (i, off_x, off_y, area * 100, conf * 100))
        else:
            log("  sample %d: not seen" % i)
        time.sleep(0.25)
    if not xs:
        return ("ERROR: could not see %s — turn DETECTION ON in the GUI and "
                "make sure the box is in the ARM camera's view" % medicine)

    x = sum(xs) / len(xs)
    y = sum(ys) / len(ys)
    saved = grip_target.save(x=x, y=y, area=sum(areas) / len(areas))
    px = int((x + 1.0) * 320)          # back to 640x480 pixels, for comparison
    py = int((y + 1.0) * 240)
    return ("OK: Grip point = x %+.3f, y %+.3f  (pixel %d,%d — Hiwonder's own "
            "value is 287,388). Calibration complete: put the box back and "
            "deploy." % (saved["x"], saved["y"], px, py))


def set_grip_point(medicine, link):
    """Move the red cross to wherever the medicine is right now.

    Run this with the box sitting exactly where the arm grabs it.
    Whatever the camera sees at that moment IS the grab point, so from then on
    "cross inside the box" genuinely means "the jaws will close on it".
    """
    import grip_target

    log = link.log
    log("SET GRIP POINT — the box must be where the arm actually grabs it")
    _arm_to_pick_pose(log)

    xs, ys = [], []
    for i in range(1, 6):
        r = link.request_detection(medicine)
        if r[0]:
            xs.append(r[3])
            ys.append(r[4])
            log("  sample %d: x %+.3f  y %+.3f" % (i, r[3], r[4]))
        else:
            log("  sample %d: %s not seen" % (i, medicine))
        time.sleep(0.25)

    if not xs:
        return ("ERROR: could not see %s in the ARM camera. Turn DETECTION on "
                "in the GUI and make sure the box is in view." % medicine)

    x = sum(xs) / len(xs)
    y = sum(ys) / len(ys)
    saved = grip_target.save(x=x, y=y)
    px = int((x + 1.0) * 320)
    py = int((y + 1.0) * 240)
    return ("OK: Grip point set to x %+.3f y %+.3f (pixel %d,%d). The red "
            "cross is now where the gripper grabs — picks will drive the "
            "medicine onto it." % (saved["x"], saved["y"], px, py))


def calibrate_depth(medicine, link):
    """Measure, in METRES, where the medicine sits when the arm can grab it.

    Put the box on the spot where the arm actually grabs it, then
    run this. The depth camera records the real distance and sideways offset,
    and every future pick drives until it measures the same numbers.
    """
    import depth_sense
    import grip_target

    log = link.log
    log("DEPTH CALIBRATION — box must be on the spot where the arm GRABS it")
    _arm_to_pick_pose(log)

    zs, xs = [], []
    for i in range(1, 6):
        found, conf, area, off_x, off_y = link.request_detection(medicine, "main")
        if not found:
            log("  sample %d: %s not visible in the main camera" % (i, medicine))
            time.sleep(0.3)
            continue
        pos = depth_sense.measure(off_x, off_y, log=log)
        if pos is None:
            time.sleep(0.3)
            continue
        x, _y, z = pos
        zs.append(z)
        xs.append(x)
        log("  sample %d: %.3f m ahead, %+.3f m sideways" % (i, z, x))
        time.sleep(0.3)

    if len(zs) < 2:
        return ("ERROR: could not measure %s with the depth camera. Check the "
                "MAIN camera can see it, DETECTION is ON, and the box is at "
                "least %.0f cm away." % (medicine, config.DEPTH_MIN_M * 100))

    z = sum(zs) / len(zs)
    x = sum(xs) / len(xs)
    saved = grip_target.save(grab_z=z, grab_x=x)
    return ("OK: Grab position measured — %.3f m ahead, %+.3f m sideways "
            "(from %d readings). Picks will now drive to exactly this."
            % (saved["grab_z"], saved["grab_x"], len(zs)))


def calibrate_empty(link):
    """PHASE 1 (run first) — the gripper shows you where it grabs.

    Runs the real pick action with NOTHING in front of the robot. Two things
    come out of it:
      * the gripper's 'closed on nothing' angle, used later to tell whether a
        pick actually caught the box;
      * a spot on the floor you can SEE — wherever the jaws closed. Put the
        medicine exactly there for phase 2.
    """
    import grip_target
    import arm_control

    log = link.log
    log("CALIBRATION 1/2 — WATCH THE GRIPPER. Nothing in front of the robot.")
    log("Note exactly where the jaws close — that is the grab spot.")
    try:
        pick_action = arm_control.resolve_action(
            config.ACTION_PICK_CANDIDATES, log=log)
        _arm_to_pick_pose(log)
        log("running '%s' on empty air..." % pick_action)
        arm_control.run_action(pick_action, log=log)
        time.sleep(0.5)
        empty = grip_target.read_gripper_position()
    except Exception as e:
        return ("ERROR: could not run the pick action (%s) — grip verification "
                "will stay off" % e)

    _arm_to_pick_pose(log)
    if empty is None:
        log("WARNING: could not read the gripper joint '%s' — the robot will "
            "not be able to verify picks" % config.GRIP_JOINT_NAME)
        return ("OK: Pick motion done (gripper angle unreadable). Now place the "
                "medicine EXACTLY where the jaws closed, then continue.")

    saved = grip_target.save(empty_pos=empty)
    return ("OK: Empty gripper reads %+.3f rad. Now place the medicine EXACTLY "
            "where the jaws closed, then continue." % saved["empty_pos"])


def adjust_grip(args, link):
    """Nudge the grab point without editing files.

        grip up      robot stops FURTHER BACK (box higher in the frame)
        grip down    robot drives CLOSER      (box lower in the frame)
        grip left / grip right                 sideways
        grip up 0.10                           bigger step
        grip show / grip reset
    """
    import grip_target

    tgt = grip_target.load()
    if not args or args[0] == "show":
        px = int((tgt["x"] + 1.0) * 320)
        py = int((tgt["y"] + 1.0) * 240)
        return ("OK: grip point x %+.3f y %+.3f  (pixel %d,%d)%s"
                % (tgt["x"], tgt["y"], px, py,
                   "" if tgt["calibrated"] else "  [defaults]"))

    if args[0] == "reset":
        grip_target.save(x=config.GRIP_TARGET_X, y=config.GRIP_TARGET_Y)
        return ("OK: grip point reset to x %+.3f y %+.3f"
                % (config.GRIP_TARGET_X, config.GRIP_TARGET_Y))

    step = config.GRIP_NUDGE
    if len(args) > 1:
        try:
            step = abs(float(args[1]))
        except ValueError:
            pass

    x, y = tgt["x"], tgt["y"]
    where = args[0]
    if where == "up":        # box higher in frame -> robot stops further back
        y -= step
    elif where == "down":    # box lower in frame  -> robot drives closer
        y += step
    elif where == "left":
        x -= step
    elif where == "right":
        x += step
    else:
        return ("ERROR: use  grip up | down | left | right [amount],  "
                "or  grip show | grip reset")

    x = max(-0.95, min(0.95, x))
    y = max(-0.95, min(0.95, y))
    saved = grip_target.save(x=x, y=y)
    link.log("grip point moved %s by %.2f" % (where, step))
    return ("OK: grip point now x %+.3f y %+.3f — %s"
            % (saved["x"], saved["y"],
               "robot will stop further back" if where == "up" else
               "robot will drive closer" if where == "down" else
               "shifted " + where))


def run_command(command, link):
    """Route a command line to the right mission."""
    text = command.strip().lower()

    # "align medX" — drive to the medicine and line up, then STOP without
    # picking. Lets you check the final position before committing to a grab.
    if text.startswith("align"):
        parts = text.split()
        med = parts[1] if len(parts) > 1 else config.VALID_MEDICINES[0]
        if med not in config.VALID_MEDICINES:
            return "ERROR: Unknown medicine '%s'" % med
        return delivery.align_only(med, log=link.log,
                                       detect=link.request_detection)

    # "grip up|down|left|right [amount]" — nudge the grab point live.
    # "grip show" / "grip reset" also available.
    if text.startswith("grip"):
        return adjust_grip(text.split()[1:], link)

    # "setgrip medX" — put the red cross exactly where the medicine is RIGHT
    # NOW. Use it with the box sitting where the arm actually grabs it.
    if text.startswith("setgrip"):
        parts = text.split()
        med = parts[1] if len(parts) > 1 else config.VALID_MEDICINES[0]
        if med not in config.VALID_MEDICINES:
            return "ERROR: Unknown medicine '%s'" % med
        return set_grip_point(med, link)

    if text.startswith("calibrate"):
        parts = text.split()
        arg = parts[1] if len(parts) > 1 else config.VALID_MEDICINES[0]
        if arg == "empty":
            return calibrate_empty(link)
        if arg == "depth":
            med = parts[2] if len(parts) > 2 else config.VALID_MEDICINES[0]
            return calibrate_depth(med, link)
        if arg not in config.VALID_MEDICINES:
            return "ERROR: Unknown medicine '%s'" % arg
        return calibrate_grip(arg, link)

    # "move medX to bedY" -> verify the medicine with the Mac's model, pick
    # it, carry it to the requested bed, place it, and return home.
    from parser import parse_command
    parsed, error = parse_command(command)
    if error:
        if text.startswith("move"):
            return error          # malformed "move ..." is a real mistake
        link.log("starting delivery")
        return delivery.run(log=link.log)
    return delivery.run(parsed["medicine"], parsed["destination"],
                            log=link.log, detect=link.request_detection)


def handle_client(conn, addr):
    print("[server] Mac connected: %s" % str(addr))
    link = LineSocket(conn)
    try:
        while not rospy.is_shutdown():
            command = link.recv_line()
            if command is None:
                print("[server] Mac disconnected")
                break
            if not command:
                continue
            print("[server] command: %s" % command)
            try:
                result = run_command(command, link)
            except Exception as e:
                result = "ERROR: Delivery failed — %s" % e
                rospy.logerr(result)
            print("[server] result: %s" % result)
            link.send_line(result)
    except Exception as e:
        print("[server] connection error: %s" % e)
    finally:
        conn.close()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((config.SERVER_HOST, config.SERVER_PORT))
    except socket.error as e:
        print("\nERROR: port %d is already in use (%s)." % (config.SERVER_PORT, e))
        print("An older server is still running. Stop it with:")
        print("    pkill -f chat_server.py")
        print("then start this again.\n")
        raise SystemExit(1)
    server.listen(1)
    print("[server] waiting for the Mac on port %d..." % config.SERVER_PORT)
    while not rospy.is_shutdown():
        conn, addr = server.accept()
        handle_client(conn, addr)   # after disconnect, wait for reconnect


if __name__ == "__main__":
    rospy.init_node("chat_server_node", anonymous=True)
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n[server] stopped.")
