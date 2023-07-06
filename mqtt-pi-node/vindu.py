import paho.mqtt.client as mqtt
import time
import pigpio
from threading import Condition

OPEN_PIN = 2
CLOSE_PIN = 3

RF_PIN = 4

IDLE_WAIT_TIME = 1000
ACTIVE_WAIT_TIME = 0.3

mqtt_server = "192.168.1.8"
mqtt_port = 1883
mqtt_reconnect_seconds = 60

ALIGN_AMOUNT = 4.0


pi = pigpio.pi()  # Connect to local Pi.

def parseCommand(payload, previousState):
    if payload == "ON":
        return 1
    elif payload == "OFF":
        return -1
    elif payload == "DECREASE":
        return -1
    elif payload == "INCREASE":
        return 1
    elif payload.isalnum():
        return int(payload)
    else:
        return previousState


class BlindsController:
    
    def __init__(self, pi, rf_pin,
                    up_command, stop_command, down_command,
                    rf_pulse_time,
                    packet_unit_time, num_repeat_packets,
                    minimum_interval,
                    make_long_pause=False,
                    start_state=0,
                    full_open_time=60.0):
        self.target_percentage = start_state
        self.current_percentage = start_state
        self.current_mode = 0
        self.start_percentage = start_state
        self.last_command_time = 0

        self.pi = pi
        self.minimum_interval = minimum_interval
        # Add a small fudge factor to account for imprecision in the timing
        self.minimum_adjustable_percentage = 1.6 * (minimum_interval * 100.0 / full_open_time)
        self.packet_unit_time = packet_unit_time
        self.num_repeat_packets = num_repeat_packets
        self.make_long_pause = make_long_pause
        self.full_open_time = full_open_time

        self.pi.set_mode(rf_pin, pigpio.OUTPUT)
        self.up_wave = self.make_wave(pi, rf_pin, rf_pulse_time, up_command)
        self.stop_wave = self.make_wave(pi, rf_pin, rf_pulse_time, stop_command)
        self.down_wave = self.make_wave(pi, rf_pin, rf_pulse_time, down_command)
    
        self.send_wave(self.stop_wave)


    def make_wave(self, pi, rf_pin, rf_pulse_time, hex_string):
        bin_string = bin(int(hex_string, 16))[2:].zfill(len(hex_string)*4)
        waves = []
        pin_mask = 1<<rf_pin
        for bit in bin_string:
            wave = []
            # Set the pin high or low depending on the bit value
            wave = [
                    pigpio.pulse(
                            pin_mask if bit == '1' else 0,
                            pin_mask if bit == '0' else 0,
                            int(rf_pulse_time*1e6)
                            )
                    ]
            waves.extend(wave)
        # Always return to zero
        waves.append(pigpio.pulse(0, pin_mask, int(rf_pulse_time*1e6)))
        pi.wave_add_generic(waves)
        return pi.wave_create()


    def send_wave(self, wave_id):
        #print("SENDING WAVE", wave_id)
        for i in range(self.num_repeat_packets):
            self.pi.wave_send_once(wave_id)
            time.sleep(self.packet_unit_time)
            if i == self.num_repeat_packets / 2 and self.make_long_pause:
                time.sleep(self.packet_unit_time * 2)


    def update(self, currentTime, changed_percentage_callback):
        """Compute the window position, execute the required action.

        Returns the expected remaining time for the manoeuvre or maximum timeout."""
        
        newPercentage = self.current_percentage
        elapsedTime = currentTime - self.last_command_time
        if self.current_mode != 0:
            deltaPercentage = 100.0 * elapsedTime * self.current_mode / self.full_open_time
            newPercentage = max(0, min(100, self.start_percentage + deltaPercentage))

        # If running we want to go past the target, if stopped, be close to it
        up_slack = self.minimum_adjustable_percentage if self.current_mode != 1 else 0
        dn_slack = self.minimum_adjustable_percentage if self.current_mode != -1 else 0

        # Determine new desired mode
        if newPercentage < (self.target_percentage - up_slack):
            set_mode = 1
        elif newPercentage > (self.target_percentage + dn_slack):
            set_mode = -1
        else:
            set_mode = 0
        
        if set_mode != self.current_mode:
            if elapsedTime > self.minimum_interval:
                if set_mode in [-1, 1] or int(self.target_percentage) not in [0, 100]:
                    # Active go / stop commands
                    self.current_mode = set_mode
                    if set_mode == 1:
                        self.last_command_time = currentTime
                        self.start_percentage = newPercentage
                        self.send_wave(self.up_wave)
                    elif set_mode == -1:
                        self.last_command_time = currentTime
                        self.start_percentage = newPercentage
                        self.send_wave(self.down_wave)
                    else:
                        # No need to send stop if going to 0 or 100 because it will stop
                        # automatically
                        self.last_command_time = currentTime
                        self.start_percentage = newPercentage
                        self.send_wave(self.stop_wave)
                elif set_mode == 0 and int(self.target_percentage) in [0, 100]:
                    # Just let it stop itself - but note that we change mode
                    self.current_mode = set_mode
                    self.last_command_time = currentTime
                    self.start_percentage = newPercentage

        if newPercentage != self.current_percentage:
            self.current_percentage = newPercentage
            if changed_percentage_callback:
                new_pct = str(round(self.current_percentage))
                changed_percentage_callback(new_pct)

        if self.current_mode == 0 and set_mode == 0:
            #print('wait', IDLE_WAIT_TIME)
            return IDLE_WAIT_TIME
        else:
            #print('waiting', self.current_mode , set_mode , self.current_percentage, newPercentage, self.target_percentage)
            return min(ACTIVE_WAIT_TIME,
                    (self.full_open_time *
                        abs(self.target_percentage - self.current_percentage) / 100.0)
                    )


    def command(self, set_new_percentage):
        self.target_percentage = set_new_percentage

    def dispose(self):
        self.pi.wave_clear()
        

