import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import time
from threading import Condition

OPEN_PIN = 2
CLOSE_PIN = 3

mqtt_server = "192.168.1.8"
mqtt_port = 1883

fullOpenTime = 44.0
targetPercentage = 0.0
currentPercentage = 0.0
currentMode = 0
alignFirst = 0
ALIGN_AMOUNT = 2.0
alignAmountRemain = 0.0
newCommandCond = Condition()

def mqttCallback(client, userdata, message):
    global targetPercentage, alignFirst, alignAmountRemain
    payload = message.payload.decode()
    topic = message.topic

    if topic == "soverom/vindu/aapning":
        if payload == "ON":
            targetPercentage = 100.0
        elif payload == "OFF":
            targetPercentage = 0.0
        elif payload == "DECREASE":
            targetPercentage = max(0, targetPercentage - 1)
        elif payload == "INCREASE":
            targetPercentage = min(100, targetPercentage + 1)
        elif payload.isalnum():
            targetPercentage = min(max(int(payload), 0), 100)
        else:
            return

        alignFirst = 0
        if targetPercentage < 2:
            alignFirst = -1
            alignAmountRemain = ALIGN_AMOUNT
        elif targetPercentage > 98:
            alignFirst = 1
            alignAmountRemain = ALIGN_AMOUNT

        with newCommandCond:
            newCommandCond.notify()

    elif topic == "soverom/vindu/konf/tid":
        fullOpenTime = int(payload)


def controlWindow(client):
    global currentPercentage, currentMode, alignFirst, alignAmountRemain

    lastCommandTime = 0
    while True:
        currentTime = time.time()
        elapsedTime = currentTime - lastCommandTime
        newPercentage = currentPercentage

        if currentMode != 0:
            deltaPercentage = 100.0 * elapsedTime * currentMode / fullOpenTime
            newPercentage = max(0, min(100, currentPercentage + deltaPercentage))

            if alignFirst == -1 and newPercentage == 0.0:
                alignAmountRemain += deltaPercentage
            elif alignFirst == 1 and newPercentage == 100.0:
                alignAmountRemain -= deltaPercentage
            if alignAmountRemain < 0:
                alignFirst = 0

        if alignFirst != 0:
            currentMode = alignFirst
            lastCommandTime = currentTime
        elif (targetPercentage - currentPercentage) > 0.5:
            currentMode = 1
            lastCommandTime = currentTime
        elif (currentPercentage - targetPercentage) > 0.5:
            currentMode = -1
            lastCommandTime = currentTime
        else:
            currentMode = 0

        GPIO.output(OPEN_PIN, GPIO.HIGH if currentMode == 1 else GPIO.LOW)
        GPIO.output(CLOSE_PIN, GPIO.HIGH if currentMode == -1 else GPIO.LOW)

        if newPercentage != currentPercentage:
            currentPercentage = newPercentage
            newPct = str(round(currentPercentage))
            client.publish("soverom/vindu/aapningStatus", newPct)
        
        with newCommandCond:
            if currentMode == 0 or alignFirst:
                newCommandCond.wait(timeout=0.5)
            else:
                remainTime = fullOpenTime * abs(targetPercentage - currentPercentage) / 100.0
                newCommandCond.wait(timeout=max(0, min(0.5, remainTime)))



def main():
    client = mqtt.Client()
    client.on_message = mqttCallback
    connected = False
    while True:
        while not connected:
            time.sleep(5)
            try:
                client.connect(mqtt_server)
                connected = True
            except IOError:
                pass

        client.loop_start()
        client.subscribe("soverom/vindu/aapning")
        client.subscribe("soverom/vindu/konf/tid")
        client.publish("soverom/vindu/oppstart", "ON")

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(OPEN_PIN, GPIO.OUT)
        GPIO.setup(CLOSE_PIN, GPIO.OUT)

        GPIO.output(OPEN_PIN, GPIO.LOW)
        GPIO.output(CLOSE_PIN, GPIO.LOW)

        try:
            controlWindow(client)
        finally:
            GPIO.cleanup()
            client.loop_stop()

if __name__ == "__main__":
    main()
