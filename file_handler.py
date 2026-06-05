import csv
import os
from datetime import datetime


def save_to_csv(command_string, destination, color, filename="report.csv"):
    """Writes the execution payload to a local CSV edge cache."""
    headers = [
        "timestamp", "input_command_string", "assigned_station_goal",
        "detected_object_color", "vision_confidence", "final_execution_state"
    ]
    file_exists = os.path.isfile(filename)

    with open(filename, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(headers)

        writer.writerow([
            datetime.now().isoformat(),
            command_string,
            destination,
            color,
            1.0,  # Simulated vision confidence
            "Dispatched"
        ])
    return filename