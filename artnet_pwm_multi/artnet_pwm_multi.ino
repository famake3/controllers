#include <PubSubClient.h>
#include <Ethernet2.h>
#include <EthernetUdp.h>
#include <EthernetClient.h>

byte mac[] = {
  0xFE, 0xED, 0xFA, 0xAA, 0xAA, 0xAA
};
IPAddress ip(192, 168, 1, 225);

EthernetUDP udp;
EthernetClient client;
PubSubClient mqtt("192.168.1.2", 1883, client);

const int HEADER_LEN = 18, MAX_CHAN = 512;
byte packet[HEADER_LEN + MAX_CHAN];

const int UNIVERSE_0[] = {45,3,4,5,6,7,8,9};
const int UNIVERSE_1[] = {10,11,12,13};
const int* ANT_UNIVERSE[] = {UNIVERSE_0, UNIVERSE_1};
const int N_CHAN[] = {8, 4};
const int N_UNIVERSE = sizeof(ANT_UNIVERSE) / sizeof(ANT_UNIVERSE[0]);

const int STROBE_PINNA = 0;

const int INPUT_PINNA = 1;
int doorStatus = -1;

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
  pinMode(STROBE_PINNA, INPUT); // TODO output sjekk pin
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
      int universe = getTwo(packet, 14);
      int length = getTwo(packet, 16);

      if (length == nread - HEADER_LEN) {
        // Art-Net packet
        if (universe < N_UNIVERSE) {
          int* channels = ANT_UNIVERSE[universe];
          for (int ch=0; ch<min(N_CHAN[universe], length); ++ch) {
            analogWrite(channels[ch], packet[HEADER_LEN + ch]);
          }
        }
      }
    }
  }
  // 2. Input: door fooler
  int door = digitalRead(INPUT_PINNA) == HIGH ? 1 : 0;
  if (door != doorStatus) {
    //mqtt.publish();
    doorStatus = door;
  }
  
}

int getTwo(byte* data, int index) {
  return data[index] + (data[index] << 8);
}