class WindowController:
    def __init__(self, pi, open_pin, close_pin, full_open_time=60.0):
        self.full_open_time = full_open_time
        self.target_opening = 0.0
        self.current_opening = 0.0
        self.current_mode = 0
        self.align_first = 0
        self.align_amount_remain = 0.0
        self.open_pin = open_pin
        self.close_pin = close_pin
        self.pi = pi
        self.last_command_time = 0
        self.start_opening = 0

        self.pi.set_mode(self.open_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.close_pin, pigpio.OUTPUT)

        self.pi.write(self.open_pin, pigpio.LOW)
        self.pi.write(self.close_pin, pigpio.LOW)

        self.minimum_adjustment_error = 1.8 * (ACTIVE_WAIT_TIME * 100.0 / full_open_time)


    def update(self, currentTime, changed_opening_callback):
        """Compute the window position, execute the required action.
        
        Returns the expected remaining time for the manoeuvre or maximum timeout."""

        newOpening = self.current_opening

        if self.current_mode != 0:
            elapsedTime = currentTime - self.last_command_time
            deltaOpening = 100.0 * elapsedTime * self.current_mode / self.full_open_time
            newOpening = max(0, min(100, self.start_opening + deltaOpening))

            if self.align_first == -1 and newOpening == 0.0:
                self.align_amount_remain += deltaOpening
            elif self.align_first == 1 and newOpening == 100.0:
                self.align_amount_remain -= deltaOpening
            if self.align_first and self.align_amount_remain < 0:
                self.align_first = 0

        if self.align_first != 0:
            self.current_mode = self.align_first
            self.last_command_time = currentTime
            self.start_opening = newOpening
        elif (self.target_opening - self.current_opening) > self.minimum_adjustment_error:
            self.current_mode = 1
            self.last_command_time = currentTime
            self.start_opening = newOpening
        elif (self.current_opening - self.target_opening) > self.minimum_adjustment_error:
            self.current_mode = -1
            self.last_command_time = currentTime
            self.start_opening = newOpening
        else:
            self.current_mode = 0

        if newOpening != self.current_opening:
            self.current_opening = newOpening
            if changed_opening_callback:
                new_pct = str(round(self.current_opening))
                changed_opening_callback(new_pct)

        self.pi.write(self.open_pin, pigpio.HIGH if self.current_mode == 1 else pigpio.LOW)
        self.pi.write(self.close_pin, pigpio.HIGH if self.current_mode == -1 else pigpio.LOW)

        if self.current_mode == 0:
            return IDLE_WAIT_TIME
        else:
            return max(0, min(ACTIVE_WAIT_TIME,
                (self.full_open_time * self.current_mode * (self.target_opening - self.current_opening) / 100.0)
                    ))


    def command(self, set_new_opening):
        alignFirst = 0
        if set_new_opening < 2:
            self.align_first = -1
            self.align_amount_remain = ALIGN_AMOUNT
        elif set_new_opening > 98:
            self.align_first = 1
            self.align_amount_remain = ALIGN_AMOUNT

        self.target_opening = set_new_opening


def main():
    client = mqtt.Client()
    newCommandCond = Condition()
    window = WindowController(pi, OPEN_PIN, CLOSE_PIN, 44.0)
    blinds = BlindsController(pi, RF_PIN,
            up_command="fffc349b6d36d369369269a49249a49a498",
            stop_command="fffc349b6d36d369369269a49249a69a698",
            down_command="fffc349b6d36d369369269a49249a4da4d8",
            packet_unit_time=57824e-6,
            rf_pulse_time=350e-6,
            num_repeat_packets=6,
            minimum_interval=1.0,
            make_long_pause=True,
            start_state=100,
            full_open_time=36.5)
    
    def mqttCallback(client, userdata, message):
        payload = message.payload.decode()
        topic = message.topic
        if topic == "soverom/vindu/aapning":
            target_p = parseCommand(payload, window.target_opening)
            with newCommandCond:
                window.command(target_p)
                newCommandCond.notify()

        elif topic == "soverom/rullgardin/aapning":
            target_p = parseCommand(payload, blinds.target_percentage)
            with newCommandCond:
                blinds.command(target_p)
                newCommandCond.notify()

    client.on_message = mqttCallback
    connected = False
    try:
        while not connected:
            time.sleep(5)
            try:
                client.connect(mqtt_server, mqtt_port, mqtt_reconnect_seconds)
                connected = True
            except IOError as e:
                print("client.connect:", e)

        def window_new_percentage_callback(new_pct):
            client.publish("soverom/vindu/aapningStatus", new_pct)

        def blinds_new_percentage_callback(new_pct):
            client.publish("soverom/rullgardin/aapningStatus", new_pct)

        client.loop_start()
        client.subscribe("soverom/vindu/aapning")
        client.subscribe("soverom/rullgardin/aapning")
        #client.subscribe("soverom/vindu/konf/tid") # Setting open time is not implemented
        client.publish("soverom/vindu/oppstart", "ON")

        while True:
            current_time = time.time()

            window_time = window.update(current_time, window_new_percentage_callback)
            blinds_time = blinds.update(current_time, blinds_new_percentage_callback)
            wait_time = min(window_time, blinds_time)
            with newCommandCond:
                newCommandCond.wait(timeout=wait_time)

    finally:
        pi.stop()
        client.loop_stop()
        blinds.dispose()

if __name__ == "__main__":
    main()
