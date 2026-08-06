#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Medicine delivery sequence.

On "move medX to bedY" the robot:
    1. locates the medicine table and drives to it
    2. confirms the requested medicine with the vision model
    3. lines the gripper up and picks it
    4. returns to the centre, then carries it to the requested bed
    5. places it, releases, and returns home

Arm motions use the JetAuto's own pre-recorded action groups.
"""
import json
import threading
import time

import rospy

import config
import motion
import waypoint
import arm_control


# ── fallback path: hand-recorded poses ─────────────────────────────────────
def load_poses():
    """Read hand-recorded demo poses (only used if action groups are absent)."""
    try:
        with open(config.DEMO_POSES_FILE, "r") as f:
            poses = json.load(f)
    except Exception as e:
        raise RuntimeError(
            "cannot read %s (%s) — record the arm positions first: "
            "the demo_setup tool in dev/robot-tools" % (config.DEMO_POSES_FILE, e))
    missing = [n for n in config.DEMO_POSE_NAMES if n not in poses]
    if missing:
        raise RuntimeError(
            "arm positions missing: %s — record them with the demo_setup "
            "tool in dev/robot-tools"
            % ", ".join(missing))
    if "gripper_open" not in poses or "gripper_closed" not in poses:
        raise RuntimeError(
            "gripper pulses not recorded — use the demo_setup tool in "
            "dev/robot-tools")
    return poses


def _go(poses, name, log, duration=None):
    duration = config.DEMO_ARM_SEC if duration is None else duration
    log("arm -> %s" % name)
    arm_control.send_arm_command(poses[name], duration)
    time.sleep(duration + 0.3)


def _grip(poses, closed, log):
    pulse = poses["gripper_closed"] if closed else poses["gripper_open"]
    log("gripper -> %s" % ("close" if closed else "open"))
    arm_control.send_arm_command([[config.GRIPPER_SERVO_ID, pulse]],
                                 config.DEMO_GRIP_PAUSE)
    time.sleep(config.DEMO_GRIP_PAUSE + 0.3)


def _pick_with_poses(log):
    poses = load_poses()
    _go(poses, "home", log)
    _grip(poses, False, log)
    _go(poses, "approach", log)
    _go(poses, "grip", log)
    _grip(poses, True, log)
    _go(poses, "lift", log)
    _go(poses, "home", log)


def _place_with_poses(log):
    poses = load_poses()
    _go(poses, "drop_right", log)
    _grip(poses, False, log)
    _go(poses, "home", log)


# ── the mission ────────────────────────────────────────────────────────────
def _confirm_medicine(medicine, log, detect):
    """Ask the Mac's YOLO model to verify the medicine. Returns confidence."""
    log("verifying %s with the vision model..." % medicine)
    for attempt in range(1, config.DEMO_VISION_ATTEMPTS + 1):
        result = detect(medicine)
        found = result[0]
        conf = result[1] if len(result) > 1 else 0.0
        if found:
            log("vision confirmed %s (%.0f%%)" % (medicine, conf * 100))
            return conf
        log("vision check %d/%d — %s not seen yet"
            % (attempt, config.DEMO_VISION_ATTEMPTS, medicine))
        time.sleep(config.DEMO_VISION_RETRY_SEC)
    return None


