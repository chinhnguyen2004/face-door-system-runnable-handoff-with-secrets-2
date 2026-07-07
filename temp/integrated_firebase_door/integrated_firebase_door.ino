/*
  Integrated ESP8266 door firmware

  Current hardware mapping:
    LCD I2C:
      SCL -> D1 / GPIO5
      SDA -> D2 / GPIO4
      VCC -> 5V/VIN or 3V3
      GND -> GND

    HC-SR04 4-pin ultrasonic sensor:
      VCC  -> 5V/VIN
      GND  -> GND shared with ESP8266
      TRIG -> D5 / GPIO14
      ECHO -> D6 / GPIO12 through level shifter/voltage divider to 3.3V

    Servo:
      DATA/SIGNAL -> D0 / GPIO16
      VCC         -> 5V/VIN or external 5V
      GND         -> GND shared with ESP8266

  Firebase flow:
    - If distance <= PERSON_THRESHOLD_CM, set /capture_request = true
    - Python listener sees flag, runs face recognition, writes /recognitions/esp01/result
    - ESP reads result:
        Quan / Tuan Anh / TEST_OK / KNOWN -> open servo
        Unknown / other -> keep closed
*/

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <Firebase_ESP_Client.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Servo.h>
#include "secrets.h"

// Pin mapping
const uint8_t LCD_SCL_PIN = D1;
const uint8_t LCD_SDA_PIN = D2;
const uint8_t TRIG_PIN    = D5;
const uint8_t ECHO_PIN    = D6;
const uint8_t SERVO_PIN   = D7;
const uint8_t LED_SUCCESS_PIN = D4; // Đèn trắng sáng khi đúng MSV (D4)
const uint8_t LED_FAIL_PIN    = D3; // Đèn đỏ sáng khi không phải/unknown (D3)

// Behavior config
const String DEVICE_ID = "esp01";
const float PERSON_THRESHOLD_CM = 50.0;
const unsigned long SENSOR_INTERVAL_MS = 300;
const unsigned long FIREBASE_INTERVAL_MS = 1000;
const unsigned long RECOGNITION_TIMEOUT_MS = 15000;
const unsigned long DOOR_OPEN_MS = 500;
const unsigned long ECHO_TIMEOUT_US = 30000UL;

const int SERVO_CLOSED_DEG = 0;
const int SERVO_OPEN_DEG   = 90;

// Firebase paths
String capturePath = "/capture_request";
String resultPath = "/recognitions/" + DEVICE_ID + "/result";
String resultTimePath = "/recognitions/" + DEVICE_ID + "/timestamp";
String distancePath = "/status/" + DEVICE_ID + "/distance_cm";
String doorPath = "/status/" + DEVICE_ID + "/doorOpen";
String lastSeenPath = "/status/" + DEVICE_ID + "/lastSeenMs";
String messagePath = "/status/" + DEVICE_ID + "/message";

FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

LiquidCrystal_I2C *lcd = nullptr;
bool lcdFound = false;
uint8_t lcdAddress = 0x27;

Servo doorServo;
bool doorOpen = false;
bool captureRequested = false;
unsigned long captureStartedMs = 0;
unsigned long doorOpenedMs = 0;
unsigned long lastSensorMs = 0;
unsigned long lastFirebaseMs = 0;
String lastResultTimestamp = "";
float lastDistance = -1.0;
int consecutiveOutCount = 0;

void lcdLine(uint8_t row, String text) {
  if (!lcdFound || lcd == nullptr) return;
  while (text.length() < 16) text += ' ';
  lcd->setCursor(0, row);
  lcd->print(text.substring(0, 16));
}

uint8_t scanI2CAddress() {
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) return addr;
  }
  return 0;
}

void setupLCD() {
  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN); // ESP8266 order: SDA, SCL
  delay(100);
  uint8_t found = scanI2CAddress();
  if (found != 0) {
    lcdAddress = found;
    lcd = new LiquidCrystal_I2C(lcdAddress, 16, 2);
    lcd->init();
    lcd->backlight();
    lcdFound = true;
    lcdLine(0, "Door system");
    lcdLine(1, "LCD OK 0x" + String(lcdAddress, HEX));
  }
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi connecting");
  lcdLine(0, "WiFi connecting");
  lcdLine(1, WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print('.');
  }
  Serial.println();
  Serial.print("WiFi OK IP=");
  Serial.println(WiFi.localIP());
  lcdLine(0, "WiFi OK");
  lcdLine(1, WiFi.localIP().toString());
}

