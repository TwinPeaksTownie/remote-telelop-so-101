#!/usr/bin/env python
"""SO-101 follower network host. Runs ON the Raspberry Pi (CM4) with the
follower arm on its USB. Torch-free: imports only lerobot.motors (the
lerobot.types/torch chain SIGILLs on Cortex-A72), and ports SOFollower's
behavior verbatim from lerobot 0.5.1 so_follower.py.

Transport modeled on lekiwi_host.py: ZMQ PULL cmd / PUSH obs, CONFLATE so
only the freshest packet survives.

Usage on the Pi:
  source ~/so101/.venv/bin/activate
  python ~/so101/so101_host.py --port /dev/ttyACM0 --id follower
"""

import argparse
import json
import logging
import time
from pathlib import Path

import zmq

from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode

PORT_ZMQ_CMD = 5555
PORT_ZMQ_OBS = 5556
WATCHDOG_TIMEOUT_MS = 500
MAX_LOOP_FREQ_HZ = 60

logging.basicConfig(level=logging.INFO)


def make_bus(port: str, calibration: dict[str, MotorCalibration]) -> FeetechMotorsBus:
    # Motor table: so_follower.py:52-60 (use_degrees=True default -> DEGREES body)
    norm_mode_body = MotorNormMode.DEGREES
    return FeetechMotorsBus(
        port=port,
        motors={
            "shoulder_pan": Motor(1, "sts3215", norm_mode_body),
            "shoulder_lift": Motor(2, "sts3215", norm_mode_body),
            "elbow_flex": Motor(3, "sts3215", norm_mode_body),
            "wrist_flex": Motor(4, "sts3215", norm_mode_body),
            "wrist_roll": Motor(5, "sts3215", norm_mode_body),
            "gripper": Motor(6, "sts3215", MotorNormMode.RANGE_0_100),
        },
        calibration=calibration,
    )


def load_calibration(fpath: Path) -> dict[str, MotorCalibration]:
    with open(fpath) as f:
        raw = json.load(f)
    return {motor: MotorCalibration(**vals) for motor, vals in raw.items()}


def configure(bus: FeetechMotorsBus) -> None:
    # Verbatim from so_follower.py configure() (P=16 to avoid shakiness,
    # gripper torque/current limits to avoid burnout), with num_retry added:
    # single missed status packets over the CM4's USB are transient.
    RETRY = 3
    bus.disable_torque(num_retry=RETRY)
    try:
        bus.configure_motors()
        for motor in bus.motors:
            bus.write("Operating_Mode", motor, OperatingMode.POSITION.value, num_retry=RETRY)
            bus.write("P_Coefficient", motor, 16, num_retry=RETRY)
            bus.write("I_Coefficient", motor, 0, num_retry=RETRY)
            bus.write("D_Coefficient", motor, 32, num_retry=RETRY)
            if motor == "gripper":
                bus.write("Max_Torque_Limit", motor, 500, num_retry=RETRY)
                bus.write("Protection_Current", motor, 250, num_retry=RETRY)
                bus.write("Overload_Torque", motor, 25, num_retry=RETRY)
    finally:
        bus.enable_torque(num_retry=RETRY)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--id", default="follower")
    args = ap.parse_args()

    calib_fpath = (
        Path.home()
        / ".cache/huggingface/lerobot/calibration/robots/so_follower"
        / f"{args.id}.json"
    )
    calibration = load_calibration(calib_fpath)

    bus = make_bus(args.port, calibration)
    bus.connect()
    if not bus.is_calibrated:
        logging.info("writing calibration file values to motors")
        bus.write_calibration(calibration)
    configure(bus)
    logging.info("follower connected and configured on %s", args.port)

    ctx = zmq.Context()
    cmd_sock = ctx.socket(zmq.PULL)
    cmd_sock.setsockopt(zmq.CONFLATE, 1)
    cmd_sock.setsockopt(zmq.LINGER, 0)
    cmd_sock.bind(f"tcp://*:{PORT_ZMQ_CMD}")
    obs_sock = ctx.socket(zmq.PUSH)
    obs_sock.setsockopt(zmq.CONFLATE, 1)
    obs_sock.setsockopt(zmq.LINGER, 0)
    obs_sock.bind(f"tcp://*:{PORT_ZMQ_OBS}")

    last_cmd_time = time.time()
    watchdog_active = False
    logging.info("waiting for commands on tcp ports %d/%d", PORT_ZMQ_CMD, PORT_ZMQ_OBS)
    try:
        while True:
            loop_start = time.time()
            try:
                msg = cmd_sock.recv_string(zmq.NOBLOCK)
                action = json.loads(msg)
                # send_action port: so_follower.py:210-221 (no max_relative_target)
                goal_pos = {
                    k.removesuffix(".pos"): v for k, v in action.items() if k.endswith(".pos")
                }
                bus.sync_write("Goal_Position", goal_pos)
                last_cmd_time = time.time()
                if watchdog_active:
                    logging.info("commands resumed")
                watchdog_active = False
            except zmq.Again:
                pass
            except Exception as e:
                logging.error("command handling failed: %s", e)

            if (time.time() - last_cmd_time > WATCHDOG_TIMEOUT_MS / 1000) and not watchdog_active:
                # Arm holds its last pose; just note the silence.
                logging.warning("no commands for %dms, holding pose", WATCHDOG_TIMEOUT_MS)
                watchdog_active = True

            try:
                # get_observation port: so_follower.py:181-184 (no cameras)
                obs = bus.sync_read("Present_Position")
                obs = {f"{motor}.pos": val for motor, val in obs.items()}
                obs_sock.send_string(json.dumps(obs), flags=zmq.NOBLOCK)
            except zmq.Again:
                pass
            except Exception as e:
                logging.error("observation failed: %s", e)
                try:
                    bus.port_handler.is_using = False
                except Exception:
                    pass

            time.sleep(max(1 / MAX_LOOP_FREQ_HZ - (time.time() - loop_start), 0))
    except KeyboardInterrupt:
        pass
    finally:
        logging.info("shutting down, torque off")
        bus.disconnect(True)
        cmd_sock.close()
        obs_sock.close()
        ctx.term()


if __name__ == "__main__":
    main()
