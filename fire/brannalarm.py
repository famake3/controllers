from RPi import GPIO
import time
from paho.mqtt import client as mqtt

MINUS_PIN = 10
PLUS_INPUT_PIN = 8
FIRE_TOPIC = "stue/brann"
CONTINUITY_TOPIC = "stue/brannAlarmOk"

GPIO.setmode(GPIO.BOARD)
GPIO.setup(MINUS_PIN, GPIO.OUT)
GPIO.setup(PLUS_INPUT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

alarm_time = 0
alarm_on_state = False

client = mqtt.Client()
client.connect("192.168.1.2", 1883, 60)
client.loop_start()

def detect_and_report():
	client.publish(FIRE_TOPIC, "ON" if GPIO.input(PLUS_INPUT_PIN) else "OFF")

# Check if on fire when starting program
detect_and_report()

try:
	while True:
		result = GPIO.wait_for_edge(PLUS_INPUT_PIN, GPIO.RISING, timeout=60000)

		if result: # Fire
			if not alarm_on_state:
				client.publish(FIRE_TOPIC, "ON")
			alarm_on_state = True
		
		else: # Timeout, no new fire
			input_plus_state = GPIO.input(PLUS_INPUT_PIN)
			# Periodic continuity test if off
			if not input_plus_state:
				# Set minus pin high to check continuity
				GPIO.output(MINUS_PIN, True)
				time.sleep(0.1) # Give the electrons time to move
				input_plus_state = GPIO.input(PLUS_INPUT_PIN)
				client.publish(CONTINUITY_TOPIC, "ON" if input_plus_state else "OFF")
				GPIO.output(MINUS_PIN, False)
				time.sleep(0.1)
				input_plus_state = GPIO.input(PLUS_INPUT_PIN)
			if input_plus_state: # This can only mean one thing
				client.publish(FIRE_TOPIC, "ON")
			else:
				if alarm_on_state:
					client.publish(FIRE_TOPIC, "OFF")
				alarm_on_state = False
			
except RuntimeError: # Force to handle runtime error from wait_for_edge, to run finally
	pass
finally:
	print("Finally block hello")
	client.publish(CONTINUITY_TOPIC, "OFF")
	client.loop_stop()
	GPIO.cleanup()
	print("Finally block hello")

