#include <IRremote.h>

const int RELAY_PIN = 2;
const int TEMP_PINS[] = {A0, A1};
const int NUM_TEMP = 2;
const int IR_PIN = 3;
const int RF_RECV_PIN = 2;
const int RF_SEND_PIN = 4; 

const int FN_TEMP = 0x80, FN_SCREEN = 1, FN_IR = 3, FN_RF = 4;

int prevTemp[NUM_TEMP];
long prevReport = 0;

IRsend irsend;


void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH);
}

void loop() {
  int i;
  if (Serial) {
    if (Serial.available() >= 3) {
      if (Serial.read() != '!') return;
      int funcId = Serial.read();
      int len = Serial.read();
      byte data[len];
      Serial.readBytes(data, len);
      switch (funcId) {
        case FN_SCREEN:
          digitalWrite(RELAY_PIN, !data[0]);
          break;
        case FN_IR:
          irSend();
          break;
      }
      if (funcId >= FN_TEMP && funcId < FN_TEMP + NUM_TEMP) {
        prevTemp[funcId - FN_TEMP] = 0;
        prevReport = 0;
      }
    }
    long now = millis();
    if (now > prevReport + 60000) {
      for (i = 0; i<NUM_TEMP; ++i) {
        updateTemperature(i);
      }
      prevReport = now;
    }
  }
}

void updateTemperature(int i_temp) {
    int temp = analogRead(TEMP_PINS[i_temp]);
    if (temp != prevTemp[i_temp]) {
      Serial.write('!');
      Serial.write(FN_TEMP + i_temp);
      Serial.write(2);
      Serial.write(temp >> 8);
      Serial.write(temp & 0xFF);
      Serial.println(temp);
      prevTemp[i_temp] = temp;
      prevReport = millis();
    }
}

void irSend() {
  long code = 0;
  for (int i=0; i<4; ++i) {
    code << 8;
    code |= Serial.read();
  }
  irsend.sendNEC(code, 32);
}



