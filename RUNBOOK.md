# AI Nurse Robot — Complete Runbook

Everything needed to go from here to a working live demo, in order.
Code is COMPLETE on both sides; what remains are the **hardware calibration
steps (A–C)** that can only be done with the robot present.

---

## System overview

```
        MAC (workstation)                      ROBOT (JetAuto Pro)
┌────────────────────────────┐   WiFi   ┌────────────────────────────┐
│ main.py (GUI)              │◄────────►│ chat_server.py (port 5050) │
│  · camera feeds (8080)     │  socket  │  · delivery.py sequence    │
│  · best.pt YOLO detection  │          │  · navigator.py (move_base)│
│  · answers DETECT requests │          │  · arm_control.py (servos) │
│  · telemetry + notification│          │  · asks Mac for vision     │
└────────────────────────────┘          └────────────────────────────┘
```

Delivery flow: GUI sends `move med1 to bed1` → robot navigates to shelf →
aims arm camera → asks Mac "DETECT med1" → Mac runs best.pt on live arm-cam
frame → robot picks → navigates to bed → drops → `OK: Delivered ...` →
GUI logs telemetry CSV + macOS notification.

## Environments

- **Mac**: conda env `yolo` — `conda activate yolo` (has ultralytics, Pillow,
  tkinter). Run everything from `~/Desktop/robotProject`.
- **Robot**: SSH `jetauto@192.168.149.1`, always
  `source ~/jetauto_ws/devel/setup.bash` first. Python 3.6-safe code, no
  extra pip packages required for the delivery pipeline.

## One-time: copy code to the robot

```bash
# Mac, on ROBOT WiFi (HW-2DC16182):
cd ~/Desktop/robotProject
scp -r robot/ jetauto@192.168.149.1:~/delivery/
```

---

# PART 1 — Hardware calibration (do once, robot present)

## A. Build the map (guidebook Ch. 3)

```bash
# SSH 1: roscore              (if not already running)
# SSH 2: robot bringup        (skip if the standard app service provides it)
sudo systemctl stop start_app_node.service
roslaunch jetauto_slam slam.launch slam_methods:=gmapping
# SSH 3: drive slowly with keyboard
rosrun teleop_twist_keyboard teleop_twist_keyboard.py   # or Lab-5 controller
# RViz (NoMachine or Mac with ROS): watch /map fill in
# When complete:
rosrun map_server map_saver -f ~/room_map map:=/map     # or /jetauto_1/map
```
Checklist: walls continuous, shelf + 3 beds visible, floor white. Back up
`room_map.pgm/.yaml` to the Mac.

## B. Record the four locations (guidebook Ch. 4)

```bash
roslaunch jetauto_navigation navigation.launch map:=$HOME/room_map.yaml
# RViz: "2D Pose Estimate" on the robot's true start pose, then
# "2D Nav Goal" to drive it in front of the SHELF; when stopped:
rostopic echo /amcl_pose -n 1        # (or /jetauto_1/amcl_pose)
```
Write down x, y and convert orientation z,w → angle = 2·atan2(z, w).
Repeat for bed1, bed2, bed3. Then on the robot:

```bash
cp ~/delivery/locations.template.json ~/locations.json
nano ~/locations.json                # fill in the four x/y/angle sets
python3 ~/delivery/navigator.py medicine_shelf   # test each location 3×
python3 ~/delivery/navigator.py bed1             # ... bed2, bed3
```

## C. Record arm positions (guidebook Ch. 7)

```bash
cd ~/delivery
python3 arm_probe.py        # sanity check: servo topics + joint names
python3 arm_recorder.py     # interactive: 13 poses, follow the prompts
# Tune gripper pulses in config.py (GRIPPER_OPEN/CLOSED_PULSE), then test:
python3 arm_control.py gripper close
python3 arm_control.py gripper open
python3 arm_control.py med1          # full pick — robot AT the shelf, med1 placed
python3 arm_control.py drop
```
Each pick must succeed 5/5 before moving on (guidebook 7.9).
If anything looks wrong, paste `arm_probe.py` output back to Claude.

---

# PART 2 — Running the system (every session)

## On the robot (SSH, robot WiFi)

```bash
sudo systemctl stop start_app_node.service          # stop the phone-app service
source ~/jetauto_ws/devel/setup.bash
# T1: navigation stack with your map
roslaunch jetauto_navigation navigation.launch map:=$HOME/room_map.yaml
# T2: camera web streams (GUI feeds)
rosrun web_video_server web_video_server            # port 8080
# T3: localize once in RViz ("2D Pose Estimate" at the start mark), then:
cd ~/delivery && python3 chat_server.py             # waits for the Mac
```

## On the Mac (robot WiFi)

```bash
cd ~/Desktop/robotProject
conda activate yolo
python main.py
```

1. **CONNECT TO ROBOT** — status green, both cameras live.
2. **DETECTION: ON** — live YOLO boxes on the arm camera (first load ~5 s).
3. Pick medicine + bed → **INITIATE DEPLOYMENT**.
4. Watch step-by-step 🤖 logs stream in Telemetry; macOS notification +
   report.csv row on completion.

## Rehearsal without nav/arm (works TODAY)

On the robot: `python3 ~/delivery/link_test_server.py`
Then connect from the GUI and deploy — the robot fakes navigation but the
**vision check is real**: hold the medicine in front of the arm camera and
the delivery completes with the true confidence. Great for demo practice
and for proving Milestone-3 integration.

## Mock everything (no robot at all)

```bash
conda activate yolo && python mock_robot.py          # terminal 1
conda activate yolo && ROBOT_HOST=127.0.0.1 python main.py   # terminal 2
```

---

# Troubleshooting

| Symptom | Fix |
|---|---|
| Connection refused | No server on robot — start `chat_server.py` (or link_test) |
| Cameras "no signal" | `rosrun web_video_server web_video_server` on robot |
| Wrong WiFi | Robot hotspot `HW-2DC16182`; Mac IP must be 192.168.149.x |
| move_base not available | Navigation launch not running, or namespace — navigator auto-detects `/move_base` and `/jetauto_1/move_base` |
| Robot at wrong spot | Re-do "2D Pose Estimate"; robot must start on its tape mark |
| Detection misses | Lighting! Same lamp position as training photos; DETECTION: ON to watch live confidence; lower `confidence` in config/config_data.json "model" |
| Arm doesn't move | `source ~/jetauto_ws/devel/setup.bash` first; run `arm_probe.py`, paste output to Claude |
| GUI frozen feel | It never blocks — check Telemetry for the error line |

# File map

| Mac | Robot (`~/delivery/`) |
|---|---|
| main.py — GUI | chat_server.py — socket server |
| robot_link.py — protocol client | protocol.py — framing + DETECT |
| camera_view.py — MJPEG viewer | delivery.py — 5-step sequence |
| medicine_detector.py — best.pt | navigator.py — move_base goals |
| mock_robot.py — full simulator | arm_control.py — bus-servo pick/drop |
| config/config_data.json — settings | arm_recorder.py / arm_probe.py — tools |
| best.pt — trained YOLO model | config.py — all robot settings |
| report.csv — telemetry log | parser.py — command validation |