void setupFirebase() {
  config.database_url = DATABASE_URL;
  config.signer.tokens.legacy_token = DATABASE_SECRET;
  
  // Giới hạn kích thước bộ đệm phản hồi để giải phóng RAM cho kết nối SSL
  fbdo.setResponseSize(512);

  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  Firebase.RTDB.setBool(&fbdo, doorPath.c_str(), false);
  Firebase.RTDB.setString(&fbdo, messagePath.c_str(), "ESP online");
  Firebase.RTDB.setBool(&fbdo, capturePath.c_str(), false);
  
  // Đọc timestamp hiện tại để tránh nhận diện nhầm kết quả cũ khi vừa khởi động
  if (Firebase.RTDB.getString(&fbdo, resultTimePath.c_str())) {
    lastResultTimestamp = fbdo.stringData();
    Serial.print("Initial result timestamp: ");
    Serial.println(lastResultTimestamp);
  }
}

float readDistanceCM() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (duration == 0) return -1.0;
  return duration / 58.0;
}

void openDoor() {
  if (!doorOpen) {
    // Chỉ attach khi cần quay để tránh nhiễu/quay liên tục do SSL
    doorServo.attach(SERVO_PIN);
    doorServo.write(SERVO_OPEN_DEG);
    delay(600); // Đợi servo quay xong
    doorServo.detach(); // Detach ngay để triệt tiêu tiếng rung/nhiễu
    
    doorOpen = true;
    doorOpenedMs = millis();
    Firebase.RTDB.setBool(&fbdo, doorPath.c_str(), true);
    Firebase.RTDB.setString(&fbdo, messagePath.c_str(), "Door opened");
    lcdLine(0, "Access OK");
    lcdLine(1, "Door opened");
    Serial.println("Door opened");
    
    // Bật đèn xanh D3, tắt đèn đỏ D4
    digitalWrite(LED_SUCCESS_PIN, HIGH);
    digitalWrite(LED_FAIL_PIN, LOW);
  }
}

void closeDoor() {
  if (doorOpen) {
    // Chỉ attach khi cần quay để tránh nhiễu/quay liên tục do SSL
    doorServo.attach(SERVO_PIN);
    doorServo.write(SERVO_CLOSED_DEG);
    delay(600); // Đợi servo quay xong
    doorServo.detach(); // Detach ngay để triệt tiêu tiếng rung/nhiễu
    
    doorOpen = false;
    Firebase.RTDB.setBool(&fbdo, doorPath.c_str(), false);
    Firebase.RTDB.setString(&fbdo, messagePath.c_str(), "Door closed");
    lcdLine(0, "Door closed");
    lcdLine(1, "Waiting");
    Serial.println("Door closed");
  }
  // Tắt đèn xanh D3 khi đóng cửa
  digitalWrite(LED_SUCCESS_PIN, LOW);
}

bool isAuthorizedResult(String result) {
  result.trim();
  result.toLowerCase();
  // Chấp nhận mọi kết quả nhận diện thành công (không phải unknown, failed hoặc rỗng)
  return result != "" && result != "unknown" && result != "waiting" && result != "failed";
}

void requestCaptureIfNeeded() {
  if (captureRequested) return;
  captureRequested = true;
  captureStartedMs = millis();
  Firebase.RTDB.setBool(&fbdo, capturePath.c_str(), true);
  Firebase.RTDB.setString(&fbdo, messagePath.c_str(), "Capture requested");
  lcdLine(0, "Person detected");
  lcdLine(1, "Face scan...");
  Serial.println("capture_request=true");
  
  // Tắt cả hai đèn khi bắt đầu lượt quét mới
  digitalWrite(LED_SUCCESS_PIN, LOW);
  digitalWrite(LED_FAIL_PIN, LOW);
}

