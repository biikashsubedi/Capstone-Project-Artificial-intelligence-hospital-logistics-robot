# Robot-Side Delivery System

Runs on the JetAuto Pro. Copy this folder to `~/delivery/` on the robot.

| File | Purpose |
|---|---|
| `config.py` | All settings — layout, speeds, marker IDs, arm values |
| `chat_server.py` | Socket server the workstation connects to (port 5050) |
| `protocol.py` | Message framing and vision requests |
| `delivery.py` | The delivery sequence |
| `marker_nav.py` | Locates places by their ArUco markers |
| `motion.py` | Base movement (mecanum drive) |
| `waypoint.py` | Odometry-based movement (used when `NAV_MODE = "odom"`) |
| `navigator.py` | move_base navigation (used when `NAV_MODE = "map"`) |
| `arm_control.py` | Arm and gripper via the JetAuto action groups |
| `auto_pick.py` | Uses the robot's own `/automatic_pick` service when available |
| `grip_target.py` | Where the gripper closes, and grip verification |
| `depth_sense.py` | Distance measurement from the depth camera |
| `parser.py` | Validates `move medX to bedY` |
| `start_robot.sh` | Brings the robot up and checks everything |

## Start
```bash
bash ~/delivery/start_robot.sh
source ~/delivery/robot_env.sh
cd ~/delivery && python3 chat_server.py
```
Then connect from the workstation and press **INITIATE DEPLOYMENT**.

## Maintenance commands
Sent from the workstation (or any socket client):

| Command | Effect |
|---|---|
| `move medX to bedY` | Run a delivery |
| `grip show` | Report the gripper's target point |
| `grip up\|down\|left\|right [amount]` | Nudge that point |
| `grip reset` | Restore the default |
| `setgrip medX` | Set the point to where the medicine currently is |
| `align medX` | Drive up and line up, without picking |

## Diagnostic tools
Kept outside the deployed build in `dev/robot-tools/` on the workstation:
`arm_test.py`, `arm_probe.py`, `marker_test.py`, `depth_test.py`,
`waypoint_test.py`, `demo_setup.py`, `link_test_server.py`.
Copy one across only if you need to diagnose something.
