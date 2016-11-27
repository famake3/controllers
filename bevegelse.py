from RPi import GPIO
import time
import sys
import paho.mqtt.client as mqtt
from functools import partial

PIN = 17

def main(mqtt_server, topic):
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(PIN, GPIO.IN)
	client = None
	prev = None
	while True:
		while client == None:
			try:
				client = mqtt.Client()
				client.connect(mqtt_server, 1883, 60)
			except:
				client = None
				time.sleep(10)
		try:
			GPIO.wait_for_edge(PIN, GPIO.BOTH, timeout=60)
			if GPIO.input(PIN):
				payload = "ON"
			else:
				payload = "OFF"

			if prev != payload:
					client.publish(topic, payload)
			prev = payload
			client.loop()
		except:
			time.sleep(10)
			try:
				client.disconnect()
			except:
				pass
			client = None

if __name__ == "__main__":
	main(sys.argv[1], sys.argv[2])

