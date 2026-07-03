#!/usr/bin/env python3
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

import rospy

from protocol import LineSocket
from delivery import execute_delivery
import config


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
                result = execute_delivery(
                    command,
                    log=link.log,
                    detect=link.request_detection)
            except Exception as e:
                result = "ERROR: delivery crashed — %s" % e
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
    server.bind((config.SERVER_HOST, config.SERVER_PORT))
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
