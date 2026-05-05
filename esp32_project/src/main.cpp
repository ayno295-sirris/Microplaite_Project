#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("microplaite esp32-s3 boot");
}

void loop() {
  delay(1000);
}
