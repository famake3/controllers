#!/usr/bin/env python3
import time
import logging
import sys
import os

from pycalima.Calima import Calima
from bluepy.btle import BTLEDisconnectError
import paho.mqtt.client as mqtt

# 1) Update these to match your setup:
logger = logging.getLogger("CalimaMQTT")


def _create_fan_with_retry(mac, pin, retries=3, delay_s=0.5):
    """
    Try to instantiate Calima(mac, pin). On BTLEDisconnectError, wait and retry.
    Returns a connected Calima instance or raises the last exception.
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return Calima(mac, pin)
        except BTLEDisconnectError as e:
            last_exc = e
            logger.warning("BLE constructor failed attempt %d/%d: %s", attempt, retries, e)
            if attempt < retries:
                time.sleep(delay_s)
    raise last_exc

def set_speeds_with_retry(mac, pin, humidity, light, trickle, retries=3, delay_s=0.5):
    fan = None
    try:
        # retry the constructor itself
        fan = _create_fan_with_retry(mac, pin, retries, delay_s)
        # then retry the setting call
        _with_retry = lambda fn, *args: _generic_retry(fn, args, retries, delay_s)
        _with_retry(fan.setFanSpeedSettings, humidity, light, trickle)

        logger.info("Fan speeds sent successfully: %r", (humidity, light, trickle))
    finally:
        if fan:
            try: fan.disconnect()
            except: pass

def set_boost_with_retry(mac, pin, on, speed, duration, retries=3, delay_s=0.5):
    fan = None
    try:
        fan = _create_fan_with_retry(mac, pin, retries, delay_s)
        _with_retry = lambda fn, *args: _generic_retry(fn, args, retries, delay_s)
        _with_retry(fan.setBoostMode, on, speed, duration)
        logger.info("Boost mode set: on=%s speed=%d duration=%ds", on, speed, duration)
    finally:
        if fan:
            try: fan.disconnect()
            except: pass

def _generic_retry(fn, args, retries, delay_s):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args)
        except BTLEDisconnectError as e:
            last_exc = e
            logger.warning("BTLE call failed attempt %d/%d: %s", attempt, retries, e)
            if attempt < retries:
                time.sleep(delay_s)
    raise last_exc


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
    try:
        if msg.topic == MQTT_SPEED_TOPIC:
            payload = msg.payload.decode("utf-8").strip()
            logger.info("Received speed command: {}".format(payload))
            try:
                humidity, light, trickle = [int(x) for x in payload.split("|")]
            except Exception as e:
                logger.error("Payload '{}' is not a valid triple.".format(payload))
                return
            set_speeds_with_retry(MAC_ADDRESS, PINCODE, humidity, light, trickle)

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
            set_boost_with_retry(MAC_ADDRESS, PINCODE, on, speed, time)
        else:
            logger.info("Ignoring unknown topic {}.".format(msg.topic))

    except Exception as e:
        logger.error("Error while controlling fan: {}".format(e))


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
