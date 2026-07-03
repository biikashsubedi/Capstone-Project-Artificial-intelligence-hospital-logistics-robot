import socket
import sys

COMMANDS = ["forward", "backward", "left", "right", "stop"]

def print_help():
    print("\nAvailable commands:")
    for cmd in COMMANDS:
        print(f"  {cmd}")
    print("  quit  — exit\n")


def start_client():
    host = '192.168.149.1'
    port = 5050

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(10)  # wait up to 10s for robot confirmation

    try:
        print(f"Connecting to Robot at {host}:{port}...")
        client.connect((host, port))
        print("✅ Connected to Robot!\n")
        print_help()

        while True:
            try:
                cmd = input("Command: ").strip().lower()
            except EOFError:
                break

            if cmd == 'quit':
                print("Disconnecting...")
                break

            if cmd == 'help':
                print_help()
                continue

            if cmd not in COMMANDS:
                print(f"⚠️  Unknown command '{cmd}'. Type 'help' to see options.")
                continue

            # Send command to robot
            print(f"📤 Sending: {cmd}")
            client.send(cmd.encode('utf-8'))

            # Wait for confirmation from robot
            try:
                response = client.recv(1024).decode('utf-8').strip()
                if response.startswith("OK"):
                    print(f"✅ Robot confirmed: {response}\n")
                elif response.startswith("ERROR"):
                    print(f"❌ Robot error: {response}\n")
                else:
                    print(f"📨 Robot says: {response}\n")
            except socket.timeout:
                print("⚠️  No confirmation received (timeout). Robot may still be moving.\n")

    except ConnectionRefusedError:
        print(f"❌ Could not connect to {host}:{port}. Is chat_server.py running on the robot?")
    except KeyboardInterrupt:
        print("\nStopping client...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    start_client()