def _lock_onto_medicine(medicine, log, detect):
    """Move until the gripper's grab point sits INSIDE the medicine's box.

    The red cross drawn on the arm camera is where the jaws close. If that
    cross falls inside the detected medicine, the gripper is over the object
    and the grab will work. So the rule is simply:

        keep moving until the cross is inside the box, THEN pick.

    Sideways error is corrected by strafing, distance by driving forward or
    back. Returns True when locked on, False if the medicine was lost.
    """
    import grip_target
    tgt = grip_target.load()
    gx, gy = tgt["x"], tgt["y"]
    log("locking on: the grab point (%+.3f, %+.3f) must land inside %s"
        % (gx, gy, medicine))

    for attempt in range(1, config.LOCK_MAX_TRIES + 1):
        r = detect(medicine)
        if not r[0]:
            # A single missed frame is common (motion blur, model flicker), so
            # look again before deciding the medicine is really gone.
            for retry in range(config.LOCK_LOST_RETRIES):
                time.sleep(0.3)
                r = detect(medicine)
                if r[0]:
                    log("  (re-acquired %s)" % medicine)
                    break
            else:
                log("lost sight of %s while locking on" % medicine)
                return False
        cx = r[3] if len(r) > 3 else 0.0
        cy = r[4] if len(r) > 4 else 0.0
        if len(r) >= 9 and (r[7] > r[5] or r[8] > r[6]):
            x1, y1, x2, y2 = r[5], r[6], r[7], r[8]
        else:
            # The Mac didn't send box edges — it's running older code. Assume a
            # modest box around the centre so the check still means something.
            if attempt == 1:
                log("NOTE: the Mac isn't sending box edges (restart the GUI to "
                    "get the exact check) — using an estimated box")
            x1, y1, x2, y2 = cx - 0.12, cy - 0.12, cx + 0.12, cy + 0.12

        # Shrink the box slightly so we aim for a solid part of the medicine
        # rather than its very edge.
        mx = (x2 - x1) * config.LOCK_INSET
        my = (y2 - y1) * config.LOCK_INSET
        lined_up_x = (x1 + mx) <= gx <= (x2 - mx)
        lined_up_y = (y1 + my) <= gy <= (y2 - my)
        # By default only the sideways alignment decides — chasing the vertical
        # position drove the robot straight past the medicine.
        inside = lined_up_x and (lined_up_y or not config.LOCK_CHECK_DISTANCE)

        log("  CHECK %d/%d: red cross (%+.2f,%+.2f) vs %s [x %+.2f..%+.2f]%s"
            "  ->  %s"
            % (attempt, config.LOCK_MAX_TRIES, gx, gy, medicine, x1, x2,
               " [y %+.2f..%+.2f]" % (y1, y2) if config.LOCK_CHECK_DISTANCE
               else "",
               "LINED UP" if inside else "not yet - keep moving"))
        if inside:
            log("*** LOCKED ON: the red cross is on %s - safe to grab ***"
                % medicine)
            return True

        # Not inside: move so the box travels toward the cross.
        # err > 0 means the box sits right of / below the cross.
        err_x = cx - gx
        err_y = cy - gy
        if config.LOCK_CHECK_DISTANCE and abs(err_y) > abs(err_x):
            # Vertical error -> drive forward or back. Which way depends on the
            # arm camera's angle, so the sign comes from LOCK_Y_DIRECTION
            # (measured on the real robot, not assumed).
            sign = (config.LOCK_Y_DIRECTION if err_y > 0
                    else -config.LOCK_Y_DIRECTION)
            secs = max(config.LOCK_MIN_STEP,
                       min(config.LOCK_MAX_STEP, abs(err_y) * config.LOCK_GAIN))
            log("    %s sits %s the cross — driving %s %.2fs"
                % (medicine, "below" if err_y > 0 else "above",
                   "forward" if sign > 0 else "back", secs))
            motion.drive(sign * config.LOCK_SPEED, secs, log=log)
        else:
            # Sideways: follow the picture. Medicine on the left -> slide left,
            # on the right -> slide right, until the cross is on it.
            sign = (config.LOCK_X_DIRECTION if err_x > 0
                    else -config.LOCK_X_DIRECTION)
            secs = max(config.LOCK_MIN_STEP,
                       min(config.LOCK_MAX_STEP, abs(err_x) * config.LOCK_GAIN))
            log("    %s looks %s of the cross — sliding %s %.2fs"
                % (medicine, "right" if err_x > 0 else "left",
                   "left" if sign > 0 else "right", secs))
            motion.drive(0.0, secs, log=log,
                         linear_y=sign * config.LOCK_STRAFE_SPEED)
        time.sleep(config.LOCK_SETTLE)

    log("could not get the grab point onto %s after %d tries"
        % (medicine, config.LOCK_MAX_TRIES))
    return False


