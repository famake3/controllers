import subprocess
from paho.mqtt import client as mqtt
import sys
import os
import time
import re

# Run predefined commands on computer

wakealarm_process = None
# MQTT 0..100 maps linearly to this HDR backlight range (not nits).
# Raise/lower HDR_BACKLIGHT_MAX to choose the brightness at MQTT 100%.
# DP-3 supports 10..210; 100 is a deliberately lower, adjustable ceiling.
HDR_MONITOR = "DP-3"
HDR_BACKLIGHT_MIN = 10
HDR_BACKLIGHT_MAX = 100
COMMAND_TIMEOUT = 5


def hdr_backlight(brightness):
    brightness = max(0, min(100, brightness))
    ceiling = max(HDR_BACKLIGHT_MIN, min(210, HDR_BACKLIGHT_MAX))
    return round(HDR_BACKLIGHT_MIN + brightness / 100 * (ceiling - HDR_BACKLIGHT_MIN))


def run_quiet(cmd):
    """Run a command quietly and return True when it succeeded."""
    try:
        result = subprocess.run(
            cmd,
            check=False,
            timeout=COMMAND_TIMEOUT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def hdr_backlight_active():
    """Check backlight availability on our OLED, not another HDR monitor.

    Return None on a failed query: do not silently change control methods
    when GNOME's session bus or gdctl is temporarily unavailable.
    """
    try:
        result = subprocess.run(
            ["gdctl", "show"], check=False, capture_output=True,
            text=True, timeout=COMMAND_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Cannot query gdctl: {error}", file=sys.stderr, flush=True)
        return None
    if result.returncode != 0:
        print("gdctl show failed; skipping OLED brightness", file=sys.stderr, flush=True)
        return None

    connector = None
    for line in result.stdout.splitlines():
        match = re.search(r"\bMonitor\s+(\S+)", line)
        if match:
            connector = match.group(1)
        elif connector == HDR_MONITOR:
            if re.search(r"\bactive\s*(?:⇒|=>|:)\s*True\b", line):
                return True
            if re.search(r"\bactive\s*(?:⇒|=>|:)\s*False\b", line) or "Backlight: None" in line:
                return False
    print(f"Unknown backlight status for {HDR_MONITOR}; skipping OLED brightness",
          file=sys.stderr, flush=True)
    return None


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

    last_brightness = None
    brightness_commands_state = [None, None]

    def on_connect(client, _, flags, rc):
        client.subscribe("{}/#".format(topic_base))

    client.on_connect = on_connect
    sounddir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sounds")

    def apply_brightness(brightness, force=False):
        """LCD uses DDC; OLED uses gdctl when its backlight is active.

        SDR retains the original DDC brightness-minus-12 behavior.
        HDR has its own 10..configured-maximum mapping, without that offset.
        Failed HDR commands are retried on the next message, not via DDC.
        """
        brightness = max(0, min(100, brightness))

        # Current buses on nepe:
        #   Display 1 -> /dev/i2c-5   (LCD, generally dimmer; no HDR)
        #   Display 2 -> /dev/i2c-15  (MSI OLED, keep a bit lower)
        lcd_brightness = brightness
        oled_brightness = max(0, min(100, brightness - 12))

        # Display 1: keep existing DDC/CI behavior.
        lcd_cmd = ["ddcutil", "--bus=5", "setvcp", "10", str(lcd_brightness)]
        if force or lcd_cmd != brightness_commands_state[0]:
            if run_quiet(lcd_cmd):
                brightness_commands_state[0] = lcd_cmd

        hdr_active = hdr_backlight_active()
        if hdr_active is None:
            return
        if hdr_active:
            oled_cmd = ["gdctl", "prefs", "--monitor", HDR_MONITOR,
                        "--backlight", str(hdr_backlight(brightness))]
        else:
            oled_cmd = ["ddcutil", "--bus=15", "setvcp", "10", str(oled_brightness)]

        if force or oled_cmd != brightness_commands_state[1]:
            if run_quiet(oled_cmd):
                brightness_commands_state[1] = oled_cmd
            else:
                print(f"Brightness command failed: {oled_cmd}", file=sys.stderr, flush=True)

    def on_message(client, _, msg):
        nonlocal last_brightness
        global wakealarm_process
        try:
            str_payload = msg.payload.decode('ascii')
        except ValueError:
            return
        if msg.topic == "{}/command".format(topic_base):
            if str_payload == "alarmbeep":
                subprocess.run(["paplay", "{}/pipipipipipip.wav".format(sounddir)])
            elif str_payload == "beep":
                subprocess.run(["paplay", "{}/pip.wav".format(sounddir)])
            elif str_payload == "lockscreen" and pc in ['tv', 'nepe']:
                subprocess.run(["bash", "/home/fa2k/bin/lock-screen.sh"])
            elif str_payload == "screenoff" and pc in ['tv']:
                # turn off screen
                pass
            elif str_payload == "screenon" and pc in ['tv']:
                subprocess.run(["bash", "/home/fa2k/bin/turn-on-screen.sh"])
            elif str_payload == "wakealarm":
                wakealarm_process = subprocess.Popen(["paplay", "{}/vekke.wav".format(sounddir)])
            elif str_payload == "wakealarmkill":
                if wakealarm_process is not None and wakealarm_process.poll() is None:
                    wakealarm_process.kill()
        elif msg.topic == "{}/brightness".format(topic_base):
            try:
                brightness = int(round(float(str_payload)))
            except (ValueError, OverflowError):
                return

            brightness = max(0, min(100, brightness))
            last_brightness = brightness
            apply_brightness(brightness)

        elif msg.topic == "{}/refreshBrightness".format(topic_base):
            # Re-evaluate HDR state instead of blindly replaying the previous
            # command. That way a runtime HDR on/off change automatically
            # switches between gdctl and ddcutil.
            if last_brightness is not None:
                apply_brightness(last_brightness, force=True)

    client.on_message = on_message
    client.loop_forever()


if __name__ == "__main__":
    main(*sys.argv[1:])
