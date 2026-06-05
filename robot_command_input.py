import tkinter as tk
from tkinter import ttk, messagebox
import json
from datetime import datetime
from tkmacosx import Button
import os, csv


class CapstoneWorkstationUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AIG200 Capstone: WRobot orkstation Control Panel")
        # Increased height to 650 to comfortably fit the new Voice UI
        self.root.geometry("900x650")
        self.root.configure(bg="#f5f6fa")

        # macOS Theme Styling
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TLabel", background="#f5f6fa", font=("Helvetica", 12))
        self.style.configure("Header.TLabel", font=("Helvetica", 15, "bold"), foreground="#2c3e50")

        self.build_ui()

    def build_ui(self):
        # UI Split: Left (Layer 1 Inputs) vs Right (Layer 4 Telemetry)
        left_panel = tk.Frame(self.root, bg="#f5f6fa", width=400, padx=20, pady=20)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)

        right_panel = tk.Frame(self.root, bg="#ecf0f1", width=500, padx=20, pady=20)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # ----------------- LEFT PANEL: COMMAND DISPATCH -----------------
        ttk.Label(left_panel, text="Layer 1: Perception & Input", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 20))

        # --- NEW SUCCESS GREEN BUTTON (Connect to Robot) ---
        self.connect_btn = Button(
            left_panel, text="📡 CONNECT TO ROBOT", command=self.connect_system,
            bg="#2980b9", fg="white", font=("Helvetica", 12, "bold"),
            padx=10, pady=8, borderless=1, cursor="hand2"
        )
        self.connect_btn.pack(fill=tk.X, pady=(0, 20))

        self.connect_btn.bind("<Enter>", lambda e: self.connect_btn.config(bg="#3498db"))
        self.connect_btn.bind("<Leave>", lambda e: self.connect_btn.config(bg="#2980b9"))

        # Target Medicine Color Dropdown
        ttk.Label(left_panel, text="Select Target Medicine Color:").pack(anchor=tk.W, pady=(10, 2))
        self.color_var = tk.StringVar()
        self.color_dropdown = ttk.Combobox(left_panel, textvariable=self.color_var, state="readonly", width=30)
        self.color_dropdown['values'] = ("Red Box (Medicine A)", "Blue Box (Medicine B)", "Green Box (Medicine C)")
        self.color_dropdown.current(0)
        self.color_dropdown.pack(anchor=tk.W, pady=(0, 15))

        # Target Destination Dropdown
        ttk.Label(left_panel, text="Select Destination Bay:").pack(anchor=tk.W, pady=(10, 2))
        self.dest_var = tk.StringVar()
        self.dest_dropdown = ttk.Combobox(left_panel, textvariable=self.dest_var, state="readonly", width=30)
        self.dest_dropdown['values'] = ("Patient Bay 1 (Bed A)", "Patient Bay 2 (Bed B)", "Emergency Standby Hub")
        self.dest_dropdown.current(0)
        self.dest_dropdown.pack(anchor=tk.W, pady=(0, 25))

        # --- MEDICAL BLUE BUTTON (Dispatch Robot) ---
        self.dispatch_btn = Button(
            left_panel, text="⚡ INITIATE DEPLOYMENT", command=self.execute_command,
            bg="#005ce6", fg="white", font=("Helvetica", 13, "bold"),
            padx=10, pady=10, borderless=1, cursor="hand2"
        )
        self.dispatch_btn.pack(fill=tk.X, pady=10)

        self.dispatch_btn.bind("<Enter>", lambda e: self.dispatch_btn.config(bg="#3385ff"))
        self.dispatch_btn.bind("<Leave>", lambda e: self.dispatch_btn.config(bg="#005ce6"))

        # --- VISUAL SEPARATOR ---
        separator = ttk.Separator(left_panel, orient='horizontal')
        separator.pack(fill=tk.X, pady=20)

        # --- VOICE COMMAND SECTION ---
        ttk.Label(left_panel, text="Voice Command Override", style="Header.TLabel").pack(anchor=tk.W, pady=(0, 10))

        self.voice_btn = Button(
            left_panel, text="🎙️ ACTIVATE MICROPHONE", command=self.simulate_voice_listening,
            bg="#8e44ad", fg="white", font=("Helvetica", 12, "bold"),
            padx=10, pady=10, borderless=1, cursor="hand2"
        )
        self.voice_btn.pack(fill=tk.X, pady=(0, 10))

        # Voice Button Purple Hover Events
        self.voice_btn.bind("<Enter>", lambda e: self.voice_btn.config(bg="#9b59b6") if self.voice_btn[
                                                                                            'text'] != "🔴 LISTENING..." else None)
        self.voice_btn.bind("<Leave>", lambda e: self.voice_btn.config(bg="#8e44ad") if self.voice_btn[
                                                                                            'text'] != "🔴 LISTENING..." else None)

        self.voice_status_var = tk.StringVar(value="Status: Mic Standby")
        ttk.Label(left_panel, textvariable=self.voice_status_var, font=("Helvetica", 11, "italic"),
                  foreground="#7f8c8d").pack(anchor=tk.W)

        # ----------------- RIGHT PANEL: TELEMETRY & LOGS -----------------
        ttk.Label(right_panel, text="Layer 4: Cloud Telemetry Stream", style="Header.TLabel",
                  background="#ecf0f1").pack(anchor=tk.W, pady=(0, 15))

        # Terminal Output Box
        self.terminal = tk.Text(right_panel, bg="#2c3e50", fg="#ecf0f1", font=("Courier", 12), wrap=tk.WORD, height=18)
        self.terminal.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        self.log_to_terminal("System Offline. Click 'Connect to Robot' to initialize...\n")

        # Execution State Status
        self.state_lbl = ttk.Label(right_panel, text="CURRENT STATE: OFFLINE", font=("Helvetica", 12, "bold"),
                                   foreground="#7f8c8d", background="#ecf0f1")
        self.state_lbl.pack(anchor=tk.W)

    def log_to_terminal(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.terminal.insert(tk.END, f"[{timestamp}] {message}\n")
        self.terminal.see(tk.END)

    def connect_system(self):
        self.log_to_terminal("Establishing local network connection to JetAuto robot...")
        self.log_to_terminal("✓ Connected to JetAuto Pro ROS Network\n")
        self.state_lbl.configure(text="CURRENT STATE: IDLE (CONNECTED)", foreground="#10ac84")

    # --- NEW: VOICE SIMULATION LOGIC ---
    def simulate_voice_listening(self):
        # Change UI to show it's recording
        self.log_to_terminal("🎙️ Activating microphone array. Awaiting verbal command...")
        self.voice_status_var.set("Status: Listening...")
        self.voice_btn.config(bg="#e74c3c", text="🔴 LISTENING...")  # Turns red to indicate recording

        # Simulate a 2.5 second delay while the user "speaks", then call the processor
        self.root.after(2500, self.process_mock_voice_command)

    def process_mock_voice_command(self):
        # Reset the button UI
        self.voice_btn.config(bg="#8e44ad", text="🎙️ ACTIVATE MICROPHONE")
        self.voice_status_var.set("Status: Command Recognized")

        # Force the UI dropdowns to update based on the "spoken" command
        self.color_var.set("Green Box (Medicine C)")
        self.dest_var.set("Emergency Standby Hub")

        self.log_to_terminal("Speech-to-Text parsed: 'Fetch Green Box, Deliver to Emergency Hub'")

        # Automatically trigger the dispatch sequence
        self.execute_command()

    def execute_command(self):
        color = self.color_var.get()
        destination = self.dest_var.get()

        # Format the structural command string
        command_string = f"Fetch {color} Box, Deliver to {destination.replace('_', ' ')}"

        self.log_to_terminal(f"Transmitting command: '{command_string}'")
        self.state_lbl.configure(text="CURRENT STATE: DISPATCHED", foreground="#005ce6")

        # Define CSV file path and headers matching your telemetry schema
        cache_file = "report.csv"
        headers = ["timestamp", "input_command_string", "assigned_station_goal", "detected_object_color",
                   "vision_confidence", "final_execution_state"]

        # Check if file exists so we know whether to write the header row
        file_exists = os.path.isfile(cache_file)

        # Write to CSV
        try:
            with open(cache_file, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                # Write header only if the file is brand new
                if not file_exists:
                    writer.writerow(headers)

                # Write the actual data row
                writer.writerow([
                    datetime.now().isoformat(),
                    command_string,
                    destination,
                    color,
                    1.0,
                    "Dispatched"
                ])

            self.log_to_terminal(f"✓ Payload successfully cached to {cache_file}\n")
        except Exception as e:
            messagebox.showerror("System Error", f"Failed to cache telemetry: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = CapstoneWorkstationUI(root)
    root.mainloop()