def _approach_by_depth(medicine, log, detect):
    """Measure the real distance to the medicine and drive exactly that far.

    Uses the depth camera rather than guessing from apparent size:
      1. find the medicine in the MAIN (depth-aligned) camera
      2. read its true position in metres
      3. drive the measured gap to the calibrated grab position
      4. re-measure and repeat until within a couple of centimetres

    Returns True if it got to the grab position, False if it could not
    measure (caller then falls back to the camera-only alignment).
    """
    import depth_sense
    import grip_target

    tgt = grip_target.load()
    want_z, want_x = tgt.get("grab_z"), tgt.get("grab_x")
    if want_z is None:
        log("no depth grab position recorded — run 'calibrate depth' with the "
            "box on the spot that works. Falling back to camera-only aiming.")
        return False

    log("depth approach: target %.3f m ahead, %+.3f m sideways"
        % (want_z, want_x or 0.0))
    for move in range(1, config.GRAB_MAX_MOVES + 1):
        found, conf, area, off_x, off_y = detect(medicine, "main")
        if not found:
            log("depth approach: %s not visible in the main camera" % medicine)
            return False
        pos = depth_sense.measure(off_x, off_y, log=log)
        if pos is None:
            log("depth approach: no usable depth reading")
            return False
        x, _y, z = pos
        err_z = z - want_z
        err_x = x - (want_x or 0.0)
        log("  measured %.3f m ahead (%+.3f m off target), %+.3f m sideways "
            "(%+.3f m off)" % (z, err_z, x, err_x))

        if abs(err_z) <= config.GRAB_TOL_Z and abs(err_x) <= config.GRAB_TOL_X:
            log("in the grab position (within %.0f cm) — ready to pick"
                % (config.GRAB_TOL_Z * 100))
            return True

        # Sideways first: turning up at the right distance but off to one side
        # is the failure we keep hitting.
        if abs(err_x) > config.GRAB_TOL_X:
            secs = min(2.0, abs(err_x) / config.GRAB_STRAFE_SPEED)
            log("  move %d: sliding %s %.0f cm"
                % (move, "right" if err_x > 0 else "left", abs(err_x) * 100))
            motion.drive(0.0, secs, log=log,
                         linear_y=(-1.0 if err_x > 0 else 1.0)
                         * config.GRAB_STRAFE_SPEED)
        else:
            secs = min(3.0, abs(err_z) / config.GRAB_APPROACH_SPEED)
            log("  move %d: driving %s %.0f cm"
                % (move, "forward" if err_z > 0 else "back", abs(err_z) * 100))
            motion.drive((1.0 if err_z > 0 else -1.0) * config.GRAB_APPROACH_SPEED,
                         secs, log=log)
        time.sleep(config.DEMO_ALIGN_SETTLE)

    log("depth approach: ran out of moves")
    return False


