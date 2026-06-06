import json
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox

# ── Optional dependencies ──────────────────────────────────────────────────────
try:
    from tkmacosx import Button as MacButton

    USE_MAC_BTN = True
except ImportError:
    USE_MAC_BTN = False

try:
    import file_handler

    HAS_FILE_HANDLER = True
except ImportError:
    HAS_FILE_HANDLER = False

try:
    from voice_engine import VoiceController

    HAS_VOICE = True
except ImportError:
    HAS_VOICE = False

# ── Config loading ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent


def load_json(filename):
    path = BASE_DIR / "config" / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Colour tokens ──────────────────────────────────────────────────────────────
C = {
    "bg": "#f8fafd",
    "sidebar": "#ffffff",
    "right": "#f0f4fa",
    "topbar": "#ffffff",
    "topbar_bd": "#dde3ef",
    "brand": "#1a56db",
    "brand_hover": "#1745c0",
    "green": "#065f46",
    "green_bg": "#d1fae5",
    "purple": "#6d28d9",
    "purple_hov": "#7c3aed",
    "red": "#dc2626",
    "red_hover": "#b91c1c",
    "text": "#0f1726",
    "text2": "#4a5568",
    "muted": "#8a98b0",
    "border": "#dde3ef",
    "box_bg": "#f0f4ff",
    "box_bd": "#c7d9f9",
    "term_bg": "#0d1117",
    "term_fg": "#8b949e",
    "term_grn": "#3fb950",
    "term_blu": "#58a6ff",
    "term_ylw": "#d29922",
}

FONT_HEADER = ("Helvetica", 11, "bold")
FONT_BODY = ("Helvetica", 11)
FONT_SMALL = ("Helvetica", 9)
FONT_MONO = ("Courier", 11)

MISSION_DELAY_MS = 5000  # simulated robot work time in milliseconds

# Loading animation frames shown on the deploy button while robot is busy
LOADING_FRAMES = [
    "Working  [=     ]",
    "Working  [==    ]",
    "Working  [===   ]",
    "Working  [====  ]",
    "Working  [===== ]",
    "Working  [======]",
    "Working  [===== ]",
    "Working  [====  ]",
    "Working  [===   ]",
    "Working  [==    ]",
]
LOADING_INTERVAL_MS = 180  # ms between each animation frame


# ── Button factory ─────────────────────────────────────────────────────────────
def make_btn(parent, text, command, bg, fg="white", hover=None, font=None,
             padx=10, pady=8):
    font = font or FONT_HEADER
    hover_bg = hover or bg
    if USE_MAC_BTN:
        b = MacButton(
            parent, text=text, command=command,
            bg=bg, fg=fg, font=font,
            padx=padx, pady=pady, borderless=1, cursor="hand2",
        )
        b.bind("<Enter>", lambda e: b.config(bg=hover_bg))
        b.bind("<Leave>", lambda e: b.config(bg=bg))
    else:
        b = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg, font=font,
            padx=padx, pady=pady, relief="flat", cursor="hand2",
            activebackground=hover_bg, activeforeground=fg, bd=0,
        )
    return b


def make_box(parent, bg=None, bd_color=None):
    """Return a framed box matching the Voice Override card style."""
    bg = bg or C["box_bg"]
    bd_color = bd_color or C["box_bd"]
    return tk.Frame(parent, bg=bg,
                    highlightbackground=bd_color, highlightthickness=1)


