#include <IRremote.h>

const int RELAYPIN = 2;
const int TEMPPIN = A0;

const int FN_SCREEN = 1, FN_TEMP = 2, FN_IR = 3;

int prevTemp = -1;
long prevReport = 0;

IRsend irsend;

void setup() {
  Serial.begin(115200);
  pinMode(RELAYPIN, OUTPUT);
  digitalWrite(RELAYPIN, HIGH);
}

void loop() {
  if (Serial) {
    if (Serial.available() >= 3) {
      if (Serial.read() != '!') return;
      int funcId = Serial.read();
      int len = Serial.read();
      byte data[len];
      Serial.readBytes(data, len);
      switch (funcId) {
        case FN_SCREEN:
          digitalWrite(RELAYPIN, !data[0]);
          break;
        case FN_TEMP:
          prevTemp = -1;
          prevReport = 0;
          break;
        case FN_IR:
          irSend();
          break;
      }
    }
    updateTemperature();
  }
}

void updateTemperature() {
    int temp = analogRead(TEMPPIN);
    if (temp != prevTemp && millis() > prevReport + 60000) {
      Serial.write('!');
      Serial.write(FN_TEMP);
      Serial.write(2);
      Serial.write(temp >> 8);
      Serial.write(temp & 0xFF);
      prevTemp = temp;
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



