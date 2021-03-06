#include "settings.h"

#include <HomeEasy.h>

const int FN_TEMP = 0x80, FN_SWITCH = 1, FN_INPUTSWITCH = 0x40;

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
const int TEMP_PINS[] = {A0, A1, A2};
const int NUM_TEMP = 3;
const int IR_PIN = 3;

const int N_SAMPLES = 10; // Even number
long tempSampleTime;
int tempReportCounter = 0;
int tempSamples[NUM_TEMP][N_SAMPLES] = {};

const int INPUTSWITCH_PINS[] = {4,5};
const int INPUTSWITCH_MODE[] = {INPUT, INPUT_PULLUP};
const int N_INPUT_SWITCHES = sizeof(INPUTSWITCH_PINS) / sizeof(int);
bool inputSwitchState[N_INPUT_SWITCHES] = {};

void setup() {
  Serial.begin(9600);
  pinMode(SWITCH_PIN, OUTPUT);
  digitalWrite(SWITCH_PIN, HIGH);
  for (int i=0; i<N_INPUT_SWITCHES; ++i) 
    pinMode(INPUTSWITCH_PINS[i], INPUTSWITCH_MODE[i]);
#ifdef ENABLE_NEXA_RF
  pinMode(13, OUTPUT);
  digitalWrite(13, LOW);
  homeEasy = HomeEasy();
  homeEasy.registerAdvancedProtocolHandler(receivedHomeEasy);
  homeEasy.init();
  tempSampleTime = millis();
#endif
}

void loop() {
  int i;
  long now = millis();
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
        updateTemperature(funcId-FN_TEMP, analogRead(TEMP_PINS[funcId-FN_TEMP]));
      }
      if (funcId >= FN_INPUTSWITCH && funcId < FN_INPUTSWITCH + N_INPUT_SWITCHES) {
        sendSwitchState(funcId-FN_INPUTSWITCH);
      }
    }
    // Rate-limit to 1/sec
    
    if ((now - tempSampleTime) >= 0) {
      tempSampleTime += 600;
      for (int t = 0; t<NUM_TEMP; ++t) {
        int val = analogRead(TEMP_PINS[t]);
        for (i=0; i<N_SAMPLES && val < tempSamples[t][i]; ++i);
        int prev = val;
        for (; i<N_SAMPLES; ++i) {
          int cur = tempSamples[t][i];
          tempSamples[t][i] = prev;
          prev = cur;
        }
      }
      if (++tempReportCounter == N_SAMPLES) {
        for (int t = 0; t<NUM_TEMP; ++t) {
          long sum = 0;
          for (i=1; i<N_SAMPLES-1; ++i) {
            sum += tempSamples[t][i];
          }
          float val = sum / (N_SAMPLES-2.0);
          updateTemperature(t, val);
          for (i=0; i<N_SAMPLES; ++i) 
            tempSamples[t][i] = 0;
        }
        tempReportCounter = 0;
      }
    }
  }

  for (int i=0; i<N_INPUT_SWITCHES; ++i) {
    bool newState = (byte)digitalRead(INPUTSWITCH_PINS[i]);
    if (newState != inputSwitchState[i]) {
      inputSwitchState[i] = newState;
      sendSwitchState(i);
    }
  }
}


void sendSwitchState(int index) {
  Serial.write('!');
  Serial.write(FN_INPUTSWITCH + index);
  Serial.write(1);
  Serial.write(inputSwitchState[index]);
}


void updateTemperature(int i_temp, float val) {
    float volt = (5.0 * val / 1023.0);
    float real_temp = (volt - 0.5) * 100.0;
    int temp = round(10 * real_temp);
    Serial.write('!');
    Serial.write(FN_TEMP + i_temp);
    Serial.write(2);
    Serial.write(temp >> 8);
    Serial.write(temp & 0xFF);
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

