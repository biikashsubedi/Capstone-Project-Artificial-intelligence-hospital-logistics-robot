#!/usr/bin/env python3
"""
Mock robot — stands in for the real robot so you can rehearse the workstation UI
(and the Milestone demo) WITHOUT hardware. It provides BOTH things the GUI talks to:

  1. Socket command server (port 5050) — same protocol as robot/chat_server.py:
     receives "move medX to bedY", waits, replies "OK: Delivered ... (vision NN%)".
  2. MJPEG video server (port 8080) — same shape as web_video_server: serves a
     synthetic animated feed at /stream?topic=... so the GUI's camera tiles show
     live moving video.

Run:
    python3 mock_robot.py
    ROBOT_HOST=127.0.0.1 python3 main.py
Then in the UI: CONNECT -> watch the two camera tiles -> run a delivery.
"""
import io
import math
import random
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

CMD_PORT = 5050
VIDEO_PORT = 8080
DELAY_SEC = 4  # pretend a delivery takes this long

try:
    from PIL import Image, ImageDraw
    PIL_OK = True
except ImportError:
    PIL_OK = False


# ── Socket command server (mirrors robot/chat_server.py protocol) ──────────────
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


def handle_cmd_client(conn, addr):
    print("[mock] Mac connected:", addr)
    link = LineSocket(conn)
    while True:
        cmd = link.recv_line()
        if cmd is None:
            print("[mock] Mac disconnected")
            break
        print("[mock] received:", cmd)
        parts = cmd.split()
        if not (len(parts) == 4 and parts[0] == "move" and parts[2] == "to"):
            link.send_line("ERROR: Invalid format. Use: move medX to bedY")
            continue
        med, bed = parts[1], parts[3]

        link.send_line("LOG Step 1/5 — navigating to medicine shelf")
        time.sleep(DELAY_SEC / 4.0)
        link.send_line("LOG Step 2/5 — verifying %s with vision model" % med)
        link.send_line("DETECT %s" % med)
        reply = link.recv_line()
        print("[mock] detect reply:", reply)
        if reply is None:
            break
        p = reply.split()
        found = len(p) >= 2 and p[0] == "DETECT_RESULT" and p[1] == "FOUND"
        conf = float(p[2]) if len(p) > 2 and found else random.uniform(0.88, 0.99)
        if found:
            link.send_line("LOG vision confirmed %s (%.0f%%)" % (med, conf * 100))
        else:
            link.send_line("LOG vision did not see %s — mock proceeds anyway"
                           % med)
        link.send_line("LOG Step 3/5 — picking %s" % med)
        time.sleep(DELAY_SEC / 4.0)
        link.send_line("LOG Step 4/5 — navigating to %s" % bed)
        time.sleep(DELAY_SEC / 4.0)
        link.send_line("LOG Step 5/5 — dropping at %s" % bed)
        time.sleep(DELAY_SEC / 4.0)
        reply = "OK: Delivered %s to %s (vision %.0f%%)" % (med, bed, conf * 100)
        print("[mock] reply:", reply)
        link.send_line(reply)
    conn.close()


def command_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", CMD_PORT))
    srv.listen(1)
    print("[mock] command server on 127.0.0.1:%d" % CMD_PORT)
    while True:
        conn, addr = srv.accept()
        handle_cmd_client(conn, addr)


# ── MJPEG video server (mirrors web_video_server) ──────────────────────────────
def make_frame(label, t, bg):
    img = Image.new("RGB", (320, 240), bg)
    d = ImageDraw.Draw(img)
    d.text((10, 10), label, fill="white")
    d.text((10, 28), time.strftime("%H:%M:%S"), fill="white")
    x = int(160 + 120 * math.sin(t))                      # bouncing marker
    d.rectangle([x - 16, 170, x + 16, 202], outline="white", width=3)
    d.text((110, 220), "MOCK FEED", fill=(150, 150, 150))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70)
    return buf.getvalue()


class VideoHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        topic = parse_qs(urlparse(self.path).query).get("topic", [""])[0]
        is_arm = "usb" in topic or "arm" in topic
        label = ("ARM CAM " if is_arm else "MAIN CAM ") + topic
        bg = (24, 32, 64) if is_arm else (20, 52, 42)
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        t = 0.0
        try:
            while True:
                frame = make_frame(label, t, bg)
                self.wfile.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n"
                    % len(frame) + frame + b"\r\n")
                t += 0.18
                time.sleep(0.08)
        except (BrokenPipeError, ConnectionResetError):
            return


def video_server():
    srv = ThreadingHTTPServer(("127.0.0.1", VIDEO_PORT), VideoHandler)
    print("[mock] video server on 127.0.0.1:%d" % VIDEO_PORT)
    srv.serve_forever()


def main():
    if PIL_OK:
        threading.Thread(target=video_server, daemon=True).start()
    else:
        print("[mock] Pillow not installed — video disabled (cameras show 'no signal')")
    try:
        command_server()
    except KeyboardInterrupt:
        print("\n[mock] stopped")


if __name__ == "__main__":
    main()
