import os
import glob
import time
 
from paho.mqtt import client as mqtt

TEMP_TOPIC = "sov/skrivebordTemp"
base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'
 
def read_temp_raw():
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines
 
def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        return temp_c


client = mqtt.Client()
connected = False
while not connected:
    time.sleep(5)
    try:
        client.connect("192.168.1.8", 1883, 60)
        connected = True
    except IOError as e:
        print("client.connect:", e)

client.loop_start()

prev_temp = None

try:
    while True:
        temp = round(read_temp(), 1)
        if temp != prev_temp:
            client.publish(TEMP_TOPIC, str(temp))
            prev_temp = temp
        time.sleep(1)
finally:
    client.loop_stop()

