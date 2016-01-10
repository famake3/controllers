from RPi import GPIO
import time
import paho.mqtt.client as mqtt
from functools import partial

PIN = 4

def main():
	client = mqtt.Client()
	client.connect("192.168.1.2", 1883, 60)
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(PIN, GPIO.IN)
	prev = None
	while True:
		GPIO.wait_for_edge(PIN, GPIO.BOTH, timeout=60)
		if GPIO.input(PIN):
			payload = "ON"
		else:
			payload = "OFF"

		if prev != payload:
			client.publish("kjokken/pi/bevegelse", payload)
			prev = payload
		client.loop()

main()

