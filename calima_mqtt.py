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

def _with_retry(fn, *args, retries=3, delay_s=0.5):
    """
    Try to call fn(*args).  On BTLEDisconnectError, wait and retry.
    Returns the result of fn, or raises the last exception if all retries fail.
    """
    last_exc = None
    for attempt in range(1, retries+1):
        try:
            return fn(*args)
        except BTLEDisconnectError as e:
            last_exc = e
            logger.warning("BTLE disconnect on attempt %d/%d: %s", attempt, retries, e)
            if attempt < retries:
                time.sleep(delay_s)
    # all retries failed
    raise last_exc

def set_speeds_with_retry(mac, pin, humidity, light, trickle):
    fan = Calima(mac, pin)
    try:
        # wrap the actual speed‑setting call
        _with_retry(fan.setFanSpeedSettings, humidity, light, trickle)
        # optionally verify that the settings took by reading them back
        actual = fan.getFanSpeedSettings()
        if (actual.Humidity, actual.Light, actual.Trickle) != (humidity, light, trickle):
            logger.warning("Settings mismatch: asked %r, got %r", 
                           (humidity, light, trickle), actual)
        else:
            logger.info("Fan speeds set successfully: %r", (humidity, light, trickle))
    finally:
        # make sure we always disconnect
        try:
            fan.disconnect()
        except Exception:
            pass

def set_boost_with_retry(mac, pin, on, speed, duration):
    fan = Calima(mac, pin)
    try:
        _with_retry(fan.setBoostMode, on, speed, duration)
        logger.info("Boost mode set: on=%s speed=%d/%ds", on, speed, duration)
    finally:
        try:
            fan.disconnect()
        except:
            pass



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
