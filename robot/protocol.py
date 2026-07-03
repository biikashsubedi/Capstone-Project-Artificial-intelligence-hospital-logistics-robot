#!/usr/bin/env python3
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

    def request_detection(self, med):
        """Ask the Mac to run its vision model. Returns (found, confidence)."""
        self.send_line("DETECT %s" % med)
        reply = self.recv_line()
        if reply is None:
            raise ConnectionError("Mac disconnected during detection request")
        parts = reply.split()
        # Expected: DETECT_RESULT FOUND|NOT_FOUND <confidence>
        if len(parts) >= 2 and parts[0] == "DETECT_RESULT":
            found = parts[1] == "FOUND"
            try:
                conf = float(parts[2]) if len(parts) > 2 else 0.0
            except ValueError:
                conf = 0.0
            return found, conf
        print("[robot] WARNING: unexpected detect reply: %r" % reply)
        return False, 0.0
