#include <ESP8266WiFi.h>
#include <HX711.h>
#include <EEPROM.h>

const char* ssid     = "ZPF_002";
const char* password = "samheos666";

IPAddress local_ip(192, 168, 10, 200);
IPAddress gateway(192, 168, 10, 1);
IPAddress subnet(255, 255, 255, 0);

WiFiServer server(8266);
WiFiClient client;

#define LEFT_PIN   D1
#define RIGHT_PIN  D2

HX711 left_scale;
HX711 right_scale;

// EEPROM 地址分配（long 占 4 字节，float 占 4 字节）
#define LEFT_OFFSET_ADDR  0      // long
#define LEFT_FULL_ADDR    4      // float
#define RIGHT_OFFSET_ADDR 8      // long
#define RIGHT_FULL_ADDR   12     // float

float left_full = 1000.0;
float right_full = 1000.0;

// 读取 long 类型的 offset
long read_offset(int addr) {
  long val = 0;
  EEPROM.get(addr, val);
  // 如果偏移量异常（绝对值 > 10000000，即千万级），视为无效
  if (abs(val) > 10000000L) {
    val = 0;
  }
  return val;
}

// 写入 long 类型的 offset
void write_offset(int addr, long val) {
  EEPROM.put(addr, val);
  EEPROM.commit();
}

// 读取 float 类型的满量
float read_full(int addr) {
  float val = 1000.0;
  EEPROM.get(addr, val);
  if (val < 10.0) val = 1000.0;   // 至少 10g
  return val;
}

// 写入 float 类型的满量
void write_full(int addr, float val) {
  EEPROM.put(addr, val);
  EEPROM.commit();
}

void setup() {
  Serial.begin(115200);
  delay(10);

  pinMode(LEFT_PIN, OUTPUT);
  pinMode(RIGHT_PIN, OUTPUT);
  digitalWrite(LEFT_PIN, LOW);
  digitalWrite(RIGHT_PIN, LOW);

  // 初始化 HX711
  left_scale.begin(14, 12);   // DT=D5, SCK=D6
  right_scale.begin(13, 15);  // DT=D7, SCK=D8

  // 初始化 EEPROM
  EEPROM.begin(16);           // 我们只需要 16 字节
  long left_off = read_offset(LEFT_OFFSET_ADDR);
  long right_off = read_offset(RIGHT_OFFSET_ADDR);
  left_full = read_full(LEFT_FULL_ADDR);
  right_full = read_full(RIGHT_FULL_ADDR);

  // 设置偏移
  left_scale.set_offset(left_off);
  right_scale.set_offset(right_off);

  Serial.printf("Left offset: %ld, Left full: %.1f\n", left_off, left_full);
  Serial.printf("Right offset: %ld, Right full: %.1f\n", right_off, right_full);

  // WiFi
  WiFi.mode(WIFI_STA);
  WiFi.config(local_ip, gateway, subnet);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  server.begin();
  Serial.println("Server started");
}

void loop() {
  if (!client.connected()) {
    client = server.available();
  }

  if (client && client.connected()) {
    if (client.available()) {
      String cmd = client.readStringUntil('\n');
      cmd.trim();

      if (cmd == "LEFT_ON") {
        digitalWrite(LEFT_PIN, HIGH);
        client.print("OK\n");
      } else if (cmd == "LEFT_OFF") {
        digitalWrite(LEFT_PIN, LOW);
        client.print("OK\n");
      } else if (cmd == "RIGHT_ON") {
        digitalWrite(RIGHT_PIN, HIGH);
        client.print("OK\n");
      } else if (cmd == "RIGHT_OFF") {
        digitalWrite(RIGHT_PIN, LOW);
        client.print("OK\n");
      }
      else if (cmd == "GET_WATER") {
        float left_net = left_scale.get_units(3);
        float right_net = right_scale.get_units(3);
        float leftP = (left_net / left_full) * 100.0;
        float rightP = (right_net / right_full) * 100.0;
        if (leftP < 0) leftP = 0;
        if (leftP > 100) leftP = 100;
        if (rightP < 0) rightP = 0;
        if (rightP > 100) rightP = 100;
        client.printf("%.1f,%.1f\n", leftP, rightP);
      }
      else if (cmd == "TARE_LEFT") {
        left_scale.tare();                          // 硬件去皮
        long new_offset = left_scale.get_offset();  // 获取新偏移（long）
        write_offset(LEFT_OFFSET_ADDR, new_offset);
        Serial.printf("Left TARE offset: %ld\n", new_offset);
        client.print("OK\n");
      } else if (cmd == "TARE_RIGHT") {
        right_scale.tare();
        long new_offset = right_scale.get_offset();
        write_offset(RIGHT_OFFSET_ADDR, new_offset);
        Serial.printf("Right TARE offset: %ld\n", new_offset);
        client.print("OK\n");
      }
      else if (cmd == "SET_LEFT_FULL") {
        float net = left_scale.get_units(10);
        if (net > 10) {
          left_full = net;
          write_full(LEFT_FULL_ADDR, left_full);
          Serial.printf("Left FULL set to: %.1f\n", left_full);
          client.print("OK\n");
        } else {
          client.print("FAIL\n");
        }
      } else if (cmd == "SET_RIGHT_FULL") {
        float net = right_scale.get_units(10);
        if (net > 10) {
          right_full = net;
          write_full(RIGHT_FULL_ADDR, right_full);
          Serial.printf("Right FULL set to: %.1f\n", right_full);
          client.print("OK\n");
        } else {
          client.print("FAIL\n");
        }
      }
      else {
        client.print("UNKNOWN\n");
      }
    }
  } else {
    client = WiFiClient();
  }
  delay(10);
}