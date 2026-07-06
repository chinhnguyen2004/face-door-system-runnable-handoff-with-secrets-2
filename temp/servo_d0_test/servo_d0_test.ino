/*
  Servo test for ESP8266 / NodeMCU

  Current request:
    Servo DATA/SIGNAL -> D0

  IMPORTANT wiring:
    Servo signal/data -> D0 / GPIO16
    Servo VCC         -> external 5V or VIN/5V, NOT D0
    Servo GND         -> GND shared with ESP8266

  Serial Monitor: 115200 baud

  Behavior:
    Moves servo safely between 0, 45, 90, 45 degrees.
    This avoids an aggressive full 180-degree sweep.
*/






#include <Arduino.h>
#include <Servo.h>

const uint8_t SERVO_PIN = D0;  // GPIO16

Servo testServo;
const int positions[] = {0, 45, 90, 45};
const int NUM_POSITIONS = sizeof(positions) / sizeof(positions[0]);
int indexPos = 0;

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("=== SERVO D0 TEST ===");
  Serial.println("Servo signal/data -> D0 / GPIO16");
  Serial.println("Servo VCC -> 5V/VIN/external 5V, GND common");

  testServo.attach(SERVO_PIN);
  delay(300);
  testServo.write(45);
  Serial.println("Initial position: 45 deg");
  delay(1000);
}

void loop() {
  int angle = positions[indexPos];
  testServo.write(angle);

  Serial.print("Servo write angle: ");
  Serial.println(angle);

  indexPos = (indexPos + 1) % NUM_POSITIONS;
  delay(1000);
}
