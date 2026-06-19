#!/usr/bin/env python
"""SO-101 remote teleop client. Runs on the Mac with the leader arm on USB.
Reads the leader at 60 Hz and streams its action dict over ZMQ to so101_host.py
on the UGV's Raspberry Pi. Counterpart of lekiwi_client's transport.

Usage:
  source /Users/twinpeakstownie/lerobot/.venv/bin/activate
  python /Users/twinpeakstownie/lerobot/so101_leader_client.py --host 192.168.0.130
"""

import argparse
import json
import logging
import time

import zmq

from lerobot.teleoperators.so_leader import SO101Leader, SOLeaderTeleopConfig

PORT_ZMQ_CMD = 5555
PORT_ZMQ_OBS = 5556
FPS = 60

logging.basicConfig(level=logging.INFO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.0.130")
    ap.add_argument("--port", default="/dev/cu.usbmodem5B415318721")
    ap.add_argument("--id", default="leader")
    args = ap.parse_args()

    leader = SO101Leader(SOLeaderTeleopConfig(port=args.port, id=args.id))
    leader.connect()
    logging.info("leader connected on %s", args.port)

    ctx = zmq.Context()
    cmd_sock = ctx.socket(zmq.PUSH)
    cmd_sock.setsockopt(zmq.CONFLATE, 1)
    cmd_sock.setsockopt(zmq.LINGER, 0)
    cmd_sock.connect(f"tcp://{args.host}:{PORT_ZMQ_CMD}")
    obs_sock = ctx.socket(zmq.PULL)
    obs_sock.setsockopt(zmq.CONFLATE, 1)
    obs_sock.setsockopt(zmq.LINGER, 0)
    obs_sock.connect(f"tcp://{args.host}:{PORT_ZMQ_OBS}")

    logging.info("streaming to %s at %d Hz, ctrl-c to stop", args.host, FPS)
    n = 0
    try:
        while True:
            loop_start = time.time()
            try:
                action = leader.get_action()
            except Exception as e:
                logging.warning("failed to get leader action: %s, retrying...", e)
                try:
                    leader.bus.port_handler.is_using = False
                except Exception:
                    pass
                time.sleep(0.01)
                continue
            cmd_sock.send_string(json.dumps(action), flags=zmq.NOBLOCK)
            try:
                obs_sock.recv_string(zmq.NOBLOCK)  # drain; keeps obs flowing for future use
            except zmq.Again:
                pass
            n += 1
            if n % 300 == 0:
                logging.info("streaming ok, %d frames sent", n)
            time.sleep(max(1 / FPS - (time.time() - loop_start), 0))
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("disconnecting leader")
        leader.disconnect()
        cmd_sock.close()
        obs_sock.close()
        ctx.term()


if __name__ == "__main__":
    main()
