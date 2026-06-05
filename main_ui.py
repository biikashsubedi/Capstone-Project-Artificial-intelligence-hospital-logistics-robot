import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from tkmacosx import Button

# Import your newly separated modules
import file_handler
from voice_engine import VoiceController

class CapstoneWorkstationUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AIG200 Capstone: Workstation Control Panel")
        self.root.geometry("900x650")
        self.root.configure(bg="#f5f6fa")

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TLabel", background="#f5f6fa", font=("Helvetica", 12))
        self.style.configure("Header.TLabel", font=("Helvetica", 15, "bold"), foreground="#2c3e50")

        # Initialize the separated Voice Controller
        self.voice = VoiceController(
            on_log=self.safe_log,
            on_transcription=self.handle_transcription,
            on_error=self.handle_voice_error,
            on_stop=self.handle_voice_stop
        )

        self.build_ui()

    def build_ui(self):
        left_panel = tk.Frame(self.root, bg="#f5f6fa", width=400, padx=20, pady=20)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)

        right_panel = tk.Frame(self.root, bg="#ecf0f1", width=500, padx=20, pady=20)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # --- LEFT PANEL UI ---
        ttk.Label(left_panel, text="Layer 1: Perception & Input", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 20))

        self.connect_btn = Button(left_panel, text="📡 CONNECT TO ROBOT", command=self.connect_system, bg="#2980b9", fg="white", font=("Helvetica", 12, "bold"), padx=10, pady=8, borderless=1, cursor="hand2")
        self.connect_btn.pack(fill=tk.X, pady=(0, 20))
        self.connect_btn.bind("<Enter>", lambda e: self.connect_btn.config(bg="#3498db"))
        self.connect_btn.bind("<Leave>", lambda e: self.connect_btn.config(bg="#2980b9"))

        ttk.Label(left_panel, text="Select Target Medicine Color:").pack(anchor=tk.W, pady=(10, 2))
        self.color_var = tk.StringVar()
        self.color_dropdown = ttk.Combobox(left_panel, textvariable=self.color_var, state="readonly", width=30)
        self.color_dropdown['values'] = ("Red Box (Medicine A)", "Blue Box (Medicine B)", "Green Box (Medicine C)")
        self.color_dropdown.current(0)
        self.color_dropdown.pack(anchor=tk.W, pady=(0, 15))

        ttk.Label(left_panel, text="Select Destination Bay:").pack(anchor=tk.W, pady=(10, 2))
        self.dest_var = tk.StringVar()
        self.dest_dropdown = ttk.Combobox(left_panel, textvariable=self.dest_var, state="readonly", width=30)
        self.dest_dropdown['values'] = ("Patient Bay 1 (Bed A)", "Patient Bay 2 (Bed B)", "Emergency Standby Hub")
        self.dest_dropdown.current(0)
        self.dest_dropdown.pack(anchor=tk.W, pady=(0, 25))

        self.dispatch_btn = Button(left_panel, text="⚡ INITIATE DEPLOYMENT", command=self.execute_command, bg="#005ce6", fg="white", font=("Helvetica", 13, "bold"), padx=10, pady=10, borderless=1, cursor="hand2")
        self.dispatch_btn.pack(fill=tk.X, pady=10)
        self.dispatch_btn.bind("<Enter>", lambda e: self.dispatch_btn.config(bg="#3385ff"))
        self.dispatch_btn.bind("<Leave>", lambda e: self.dispatch_btn.config(bg="#005ce6"))

        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=20)

        # --- VOICE UI ---
        ttk.Label(left_panel, text="Voice Command Override", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 10))

        self.voice_btn = Button(left_panel, text="🎙️ ACTIVATE MICROPHONE", command=self.toggle_mic, bg="#8e44ad", fg="white", font=("Helvetica", 12, "bold"), padx=10, pady=10, borderless=1, cursor="hand2")
        self.voice_btn.pack(fill=tk.X, pady=(0, 10))
        self.voice_btn.bind("<Enter>", lambda e: self.voice_btn.config(bg="#c0392b" if self.voice.is_listening else "#9b59b6"))
        self.voice_btn.bind("<Leave>", lambda e: self.voice_btn.config(bg="#e74c3c" if self.voice.is_listening else "#8e44ad"))

        self.voice_status_var = tk.StringVar(value="Status: Mic Standby")
        ttk.Label(left_panel, textvariable=self.voice_status_var, font=("Helvetica", 11, "italic"), foreground="#7f8c8d").pack(anchor=tk.W)

        # --- RIGHT PANEL UI ---
        ttk.Label(right_panel, text="Layer 4: Cloud Telemetry Stream", style="Header.TLabel", background="#ecf0f1").pack(anchor=tk.W, pady=(0, 15))

        self.terminal = tk.Text(right_panel, bg="#2c3e50", fg="#ecf0f1", font=("Courier", 12), wrap=tk.WORD, height=18)
        self.terminal.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        self.safe_log("System Offline. Click 'Connect to Robot' to initialize...\n")

        self.state_lbl = ttk.Label(right_panel, text="CURRENT STATE: OFFLINE", font=("Helvetica", 12, "bold"), foreground="#7f8c8d", background="#ecf0f1")
        self.state_lbl.pack(anchor=tk.W)

    # --- UI UPDATE METHODS ---
    def safe_log(self, message):
        """Thread-safe logging to the terminal using root.after"""
        self.root.after(0, self._insert_log, message)

    def _insert_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.terminal.insert(tk.END, f"[{timestamp}] {message}\n")
        self.terminal.see(tk.END)

    def connect_system(self):
        self.safe_log("Establishing local network connection to JetAuto robot...")
        self.safe_log("✓ Connected to JetAuto Pro ROS Network\n")
        self.state_lbl.configure(text="CURRENT STATE: IDLE (CONNECTED)", foreground="#10ac84")

    # --- VOICE COMMUNICATION PROTOCOLS ---
    def toggle_mic(self):
        if not self.voice.is_listening:
            if self.voice.start():
                self.voice_btn.config(bg="#e74c3c", text="🛑 STOP LISTENING")
                self.voice_status_var.set("Status: Listening...")
                self.safe_log("🎙️ Microphone activated. Awaiting verbal command...")
        else:
            self.voice.stop(manual=True)

    def handle_voice_stop(self, manual):
        """Callback when the voice engine stops"""
        self.root.after(0, self._reset_voice_ui, manual)

    def _reset_voice_ui(self, manual):
        self.voice_btn.config(bg="#8e44ad", text="🎙️ ACTIVATE MICROPHONE")
        self.voice_status_var.set("Status: Mic Standby")
        if manual:
            self.safe_log("🛑 Microphone deactivated manually.")

    def handle_voice_error(self, error_msg):
        """Callback for voice engine errors"""
        self.safe_log(f"⚠️ Voice Error: {error_msg}")

    def handle_transcription(self, text):
        """Callback when text is successfully transcribed"""
        self.safe_log(f"🗣️ Transcribed: '{text}'")
        self.root.after(0, self.voice_status_var.set, "Status: Transcription Complete")
        self.root.after(0, self._parse_and_execute, text)

    def _parse_and_execute(self, text):
        text = text.lower()
        color_matched, dest_matched = False, False

        if "red" in text: self.color_var.set("Red Box (Medicine A)"); color_matched = True
        elif "blue" in text: self.color_var.set("Blue Box (Medicine B)"); color_matched = True
        elif "green" in text: self.color_var.set("Green Box (Medicine C)"); color_matched = True

        if "bay 1" in text or "bed a" in text or "one" in text: self.dest_var.set("Patient Bay 1 (Bed A)"); dest_matched = True
        elif "bay 2" in text or "bed b" in text or "two" in text: self.dest_var.set("Patient Bay 2 (Bed B)"); dest_matched = True
        elif "emergency" in text or "hub" in text or "standby" in text: self.dest_var.set("Emergency Standby Hub"); dest_matched = True

        if color_matched and dest_matched:
            self.safe_log("✓ Voice command successfully mapped. Executing...")
            self.execute_command()
        else:
            self.safe_log("⚠️ Incomplete command. Please specify both a Color and a Destination.")

    # --- CORE EXECUTION ---
    def execute_command(self):
        color = self.color_var.get()
        destination = self.dest_var.get()
        command_string = f"Fetch {color} Box, Deliver to {destination.replace('_', ' ')}"

        self.safe_log(f"Transmitting command: '{command_string}'")
        self.state_lbl.configure(text="CURRENT STATE: DISPATCHED", foreground="#005ce6")

        try:
            # Delegate the saving process to the separated telemetry module
            file_saved = file_handler.save_to_csv(command_string, destination, color)
            self.safe_log(f"✓ Payload successfully cached to {file_saved}\n")
        except Exception as e:
            messagebox.showerror("System Error", f"Failed to cache telemetry: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CapstoneWorkstationUI(root)
    root.mainloop()