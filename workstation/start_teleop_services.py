import os
import sys
import time
import socket
import subprocess
import urllib.request
import urllib.parse
import json
import ssl
import paramiko
import io
import scipy.io.wavfile as wav
import sounddevice as sd

# IPs and Ports
PI_IP = "192.168.0.130"
MAC_IP = "192.168.0.23"
PC_IP = "127.0.0.1"

PORT_LM = 1234
PORT_TTS = 8057

def check_port(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def wait_for_port(host, port, timeout_s=10):
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        if check_port(host, port):
            return True
        time.sleep(1.0)
    return False

def requests_post_local(url, data_dict):
    data = urllib.parse.urlencode(data_dict).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    with urllib.request.urlopen(req, timeout=10.0) as r:
        return r.read()

def local_tts_speak(text):
    print(f"Announcing locally: '{text}'")
    url = f"http://localhost:{PORT_TTS}/tts"
    try:
        response = requests_post_local(url, {"text": text, "voice_url": "hf://laura"})
        rate, data = wav.read(io.BytesIO(response))
        sd.play(data, rate)
        sd.wait()
    except Exception as e:
        print(f"TTS Audio playback failed: {e}")

def main():
    print("=" * 60)
    print("=== STARTING ROBOT TELEOP SERVICES & INTEGRATION SEQUENCE ===")
    print("=" * 60)

    # 1. Check LM Studio
    print("\n[Step 1/6] Checking LM Studio...")
    if not check_port(PC_IP, PORT_LM):
        print("[ERROR] LM Studio is offline on port 1234!")
        print("[ACTION REQUIRED] Open LM Studio, load your model, and start the Local Server.")
        input("Once LM Studio is running, press ENTER to continue...")
        if not check_port(PC_IP, PORT_LM):
            print("[ERROR] Still offline. Exiting script.")
            sys.exit(1)
    print("LM Studio is active!")

    # 2. Launch Local Workstation Services
    print("\n[Step 2/6] Launching local workstation services...")
    
    # Start Pocket-TTS (Docker Container)
    if not check_port(PC_IP, PORT_TTS):
        print("Starting Pocket-TTS Server via Docker (pocket-tts-server)...")
        try:
            subprocess.run(["docker", "start", "pocket-tts-server"], check=True, capture_output=True)
            print("Waiting for Pocket-TTS to bind port 8057...")
            wait_for_port(PC_IP, PORT_TTS, 10)
        except Exception as e:
            print(f"[ERROR] Failed to start pocket-tts-server Docker container: {e}")
    else:
        print("Pocket-TTS Server is already running.")

    # Start ngrok tunnel
    print("Starting ngrok Tunnel to townie.backyard.ngrok.dev...")
    os.system("taskkill /f /im ngrok.exe >nul 2>&1")
    time.sleep(0.5)
    subprocess.Popen(
        [r"i:\ngrok.exe", "http", "--url=townie.backyard.ngrok.dev", f"{PI_IP}:8080"],
        cwd="I:\\",
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    time.sleep(3.0)

    # 3. Check Pi services status (Manual activation required via HF space)
    print("\n[Step 3/6] Checking service statuses on Raspberry Pi 500...")
    if not check_port(PI_IP, 8080):
        print(f"[ERROR] Cannot reach Web Controller on Pi ({PI_IP}:8080)!")
        print("Please make sure the Raspberry Pi is powered up and connected to the network.")
        sys.exit(1)
    else:
        print("  * Pi Web Controller        : ONLINE")

    # 4. Bootstrap Mac Mini tracker client
    print("\n[Step 4/6] Bootstrapping tracker client on Mac Mini...")
    mac_ssh = paramiko.SSHClient()
    mac_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        mac_ssh.connect(MAC_IP, username='twinpeakstownie', password='reachyultradancemix9000', timeout=8)
        
        # Check if already running on Mac Mini
        stdin, stdout, stderr = mac_ssh.exec_command("ps aux | grep -v grep | grep -E 'so101_leader_client|remote_teleop.sh'")
        procs = stdout.read().decode('utf-8').strip()
        if not procs:
            print("  - Starting fresh leader client tracking script inside screen...")
            mac_ssh.exec_command("pkill -9 -f remote_teleop.sh")
            mac_ssh.exec_command("pkill -9 -f so101_leader_client.py")
            mac_ssh.exec_command("screen -X -S leader_client quit")
            time.sleep(1.0)
            mac_ssh.exec_command(
                "cd /Users/twinpeakstownie/lerobot && chmod +x ./remote_teleop.sh && /usr/bin/screen -S leader_client -d -m ./remote_teleop.sh"
            )
            print("  - Mac Mini tracking client launched successfully in screen.")
        else:
            print("  - Mac Mini tracking client is already running.")
    except Exception as e:
        print(f"[WARNING] Failed to bootstrap Mac Mini tracker client: {e}")
        print("Please check that the Mac Mini is online and the leader arm is connected.")
    finally:
        mac_ssh.close()

    # 5. System Health Check
    print("\n[Step 5/6] Verifying system health...")
    core_health = {
        "LM Studio (Local)": check_port(PC_IP, PORT_LM),
        "Pocket-TTS (Local)": check_port(PC_IP, PORT_TTS),
        "Pi Web Controller": check_port(PI_IP, 8080),
    }
    
    pi_services = {
        "Pi Reachy Daemon": check_port(PI_IP, 8000),
        "Pi TTS Mover App": check_port(PI_IP, 8042),
        "Pi Arm Host (ZMQ)": check_port(PI_IP, 5555)
    }

    all_core_ok = True
    print("Core Workstation & Connection Status:")
    for name, status in core_health.items():
        status_str = "ONLINE" if status else "OFFLINE"
        print(f"  * {name:<25}: {status_str}")
        if not status:
            all_core_ok = False

    print("\nRaspberry Pi Daemon Services (Activate manually in HF web controller):")
    for name, status in pi_services.items():
        status_str = "ONLINE" if status else "OFFLINE"
        print(f"  * {name:<25}: {status_str}")

    # 6. Audio status announcement
    print("\n[Step 6/6] Playing startup status audio...")
    if all_core_ok:
        print("\nSYSTEM IS ONLINE AND READY FOR MANUAL ACTIVATION!")
        local_tts_speak("System online and ready for manual activation through the web controller located on Hugging Face.")
    else:
        print("\nWARNING: Core services are offline! Please check the offline items above.")
        local_tts_speak("System startup finished with warnings. Please check the console output.")

if __name__ == '__main__':
    main()
