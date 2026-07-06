/*
  HC-SR04 4-pin ultrasonic sensor test + LCD I2C display

  Sensor type: 4-pin HC-SR04 / compatible ultrasonic sensor

  Current wiring:
    LCD I2C:
      VCC -> 5V/VIN or 3V3, NOT D0
      GND -> GND
      SCL -> D1 / GPIO5
      SDA -> D2 / GPIO4

    HC-SR04 4-pin sensor:
      VCC  -> 5V/VIN
      GND  -> GND shared with ESP8266
      TRIG -> D5 / GPIO14
      ECHO -> D6 / GPIO12 through voltage divider/level shifter to 3.3V

  Serial Monitor: 115200 baud

  Notes:
    - ESP8266 GPIO is 3.3V only. HC-SR04 ECHO can output 5V.
    - Use a voltage divider on ECHO, for example:
        ECHO -- 1kΩ -- D6 -- 2kΩ -- GND
*/

#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// LCD I2C pins on ESP8266 / NodeMCU
const uint8_t LCD_SCL_PIN = D1;  // GPIO5
const uint8_t LCD_SDA_PIN = D2;  // GPIO4

// HC-SR04 4-pin ultrasonic sensor pins
const uint8_t TRIG_PIN = D5;     // GPIO14
const uint8_t ECHO_PIN = D6;     // GPIO12

const unsigned long READ_INTERVAL_MS = 500;
const unsigned long ECHO_TIMEOUT_US  = 30000UL; // ~5 m max range

uint8_t lcdAddress = 0x27;
bool lcdFound = false;
LiquidCrystal_I2C *lcd = nullptr;

uint8_t scanI2CAddress() {
  Serial.println("Scanning I2C bus on SDA=D2, SCL=D1...");

  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("I2C device found at 0x");
      if (addr < 16) Serial.print('0');
      Serial.println(addr, HEX);
      return addr;
    }
  }

  Serial.println("No I2C device found. Check LCD VCC/GND/SDA/SCL.");
  return 0;
}

float readDistanceCM() {
  // Trigger pulse for 4-pin HC-SR04: LOW 2us -> HIGH 10us -> LOW
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (duration == 0) {
    return -1.0; // timeout / out of range / no echo
  }

  // Sound round trip. Distance cm ~= duration / 58.0
  return duration / 58.0;
}

void lcdPrintLine(uint8_t row, String text) {
  if (!lcdFound || lcd == nullptr) return;

  while (text.length() < 16) text += ' ';
  lcd->setCursor(0, row);
  lcd->print(text.substring(0, 16));
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("=== HC-SR04 4-PIN SENSOR TEST ===");
  Serial.println("LCD: D1=SCL, D2=SDA");
  Serial.println("Sensor: VCC=5V, GND=GND, TRIG=D5, ECHO=D6");
  Serial.println("WARNING: ECHO should be level-shifted to 3.3V for ESP8266.");

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  // ESP8266 Wire.begin order is Wire.begin(SDA, SCL)
  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);
  delay(100);

  uint8_t found = scanI2CAddress();
  if (found != 0) {
    lcdAddress = found;
    lcd = new LiquidCrystal_I2C(lcdAddress, 16, 2);
    lcd->init();
    lcd->backlight();
    lcdFound = true;

    Serial.print("LCD initialized at 0x");
    Serial.println(lcdAddress, HEX);

    lcdPrintLine(0, "HC-SR04 4-pin");
    lcdPrintLine(1, "TRIG D5 ECHO D6");
  } else {
    lcdFound = false;
  }

  delay(1000);
}

void loop() {
  static unsigned long lastRead = 0;
  if (millis() - lastRead < READ_INTERVAL_MS) return;
  lastRead = millis();

  float distance = readDistanceCM();

  if (distance < 0) {
    Serial.println("Distance: timeout / out of range / no echo");
    lcdPrintLine(0, "HC-SR04 4-pin");
    lcdPrintLine(1, "No echo");
  } else {
    Serial.print("Distance: ");
    Serial.print(distance, 1);
    Serial.println(" cm");

    lcdPrintLine(0, "Distance:");
    lcdPrintLine(1, String(distance, 1) + " cm");
  }
}
