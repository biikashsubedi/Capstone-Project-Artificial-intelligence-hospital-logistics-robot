import socket
import threading
import sys
import time

try:
    import rospy
    from geometry_msgs.msg import Twist
    HAS_ROS = True
except ImportError:
    HAS_ROS = False
    print("[WARNING] ROS not available — motion commands will be simulated.")


def execute_command(command: str) -> str:
    """Parse and execute a movement command. Returns a status message."""
    cmd = command.strip().lower()

    if cmd == "forward":
        return move_robot(linear_x=0.2, duration=2.0)
    elif cmd == "backward":
        return move_robot(linear_x=-0.2, duration=2.0)
    elif cmd == "left":
        return move_robot(angular_z=0.5, duration=2.0)
    elif cmd == "right":
        return move_robot(angular_z=-0.5, duration=2.0)
    elif cmd == "stop":
        return move_robot(duration=0)
    else:
        return f"ERROR: Unknown command '{command}'"


def move_robot(linear_x=0.0, angular_z=0.0, duration=2.0) -> str:
    """Send velocity command to robot for a given duration, then stop."""
    if not HAS_ROS:
        # Simulate for testing without ROS
        time.sleep(duration)
        return f"OK: Simulated move (linear_x={linear_x}, angular_z={angular_z}, duration={duration}s)"

    try:
        if not rospy.core.is_initialized():
            rospy.init_node('robot_cmd_node', anonymous=True)

        pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        time.sleep(0.3)  # let publisher register

        msg = Twist()
        msg.linear.x = linear_x
        msg.angular.z = angular_z

        start = time.time()
        while time.time() - start < duration:
            pub.publish(msg)
            time.sleep(0.1)

        # Stop
        pub.publish(Twist())
        return f"OK: Moved (linear_x={linear_x}, angular_z={angular_z}) for {duration}s"

    except Exception as e:
        return f"ERROR: ROS exception — {e}"


def handle_client(conn, addr):
    print(f"[Connected] Mac at {addr[0]}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                print("[Mac disconnected]")
                break

            command = data.decode('utf-8').strip()
            print(f"[Mac]: {command}")
            print(f"[Robot] Executing: {command} ...")

            result = execute_command(command)
            print(f"[Robot] Result: {result}")

            # Send confirmation back to Mac
            conn.send(result.encode('utf-8'))

    except Exception as e:
        print(f"[Error] {e}")
    finally:
        conn.close()


def start_server():
    host = '0.0.0.0'
    port = 5050

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((host, port))
        server.listen(1)
        print(f"[Robot] Waiting for connection on port {port}...")

        conn, addr = server.accept()
        handle_client(conn, addr)

    except KeyboardInterrupt:
        print("\n[Robot] Server stopped.")
    except Exception as e:
        print(f"[Error] {e}")
    finally:
        server.close()


if __name__ == "__main__":
    start_server()