def _align_to_medicine(medicine, log, detect):
    """Move until the medicine sits ON THE GRIPPER'S GRAB POINT.

    The grab point is NOT the middle of the image — the arm camera looks at
    the scene from an angle. grip_target.load() gives the measured spot.
    Sideways error is fixed by strafing (mecanum), distance error by driving
    forward/back.
    """
    if not config.DEMO_ALIGN_MEDICINE:
        return True
    import grip_target
    tgt = grip_target.load()
    if not tgt["calibrated"]:
        log("using Hiwonder's factory grip point (from their automatic_pick.py "
            "for this same pick action) — CALIBRATE GRIP can refine it")
    log("aiming for the grip point x %+.3f, y %+.3f  (tolerance %.3f / %.3f)"
        % (tgt["x"], tgt["y"], config.GRIP_TOL_X, config.GRIP_TOL_Y))

    def _step(error, gain):
        """Seconds to move for this much error — proportional, then clamped."""
        secs = abs(error) * gain
        return max(config.GRIP_MIN_STEP, min(config.GRIP_MAX_STEP, secs))

    for attempt in range(1, config.DEMO_ALIGN_TRIES + 1):
        result = detect(medicine)
        if not result[0]:
            log("lost sight of %s while lining up" % medicine)
            return False
        off_x = result[3] if len(result) > 3 else 0.0
        off_y = result[4] if len(result) > 4 else 0.0
        err_x = off_x - tgt["x"]
        err_y = off_y - tgt["y"]

        need_x = abs(err_x) > config.GRIP_TOL_X
        need_y = config.GRIP_ALIGN_DISTANCE and abs(err_y) > config.GRIP_TOL_Y

        if not need_x and not need_y:
            log("lined up with %s (error x%+.3f y%+.3f) — ready to grip"
                % (medicine, err_x, err_y))
            return True

        # Fix distance first: getting the range right changes the sideways
        # error too, so correcting x first would just have to be redone.
        if need_y:
            # Mirrored camera: the drive direction comes from LOCK_Y_DIRECTION,
            # not from how the picture looks.
            sign = (config.LOCK_Y_DIRECTION if err_y > 0
                    else -config.LOCK_Y_DIRECTION)
            secs = _step(err_y, config.GRIP_GAIN_Y)
            log("  align %d/%d: %s sits %s the grab point (y %+.3f) — "
                "driving %s %.2fs"
                % (attempt, config.DEMO_ALIGN_TRIES, medicine,
                   "below" if err_y > 0 else "above", off_y,
                   "forward" if sign > 0 else "back", secs))
            motion.drive(sign * config.DEMO_ALIGN_FWD_SPEED, secs, log=log)
        else:
            sign = (config.LOCK_X_DIRECTION if err_x > 0
                    else -config.LOCK_X_DIRECTION)
            secs = _step(err_x, config.GRIP_GAIN_X)
            log("  align %d/%d: %s looks %s of the grab point (x %+.3f) — "
                "sliding %s %.2fs"
                % (attempt, config.DEMO_ALIGN_TRIES, medicine,
                   "right" if err_x > 0 else "left", off_x,
                   "left" if sign > 0 else "right", secs))
            motion.drive(0.0, secs, log=log,
                         linear_y=sign * config.DEMO_ALIGN_SPEED)
        time.sleep(config.DEMO_ALIGN_SETTLE)

    log("could not line %s up exactly — picking anyway (last error x%+.3f y%+.3f)"
        % (medicine, err_x, err_y))
    return True


def _travel(name, at, log):
    """Move to a named place using whichever navigation mode is configured."""
    if config.NAV_MODE == "marker":
        import marker_nav
        if not marker_nav.goto(name, log=log):
            raise RuntimeError(marker_nav.last_error
                               or "could not reach the %s marker" % name)
        return name
    if config.NAV_MODE == "map":
        import navigator
        if not navigator.go_to(name, log=log):
            raise RuntimeError("navigation to '%s' failed" % name)
        return name
    return waypoint.goto(name, at, log=log)


def align_only(medicine, log=print, detect=None):
    """Drive to the medicine, line the gripper up, then STOP — no picking.

    This is the debugging loop: run it, look at where the robot ended up, then
    try a manual pick. If that grabs the box, the aiming
    is right and a full delivery will work. If it misses, the numbers printed
    here tell you which way the grip target needs to move.
    """
    import grip_target
    try:
        log("aligning only — the robot will stop before picking")
        at = _travel("medicine", "home", log)
        conf = _confirm_medicine(medicine, log, detect)
        if conf is None:
            return "ERROR: Could not see %s at the medicine table" % medicine
        _align_to_medicine(medicine, log, detect)
        result = detect(medicine)
        tgt = grip_target.load()
        if result[0]:
            off_x = result[3] if len(result) > 3 else 0.0
            off_y = result[4] if len(result) > 4 else 0.0
            return ("OK: Stopped with %s at x %+.3f y %+.3f (target x %+.3f "
                    "y %+.3f). Try a manual pick from here "
                    "and see if it grabs."
                    % (medicine, off_x, off_y, tgt["x"], tgt["y"]))
        return "OK: Aligned, but %s is not visible now" % medicine
    except Exception as e:
        try:
            motion.stop(log=log)
        except Exception:
            pass
        return "ERROR: align failed — %s" % e


