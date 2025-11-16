#include <WiFi.h>
#include <PubSubClient.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <BLEUtils.h>

const char* ssid = "WIFI_SSID";
const char* password = "WIFI_PASSWORD";
const char* mqtt_server = "SERVER_IP"; 
WiFiClient espClient;
PubSubClient client(espClient);
// Change "ANCHORID" Respective To The Count
const char* ANCHOR_ID = "ANCHOR_1";
float anchorX = 0.0;// change axis
float anchorY = 0.0;//change axis

const char* TAG_PREFIX = "TAG_"; 
int scanTime = 2; 
BLEScan* pBLEScan;
const int MEASURED_POWER = -59; 
const float N_FACTOR = 2.0; //Factor Here For Good Environment

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
    if (client.connect(ANCHOR_ID)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}


class MyAdvertisedDeviceCallbacks: public BLEAdvertisedDeviceCallbacks {

  void onResult(BLEAdvertisedDevice advertisedDevice) {
    if (advertisedDevice.haveName() && advertisedDevice.getName().startsWith(TAG_PREFIX)) {
      String tag_id = advertisedDevice.getName();
      int rssi = advertisedDevice.getRSSI();
      Serial.print("Found Tag: ");
      Serial.print(tag_id);
      Serial.print(" | RSSI: ");
      Serial.println(rssi);
      // Formula: distance = 10 ^ ((Measured Power - RSSI) / (10 * N))
      float distance = pow(10, ((float)(MEASURED_POWER - rssi) / (10 * N_FACTOR)));
      char payload[120];
      snprintf(payload, sizeof(payload), "%s,%.2f,%.2f,%.2f,%d,%s",
               ANCHOR_ID,
               anchorX,
               anchorY,
               distance,
               rssi,
               tag_id.c_str());
      char topic[100];
      snprintf(topic, sizeof(topic), "warehouse/anchors/%s/data", ANCHOR_ID);
      client.publish(topic, payload);
      Serial.print("Published to MQTT: ");
      Serial.println(payload);
    }
  }
};

void setup() {
  Serial.begin(115200);
  Serial.println("Starting ESP32 Anchor...");
  Serial.print("Anchor ID: ");
  Serial.println(ANCHOR_ID);
  Serial.print("Position: (");
  Serial.print(anchorX);
  Serial.print(", ");
  Serial.print(anchorY);
  Serial.println(")");
  setup_wifi();
  client.setServer(mqtt_server, 1883);
  BLEDevice::init("");
  pBLEScan = BLEDevice::getScan();
  pBLEScan->setAdvertisedDeviceCallbacks(new MyAdvertisedDeviceCallbacks());
  pBLEScan->setActiveScan(true);
  pBLEScan->setInterval(100);
  pBLEScan->setWindow(99);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
  Serial.println("Starting BLE scan...");
  pBLEScan->start(scanTime, false);
  Serial.println("Scan done.");
  delay(1000); 
}