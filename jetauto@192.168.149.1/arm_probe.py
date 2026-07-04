#!/usr/bin/env python3
"""
Diagnostic: prints everything about this robot's arm/servo interfaces.
Run it once on the robot and paste the output back if the arm doesn't move —
it tells us the exact topic names and joint names to put in config.py.

    source ~/jetauto_ws/devel/setup.bash
    python3 arm_probe.py
"""
import subprocess

import rospy


def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main():
    rospy.init_node("arm_probe", anonymous=True)

    section("1. Servo / arm / joint related TOPICS (published + subscribed)")
    try:
        master = rospy.get_master()
        pubs, subs, _srvs = master.getSystemState()[2]
        seen = set()
        for kind, lst in [("pub", pubs), ("sub", subs)]:
            for topic, nodes in lst:
                low = topic.lower()
                if any(k in low for k in ["servo", "arm", "joint", "gripper"]):
                    if (kind, topic) not in seen:
                        seen.add((kind, topic))
                        print("  [%s] %s   <- %s" % (kind, topic, ",".join(nodes)))
    except Exception as e:
        print("  (failed: %s)" % e)

    section("2. One /joint_states sample (names + positions)")
    try:
        from sensor_msgs.msg import JointState
        topics = [t for t, _ in rospy.get_published_topics()]
        js = next((t for t in topics if t.endswith("joint_states")), None)
        if js:
            msg = rospy.wait_for_message(js, JointState, timeout=3)
            for n, p in zip(msg.name, msg.position):
                print("  %-20s %+.3f rad" % (n, p))
        else:
            print("  no joint_states topic found")
    except Exception as e:
        print("  (failed: %s)" % e)

    section("3. hiwonder / jetauto python packages importable?")
    for mod in ["hiwonder_servo_msgs.msg", "jetauto_sdk",
                "jetauto_sdk.bus_servo_control", "hiwonder_servo_controllers"]:
        try:
            __import__(mod)
            print("  OK      %s" % mod)
        except Exception as e:
            print("  MISSING %s  (%s)" % (mod, str(e)[:50]))

    section("4. Example scripts shipped with the robot (arm-related)")
    for pattern in ["~/jetauto_ws/src/jetauto_example/scripts",
                    "~/jetauto_ws/src"]:
        try:
            out = subprocess.check_output(
                "ls -R %s 2>/dev/null | grep -iE 'arm|servo|gripper|pick' | head -25"
                % pattern, shell=True).decode()
            if out.strip():
                print("  in %s:" % pattern)
                print("    " + "\n    ".join(out.strip().splitlines()))
                break
        except Exception:
            pass

    print("\nDone. Paste this whole output back to Claude if the arm "
          "needs different settings.")


if __name__ == "__main__":
    main()