void checkRecognitionResult() {
  if (Firebase.RTDB.getString(&fbdo, resultTimePath.c_str())) {
    String ts = fbdo.stringData();
    if (ts != lastResultTimestamp) {
      lastResultTimestamp = ts;
      if (Firebase.RTDB.getString(&fbdo, resultPath.c_str())) {
        String result = fbdo.stringData();
        Serial.print("Recognition result: ");
        Serial.println(result);

        captureRequested = false;
        Firebase.RTDB.setBool(&fbdo, capturePath.c_str(), false);

        if (isAuthorizedResult(result)) {
          openDoor();
        } else {
          closeDoor();
          Firebase.RTDB.setString(&fbdo, messagePath.c_str(), "Access denied: " + result);
          lcdLine(0, "Access denied");
          lcdLine(1, result);
          
          // Bật đèn đỏ D4 báo sai, tắt đèn xanh D3
          digitalWrite(LED_SUCCESS_PIN, LOW);
          digitalWrite(LED_FAIL_PIN, HIGH);
        }
      }
    }
  }

  if (captureRequested && millis() - captureStartedMs > RECOGNITION_TIMEOUT_MS) {
    captureRequested = false;
    Firebase.RTDB.setBool(&fbdo, capturePath.c_str(), false);
    Firebase.RTDB.setString(&fbdo, messagePath.c_str(), "Recognition timeout");
    lcdLine(0, "Face timeout");
    lcdLine(1, "Try again");
    Serial.println("Recognition timeout");
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("=== Integrated Firebase Door ===");

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  
  // Cấu hình chân đèn LED D3 và D4
  pinMode(LED_SUCCESS_PIN, OUTPUT);
  pinMode(LED_FAIL_PIN, OUTPUT);
  digitalWrite(LED_SUCCESS_PIN, LOW);
  digitalWrite(LED_FAIL_PIN, LOW);

  // Đặt vị trí ban đầu cho servo và giải phóng
  doorServo.attach(SERVO_PIN);
  doorServo.write(SERVO_CLOSED_DEG);
  delay(600);
  doorServo.detach();

  setupLCD();
  connectWiFi();
  setupFirebase();

  lcdLine(0, "System ready");
  lcdLine(1, "Waiting...");
}

void loop() {
  unsigned long now = millis();

  if (now - lastSensorMs >= SENSOR_INTERVAL_MS) {
    lastSensorMs = now;
    lastDistance = readDistanceCM();

    if (lastDistance < 0) {
      Serial.println("Distance: no echo");
      if (!captureRequested && !doorOpen) {
        lcdLine(0, "Distance:");
        lcdLine(1, "No echo");
      }
    } else {
      Serial.print("Distance: ");
      Serial.print(lastDistance, 1);
      Serial.println(" cm");

      if (!captureRequested && !doorOpen) {
        lcdLine(0, "Distance:");
        lcdLine(1, String(lastDistance, 1) + " cm");
      }

      if (lastDistance <= PERSON_THRESHOLD_CM) {
        consecutiveOutCount = 0; // Reset bộ đếm nếu phát hiện vật cản
        requestCaptureIfNeeded();
      } else {
        if (captureRequested) {
          consecutiveOutCount++;
          if (consecutiveOutCount >= 5) { // Cần 5 lần liên tiếp đo > 50cm (~1.5 giây) mới huỷ
            consecutiveOutCount = 0;
            captureRequested = false;
            Firebase.RTDB.setBool(&fbdo, capturePath.c_str(), false);
            Firebase.RTDB.setString(&fbdo, messagePath.c_str(), "Capture cancelled");
            lcdLine(0, "System ready");
            lcdLine(1, "Waiting...");
            Serial.println("capture_request=false (obstacle removed)");
          }
        }
      }
    }
  }

  // Tần suất gửi tin Firebase: 150ms khi đang quét nhận diện, 2500ms khi nhàn rỗi (tiết kiệm băng thông)
  unsigned long firebase_interval = captureRequested ? 150 : 2500;

  if (now - lastFirebaseMs >= firebase_interval) {
    lastFirebaseMs = now;
    if (lastDistance >= 0) Firebase.RTDB.setFloat(&fbdo, distancePath.c_str(), lastDistance);
    Firebase.RTDB.setInt(&fbdo, lastSeenPath.c_str(), (int)now);
    
    // Chỉ truy vấn kết quả nhận diện khi đang thực sự yêu cầu quét mặt
    if (captureRequested) {
      checkRecognitionResult();
    }
  }

  if (doorOpen && now - doorOpenedMs >= DOOR_OPEN_MS) {
    closeDoor();
  }
}
