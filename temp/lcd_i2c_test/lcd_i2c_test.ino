/*
  LCD I2C test for current ESP8266 wiring

  Wiring:
    LCD VCC -> 5V/VIN or 3V3, NOT D0
    LCD GND -> GND
    LCD SCL -> D1
    LCD SDA -> D2

  Serial Monitor: 115200 baud
*/

#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const uint8_t LCD_SCL_PIN = D1;  // GPIO5
const uint8_t LCD_SDA_PIN = D2;  // GPIO4

uint8_t lcdAddress = 0x27;
LiquidCrystal_I2C *lcd = nullptr;
bool lcdReady = false;

uint8_t scanI2C() {
  Serial.println("Scanning I2C on SDA=D2, SCL=D1...");
  uint8_t foundCount = 0;
  uint8_t firstAddr = 0;

  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      foundCount++;
      if (firstAddr == 0) firstAddr = addr;
      Serial.print("Found I2C device: 0x");
      if (addr < 16) Serial.print('0');
      Serial.println(addr, HEX);
    }
  }

  if (foundCount == 0) {
    Serial.println("No I2C device found. Check VCC/GND/SDA/SCL wiring.");
  } else {
    Serial.print("Total I2C devices: ");
    Serial.println(foundCount);
  }
  return firstAddr;
}

void lcdLine(uint8_t row, String text) {
  if (!lcdReady || lcd == nullptr) return;
  while (text.length() < 16) text += ' ';
  lcd->setCursor(0, row);
  lcd->print(text.substring(0, 16));
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("=== LCD I2C TEST ===");
  Serial.println("Wiring: D1=SCL, D2=SDA, VCC=5V/3V3, GND=GND");

  Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN); // ESP8266 order: SDA, SCL
  delay(100);

  uint8_t addr = scanI2C();
  if (addr != 0) {
    lcdAddress = addr;
    lcd = new LiquidCrystal_I2C(lcdAddress, 16, 2);
    lcd->init();
    lcd->backlight();
    lcdReady = true;

    Serial.print("LCD initialized at 0x");
    Serial.println(lcdAddress, HEX);

    lcdLine(0, "LCD OK addr 0x" + String(lcdAddress, HEX));
    lcdLine(1, "D1=SCL D2=SDA");
  }
}

void loop() {
  static unsigned long last = 0;
  static unsigned long counter = 0;

  if (millis() - last >= 1000) {
    last = millis();
    counter++;

    if (lcdReady) {
      lcdLine(0, "LCD OK 0x" + String(lcdAddress, HEX));
      lcdLine(1, "Count: " + String(counter));
    }

    Serial.print("LCD test running. Count=");
    Serial.print(counter);
    Serial.print(" lcdReady=");
    Serial.println(lcdReady ? "true" : "false");
  }
}
