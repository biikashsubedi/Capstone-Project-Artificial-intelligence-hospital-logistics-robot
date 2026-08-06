#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Command parser. Turns a text command into a structured request.

Expected format (rigid on purpose — no NLP, no ambiguity):
    move medX to bedY        e.g. "move med1 to bed1"
"""
import config


def parse_command(text):
    """Return (parsed_dict, None) on success, or (None, error_message)."""
    text = text.strip().lower()
    parts = text.split()

    # Expected: ["move", "medX", "to", "bedY"]
    if len(parts) != 4 or parts[0] != "move" or parts[2] != "to":
        return None, "ERROR: Invalid format. Use: move medX to bedY"

    medicine = parts[1]
    destination = parts[3]

    if medicine not in config.VALID_MEDICINES:
        return None, ("ERROR: Unknown medicine '%s'. Use %s"
                      % (medicine, ", ".join(config.VALID_MEDICINES)))
    if destination not in config.VALID_BEDS:
        return None, ("ERROR: Unknown destination '%s'. Use %s"
                      % (destination, ", ".join(config.VALID_BEDS)))

    return {"medicine": medicine, "destination": destination}, None


if __name__ == "__main__":
    # Quick self-test (runs anywhere, no ROS needed):
    for t in ["move med1 to bed1", "move med3 to bed2", "move med5 to bed1",
              "go med1 bed1", "move med2 to bed3"]:
        print(repr(t), "->", parse_command(t))
