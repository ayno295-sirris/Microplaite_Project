#include "services/TemperatureService.h"

#include "configPID.h"
#include "pins.h"

TemperatureService::TemperatureService()
    : _thermocouple(PIN_MAX31856_CS, PIN_MAX31856_MOSI, PIN_MAX31856_MISO, PIN_MAX31856_SCK)
{
}

void TemperatureService::begin()
{
    _available = false;
    _ready = false;
    _temperatureC = NAN;
    _fault = 0;
    _lastReadMs = 0;

    if (!_thermocouple.begin()) {
        Serial.println("MAX31856_ERROR");
        return;
    }

    _thermocouple.setThermocoupleType(MAX31856_TCTYPE_K);
    _available = true;
}

void TemperatureService::update()
{
    if (!_available) {
        _ready = false;
        _temperatureC = NAN;
        return;
    }

    const uint32_t now = millis();
    if (now - _lastReadMs < PID_SAMPLE_TIME_MS) {
        return;
    }

    readNow();
}

bool TemperatureService::readNow()
{
    _lastReadMs = millis();

    if (!_available) {
        _ready = false;
        _temperatureC = NAN;
        return false;
    }

    const uint8_t fault = _thermocouple.readFault();
    _fault = fault;
    if (fault != 0) {
        _ready = false;
        _temperatureC = NAN;
        return false;
    }

    const float temperatureC = _thermocouple.readThermocoupleTemperature();
    if (isnan(temperatureC)) {
        _ready = false;
        _temperatureC = NAN;
        return false;
    }

    _temperatureC = temperatureC;
    _ready = true;
    return true;
}

bool TemperatureService::available() const
{
    return _available;
}

bool TemperatureService::ready() const
{
    return _ready;
}

float TemperatureService::temperatureC() const
{
    return _temperatureC;
}

uint8_t TemperatureService::fault() const
{
    return _fault;
}

uint32_t TemperatureService::lastReadMs() const
{
    return _lastReadMs;
}
