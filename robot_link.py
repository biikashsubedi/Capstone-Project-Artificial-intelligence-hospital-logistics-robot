"""
Mac-side socket link to the robot's chat_server.py.

Protocol (newline-framed UTF-8 text):
    Mac -> robot : "move med1 to bed1\n"
    robot -> Mac : "LOG <message>\n"      progress lines (any number)
                   "DETECT <med>\n"       ask the Mac to run the vision model;
                                          Mac replies "DETECT_RESULT FOUND <conf>\n"
                                          or         "DETECT_RESULT NOT_FOUND 0\n"
                   "OK: ...\n"            final result — ends the exchange
                   "ERROR: ...\n"         final result — ends the exchange

Blocking calls are meant to run on a background thread; main.py wraps them
with _run_async() so the Tkinter UI never freezes.
"""
import socket


class RobotLink:
    def __init__(self, host, port=5050, timeout=180):
        self.host = host
        self.port = port
        self.timeout = timeout       # max seconds to wait between robot messages
        self.sock = None
        self._buf = b""

    # ── connection ─────────────────────────────────────────────────────────
    def connect(self, connect_timeout=10):
        """Open the TCP connection. Raises on failure."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(connect_timeout)        # fail fast if robot unreachable
        s.connect((self.host, self.port))
        s.settimeout(self.timeout)           # generous wait during a delivery
        self.sock = s
        self._buf = b""

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None
        self._buf = b""

    # ── line framing ───────────────────────────────────────────────────────
    def _send_line(self, text):
        self.sock.sendall((text.rstrip("\n") + "\n").encode("utf-8"))

    def _recv_line(self):
        """Return one line (str, no newline). Raises on disconnect/timeout."""
        while b"\n" not in self._buf:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                # Fallback for legacy servers that reply without a newline:
                # if we already hold data, treat it as a complete message.
                if self._buf:
                    line, self._buf = self._buf, b""
                    return line.decode("utf-8", "replace").strip()
                raise
            if not chunk:
                if self._buf:                     # final unterminated message
                    line, self._buf = self._buf, b""
                    return line.decode("utf-8", "replace").strip()
                raise ConnectionError("Robot closed the connection")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line.decode("utf-8", "replace").strip()

    # ── command exchange ───────────────────────────────────────────────────
    def send_command(self, text, on_log=None, on_detect=None):
        """Send one command; process robot messages until OK/ERROR.

        on_log(message)      called for each "LOG ..." progress line.
        on_detect(med) -> (found: bool, confidence: float)
                             called when the robot asks for vision confirmation.
        Returns the final result string ("OK: ..." or "ERROR: ...").
        """
        if self.sock is None:
            raise ConnectionError("Not connected to robot")
        self._send_line(text)

        while True:
            line = self._recv_line()
            if not line:
                continue
            if line.startswith("LOG "):
                if on_log:
                    on_log(line[4:])
            elif line.startswith("DETECT "):
                med = line[7:].strip()
                found, conf = (False, 0.0)
                if on_detect:
                    try:
                        found, conf = on_detect(med)
                    except Exception:
                        found, conf = (False, 0.0)
                self._send_line("DETECT_RESULT %s %.4f"
                                % ("FOUND" if found else "NOT_FOUND", conf))
            else:
                # Final reply (OK:/ERROR:, or anything a legacy server sent).
                return line
