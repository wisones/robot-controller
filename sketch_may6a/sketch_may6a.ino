
/*
  ESP8266 Spray + HX711 Liquid Level Firmware
  WiFi: connects to chassis AP ZPF_002 / samheos666
  Static IP: 192.168.10.200
  TCP Port: 8266

  Wiring:
    Left spray relay:  D1 / GPIO5
    Right spray relay: D2 / GPIO4

    Left HX711:  DT=D5 / GPIO14, SCK=D6 / GPIO12
    Right HX711: DT=D7 / GPIO13, SCK=D0 / GPIO16

  PC commands:
    LEFT_ON / LEFT_OFF / RIGHT_ON / RIGHT_OFF -> OK
    TARE_LEFT / TARE_RIGHT -> OK or ERR:...
    SET_LEFT_FULL / SET_RIGHT_FULL -> OK or ERR:...
    GET_WATER -> leftPercent,rightPercent
    GET_RAW -> diagnostic raw values
    STATUS -> WiFi/server status
    RESET_CALIB -> clear calibration
    PING -> PONG
    RST -> OK then restart
*/

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <EEPROM.h>
#include "HX711.h"

// ===================== WiFi Config =====================
const char* WIFI_SSID = "ZPF_002";
const char* WIFI_PASS = "samheos666";

IPAddress LOCAL_IP(192, 168, 10, 200);
IPAddress GATEWAY(192, 168, 10, 1);
IPAddress SUBNET(255, 255, 255, 0);
IPAddress DNS1(192, 168, 10, 1);

const uint16_t TCP_PORT = 8266;
WiFiServer server(TCP_PORT);
WiFiClient client;

// ===================== Pin Config =====================
#define LEFT_RELAY_PIN   D1
#define RIGHT_RELAY_PIN  D2

#define LEFT_HX_DT       D5
#define LEFT_HX_SCK      D6

#define RIGHT_HX_DT      D7
#define RIGHT_HX_SCK     D0

// Most relay boards are active-low.
// If ON/OFF is reversed, change to false and re-upload.
const bool RELAY_ACTIVE_LOW = false;

// If the relay still turns on during boot, set this true.
// It delays relay pin activation until WiFi/server is ready,
// while keeping pins in a safe inactive state as early as possible.
const bool EXTRA_SAFE_BOOT = true;

// ===================== HX711 =====================
HX711 hxLeft;
HX711 hxRight;

struct CalibData {
  uint32_t magic;
  long leftZero;
  long leftFull;
  long rightZero;
  long rightFull;
};

const uint32_t CALIB_MAGIC = 0x20260524;
CalibData calib;

long leftRaw = 0;
long rightRaw = 0;
bool leftOk = false;
bool rightOk = false;

float leftPercent = 0.0;
float rightPercent = 0.0;

unsigned long lastSampleMs = 0;
const unsigned long SAMPLE_INTERVAL_MS = 120;

unsigned long lastWifiTryMs = 0;
const unsigned long WIFI_RETRY_INTERVAL_MS = 5000;

// ===================== Helpers =====================
void relayWrite(uint8_t pin, bool on) {
  if (RELAY_ACTIVE_LOW) {
    digitalWrite(pin, on ? LOW : HIGH);
  } else {
    digitalWrite(pin, on ? HIGH : LOW);
  }
}

void allSprayOff() {
  relayWrite(LEFT_RELAY_PIN, false);
  relayWrite(RIGHT_RELAY_PIN, false);
}

float calcPercent(long raw, long zero, long full) {
  long span = full - zero;
  if (labs(span) < 100) {
    return 0.0;
  }

  float p = (float)(raw - zero) * 100.0f / (float)span;
  if (p < 0.0f) p = 0.0f;
  if (p > 100.0f) p = 100.0f;
  return p;
}

void saveCalib() {
  EEPROM.put(0, calib);
  EEPROM.commit();
}

