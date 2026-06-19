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
    print("DEBUG: Entering main()", flush=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.0.130")
    ap.add_argument("--port", default="/dev/cu.usbmodem5B415318721")
    ap.add_argument("--id", default="leader")
    args = ap.parse_args()

    print(f"DEBUG: Initializing leader config with port={args.port}, id={args.id}", flush=True)
    leader = SO101Leader(SOLeaderTeleopConfig(port=args.port, id=args.id))
    
    print("DEBUG: Connecting to leader...", flush=True)
    try:
        leader.connect()
        print("DEBUG: Leader connected successfully!", flush=True)
    except Exception as e:
        print(f"DEBUG: Exception during leader.connect(): {e}", flush=True)
        raise e

    print(f"DEBUG: Setting up ZMQ sockets to host={args.host}...", flush=True)
    ctx = zmq.Context()
    cmd_sock = ctx.socket(zmq.PUSH)
    cmd_sock.setsockopt(zmq.CONFLATE, 1)
    cmd_sock.setsockopt(zmq.LINGER, 0)
    cmd_sock.connect(f"tcp://{args.host}:{PORT_ZMQ_CMD}")
    
    obs_sock = ctx.socket(zmq.PULL)
    obs_sock.setsockopt(zmq.CONFLATE, 1)
    obs_sock.setsockopt(zmq.LINGER, 0)
    obs_sock.connect(f"tcp://{args.host}:{PORT_ZMQ_OBS}")
    print("DEBUG: ZMQ sockets connected successfully!", flush=True)

    print("DEBUG: Entering stream loop...", flush=True)
    n = 0
    try:
        while True:
            loop_start = time.time()
            try:
                action = leader.get_action()
            except Exception as e:
                print(f"DEBUG: exception in get_action(): {e}", flush=True)
                try:
                    leader.bus.port_handler.is_using = False
                except Exception:
                    pass
                time.sleep(0.01)
                continue

            # Convert PyTorch Tensors/NumPy arrays to JSON-serializable lists
            if isinstance(action, dict):
                serializable_action = {
                    k: v.tolist() if hasattr(v, "tolist") else v 
                    for k, v in action.items()
                }
            else:
                serializable_action = action.tolist() if hasattr(action, "tolist") else action

            # Catch zmq.Again to prevent crashes when the host is not ready
            try:
                cmd_sock.send_string(json.dumps(serializable_action), flags=zmq.NOBLOCK)
            except zmq.Again:
                print("DEBUG: zmq.Again exception caught on send_string", flush=True)
                pass
            except Exception as e:
                print(f"DEBUG: Send exception: {e}", flush=True)

            try:
                obs_sock.recv_string(zmq.NOBLOCK)
            except zmq.Again:
                pass
            except Exception as e:
                print(f"DEBUG: Recv exception: {e}", flush=True)
                
            n += 1
            if n % 100 == 0:
                print(f"DEBUG: sent {n} frames to Pi", flush=True)
            time.sleep(max(1 / FPS - (time.time() - loop_start), 0))
    except KeyboardInterrupt:
        print("DEBUG: KeyboardInterrupt in stream loop", flush=True)
    finally:
        print("DEBUG: Disconnecting leader and ZMQ sockets", flush=True)
        leader.disconnect()
        cmd_sock.close()
        obs_sock.close()
        ctx.term()


if __name__ == "__main__":
    main()
