# Robot-Side Delivery System

These scripts run **on the JetAuto Pro** (copy this folder to `~/delivery/`).
Full instructions live in the project root: **[RUNBOOK.md](../RUNBOOK.md)**.

| File | What it does |
|---|---|
| `config.py` | ALL settings — edit this first |
| `chat_server.py` | Socket server the Mac GUI talks to (port 5050) |
| `protocol.py` | Newline framing + LOG/DETECT message helpers |
| `delivery.py` | 5-step sequence: shelf → verify → pick → bed → drop |
| `navigator.py` | move_base goals from ~/locations.json (auto-detects namespace) |
| `arm_control.py` | Hiwonder bus-servo pick/drop from ~/arm_positions.json |
| `arm_recorder.py` | Interactive tool — records the 13 arm poses (run once) |
| `arm_probe.py` | Diagnostic — prints servo topics/joints if arm misbehaves |
| `parser.py` | Validates `move medX to bedY` |
| `link_test_server.py` | No-ROS test server: real socket + real Mac vision, fake motion |
| `detector.py` | OPTIONAL on-robot Roboflow fallback (not used in main flow) |
| `*.template.json` | Copy to `~/locations.json` / `~/arm_positions.json`, fill in |

Vision note: medicine detection runs **on the Mac** (best.pt over the live
arm-camera stream). The robot asks the Mac over the socket (`DETECT med1`)
and gets FOUND/NOT_FOUND back — nothing to install on the Jetson.

Quick start (after calibration steps A–C in the RUNBOOK):
```bash
source ~/jetauto_ws/devel/setup.bash
roslaunch jetauto_navigation navigation.launch map:=$HOME/room_map.yaml
rosrun web_video_server web_video_server
cd ~/delivery && python3 chat_server.py
```