# ── Main application ───────────────────────────────────────────────────────────
class CapstoneWorkstationUI:
    def __init__(self, root):
        self.root = root

        try:
            self._lbl = load_json("config_data.json")
            self._payload = load_json("data.json")
        except FileNotFoundError as e:
            messagebox.showerror("Config Error", "Missing config file:\n{}".format(e))
            root.destroy()
            return

        self.root.title(self._lbl["app"]["title"])
        self.root.geometry("980x700")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, True)

        self._is_connected = False
        self._is_busy = False
        self._loading_job = None  # after() id for the loading animation
        self._loading_frame = 0  # current animation frame index

        self.voice = None
        self._voice_active = False
        if HAS_VOICE:
            self.voice = VoiceController(
                on_log=self.safe_log,
                on_transcription=self.handle_transcription,
                on_error=self.handle_voice_error,
                on_stop=self.handle_voice_stop,
            )

        self._build_topbar()
        self._build_main()
        self._tick_clock()

    # ── Top bar ────────────────────────────────────────────────────────────────
    def _build_topbar(self):
        bar = tk.Frame(
            self.root, bg=C["topbar"], height=52, bd=0,
            highlightbackground=C["topbar_bd"], highlightthickness=1,
        )
        bar.pack(side=tk.TOP, fill=tk.X)
        bar.pack_propagate(False)

        logo = tk.Canvas(bar, width=28, height=28, bg=C["brand"],
                         highlightthickness=0)
        logo.place(x=16, y=12)
        logo.create_text(14, 14, text="o", fill="white", font=("Helvetica", 14))

        tk.Label(bar, text=self._lbl["app"]["logo"],
                 bg=C["topbar"], font=("Helvetica", 13, "bold"),
                 fg=C["text"]).place(x=52, y=10)
        tk.Label(bar, text=self._lbl["app"]["subtitle"],
                 bg=C["topbar"], font=FONT_SMALL,
                 fg=C["muted"]).place(x=52, y=30)

        tk.Label(bar, text=" {} ".format(self._lbl["app"]["version"]),
                 bg="#e8f0fe", fg=C["brand"],
                 font=("Courier", 9, "bold"), relief="flat",
                 padx=4).place(relx=1.0, x=-160, y=16)

        self._clock_var = tk.StringVar()
        tk.Label(bar, textvariable=self._clock_var,
                 bg="#f0f4fa", fg=C["text2"],
                 font=("Courier", 10), padx=8, pady=3,
                 relief="flat").place(relx=1.0, x=-16, y=14, anchor="ne")

    def _tick_clock(self):
        self._clock_var.set(datetime.now().strftime("  %Y-%m-%d  %H:%M:%S  "))
        self.root.after(1000, self._tick_clock)

    # ── Main layout ────────────────────────────────────────────────────────────
    def _build_main(self):
        outer = tk.Frame(self.root, bg=C["bg"])
        outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        self._build_sidebar(outer)
        self._build_right(outer)

    # ── Sidebar ────────────────────────────────────────────────────────────────
    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=C["sidebar"], width=320,
                      highlightbackground=C["border"], highlightthickness=1)
        sb.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sb.pack_propagate(False)

        # Scrollable inner area
        canvas = tk.Canvas(sb, bg=C["sidebar"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(sb, orient="vertical", command=canvas.yview)
        self._sb_inner = tk.Frame(canvas, bg=C["sidebar"])

        self._sb_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self._sb_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        inner = tk.Frame(self._sb_inner, bg=C["sidebar"])
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # ── Box 1: System Connection ───────────────────────────────────────
        conn_box = make_box(inner)
        conn_box.pack(fill=tk.X, pady=(0, 10))

        conn_inner = tk.Frame(conn_box, bg=C["box_bg"])
        conn_inner.pack(fill=tk.X, padx=12, pady=12)

        self._section_label(conn_inner,
                            self._lbl["connection"]["section"],
                            bg=C["box_bg"])

        status_row = tk.Frame(conn_inner, bg=C["box_bg"])
        status_row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(status_row, text=self._lbl["connection"]["robot_status"],
                 bg=C["box_bg"], font=FONT_BODY,
                 fg=C["text2"]).pack(side=tk.LEFT)
        self._status_txt = tk.Label(
            status_row, text=self._lbl["connection"]["status_offline"],
            bg=C["box_bg"], font=("Courier", 9, "bold"), fg=C["muted"])
        self._status_txt.pack(side=tk.RIGHT, padx=(0, 4))
        self._status_dot = tk.Label(
            status_row, text="●", bg=C["box_bg"],
            font=("Helvetica", 10), fg=C["muted"])
        self._status_dot.pack(side=tk.RIGHT)

        # Single toggle button: Connect / Disconnect
        self._connect_btn = make_btn(
            conn_inner,
            text=self._lbl["connection"]["btn_connect"],
            command=self._toggle_connection,
            bg=C["brand"], hover=C["brand_hover"],
            font=("Helvetica", 12, "bold"),
        )
        self._connect_btn.pack(fill=tk.X)

        # ── Box 2: Payload Config (hidden until connected) ─────────────────
        self._payload_box = make_box(inner)
        # packed in _show_connected_controls

        payload_inner = tk.Frame(self._payload_box, bg=C["box_bg"])
        payload_inner.pack(fill=tk.X, padx=12, pady=12)

        self._section_label(payload_inner,
                            self._lbl["payload"]["section"],
                            bg=C["box_bg"])

        tk.Label(payload_inner,
                 text=self._lbl["payload"]["color_label"],
                 bg=C["box_bg"], font=("Courier", 9),
                 fg=C["muted"]).pack(anchor=tk.W, pady=(0, 4))

        med_labels = [m["label"] for m in self._payload["medicines"]]
        self._color_var = tk.StringVar()
        self._color_dd = ttk.Combobox(
            payload_inner, textvariable=self._color_var,
            values=med_labels, state="readonly", width=30, font=FONT_BODY)
        self._color_dd.current(0)
        self._color_dd.pack(anchor=tk.W, pady=(0, 12))
        self._color_dd.bind("<<ComboboxSelected>>",
                            lambda e: self.safe_log(
                                "Payload updated: {}".format(self._color_var.get()), "info"))

        tk.Label(payload_inner,
                 text=self._lbl["payload"]["dest_label"],
                 bg=C["box_bg"], font=("Courier", 9),
                 fg=C["muted"]).pack(anchor=tk.W, pady=(0, 4))

        bay_labels = [b["label"] for b in self._payload["bays"]]
        self._dest_var = tk.StringVar()
        self._dest_dd = ttk.Combobox(
            payload_inner, textvariable=self._dest_var,
            values=bay_labels, state="readonly", width=30, font=FONT_BODY)
        self._dest_dd.current(0)
        self._dest_dd.pack(anchor=tk.W)
        self._dest_dd.bind("<<ComboboxSelected>>",
                           lambda e: self.safe_log(
                               "Destination updated: {}".format(self._dest_var.get()), "info"))

        # ── Box 3: Deploy (hidden until connected) ─────────────────────────
        self._deploy_box = make_box(inner)
        # packed in _show_connected_controls

        deploy_inner = tk.Frame(self._deploy_box, bg=C["box_bg"])
        deploy_inner.pack(fill=tk.X, padx=12, pady=12)

        # Deploy button — text replaced with loading animation when busy
        self._deploy_btn = make_btn(
            deploy_inner,
            text=self._lbl["deploy"]["btn_deploy"],
            command=self._execute_command,
            bg=C["brand"], hover=C["brand_hover"],
            font=("Helvetica", 12, "bold"),
        )
        self._deploy_btn.pack(fill=tk.X, pady=(0, 8))

        self._mission_lbl = tk.Label(
            deploy_inner,
            text=self._lbl["deploy"]["mission_idle"],
            bg=C["box_bg"], font=("Courier", 9), fg=C["muted"],
        )
        self._mission_lbl.pack(anchor=tk.W)

        # ── Box 4: Voice Override (hidden until connected) ─────────────────
        self._voice_box = make_box(inner)
        # packed in _show_connected_controls

        voice_inner = tk.Frame(self._voice_box, bg=C["box_bg"])
        voice_inner.pack(fill=tk.X, padx=12, pady=12)

        self._section_label(voice_inner,
                            self._lbl["voice"]["section"],
                            bg=C["box_bg"])

        self._voice_btn = make_btn(
            voice_inner,
            text=self._lbl["voice"]["btn_activate"],
            command=self._toggle_mic,
            bg=C["purple"], hover=C["purple_hov"],
            font=("Helvetica", 11, "bold"),
        )
        self._voice_btn.pack(fill=tk.X, pady=(0, 6))

        self._voice_status = tk.StringVar(
            value=self._lbl["voice"]["status_standby"])
        tk.Label(voice_inner, textvariable=self._voice_status,
                 bg=C["box_bg"], font=("Helvetica", 10, "italic"),
                 fg=C["muted"]).pack(anchor=tk.W)

    # ── Right panel ────────────────────────────────────────────────────────────
    def _build_right(self, parent):
        rp = tk.Frame(parent, bg=C["right"],
                      highlightbackground=C["border"], highlightthickness=1)
        rp.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(rp, bg=C["right"])
        inner.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        hdr = tk.Frame(inner, bg=C["right"])
        hdr.pack(fill=tk.X, pady=(0, 12))
        tk.Label(hdr, text=self._lbl["telemetry"]["title"],
                 bg=C["right"], font=("Helvetica", 13, "bold"),
                 fg=C["text"]).pack(side=tk.LEFT)
        tk.Label(hdr,
                 text=" {} ".format(self._lbl["telemetry"]["badge_connected"]),
                 bg=C["green_bg"], fg=C["green"],
                 font=("Courier", 9, "bold"),
                 padx=6, pady=2).pack(side=tk.RIGHT, padx=(4, 0))
        tk.Label(hdr,
                 text=" {} ".format(self._lbl["telemetry"]["badge_idle"]),
                 bg="#f0f4fa", fg=C["muted"],
                 font=("Courier", 9, "bold"),
                 padx=6, pady=2).pack(side=tk.RIGHT)

        self._terminal = tk.Text(
            inner, bg=C["term_bg"], fg=C["term_fg"],
            font=FONT_MONO, wrap=tk.WORD, relief="flat", bd=0,
            insertbackground=C["term_grn"],
            selectbackground="#21262d",
            state=tk.DISABLED,
        )
        self._terminal.pack(fill=tk.BOTH, expand=True)

        self._terminal.tag_config("ts", foreground="#6e7681")
        self._terminal.tag_config("default", foreground=C["term_fg"])
        self._terminal.tag_config("success", foreground=C["term_grn"])
        self._terminal.tag_config("info", foreground=C["term_blu"])
        self._terminal.tag_config("warn", foreground=C["term_ylw"])

        footer = tk.Frame(inner, bg=C["right"])
        footer.pack(fill=tk.X, pady=(10, 0))
        tk.Label(footer, text=self._lbl["telemetry"]["footer"],
                 bg=C["right"], font=("Courier", 9),
                 fg=C["muted"]).pack(side=tk.LEFT)
        self._event_var = tk.StringVar(value="0 events")
        tk.Label(footer, textvariable=self._event_var,
                 bg="#e8edf5", fg=C["text2"],
                 font=("Courier", 9), padx=8, pady=2).pack(side=tk.RIGHT)

        self._event_count = 0
        self.safe_log(self._lbl["telemetry"]["log_startup"])

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _section_label(self, parent, text, bg=None):
        bg = bg or C["box_bg"]
        row = tk.Frame(parent, bg=bg)
        row.pack(fill=tk.X, pady=(0, 10))
        tk.Frame(row, bg=C["brand"], width=3, height=14).pack(
            side=tk.LEFT, padx=(0, 8))
        tk.Label(row, text=text, bg=bg,
                 font=("Courier", 9, "bold"), fg=C["muted"]).pack(side=tk.LEFT)

    def safe_log(self, message, tag="default"):
        self.root.after(0, self._insert_log, message, tag)

    def _insert_log(self, message, tag="default"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._terminal.config(state=tk.NORMAL)
        self._terminal.insert(tk.END, "[{}] ".format(ts), "ts")
        self._terminal.insert(tk.END, message + "\n", tag)
        self._terminal.see(tk.END)
        self._terminal.config(state=tk.DISABLED)
        self._event_count += 1
        self._event_var.set("{} events".format(self._event_count))

    def _show_connected_controls(self):
        self._payload_box.pack(fill=tk.X, pady=(0, 10))
        self._deploy_box.pack(fill=tk.X, pady=(0, 10))
        self._voice_box.pack(fill=tk.X, pady=(0, 10))

    def _hide_connected_controls(self):
        self._payload_box.pack_forget()
        self._deploy_box.pack_forget()
        self._voice_box.pack_forget()

    # ── Loading animation ──────────────────────────────────────────────────────
    def _start_loading(self):
        """Start the deploy button loading animation."""
        self._loading_frame = 0
        self._animate_loading()

    def _animate_loading(self):
        """Cycle through LOADING_FRAMES on the deploy button."""
        if not self._is_busy:
            return
        frame_text = LOADING_FRAMES[self._loading_frame % len(LOADING_FRAMES)]
        self._deploy_btn.config(text=frame_text)
        self._loading_frame += 1
        self._loading_job = self.root.after(
            LOADING_INTERVAL_MS, self._animate_loading)

    def _stop_loading(self):
        """Stop animation and restore the deploy button label."""
        if self._loading_job is not None:
            self.root.after_cancel(self._loading_job)
            self._loading_job = None
        self._deploy_btn.config(text=self._lbl["deploy"]["btn_deploy"])

    def _set_busy(self, busy):
        """Lock or unlock controls; start/stop the loading animation."""
        self._is_busy = busy
        dd_state = "disabled" if busy else "readonly"
        self._color_dd.config(state=dd_state)
        self._dest_dd.config(state=dd_state)
        self._connect_btn.config(
            state=tk.DISABLED if busy else tk.NORMAL)
        if busy:
            # Disable deploy button but keep it visible with animation
            self._deploy_btn.config(state=tk.DISABLED, cursor="watch")
            self._start_loading()
        else:
            self._stop_loading()
            self._deploy_btn.config(state=tk.NORMAL, cursor="hand2")

    # ── Connection toggle ──────────────────────────────────────────────────────
    def _toggle_connection(self):
        if not self._is_connected:
            self._do_connect()
        else:
            self._do_disconnect()

    def _do_connect(self):
        self.safe_log(self._lbl["connection"]["log_connecting"], "info")
        self._connect_btn.config(state=tk.DISABLED,
                                 text="Connecting...")

        def _finish():
            self._is_connected = True
            self.safe_log(
                "✓ " + self._lbl["connection"]["log_connected"], "success")
            self._status_dot.config(fg="#10ac84")
            self._status_txt.config(
                text=self._lbl["connection"]["status_connected"],
                fg="#10ac84")
            # Switch button to Disconnect (red)
            self._connect_btn.config(
                text=self._lbl["connection"]["btn_disconnect"],
                bg=C["red"],
                state=tk.NORMAL)
            if USE_MAC_BTN:
                self._connect_btn.bind(
                    "<Enter>", lambda e: self._connect_btn.config(bg=C["red_hover"]))
                self._connect_btn.bind(
                    "<Leave>", lambda e: self._connect_btn.config(bg=C["red"]))
            else:
                self._connect_btn.config(activebackground=C["red_hover"])
            self._show_connected_controls()

        self.root.after(700, _finish)

    def _do_disconnect(self):
        if self._is_busy:
            self.safe_log("⚠ " + self._lbl["deploy"]["log_busy"], "warn")
            return
        self._is_connected = False
        self._hide_connected_controls()
        self._status_dot.config(fg=C["muted"])
        self._status_txt.config(
            text=self._lbl["connection"]["status_offline"],
            fg=C["muted"])
        # Switch button back to Connect (blue)
        self._connect_btn.config(
            text=self._lbl["connection"]["btn_connect"],
            bg=C["brand"],
            state=tk.NORMAL)
        if USE_MAC_BTN:
            self._connect_btn.bind(
                "<Enter>", lambda e: self._connect_btn.config(bg=C["brand_hover"]))
            self._connect_btn.bind(
                "<Leave>", lambda e: self._connect_btn.config(bg=C["brand"]))
        else:
            self._connect_btn.config(activebackground=C["brand_hover"])
        self.safe_log(self._lbl["connection"]["log_disconnected"], "warn")

    # ── Deployment ─────────────────────────────────────────────────────────────
    def _execute_command(self):
        if not self._is_connected:
            self.safe_log("⚠ " + self._lbl["deploy"]["log_no_connect"], "warn")
            return
        if self._is_busy:
            self.safe_log("⚠ " + self._lbl["deploy"]["log_busy"], "warn")
            return

        color = self._color_var.get().strip()
        dest = self._dest_var.get().strip()
        if not color or not dest:
            self.safe_log("⚠ " + self._lbl["deploy"]["log_incomplete"], "warn")
            return

        self._set_busy(True)
        self._mission_lbl.config(
            text=self._lbl["deploy"]["mission_active"], fg="#10ac84")

        self.safe_log(self._lbl["deploy"]["log_initiating"], "warn")
        self.root.after(400, lambda: self.safe_log(
            "Payload: {}".format(color), "info"))
        self.root.after(800, lambda: self.safe_log(
            "Destination: {}".format(dest), "info"))
        self.root.after(1400, lambda: self.safe_log(
            "Robot departing bay. Navigation mode: autonomous.", "info"))

        self.root.after(MISSION_DELAY_MS, self._mission_complete, color, dest)

    def _mission_complete(self, color, dest):
        self._set_busy(False)
        self.safe_log("✓ " + self._lbl["deploy"]["log_executing"], "success")
        self._mission_lbl.config(
            text=self._lbl["deploy"]["mission_done"], fg=C["muted"])

        if HAS_FILE_HANDLER:
            try:
                saved = file_handler.save_to_csv(
                    "Fetch {} to {}".format(color, dest), dest, color)
                self.safe_log("✓ Telemetry cached: {}\n".format(saved), "success")
            except Exception as e:
                messagebox.showerror("System Error",
                                     "Failed to cache telemetry:\n{}".format(e))

    # ── Voice ──────────────────────────────────────────────────────────────────
    def _toggle_mic(self):
        if not HAS_VOICE or self.voice is None:
            self.safe_log("⚠ " + self._lbl["voice"]["log_unavailable"], "warn")
            return
        if not self._voice_active:
            if self.voice.start():
                self._voice_active = True
                self._voice_btn.config(
                    bg=C["red"],
                    text=self._lbl["voice"]["btn_stop"])
                self._voice_status.set(self._lbl["voice"]["status_listening"])
                self.safe_log(self._lbl["voice"]["log_activated"], "info")
        else:
            self.voice.stop(manual=True)

    def handle_voice_stop(self, manual):
        self.root.after(0, self._reset_voice_ui, manual)

    def _reset_voice_ui(self, manual):
        self._voice_active = False
        self._voice_btn.config(
            bg=C["purple"],
            text=self._lbl["voice"]["btn_activate"])
        self._voice_status.set(self._lbl["voice"]["status_standby"])
        if manual:
            self.safe_log(self._lbl["voice"]["log_deactivated"])

    def handle_voice_error(self, error_msg):
        self.safe_log("⚠ Voice Error: {}".format(error_msg), "warn")

    def handle_transcription(self, text):
        self.safe_log("Transcribed: '{}'".format(text), "info")
        self._voice_status.set(self._lbl["voice"]["status_done"])
        self.root.after(0, self._parse_and_execute, text)

    def _parse_and_execute(self, text):
        text_l = text.lower()
        keywords = self._payload["voice_keywords"]
        color_match = dest_match = None

        for value, words in keywords["medicines"].items():
            if any(w in text_l for w in words):
                for m in self._payload["medicines"]:
                    if m["value"] == value:
                        color_match = m["label"]
                        break
                break

        for value, words in keywords["bays"].items():
            if any(w in text_l for w in words):
                for b in self._payload["bays"]:
                    if b["value"] == value:
                        dest_match = b["label"]
                        break
                break

        if color_match and dest_match:
            self._color_var.set(color_match)
            self._dest_var.set(dest_match)
            self.safe_log("✓ " + self._lbl["voice"]["log_mapped"], "success")
            self._execute_command()
        else:
            self.safe_log("⚠ " + self._lbl["voice"]["log_incomplete"], "warn")


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = CapstoneWorkstationUI(root)
    root.mainloop()
