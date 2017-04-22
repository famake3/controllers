#include <PubSubClient.h>
#include <Ethernet2.h>
#include <EthernetUdp.h>
#include <EthernetClient.h>

byte mac[] = {
  0xFE, 0xED, 0xFA, 0xAA, 0xAA, 0xAA
};
IPAddress ip(192, 168, 1, 226);

EthernetUDP udp;
EthernetClient client;
PubSubClient mqtt("192.168.1.2", 1883, client);

const int HEADER_LEN = 18, MAX_CHAN = 512;
byte packet[HEADER_LEN + MAX_CHAN];

const int UNIVERSE_0[] = {7,45,6,  5,3,4,  2,11,8 };
const int UNIVERSE_1[] = {12,13,9};
const int* ANT_UNIVERSE[] = {UNIVERSE_0, UNIVERSE_1};
const int N_CHAN[] = {9, 3};
const int N_UNIVERSE = sizeof(ANT_UNIVERSE) / sizeof(ANT_UNIVERSE[0]);

const int INPUT_PINNA = 14;
int doorState = -1;

const int STROBE_PINNA = 41;

float strobe_freq = 10.0, strobe_power = 40.0;
float strobe_duration = 500.0;

const float DEF_STROBE_FREQ = 10.0;
const float DEF_STROBE_DURN = 500.0;
const float MAX_FREQ = 70.0;

long strobe_last_cmd = 0;
long strobe_last_blink_us = 0;
bool strobe_active = false;

void setup() {
  Ethernet.begin(mac, ip);
  udp.begin(0x1936);
  for (int uni=0; uni<N_UNIVERSE; ++uni) {
    const int* channels = ANT_UNIVERSE[uni];
    for (int ch=0; ch<N_CHAN[uni]; ++ch) {
      pinMode(channels[ch], OUTPUT);
    }
  }
  pinMode(INPUT_PINNA, INPUT_PULLUP);
  pinMode(STROBE_PINNA, OUTPUT);
  digitalWrite(STROBE_PINNA, HIGH);
  delayMicroseconds(2);
  digitalWrite(STROBE_PINNA, LOW);
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
          for (int ch=0; ch<min(N_CHAN[universe], length); ++ch) {
            analogWrite(channels[ch], packet[HEADER_LEN + ch]);
          }
          if (universe == 0 && length > N_CHAN[universe]) {
              // Extra channels in universe 0 are for stroboscope
              int num_chan = length - N_CHAN[universe];
              strobe_freq = (MAX_FREQ * packet[HEADER_LEN + ch]) / 256.0;
              strobe_active = true;
          }
        }
      }
    }
  }
  // 2. Strobe
  long now = micros();
  float period = 1e6 / strobe_freq;
  if (now - strobe_last_blink_us >= period) {
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


