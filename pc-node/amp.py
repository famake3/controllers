import serial
from paho.mqtt import client as mqtt
import sys

# Full-duplex gateway for Rotel RA11 serial to MQTT

def main(mqtt_server, topic_base, serial_port):
    serial_port = serial.Serial(serial_port, baudrate=115200)

    client = mqtt.Client()
    client.connect(mqtt_server)

    def on_connect(client, _, flags, rc):
        client.subscribe(f"{topic_base}/cmd/#")
    client.on_connect = on_connect

    expect_error = False
    power_state = None

    def on_message(client, _, msg):
        try:
            str_payload = msg.payload.decode('ascii')
        except ValueError:
            return
        if msg.topic == f"{topic_base}/cmd/power":
            if str_payload == "ON":
                serial_port.write("power_on!".encode('ascii'))
            elif str_payload == "OFF":
                serial_port.write("power_off!".encode('ascii'))
                expect_error = True
        elif power_state == "ON":
            if msg.topic == f"{topic_base}/cmd/brightness":
                try:
                    # Convert to 0 (bright) to 6 (dim)
                    level = int(round((100.0 - float(str_payload)) / 16.6))
                    serial_port.write(f"dimmer_{level}!".encode('ascii'))
                except:
                    pass            
            elif msg.topic == f"{topic_base}/cmd/source":
                if str_payload in ['rcd', 'cd', 'coax1' 'coax2', 'opt1', 'opt2',
                                'aux1', 'aux2', 'tuner', 'phono', 'usb']:
                    serial_port.write(f"{str_payload}!".encode('ascii'))
            elif msg.topic == f"{topic_base}/cmd/volume":
                match str_payload:
                    case 'INCREASE':
                        serial_port.write("volume_up!".encode('ascii'))
                    case 'DECREASE':
                        serial_port.write("volume_down!".encode('ascii'))
                    case level:
                        if level.isdigit():
                            l = int(level)
                            if l >= 0 and l <= 96:
                                serial_port.write(f"volume_{l}!".encode('ascii'))
            elif msg.topic == f"{topic_base}/cmd/mute":
                if str_payload == "ON":
                    serial_port.write("mute_on!".encode('ascii'))
                else:
                    serial_port.write("mute_off!".encode('ascii'))
    
    client.on_message = on_message
    client.loop_start()

    serial_port.write("display_update_manual!".encode('ascii'))
    serial_port.write("get_current_power!".encode('ascii'))

    while True:
        response = ""
        c = None
        while c != '!':
            try:
                c = serial_port.read().decode('ascii')
            except ValueError:
                continue
            except IOError:
                if expect_error:
                    continue
                else:
                    raise
            response += c
        match response[:-1].split("="):
            case ['power', power]:
                power_state = "ON" if power == "on" else "OFF"
                client.publish(f"{topic_base}/state/power", power_state)
            case ['volume', 'max']:
                client.publish(f"{topic_base}/state/volume", "96")
            case ['volume', 'min']:
                client.publish(f"{topic_base}/state/volume", "0")
            case ['volume', level]:
                client.publish(f"{topic_base}/state/volume", level)
            case ['mute', mute]:
                client.publish(f"{topic_base}/state/mute", mute.upper())
            case ['dimmer', dimmer]:
                bright = 100-round(float(dimmer) * 16.6)
                client.publish(f"{topic_base}/state/brightness", bright)
            case ['dimmer', source]:
                client.publish(f"{topic_base}/state/source", source)
            
if __name__ == "__main__":
    main(*sys.argv[1:4])
