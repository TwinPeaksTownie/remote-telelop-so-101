#!/bin/zsh
# SO-101 remote teleop: leader on this Mac -> follower on the UGV's Pi (192.168.0.130).
# Start the host on the Pi first (SO-101 Arm Host desktop icon), then run this.
cd /Users/twinpeakstownie/lerobot
exec .venv/bin/python so101_leader_client.py --host 192.168.0.130
