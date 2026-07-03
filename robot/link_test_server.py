#!/usr/bin/env python3
"""
Dependency-free LINK + VISION TEST server for the robot.

Proves the Mac <-> robot socket AND the Mac's live vision model work together,
BEFORE navigation/arm are set up. No ROS, no extra packages — just Python 3.

What it does per command ("move med1 to bed1"):
  1. Streams a few LOG progress lines (they appear in the Mac's telemetry).
  2. Sends "DETECT med1" — the Mac runs best.pt on the LIVE arm camera and
     replies FOUND/NOT_FOUND with confidence.  <- hold the medicine in front
     of the arm camera to make this succeed!
  3. Replies OK (if found) or ERROR (if not).

Run on the robot:
    python3 link_test_server.py
"""
import socket
import time

HOST = "0.0.0.0"
PORT = 5050


class LineSocket:
    def __init__(self, conn):
        self.conn = conn
        self._buf = b""

    def send_line(self, text):
        self.conn.sendall((text.rstrip("\n") + "\n").encode("utf-8"))

    def recv_line(self):
        while b"\n" not in self._buf:
            chunk = self.conn.recv(4096)
            if not chunk:
                if self._buf:
                    line, self._buf = self._buf, b""
                    return line.decode("utf-8", "replace").strip()
                return None
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line.decode("utf-8", "replace").strip()


def handle(link):
    while True:
        cmd = link.recv_line()
        if cmd is None:
            print("[link-test] Mac disconnected")
            return
        print("[link-test] received: %s" % cmd)
        parts = cmd.split()
        if not (len(parts) == 4 and parts[0] == "move" and parts[2] == "to"):
            link.send_line("ERROR: Invalid format. Use: move medX to bedY")
            continue
        med, bed = parts[1], parts[3]

        link.send_line("LOG [test] pretending to navigate to medicine shelf...")
        time.sleep(1.5)
        link.send_line("LOG [test] at shelf — asking Mac to verify %s "
                       "(show it to the ARM camera!)" % med)

        found, conf = False, 0.0
        for attempt in range(1, 6):
            link.send_line("DETECT %s" % med)
            reply = link.recv_line()
            print("[link-test] detect reply: %s" % reply)
            if reply is None:
                return
            p = reply.split()
            if len(p) >= 2 and p[0] == "DETECT_RESULT" and p[1] == "FOUND":
                found = True
                conf = float(p[2]) if len(p) > 2 else 0.0
                break
            link.send_line("LOG [test] not seen yet (attempt %d/5) — "
                           "hold %s in front of the arm camera" % (attempt, med))
            time.sleep(1.5)

        if found:
            link.send_line("LOG [test] pretending to pick and deliver to %s..." % bed)
            time.sleep(1.5)
            link.send_line("OK: Delivered %s to %s (vision %.0f%%)"
                           % (med, bed, conf * 100))
        else:
            link.send_line("ERROR: Could not visually confirm %s on shelf" % med)


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(1)
    print("[link-test] listening on port %d — connect from the Mac GUI" % PORT)
    while True:
        conn, addr = srv.accept()
        print("[link-test] Mac connected from %s" % str(addr))
        try:
            handle(LineSocket(conn))
        except Exception as e:
            print("[link-test] error: %s" % e)
        finally:
            conn.close()


if __name__ == "__main__":
    main()
