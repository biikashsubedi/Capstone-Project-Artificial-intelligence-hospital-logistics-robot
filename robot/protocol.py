#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Newline-framed socket protocol helpers (robot side).

Wire format (UTF-8 text, one message per line):
    Mac -> robot : "move med1 to bed1"
    robot -> Mac : "LOG <message>"              progress, any number of lines
                   "DETECT <med>"               ask Mac to run the vision model
    Mac -> robot : "DETECT_RESULT FOUND 0.93"   (reply to DETECT)
                   "DETECT_RESULT NOT_FOUND 0"
    robot -> Mac : "OK: ..." | "ERROR: ..."     final line, ends the exchange
"""


class LineSocket:
    """Wraps a connected socket with newline framing."""

    def __init__(self, conn):
        self.conn = conn
        self._buf = b""

    def send_line(self, text):
        self.conn.sendall((text.rstrip("\n") + "\n").encode("utf-8"))

    def recv_line(self):
        """Return one line (str, stripped). None if the peer disconnected."""
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

    # ── high-level helpers used by chat_server ─────────────────────────────
    def log(self, message):
        """Stream a progress line to the Mac (also prints locally)."""
        print("[robot] %s" % message)
        try:
            self.send_line("LOG %s" % message)
        except Exception:
            pass  # Mac gone — delivery code will notice on the final send

    def request_detection(self, med, camera="arm"):
        """Ask the Mac to run its vision model.

        Returns (found, conf, area, off_x, off_y, x1, y1, x2, y2):
          area           how much of the frame the box fills (bigger = closer)
          off_x/off_y    the box's centre, -1.0 .. +1.0, 0 = middle of frame
          x1,y1,x2,y2    the box's EDGES in the same units, so the robot can
                         check whether the gripper's grab point falls inside
                         the medicine before closing the jaws.
        """
        self.send_line("DETECT %s %s" % (med, camera))
        reply = self.recv_line()
        if reply is None:
            raise ConnectionError("Mac disconnected during detection request")
        parts = reply.split()
        # DETECT_RESULT FOUND|NOT_FOUND <conf> [<area>] [<off_x>] [<off_y>]
        if len(parts) >= 2 and parts[0] == "DETECT_RESULT":
            found = parts[1] == "FOUND"

            def _num(idx):
                try:
                    return float(parts[idx]) if len(parts) > idx else 0.0
                except ValueError:
                    return 0.0

            return (found, _num(2), _num(3), _num(4), _num(5),
                    _num(6), _num(7), _num(8), _num(9))
        print("[robot] WARNING: unexpected detect reply: %r" % reply)
        return (False,) + (0.0,) * 8
