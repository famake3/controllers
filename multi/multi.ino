#include "settings.h"

#include <HomeEasy.h>

const int FN_TEMP = 0x80, FN_SWITCH = 1;


#ifdef ENABLE_IR
const int FN_IR = 3;
IRsend irsend;
#endif

#ifdef ENABLE_NEXA_RF
const int FN_RF = 4;
HomeEasy homeEasy;
#endif

#ifdef ENABLE_RF2_TX
const int FN_RF_2 = 5;
RCSwitch mySwitch = RCSwitch();
#endif

const int SWITCH_PIN = 2;
const int TEMP_PINS[] = {A0, A1};
const int NUM_TEMP = 2;
const int IR_PIN = 3;

int prevTemp[NUM_TEMP];
long prevReport = 0;


void setup() {
  Serial.begin(9600);
  pinMode(SWITCH_PIN, OUTPUT);
  digitalWrite(SWITCH_PIN, HIGH);
#ifdef ENABLE_NEXA_RF
  pinMode(13, OUTPUT);
  digitalWrite(13, LOW);
  homeEasy = HomeEasy();
  homeEasy.registerAdvancedProtocolHandler(receivedHomeEasy);
  homeEasy.init();
#endif
}

void loop() {
  int i;
  if (Serial) {
    if (Serial.available() >= 3) {
      if (Serial.read() != '!') return;
      int funcId = Serial.read();
      int len = Serial.read();
      if (len > 16) return;
      byte data[len];
      Serial.readBytes(data, len);
      switch (funcId) {
        case FN_SWITCH:
          digitalWrite(SWITCH_PIN, !data[0]);
          break;
#ifdef ENABLE_IR
        case FN_IR:
          if (len == 4)
            irSend(data);
          break;
#endif
#ifdef ENABLE_NEXA_RF
        case FN_RF:
          if (len == 8)
            rfTransmit(data);
          break;
#endif
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

#ifdef ENABLE_IR
void irSend(byte* data) {
  long code = readLong(data);
  irsend.sendNEC(code, 32);
}
#endif

#ifdef ENABLE_NEXA_RF
void rfTransmit(byte* data) {
  long sender = readLong(data);
  int recipient = (data[4] << 8) | data[5];
  homeEasy.sendAdvancedProtocolMessage(sender, recipient, data[6], data[7]);
}

void receivedHomeEasy(unsigned long sender, unsigned int recipient, bool on, bool group) {
  Serial.write('!');
  Serial.write(FN_RF);
  Serial.write(8);
  writeLong(sender);
  Serial.write(recipient >> 8);
  Serial.write(recipient);
  Serial.write(on);
  Serial.write(group);
}
#endif

void writeLong(long l) {
  Serial.write(l >> 24);
  Serial.write(l >> 16);
  Serial.write(l >> 8);
  Serial.write(l);
}

unsigned long readLong(byte* d) {
  unsigned long l = 0;
  for (int i=0; i<4; ++i) {
    l = l << 8;
    l |= (d[i] & 0xFF);
  }
  return l;
}

