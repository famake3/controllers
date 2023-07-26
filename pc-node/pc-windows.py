import subprocess
from paho.mqtt import client as mqtt
import sys
import os
import time
import playsound

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
                try:
                    playsound.playsound("{}\\pipipipipipip.wav".format(sounddir))
                except playsound.PlaysoundException as e:
                    print(e)
            elif str_payload == "beep":
                try:
                    playsound.playsound("{}\\pip.wav".format(sounddir))
                except playsound.PlaysoundException as e:
                    print(e)
            elif str_payload == "lockscreen" and pc in ['tv']:
                subprocess.run(["rundll32.exe","user32.dll,LockWorkStation"])
            elif str_payload == "screenoff" and pc in ['tv']:
                #turn off screen
                pass
            elif str_payload == "screenon" and pc in ['tv']:
                #turn on screen
                pass

    client.on_message = on_message
    client.loop_forever()

if __name__ == "__main__":
    main(*sys.argv[1:])
