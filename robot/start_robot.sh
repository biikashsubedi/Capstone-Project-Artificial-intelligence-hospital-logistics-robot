#!/bin/bash
# Bring the robot up and check everything the delivery system needs.
#
#     bash ~/delivery/start_robot.sh
#
# Then, in the SAME terminal (or any terminal after running
# `source ~/delivery/robot_env.sh`), start the server:
#
#     cd ~/delivery && python3 chat_server.py

echo "=== 1. robot services ==="
if ! systemctl is-active --quiet start_app_node.service; then
    echo "starting start_app_node.service (master, cameras, servos)..."
    sudo systemctl start start_app_node.service
    echo "waiting 30 s for it to come up..."
    sleep 30
else
    echo "start_app_node.service already running"
fi

echo
echo "=== 2. finding the ROS master ==="
FOUND=""
for URI in "http://192.168.149.1:11311|192.168.149.1" "http://127.0.0.1:11311|127.0.0.1"; do
    ADDR="${URI%%|*}"; HOSTN="${URI##*|}"
    if ROS_MASTER_URI="$ADDR" ROS_HOSTNAME="$HOSTN" timeout 5 rostopic list >/dev/null 2>&1; then
        FOUND="$ADDR"; FOUND_HOST="$HOSTN"
        echo "master reachable at $ADDR"
        break
    fi
done
if [ -z "$FOUND" ]; then
    echo "NO MASTER FOUND."
    echo "  try:  sudo systemctl restart start_app_node.service   (then wait 30 s)"
    exit 1
fi

# Save the working settings so other terminals can reuse them.
cat > ~/delivery/robot_env.sh <<EOF
export ROS_MASTER_URI=$FOUND
export ROS_HOSTNAME=$FOUND_HOST
source ~/jetauto_ws/devel/setup.bash
EOF
echo "saved to ~/delivery/robot_env.sh  (source it in other terminals)"

export ROS_MASTER_URI="$FOUND"
export ROS_HOSTNAME="$FOUND_HOST"
source ~/jetauto_ws/devel/setup.bash

echo
echo "=== 3. cameras ==="
rostopic list 2>/dev/null | grep -E "image_raw$" | head -6
if ! rostopic list 2>/dev/null | grep -q "image_raw"; then
    echo "  WARNING: no camera topics — the GUI feeds will be blank"
fi

echo
echo "=== 4. web_video_server (GUI camera feeds, port 8080) ==="
if curl -s -m 3 http://127.0.0.1:8080/ >/dev/null 2>&1; then
    echo "already serving on port 8080"
else
    echo "starting web_video_server in the background..."
    nohup rosrun web_video_server web_video_server >/tmp/wvs.log 2>&1 &
    sleep 4
    curl -s -m 3 http://127.0.0.1:8080/ >/dev/null 2>&1 \
        && echo "now serving on port 8080" \
        || echo "  FAILED - check /tmp/wvs.log"
fi

echo
echo "=== 5. arm ==="
rostopic list 2>/dev/null | grep -q "multi_id_pos_dur" \
    && echo "servo topic present" \
    || echo "  WARNING: no servo topic — the arm will not move"

echo
echo "=== 6. port 5050 (delivery server) ==="
pkill -9 -f chat_server.py 2>/dev/null
pkill -9 -f link_test_server.py 2>/dev/null
echo "cleared any old server"

echo
echo "READY. Now run:"
echo "    source ~/delivery/robot_env.sh"
echo "    cd ~/delivery && python3 chat_server.py"
