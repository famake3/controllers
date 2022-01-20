import subprocess
from paho.mqtt import client as mqtt
import sys
import os
import requests

# Run predefined commands on computer

wakealarm_process = None

def main(mqtt_server, topic_base, pc, pushover_user=None, pushover_token=None):
    client = mqtt.Client()
    client.connect(mqtt_server)

    def on_connect(client, _, flags, rc):
        client.subscribe("{}/#".format(topic_base))
    client.on_connect = on_connect
    sounddir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sounds")
    def on_message(client, _, msg):
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
            elif str_payload == "startmine" and pc in ['blackhole']:
                subprocess.run(["supervisorctl","start","xmr"])
            elif str_payload == "stopmine" and pc in ['blackhole']:
                subprocess.run(["supervisorctl","stop","xmr"])
            elif str_payload == "badmineon" and pc in ['blackhole']:
                subprocess.run(["bash","/etc/openhab-bin/badmine","on"])
            elif str_payload == "badmineoff" and pc in ['blackhole']:
                subprocess.run(["bash","/etc/openhab-bin/badmine","off"])
            elif str_payload == "lockscreen" and pc in ['blackhole']:
                subprocess.run(["bash","/etc/openhab-bin/lock-screen.sh"])
            elif str_payload == "wakealarm":
                wakealarm_process = subprocess.Popen(["paplay", "{}/vekke.wav".format(sounddir)])
            elif str_payload == "wakealarmkill":
                if wakealarm_process is not None and wakealarm_process.poll() is None:
                    wakealarm_process.kill()
        elif msg.topic == "{}/pushover".format(topic_base) and pc == "blackhole":
            pushover(0, str_payload, pushover_user, pushover_token)
        elif msg.topic == "{}/pushoverAlarm".format(topic_base) and pc == "blackhole":
            pushover(2, str_payload, pushover_user, pushover_token)

    client.on_message = on_message
    client.loop_forever()

def pushover(priority, message, user, token):
    data={
        'token': token,
        'user': user,
        'message': message,
        'title': 'Husvarsel',
        'priority': priority,
    }
    if priority >= 2:
        data['retry'] = 60
        data['expire'] = 10800
    r = requests.post(
                "https://api.pushover.net/1/messages.json",
                data=data)

if __name__ == "__main__":
    main(*sys.argv[1:])
