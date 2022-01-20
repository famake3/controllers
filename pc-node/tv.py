import serial
from paho.mqtt import client as mqtt
import sys

# Write-only gateway for LG TV serial, some specific commands

def main(mqtt_server, topic_base, serial_port):
    tv_serial = serial.Serial(serial_port)

    client = mqtt.Client()
    client.connect(mqtt_server)

    def on_connect(client, _, flags, rc):
        client.subscribe(f"{topic_base}/#")
    client.on_connect = on_connect

    def on_message(client, _, msg):
        try:
            str_payload = msg.payload.decode('ascii')
        except ValueError:
            return
        if msg.topic == f"{topic_base}/power":
            if str_payload == "ON":
                tv_serial.write("ka 00 01\r".encode('ascii'))
            elif str_payload == "OFF":
                tv_serial.write("ka 00 00\r".encode('ascii'))
        elif msg.topic == f"{topic_base}/backlight":
            try:
                tv_serial.write("mg 00 {:02x}\r".format(int(str_payload)).encode('ascii'))
            except ValueError:
                pass
        elif msg.topic == f"{topic_base}/input":
            match str_payload:
                case 'HDMI1':
                    tv_serial.write("xb 00 90\r".encode('ascii'))
                case 'HDMI2':
                    tv_serial.write("xb 00 91\r".encode('ascii'))

        elif msg.topic == f"{topic_base}/colorTemperature":
            match str_payload:
                case 'warm':
                    tv_serial.write("ku 00 2\r".encode('ascii'))
                case 'normal':
                    tv_serial.write("ku 00 1\r".encode('ascii'))
                case 'cool':
                    tv_serial.write("ku 00 0\r".encode('ascii'))
        f = tv_serial.read(10)
        
    client.on_message = on_message
    client.loop_forever()

if __name__ == "__main__":
    main(*sys.argv[1:4])
