#include <PubSubClient.h>

#include <Ethernet.h>

byte mac[] = {
  0xFE, 0xED, 0xFA, 0xAA, 0xAA, 0xAA
};
IPAddress ip(192, 168, 1, 226);

EthernetUDP udp;
EthernetClient client;
PubSubClient mqtt("192.168.1.8", 1883, client);

const int HEADER_LEN = 18, MAX_CHAN = 512;
byte packet[HEADER_LEN + MAX_CHAN];

const int UNIVERSE_0[] = {7,45,6,  5,3,4,  2,11,8 };
const int UNIVERSE_1[] = {12,13,9};
const int* ANT_UNIVERSE[] = {UNIVERSE_0, UNIVERSE_1};
const int N_CHAN[] = {9, 3};
const int N_UNIVERSE = sizeof(ANT_UNIVERSE) / sizeof(ANT_UNIVERSE[0]);

const int TEMP_PINS[] = {A0};
const int TEMP_FUDGE[] = {0};
const int N_TEMP_SMOOTH = 16;
const int TEMP_RATE_LIMIT_INTERVAL = 5000;
const int N_TEMP_IN = sizeof(TEMP_PINS) / sizeof(TEMP_PINS[0]);
const char* TEMP_TOPIC[] = {
  "stue/temp"
};
int temp_last_out[N_TEMP_IN];
long temp_last_time[N_TEMP_IN];
int temp_adc_samples[N_TEMP_IN][N_TEMP_SMOOTH];
long temp_adc_sum[N_TEMP_IN];
int temp_adc_index[N_TEMP_IN];
char temp_string_buffer[8];

const int INPUT_PINNA = 14;
int doorState = -1;


void setup() {
  analogReference(EXTERNAL);
  Ethernet.begin(mac, ip);
  udp.begin(0x1936);
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
  // 2. Analog in
  for (int i=0; i<N_TEMP_IN; ++i) {
    int val = analogRead(TEMP_PINS[i]) + TEMP_FUDGE[i];
    // volt = (5 * val / 1023)
    // cels = (volt - 0.5) * 100
    temp_adc_samples[i][temp_adc_index[i]] = val;
    temp_adc_sum[i] += val;
    temp_adc_index[i] = (temp_adc_index[i] + 1) % N_TEMP_SMOOTH;
    temp_adc_sum[i] -= temp_adc_samples[i][temp_adc_index[i]];
    int deciCelsius = (int)(((3300L * temp_adc_sum[i]) / 1023) / N_TEMP_SMOOTH - 500);
    if ((now - temp_last_time[i]) > TEMP_RATE_LIMIT_INTERVAL && deciCelsius != temp_last_out[i]) {
      dtostrf(deciCelsius * 0.1, 4, 1, temp_string_buffer);
      mqtt.publish(TEMP_TOPIC[i], temp_string_buffer);
      temp_last_out[i] = deciCelsius;
      temp_last_time[i] = now;
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
