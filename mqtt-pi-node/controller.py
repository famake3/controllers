from RPi import GPIO
import time
from paho.mqtt import client as mqtt

PIR_PIN = 23
PIR_TOPIC = "stue/pir"

GPIO.setmode(GPIO.BCM)
GPIO.setup(PIR_PIN, GPIO.IN)

# RF Transmitter is not used, but keep it low to avoid spamming RF
GPIO.setup(21, GPIO.IN)

client = mqtt.Client()
client.connect("192.168.1.8", 1883, 60)
client.loop_start()

try:
	client.publish(PIR_TOPIC, "ON" if GPIO.input(PIR_PIN) else "OFF")
	while True:
		result = GPIO.wait_for_edge(PIR_PIN, GPIO.BOTH, timeout=1800000)
		client.publish(PIR_TOPIC, "ON" if GPIO.input(PIR_PIN) else "OFF")
		time.sleep(0.1)

except RuntimeError: # Force to handle runtime error from wait_for_edge, to run finally
	pass
finally:
	client.loop_stop()
	GPIO.cleanup()

