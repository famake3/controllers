import os
import shutil
import subprocess
import sys
import threading
import time

import playsound
from paho.mqtt import client as mqtt

try:
    import winsound
except ImportError:
    winsound = None


PC_CONFIGS = {
    "tv": {
        "lockscreen": True,
        "monitors": [],
    },
    "nepe": {
        "lockscreen": True,
        "monitors": [
            {"id": r"\\.\DISPLAY5\Monitor0", "offset": 0},
            {"id": r"\\.\DISPLAY1\Monitor0", "offset": -12},
        ],
    },
}


wakealarm_stop = threading.Event()
DEBUG = False


def debug_print(*args):
    if DEBUG:
        print("[pc-windows]", *args, flush=True)


def get_pc_config(pc):
    return PC_CONFIGS.get(pc.lower(), {"lockscreen": False, "monitors": []})


def play_sound(path):
    if winsound is not None:
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME)
            return
        except RuntimeError as e:
            print(e)
    try:
        playsound.playsound(path)
    except playsound.PlaysoundException as e:
        print(e)


def start_wakealarm(path):
    wakealarm_stop.clear()

    def _loop():
        while not wakealarm_stop.is_set():
            play_sound(path)
            if wakealarm_stop.is_set():
                break
            time.sleep(0.2)

    threading.Thread(target=_loop, daemon=True).start()


def stop_wakealarm():
    wakealarm_stop.set()
    if winsound is not None:
        try:
            winsound.PlaySound(None, 0)
        except RuntimeError:
            pass


def find_controlmymonitor():
    candidates = [
        os.environ.get("CONTROLMYMONITOR_PATH"),
        r"C:\Users\mariu\Software\ControlMyMonitor\ControlMyMonitor.exe",
        shutil.which("ControlMyMonitor.exe"),
        shutil.which("ControlMyMonitor"),
        r"C:\Program Files\ControlMyMonitor\ControlMyMonitor.exe",
        r"C:\Program Files (x86)\ControlMyMonitor\ControlMyMonitor.exe",
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "ControlMyMonitor.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            debug_print("Using ControlMyMonitor:", candidate)
            return candidate
    debug_print("ControlMyMonitor not found in candidates:", candidates)
    return None


def set_monitor_brightness(controlmymonitor, monitor_id, brightness):
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    cmd = [controlmymonitor, "/SetValue", monitor_id, "10", str(brightness)]
    debug_print("Running:", cmd)
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=DEBUG,
        creationflags=creationflags,
    )
    if DEBUG:
        stdout = result.stdout.decode(errors="replace").strip() if result.stdout else ""
        stderr = result.stderr.decode(errors="replace").strip() if result.stderr else ""
        debug_print("Return code:", result.returncode)
        if stdout:
            debug_print("stdout:", stdout)
        if stderr:
            debug_print("stderr:", stderr)
    return result.returncode


def apply_brightness(pc, brightness):
    config = get_pc_config(pc)
    monitors = config.get("monitors", [])
    debug_print("Brightness request for", pc, "=", brightness)
    debug_print("Monitor config:", monitors)
    if not monitors:
        debug_print("No monitors configured for", pc)
        return

    controlmymonitor = find_controlmymonitor()
    if controlmymonitor is None:
        print("ControlMyMonitor.exe not found; brightness command ignored")
        return

    # After monitor sleep, DDC/CI often needs a few seconds before it responds.
    for delay in (0, 3, 8):
        if delay:
            debug_print("Sleeping", delay, "seconds before retry")
            time.sleep(delay)
        all_ok = True
        seen = set()
        for monitor in monitors:
            monitor_id = monitor["id"]
            if monitor_id in seen:
                debug_print("Skipping duplicate monitor id", monitor_id)
                continue
            seen.add(monitor_id)
            monitor_brightness = max(0, min(100, brightness + monitor.get("offset", 0)))
            debug_print("Setting", monitor_id, "to", monitor_brightness, "(offset", monitor.get("offset", 0), ")")
            rc = set_monitor_brightness(controlmymonitor, monitor_id, monitor_brightness)
            if rc != 0:
                all_ok = False
        if all_ok:
            debug_print("Brightness update succeeded")
            break
    else:
        debug_print("Brightness update failed after retries")


def main(mqtt_server, topic_base, pc):
    client = mqtt.Client()
    connected = False
    while not connected:
        time.sleep(5)
        try:
            client.connect(mqtt_server)
            connected = True
        except IOError:
            pass

    def on_connect(client, _, flags, rc):
        client.subscribe("{}/#".format(topic_base))

    client.on_connect = on_connect
    sounddir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sounds")
    config = get_pc_config(pc)

    def on_message(client, _, msg):
        try:
            str_payload = msg.payload.decode("ascii")
        except ValueError:
            return

        if msg.topic == "{}/command".format(topic_base):
            if str_payload == "alarmbeep":
                play_sound(os.path.join(sounddir, "pipipipipipip.wav"))
            elif str_payload == "beep":
                play_sound(os.path.join(sounddir, "pip.wav"))
            elif str_payload == "lockscreen" and config.get("lockscreen"):
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
            elif str_payload == "screenoff" and pc.lower() in ["tv"]:
                # turn off screen
                pass
            elif str_payload == "screenon" and pc.lower() in ["tv"]:
                # turn on screen
                pass
            elif str_payload == "wakealarm":
                start_wakealarm(os.path.join(sounddir, "vekke.wav"))
            elif str_payload == "wakealarmkill":
                stop_wakealarm()
        elif msg.topic == "{}/brightness".format(topic_base):
            try:
                brightness = int(round(float(str_payload)))
            except ValueError:
                return
            brightness = max(0, min(100, brightness))
            threading.Thread(target=apply_brightness, args=(pc, brightness), daemon=True).start()

    client.on_message = on_message
    client.loop_forever()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--debug" in args:
        DEBUG = True
        args = [arg for arg in args if arg != "--debug"]
        debug_print("Debug enabled")
    main(*args)