void loadCalib() {
  EEPROM.begin(128);
  EEPROM.get(0, calib);
  if (calib.magic != CALIB_MAGIC) {
    calib.magic = CALIB_MAGIC;
    calib.leftZero = 0;
    calib.leftFull = 0;
    calib.rightZero = 0;
    calib.rightFull = 0;
    saveCalib();
  }
}

void sampleHX711() {
  unsigned long now = millis();
  if (now - lastSampleMs < SAMPLE_INTERVAL_MS) return;
  lastSampleMs = now;

  leftOk = hxLeft.is_ready();
  if (leftOk) {
    leftRaw = hxLeft.read();
    leftPercent = calcPercent(leftRaw, calib.leftZero, calib.leftFull);
  }

  rightOk = hxRight.is_ready();
  if (rightOk) {
    rightRaw = hxRight.read();
    rightPercent = calcPercent(rightRaw, calib.rightZero, calib.rightFull);
  }
}

void sendLine(const String& s) {
  if (client && client.connected()) {
    client.print(s);
    client.print('\n');
    client.flush();
  }
}

String rawStatusString() {
  String s;
  s.reserve(220);
  s += "WIFI=" + String(WiFi.status() == WL_CONNECTED ? 1 : 0);
  s += ",IP=" + WiFi.localIP().toString();
  s += ",LRAW=" + String(leftRaw);
  s += ",RRAW=" + String(rightRaw);
  s += ",LOK=" + String(leftOk ? 1 : 0);
  s += ",ROK=" + String(rightOk ? 1 : 0);
  s += ",L0=" + String(calib.leftZero);
  s += ",LF=" + String(calib.leftFull);
  s += ",R0=" + String(calib.rightZero);
  s += ",RF=" + String(calib.rightFull);
  s += ",LP=" + String(leftPercent, 1);
  s += ",RP=" + String(rightPercent, 1);
  return s;
}

void printStatusToSerial() {
  Serial.println(rawStatusString());
}

void startWifiIfNeeded() {
  if (WiFi.status() == WL_CONNECTED) return;

  unsigned long now = millis();
  if (now - lastWifiTryMs < WIFI_RETRY_INTERVAL_MS) return;
  lastWifiTryMs = now;

  Serial.print("Connecting to AP ");
  Serial.println(WIFI_SSID);

  WiFi.disconnect();
  WiFi.mode(WIFI_STA);
  WiFi.config(LOCAL_IP, GATEWAY, SUBNET, DNS1);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

void handleCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  if (cmd.length() == 0) return;

  Serial.print("CMD: ");
  Serial.println(cmd);

  if (cmd == "LEFT_ON") {
    relayWrite(LEFT_RELAY_PIN, true);
    sendLine("OK");
  } else if (cmd == "LEFT_OFF") {
    relayWrite(LEFT_RELAY_PIN, false);
    sendLine("OK");
  } else if (cmd == "RIGHT_ON") {
    relayWrite(RIGHT_RELAY_PIN, true);
    sendLine("OK");
  } else if (cmd == "RIGHT_OFF") {
    relayWrite(RIGHT_RELAY_PIN, false);
    sendLine("OK");

  } else if (cmd == "TARE_LEFT") {
    sampleHX711();
    if (leftOk) {
      calib.leftZero = leftRaw;
      saveCalib();
      leftPercent = calcPercent(leftRaw, calib.leftZero, calib.leftFull);
      sendLine("OK");
    } else {
      sendLine("ERR:LEFT_HX711_NOT_READY");
    }
  } else if (cmd == "TARE_RIGHT") {
    sampleHX711();
    if (rightOk) {
      calib.rightZero = rightRaw;
      saveCalib();
      rightPercent = calcPercent(rightRaw, calib.rightZero, calib.rightFull);
      sendLine("OK");
    } else {
      sendLine("ERR:RIGHT_HX711_NOT_READY");
    }

  } else if (cmd == "SET_LEFT_FULL") {
    sampleHX711();
    if (leftOk) {
      calib.leftFull = leftRaw;
      saveCalib();
      leftPercent = calcPercent(leftRaw, calib.leftZero, calib.leftFull);
      sendLine("OK");
    } else {
      sendLine("ERR:LEFT_HX711_NOT_READY");
    }
  } else if (cmd == "SET_RIGHT_FULL") {
    sampleHX711();
    if (rightOk) {
      calib.rightFull = rightRaw;
      saveCalib();
      rightPercent = calcPercent(rightRaw, calib.rightZero, calib.rightFull);
      sendLine("OK");
    } else {
      sendLine("ERR:RIGHT_HX711_NOT_READY");
    }

  } else if (cmd == "GET_WATER") {
    sendLine(String(leftPercent, 1) + "," + String(rightPercent, 1));

  } else if (cmd == "GET_RAW") {
    sendLine(rawStatusString());

  } else if (cmd == "STATUS") {
    String s;
    s += "SSID=" + String(WIFI_SSID);
    s += ",WIFI=" + String(WiFi.status() == WL_CONNECTED ? 1 : 0);
    s += ",IP=" + WiFi.localIP().toString();
    s += ",PORT=" + String(TCP_PORT);
    s += ",CLIENT=" + String(client && client.connected() ? 1 : 0);
    sendLine(s);

  } else if (cmd == "RESET_CALIB" || cmd == "CLEAR_CALIB") {
    calib.magic = CALIB_MAGIC;
    calib.leftZero = 0;
    calib.leftFull = 0;
    calib.rightZero = 0;
    calib.rightFull = 0;
    saveCalib();
    leftPercent = 0;
    rightPercent = 0;
    sendLine("OK");

  } else if (cmd == "PING") {
    sendLine("PONG");

  } else if (cmd == "RST") {
    sendLine("OK");
    delay(100);
    ESP.restart();

  } else {
    sendLine("ERR:UNKNOWN_CMD");
  }
}

