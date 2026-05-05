#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("microplaite esp32-s3 boot");
}

void loop() {
  Serial.println("heartbeat");
  delay(1000);
}
