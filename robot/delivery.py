#!/usr/bin/env python3
"""
Full delivery sequence — ties navigation + vision + arm together.

execute_delivery("move med1 to bed1", log, detect):
    shelf -> aim camera -> confirm medicine (via Mac's vision model)
          -> pick -> bed -> drop -> "OK: Delivered ..."

`log(msg)`      streams progress to the Mac's telemetry panel.
`detect(med)`   returns (found: bool, confidence: float). In the live system
                this asks the MAC to run best.pt on the arm camera; in tests
                it's a stub.

Returns a single result string ("OK: ..." or "ERROR: ...").
"""
import time

from parser import parse_command
from navigator import go_to
import arm_control
import config


def execute_delivery(command_text, log=print, detect=None):
    parsed, error = parse_command(command_text)
    if error:
        return error

    medicine = parsed["medicine"]        # e.g. "med1"
    destination = parsed["destination"]  # e.g. "bed1"

    # 1) Navigate to the medicine shelf
    log("Step 1/5 — navigating to medicine shelf")
    if not go_to("medicine_shelf", log=log):
        return "ERROR: Could not reach medicine shelf"

    # 2) Confirm the requested medicine with the vision model (on the Mac)
    log("Step 2/5 — verifying %s with vision model" % medicine)
    confidence = 0.0
    if detect is None:
        log("WARNING: no vision link — skipping visual confirmation")
        found = True
    else:
        arm_control.look(log=log)        # aim the arm camera at the shelf
        found = False
        for attempt in range(1, config.DETECT_ATTEMPTS + 1):
            log("vision check %d/%d for %s..."
                % (attempt, config.DETECT_ATTEMPTS, medicine))
            found, confidence = detect(medicine)
            if found:
                log("vision confirmed %s (%.0f%%)" % (medicine, confidence * 100))
                break
            time.sleep(config.DETECT_RETRY_DELAY_SEC)
        if not found:
            return ("ERROR: Could not visually confirm %s on the shelf"
                    % medicine)

    # 3) Pick it up
    log("Step 3/5 — picking %s" % medicine)
    try:
        arm_control.pick(medicine, log=log)
    except Exception as e:
        return "ERROR: Arm pick failed — %s" % e

    # 4) Navigate to the destination bed
    log("Step 4/5 — navigating to %s" % destination)
    if not go_to(destination, log=log):
        return "ERROR: Could not reach %s (item still held)" % destination

    # 5) Drop it
    log("Step 5/5 — dropping at %s" % destination)
    try:
        arm_control.drop(log=log)
    except Exception as e:
        return "ERROR: Arm drop failed — %s" % e

    return "OK: Delivered %s to %s (vision %.0f%%)" % (
        medicine, destination, confidence * 100)


if __name__ == "__main__":
    import sys
    import rospy
    rospy.init_node("delivery_node", anonymous=True)
    if len(sys.argv) < 2:
        print('Usage: python3 delivery.py "move med1 to bed1"')
        sys.exit(1)
    print(execute_delivery(" ".join(sys.argv[1:])))