def _place_and_release(place_action, log):
    """Run the place action and open the gripper WHILE the arm is still out.

    The place_* action groups swing the arm over the drop point and then fold
    it back again, all inside one blocking call. Opening the gripper after
    that call returns is too late — the arm is already home and the medicine
    lands at the robot's feet. So the release is fired on a timer that goes
    off partway through the action, while the arm is still extended.

    Tune config.PLACE_RELEASE_AT_SEC if the box lets go too early or too late;
    the measured length of the action is logged to help you pick a value.
    """
    released = {"done": False}

    def release():
        try:
            log("releasing the box (arm is out over the bed)")
            arm_control.set_gripper(open_gripper=True, log=log)
            released["done"] = True
        except Exception as e:
            log("WARNING: could not open the gripper — %s" % e)

    timer = threading.Timer(config.PLACE_RELEASE_AT_SEC, release)
    timer.daemon = True
    timer.start()

    started = time.time()
    try:
        arm_control.run_action(place_action, log=log)
    finally:
        took = time.time() - started
        timer.cancel()

    log("'%s' took %.1f s; release was set for %.1f s"
        % (place_action, took, config.PLACE_RELEASE_AT_SEC))
    if not released["done"]:
        # The action finished before the timer fired — the arm has folded
        # back, so opening now would drop the box in the wrong place. Say so
        # rather than doing it silently.
        log("WARNING: the place action finished in %.1f s, before the %.1f s "
            "release. Lower PLACE_RELEASE_AT_SEC in config.py to about %.1f s."
            % (took, config.PLACE_RELEASE_AT_SEC, max(0.5, took * 0.5)))
        release()


def _return_home(at, log):
    """Come back to the centre after picking.

    Reversing the exact distance driven out is quicker than searching for the
    home marker, and it works even when that marker is behind the robot — the
    case where the search used to spin a full circle and fail.
    """
    if config.NAV_MODE == "marker" and config.RETURN_BY_RETRACE:
        import marker_nav
        if marker_nav.retrace("medicine", log=log):
            return "home"
        log("nothing to retrace — looking for the home marker instead")
    return _travel("home", at, log)


