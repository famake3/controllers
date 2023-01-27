#include <PubSubClient.h>

#include <Ethernet.h>

#include <Wire.h>
#include "Adafruit_MCP9808.h"

byte mac[] = {
  0xFE, 0xED, 0xFA, 0xAA, 0xAA, 0xAA
};
IPAddress ip(192, 168, 1, 226);

EthernetUDP udp;
EthernetClient client;
PubSubClient mqtt("192.168.1.8", 1883, client);
Adafruit_MCP9808 tempsensor = Adafruit_MCP9808();

const int HEADER_LEN = 18, MAX_CHAN = 512;
byte packet[HEADER_LEN + MAX_CHAN];

const int UNIVERSE_0[] = {7,45,6,  5,3,44,  2,11,8 };
const int UNIVERSE_1[] = {12,13,9};
const int* ANT_UNIVERSE[] = {UNIVERSE_0, UNIVERSE_1};
const int N_CHAN[] = {9, 3};
const int N_UNIVERSE = sizeof(ANT_UNIVERSE) / sizeof(ANT_UNIVERSE[0]);

const int TEMP_RATE_LIMIT_INTERVAL = 5000;
const char* TEMP_TOPIC = "stue/temp";
float temp_last_out;
long temp_last_time;
char temp_string_buffer[8];

const int INPUT_PINNA = 14;
int doorState = -1;


void setup() {
  Ethernet.begin(mac, ip);
  udp.begin(0x1936);
  
  tempsensor.begin(0x18);
    // Mode Resolution SampleTime
  //  0    0.5°C       30 ms
  //  1    0.25°C      65 ms
  //  2    0.125°C     130 ms
  //  3    0.0625°C    250 ms
  tempsensor.setResolution(3);
  for (int uni=0; uni<N_UNIVERSE; ++uni) {
    const int* channels = ANT_UNIVERSE[uni];
    for (int ch=0; ch<N_CHAN[uni]; ++ch) {
      pinMode(channels[ch], OUTPUT);
    }
  }
  pinMode(INPUT_PINNA, INPUT_PULLUP);
}

void loop() {
  if (!mqtt.connected()) {
    delay(1000);
    mqtt.connect("Stue");
    return;
  }
  // 1. Lys
  int packetSize = udp.parsePacket();
  if (packetSize > 0 && packetSize <= HEADER_LEN + 512) {
    int nread = udp.read(packet, packetSize);
    if (nread == packetSize) {
      int op = getTwo(packet, 8);
      int universe = getTwoTwo(packet, 14);
      int length = getTwo(packet, 16);
      
      if (length == nread - HEADER_LEN) {
        // Art-Net packet
        if (universe < N_UNIVERSE) {
          const int* channels = ANT_UNIVERSE[universe];
          int ch;
          for (ch=0; ch<min(N_CHAN[universe], length); ++ch) {
            analogWrite(channels[ch], packet[HEADER_LEN + ch]);
          }
        }
      }
    }
  }
  long now = millis();
  if ((now - temp_last_time) > TEMP_RATE_LIMIT_INTERVAL) {
    
    float tempC = tempsensor.readTempC();
    if (tempC != temp_last_out) {
      dtostrf(tempC, 4, 1, temp_string_buffer);
      mqtt.publish(TEMP_TOPIC, temp_string_buffer);
      temp_last_out = tempC;
      temp_last_time = now;
    }
  }

  // 3. Input: door fooler
  int door = digitalRead(INPUT_PINNA) == HIGH ? 1 : 0;
  if (door != doorState) {
    mqtt.publish("stue/skapDoor", door ? "OPEN" : "CLOSED");
    doorState = door;
  }
  mqtt.loop();
}

int getTwo(byte* data, int index) {
  return (data[index] << 8) + (data[index+1]);
}

int getTwoTwo(byte* data, int index) {
  return (data[index+1] << 8) + (data[index]);
}
