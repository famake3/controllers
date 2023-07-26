import subprocess
from paho.mqtt import client as mqtt
import sys
import os
import time
import requests

# Run predefined commands on computer

wakealarm_process = None

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
            elif str_payload == "lockscreen" and pc in ['tv', 'nepe']:
                subprocess.run(["bash","/home/fa2k/bin/lock-screen.sh"])
            elif str_payload == "screenoff" and pc in ['tv']:
                #subprocess.run(["xset","dpms", "force", "off"])
                pass
            elif str_payload == "screenon" and pc in ['tv']:
                time.sleep(1.0)
                subprocess.run(["xset","dpms", "force", "off"])
                time.sleep(5.0)
                subprocess.run(["xset","-dpms"])
            elif str_payload == "wakealarm":
                wakealarm_process = subprocess.Popen(["paplay", "{}/vekke.wav".format(sounddir)])
            elif str_payload == "wakealarmkill":
                if wakealarm_process is not None and wakealarm_process.poll() is None:
                    wakealarm_process.kill()

    client.on_message = on_message
    client.loop_forever()

if __name__ == "__main__":
    main(*sys.argv[1:])