String rxLine;

void setup() {
  // First instruction after boot: force relays OFF.
  pinMode(LEFT_RELAY_PIN, OUTPUT);
  pinMode(RIGHT_RELAY_PIN, OUTPUT);
  allSprayOff();

  Serial.begin(115200);
  delay(80);
  Serial.println();
  Serial.println("ESP8266 Spray HX711 ZPF_002 Firmware");

  loadCalib();

  hxLeft.begin(LEFT_HX_DT, LEFT_HX_SCK);
  hxRight.begin(RIGHT_HX_DT, RIGHT_HX_SCK);

  pinMode(LEFT_HX_SCK, OUTPUT);
  pinMode(RIGHT_HX_SCK, OUTPUT);
  digitalWrite(LEFT_HX_SCK, LOW);
  digitalWrite(RIGHT_HX_SCK, LOW);

  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  WiFi.mode(WIFI_STA);
  WiFi.config(LOCAL_IP, GATEWAY, SUBNET, DNS1);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("Connecting WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    allSprayOff();
    sampleHX711();
    delay(250);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi connected, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi connect timeout. Firmware will keep retrying.");
  }

  server.begin();
  server.setNoDelay(true);
  Serial.print("TCP server listening on port ");
  Serial.println(TCP_PORT);

  allSprayOff();
}

void loop() {
  sampleHX711();
  startWifiIfNeeded();

  static unsigned long lastSerialMs = 0;
  if (millis() - lastSerialMs > 2500) {
    lastSerialMs = millis();
    printStatusToSerial();
  }

  if (!client || !client.connected()) {
    WiFiClient newClient = server.available();
    if (newClient) {
      if (client) client.stop();
      client = newClient;
      client.setNoDelay(true);
      rxLine = "";
      Serial.println("TCP client connected");
    }
  }

  if (client && client.connected()) {
    while (client.available()) {
      char c = (char)client.read();
      if (c == '\r') continue;
      if (c == '\n') {
        handleCommand(rxLine);
        rxLine = "";
      } else {
        if (rxLine.length() < 100) {
          rxLine += c;
        } else {
          rxLine = "";
          sendLine("ERR:LINE_TOO_LONG");
        }
      }
    }
  }

  delay(1);
}

