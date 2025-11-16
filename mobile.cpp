#include <WiFi.h>
#include <PubSubClient.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <SPI.h>
#include <MFRC522.h>

// #Change The "TagId" Respective To The Count Of ESP
const char* tagId = "TAG_001"; 
const char* ssid = "WIFI_SSID";
const char* password = "WIFI_PASSWORD";
const char* mqtt_server = "SERVER_IP"; 
const char* mqttScanTopic = "warehouse/scanner/rack_scan";

WiFiClient espClient;
PubSubClient client(espClient);
#define RST_PIN   4  // RST
#define SS_PIN    5  // SDA (CS)
// SCK PIN:  18
// MOSI PIN: 23
// MISO PIN: 19
MFRC522 mfrc522(SS_PIN, RST_PIN);
String lastScannedUID = "";
BLEServer* pServer = NULL;
#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect(tagId)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

void setup_ble() {
  BLEDevice::init(tagId);
  pServer = BLEDevice::createServer();
  BLEService *pService = pServer->createService(SERVICE_UUID);
  pService->start();
  pServer->getAdvertising()->start();
  Serial.println("Tag broadcasting BLE beacon...");
}

void setup() {
  Serial.begin(115200);
  Serial.print("Starting Mobile Tag: ");
  Serial.println(tagId);
  setup_ble();
  setup_wifi();
  client.setServer(mqtt_server, 1883);
  SPI.begin();
  mfrc522.PCD_Init();
  Serial.println("RFID Reader Ready. Hold tag near.");
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
  if ( ! mfrc522.PICC_IsNewCardPresent()) {
    delay(50);
    return;
  }
  if ( ! mfrc522.PICC_ReadCardSerial()) {
    delay(50);
    return;
  }
  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
     uid += (mfrc522.uid.uidByte[i] < 0x10 ? "0" : ""); 
     uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  if (uid != lastScannedUID) {
    lastScannedUID = uid;
    Serial.print("Scanned RFID UID: ");
    Serial.println(uid);
    char payload[100];
    snprintf(payload, sizeof(payload), 
             "{\"uid\": \"%s\", \"tag_id\": \"%s\"}", 
             uid.c_str(), 
             tagId);
    client.publish(mqttScanTopic, payload);
    Serial.println("Published scan data to MQTT.");
  }
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(1000); 
}