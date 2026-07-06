#include <Arduino.h>

// Định nghĩa chân đèn LED D3 và D4 trên NodeMCU
const uint8_t LED_D3 = D3; // Chân GPIO0
const uint8_t LED_D4 = D4; // Chân GPIO2

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== LED D3 & D4 Test Started ===");

  // Cấu hình chân D3 và D4 làm ngõ ra (OUTPUT)
  pinMode(LED_D3, OUTPUT);
  pinMode(LED_D4, OUTPUT);
  
  // Tắt cả hai đèn lúc đầu
  digitalWrite(LED_D3, LOW);
  digitalWrite(LED_D4, LOW);
}

void loop() {
  // Bước 1: Chỉ bật đèn D3 (Tắt D4) trong 2 giây
  Serial.println("LED D3 (Success) ON | LED D4 (Fail) OFF");
  digitalWrite(LED_D3, HIGH);
  digitalWrite(LED_D4, LOW);
  delay(2000);

  // Bước 2: Chỉ bật đèn D4 (Tắt D3) trong 2 giây
  Serial.println("LED D3 (Success) OFF | LED D4 (Fail) ON");
  digitalWrite(LED_D3, LOW);
  digitalWrite(LED_D4, HIGH);
  delay(2000);

  // Bước 3: Bật CẢ HAI đèn trong 2 giây
  Serial.println("BOTH LEDs ON");
  digitalWrite(LED_D3, HIGH);
  digitalWrite(LED_D4, HIGH);
  delay(2000);

  // Bước 4: Tắt CẢ HAI đèn trong 2 giây
  Serial.println("BOTH LEDs OFF");
  digitalWrite(LED_D3, LOW);
  digitalWrite(LED_D4, LOW);
  delay(2000);
}
