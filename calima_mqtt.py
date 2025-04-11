#!/usr/bin/env python3
import time
import logging
import sys
import os

from pycalima.Calima import Calima
from bluepy.btle import BTLEDisconnectError
import paho.mqtt.client as mqtt

# 1) Update these to match your setup:
try:
    MAC_ADDRESS = os.environ["CALIMA_MACADDR"]
    PINCODE = os.environ["CALIMA_PINCODE"]
except KeyError as e:
    print("ERROR: Environment variable", e, "must be set")
    sys.exit(1)

MQTT_BROKER = "192.168.1.8"
MQTT_PORT   = 1883
MQTT_SPEED_TOPIC  = "bad/vifte/farter"
MQTT_BOOST_TOPIC  = "bad/vifte/boost"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("CalimaMQTT")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker.")
        client.subscribe([(MQTT_BOOST_TOPIC, 0), (MQTT_SPEED_TOPIC, 0)])
    else:
        logger.error("Failed to connect to MQTT broker (rc={}).".format(rc))

def on_message(client, userdata, msg):
    fan = None
    try:
        if msg.topic == MQTT_SPEED_TOPIC:
            payload = msg.payload.decode("utf-8").strip()
            logger.info("Received speed command: {}".format(payload))

            try:
                humidity, light, trickle = [int(x) for x in payload.split("|")]
            except Exception as e:
                logger.error("Payload '{}' is not a valid triple.".format(payload))
                return

            fan = Calima(MAC_ADDRESS, PINCODE)
            fan.setFanSpeedSettings(humidity, light, trickle)
            logger.info("Fan speed settings sent: {}".format(payload))
        elif msg.topic == MQTT_BOOST_TOPIC:
            payload = msg.payload.decode("utf-8").strip()
            logger.info("Received boost command: {}".format(payload))

            try:
                on, speed, time = [x for x in payload.split("|")]
                on = str(on).upper() in ["TRUE", "ON", "1"]
                speed = int(speed)
                time = int(time)
            except Exception as e:
                logger.error("Payload '{}' is not a valid boost triple (on, speed, time).".format(payload))
                return
            fan = Calima(MAC_ADDRESS, PINCODE)
            fan.setBoostMode(on, speed, time)
            #speed_settings = fan.getFanSpeedSettings()
            logger.info("Fan boost settings sent: {}".format(payload))

    except BTLEDisconnectError as e:
        logger.warning("BTLE disconnect error while controlling fan: {}".format(e))
    except Exception as e:
        logger.error("Error while controlling fan: {}".format(e))
    finally:
        if fan:
            try:
                fan.disconnect()
            except:
                pass

def main():
    client = mqtt.Client(client_id="CalimaFanService")
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        logger.error("Could not connect to MQTT broker at {}:{}: {}".format(MQTT_BROKER, MQTT_PORT, e))
        sys.exit(1)

    logger.info("Starting MQTT client loop. Waiting for speed commands...")
    client.loop_forever()

if __name__ == "__main__":
    main()
