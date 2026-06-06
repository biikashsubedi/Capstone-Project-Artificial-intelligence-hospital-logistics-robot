# 🏥 AI-Powered Hospital Supply Delivery Robot

![Project Status](https://img.shields.io/badge/Status-Active_Development-success)
![Platform](https://img.shields.io/badge/Hardware-NVIDIA_Jetson-76B900)
![ROS](https://img.shields.io/badge/Middleware-ROS_1-22314E)
![Vision](https://img.shields.io/badge/Vision-YOLOv8--Nano-00FFFF)

> **An autonomous hardware-software prototype engineered to reduce nursing fatigue by automating the internal transport of clinical supplies.**

<img width="979" height="729" alt="Screenshot 2026-06-05 at 10 50 01 PM" src="https://github.com/user-attachments/assets/fe59fd65-6417-4290-894c-0426d38e0f1b" />


## 📖 Executive Summary
Currently, nursing staff spend up to 35% of their active shifts on internal logistics, contributing to workplace burnout. This capstone project introduces an autonomous mobile robot (AMR) capable of navigating a clinical environment, identifying specific medications via edge AI, executing mechanical retrieval, and logging real-time delivery states to a remote cloud dashboard.

## 🏗️ 4-Layer System Architecture
The system is decoupled into four clean operational layers to ensure modularity and fault isolation:

1. **Perception Layer:** LiDAR spatial mapping, wheel odometry, HD camera feeds, and a multi-threaded voice-command workstation console.
2. **Intelligence Layer:** NVIDIA Jetson running ROS `move_base` for dynamic obstacle avoidance, paired with a custom-trained **YOLOv8-Nano** model for high-speed edge object detection.
3. **Actuation Layer:** Omnidirectional Mecanum drive motors and a 6-Degree-of-Freedom (6DOF) robotic arm driven by Inverse Kinematics (IK).
4. **Cloud & Communication Layer:** Offline-first SQLite/CSV edge caching that synchronizes asynchronously via **FastAPI** to a remote **Supabase PostgreSQL** cluster.

## 💻 Tech Stack
* **Robotics Middleware:** ROS (Robot Operating System), Python (`rospy`)
* **Computer Vision:** OpenCV, YOLOv8-Nano (PyTorch / TensorRT)
* **Hardware Platform:** Hiwonder JetAuto Pro, NVIDIA Jetson Orin Nano, 2D LiDAR
* **Cloud Backend:** FastAPI, Supabase (PostgreSQL)
* **Workstation UI:** Python Tkinter (macOS Native), `SpeechRecognition`

## 📂 Key Repository Structure
*Highlighting the Separation of Concerns (SoC) for the Layer 1 Control Workstation:*
```text
├── /workstation_ui/
│   ├── main_ui.py          # Tkinter interface and main event loop
│   ├── voice_engine.py     # Multi-threaded Google Speech-to-Text processor
│   └── file_handler.py        # Edge-cache logic for offline-first data logging
├── /ros_workspace/         # Custom ROS nodes for navigation and IK arm control
├── /vision_pipeline/       # Roboflow dataset scripts and YOLOv8 training weights
└── /cloud_api/             # FastAPI backend gateway