def run(medicine=None, destination=None, log=print, detect=None):
    """Execute the delivery.

    medicine    'med1'/'med2'/'med3' — verified by the Mac's model before picking
    destination 'bed1'/'bed2'/'bed3' — chooses place_left/center/right
    detect      callback into the Mac's YOLO model (None = skip verification)

    Returns an 'OK: ...' or 'ERROR: ...' string.
    """
    use_actions = arm_control.HAS_ACTION_GROUPS
    if use_actions:
        log("using the robot's built-in pick/place action groups")
    else:
        log("action groups unavailable (%s) — falling back to recorded poses"
            % arm_control.ACTION_GROUPS_ERROR)

    confidence = 0.0
    at = "home"                      # where the robot currently is
    try:
        # ── 1. READY ───────────────────────────────────────────────────────
        log("Step 1/7 — arm to ready position")
        if use_actions:
            pick_action = arm_control.resolve_action(
                config.ACTION_PICK_CANDIDATES, log=log)
            # Destination picks the place action: bed1/2/3 -> left/center/right
            place_candidates = list(config.ACTION_PLACE_CANDIDATES)
            if destination in config.DEMO_BED_ACTIONS:
                place_candidates.insert(0, config.DEMO_BED_ACTIONS[destination])
            place_action = arm_control.resolve_action(place_candidates, log=log)
            home_action = arm_control.resolve_action(
                config.ACTION_HOME_CANDIDATES, log=log)
            log("using action groups: init='%s', pick='%s', place='%s'"
                % (home_action, pick_action, place_action))
            # Prefer the robot's own init action group; fall back to the
            # ready pose from automatic_pick.py if it isn't installed.
            if home_action in arm_control.list_action_groups():
                arm_control.run_action(home_action, log=log)
            else:
                arm_control.ready_pose(log=log)
        else:
            place_action = None

        # ── 2. DRIVE TO THE MEDICINE TABLE ─────────────────────────────────
        log("Step 2/7 — driving to the medicine table")
        at = _travel("medicine", at, log)

        # ── 3. VERIFY WITH THE VISION MODEL ────────────────────────────────
        if medicine and detect is not None and config.DEMO_REQUIRE_VISION:
            log("Step 3/7 — verifying the medicine")
            confidence = _confirm_medicine(medicine, log, detect)
            if confidence is None:
                log("returning home empty-handed")
                _travel("home", at, log)
                return ("ERROR: Could not visually confirm %s — nothing picked"
                        % medicine)
        else:
            log("Step 3/7 — vision check skipped")

        # ── 4. GET THE GRAB POINT ONTO THE MEDICINE, THEN PICK ─────────────
        locked = None
        if config.LOCK_BEFORE_PICK and medicine and detect is not None:
            log("Step 4/7 — moving until the grab point is on %s" % medicine)
            locked = _lock_onto_medicine(medicine, log, detect)
            if not locked and config.LOCK_REQUIRED:
                log("never got the grab point onto the medicine — not picking")
                _travel("home", at, log)
                return ("ERROR: Could not line the gripper up with %s — "
                        "it would have grabbed empty air" % medicine)

        picked_by_robot = False
        if config.PICK_MODE == "hiwonder":
            import auto_pick
            log("Step 4/7 — handing the pick to the robot's own routine")
            picked_by_robot = auto_pick.pick(log=log)
            if not picked_by_robot:
                log("the robot's pick routine was unavailable — using the "
                    "action group directly")

        if not picked_by_robot:
            # Only skip the older aiming when lock-on actually succeeded.
            if locked is not True and medicine and detect is not None:
                if not _approach_by_depth(medicine, log, detect):
                    _align_to_medicine(medicine, log, detect)
            log("Step 4/7 — picking up the box")
            if use_actions:
                arm_control.run_action(pick_action, log=log)
            else:
                _pick_with_poses(log)

        # Did the fingers actually close on something?
        import grip_target
        holding = grip_target.is_holding(log=log)
        if holding is False:
            log("the gripper came up EMPTY — aborting instead of pretending")
            _travel("home", at, log)
            return ("ERROR: Gripper closed on nothing — %s was not picked up. "
                    "Re-run CALIBRATE GRIP, or move the box slightly."
                    % medicine)
        log("box picked up")

        # ── 5. BACK TO CENTRE, THEN OUT TO THE BED ─────────────────────────
        # Returning to the middle first means the bed markers are searched for
        # from a known spot, which is far more reliable than turning around
        # right next to the medicine table.
        bed = destination if destination in config.MARKER_IDS else "bed1"
        log("Step 5/7 — returning to centre, then carrying it to %s" % bed)
        at = _return_home(at, log)
        at = _travel(bed, at, log)

        # ── 6. DROP ────────────────────────────────────────────────────────
        log("Step 6/7 — placing the box at %s" % bed)
        if use_actions:
            _place_and_release(place_action, log)
        else:
            _place_with_poses(log)
        log("box released")

        # ── 7. RETURN HOME ─────────────────────────────────────────────────
        log("Step 7/7 — returning to home position")
        at = _travel("home", at, log)
        log("back home")

        if medicine and destination:
            return "OK: Delivered %s to %s (vision %.0f%%)" % (
                medicine, destination, (confidence or 0.0) * 100)
        return "OK: Picked the medicine, delivered it and returned home"

    except Exception as e:
        # Never leave the robot driving if something failed mid-sequence,
        # and try to bring it back to its home position.
        try:
            motion.stop(log=log)
        except Exception:
            pass
        try:
            if at != "home":
                log("error recovery — returning home")
                _travel("home", at, log)
        except Exception:
            pass
        return "ERROR: Delivery failed — %s" % e


if __name__ == "__main__":
    rospy.init_node("delivery", anonymous=True)
    print(run())
