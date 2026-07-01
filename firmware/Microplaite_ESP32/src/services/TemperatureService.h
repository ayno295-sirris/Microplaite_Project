#pragma once

#include <Arduino.h>
#include <SPI.h>

#include <Adafruit_MAX31856.h>

class TemperatureService {
public:
    TemperatureService();

    void begin();
    void update();
    bool readNow();

    bool available() const;
    bool ready() const;
    float temperatureC() const;
    uint8_t fault() const;
    uint32_t lastReadMs() const;

private:
    Adafruit_MAX31856 _thermocouple;
    bool _available = false;
    bool _ready = false;
    float _temperatureC = NAN;
    uint8_t _fault = 0;
    uint32_t _lastReadMs = 0;
};
