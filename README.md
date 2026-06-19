# Remote Teleoperation for SO-101 Robot Arm

This repository contains the complete scripts and launcher configurations required to run remote teleoperation for the SO-101 robot arm (leader arm on macOS Mac Mini -> follower arm on Raspberry Pi 500).

## Repository Structure
* **`mac/`**:
  * `so101_leader_client.py`: The telemetry client script that polls the leader arm serial port and streams target angles.
  * `remote_teleop.sh`: Shell wrapper script to execute the client.
* **`pi/`**:
  * `so101_host.py`: ZMQ command puller and observation pusher running on the UGV's Raspberry Pi 500.
* **`workstation/`**:
  * `start_teleop_services.py`: Workstation launcher script coordinating LM Studio, Pocket-TTS, ngrok, and starting the Mac Mini telemetry client via SSH.
  * `start_robot_system.bat` / `start_rover_control.bat` / `start_workstation_services.bat`: Launcher shortcuts.

---

## macOS Teleoperation Challenges & Fixes

Running high-frequency hardware telemetry scripts in the background on macOS introduces several OS-level blockers. Below is an overview of these challenges and how they are resolved:

### 1. JSON Serialization Failures (PyTorch Tensors)
* **Challenge**: The LeRobot leader arm tracking script returns joint positions as PyTorch tensors or NumPy arrays. The standard Python `json.dumps()` module throws an unhandled `TypeError` when trying to serialize these raw structures.
* **Resolution**: The client code converts any custom array/tensor types to standard Python primitives (`float` and `list`) using `.tolist()` helpers prior to serialization.

### 2. Unhandled ZMQ Exceptions
* **Challenge**: Streaming frame packets to the Pi's PULL socket with `flags=zmq.NOBLOCK` raises a `zmq.Again` exception if the Pi host goes offline or socket buffers fill. Without handler wrapping, the script crashes immediately.
* **Resolution**: The send socket call is wrapped in a `try...except zmq.Again` block to gracefully drop frames during network transitions instead of crashing.

### 3. macOS Local Network Privacy blocks
* **Challenge**: macOS Sonoma and Sequoia restrict background applications from accessing the local subnet (`192.168.0.x`). Running the client inside a detached background `screen` session strip the process of its interactive login shell permissions, causing connection requests to fail silently with `[Errno 65] No route to host`. Converting to a root `LaunchDaemon` is blocked because system-level services cannot access virtual environment files inside `/Users/` user folders.
* **Resolution**: The process is launched using `nohup` combined with `caffeinate` within the active user session context:
  ```bash
  nohup caffeinate -i /Users/twinpeakstownie/lerobot/.venv/bin/python -u /Users/twinpeakstownie/lerobot/so101_leader_client.py --host 192.168.0.130 > /tmp/so101_teleop.log 2>&1 &
  ```
  This inherits the interactive shell's local network permission profile while running safely in the background.

### 4. macOS App Nap Throttling
* **Challenge**: macOS aggressively throttles CPU cycles for terminal programs running invisibly in the background. If a telemetry script attempts to poll a serial USB device at 60Hz without focus, the OS suspends the thread, causing the control loop to drop frame rates or hang entirely.
* **Resolution**: Wrapping the execution command in `caffeinate -i` creates a system-level power assertion that prevents the operating system from throttling or sleeping the python process.

### 5. TCP Half-Open Connections
* **Challenge**: If the Raspberry Pi host daemon is abruptly terminated, the Mac Mini's TCP sockets can remain in a half-open `ESTABLISHED` state. The Mac continues sending telemetry into a dead socket without triggering a reconnect.
* **Resolution**: The launch services script performs a clean cleanup (`pkill -9`) of old client instances on the Mac Mini before spinning up a new telemetry pipeline.

---

## How to Start and Monitor Teleoperation

1. **Boot the Pi Host**: Click **Start Arm** on the web controller page (running `so101_host.py`).
2. **Start the Mac Client**: Run the workstation integration script on your PC workstation:
   ```cmd
   workstation\start_teleop_services.py
   ```
3. **Monitor Stream Logs (Mac Mini)**:
   ```bash
   tail -f /tmp/so101_teleop.log
   ```
