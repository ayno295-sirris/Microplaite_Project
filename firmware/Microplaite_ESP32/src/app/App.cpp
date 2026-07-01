#include "app/App.h"

#include <Arduino.h>

#include "configSerial.h"
#include "pins.h"

App::App()
    : _neopixel(NEOPIXEL_COUNT, PIN_NEOPIXEL_DATA, NEO_GRBW + NEO_KHZ800),
      _heater(PIN_HEATER_PWM),
      _dispatcher(_state, _heater, _temperature, _pump, _neopixel),
      _serialCommands(_dispatcher)
{
}

void App::begin()
{
    Serial.begin(SERIAL_BAUD);
    beginNeoPixel();
    _heater.begin();
    _pump.begin();
    _temperature.begin();
    _safety.begin();
    _serialCommands.begin(Serial);
    updateState();
}

void App::update()
{
    _serialCommands.update();
    _temperature.update();
    updateState();
    _safety.update(_state);
    _heater.update(_state.temperatureC, _state.temperatureValid, _state.safetyLevel);
    updateState();
    writeLogIfDue();
}

void App::updateState()
{
    _state.temperatureAvailable = _temperature.available();
    _state.temperatureValid = _temperature.ready();
    _state.temperatureC = _temperature.temperatureC();
    _state.temperatureFault = _temperature.fault();
    _state.heaterEnabled = _heater.enabled() || _heater.pidEnabled();
    _state.heaterTargetC = _heater.targetC();
    _state.heaterOutputPercent = _heater.outputPercent();
    _state.uptimeMs = millis();
}

void App::beginNeoPixel()
{
    _neopixel.begin();
    _neopixel.setBrightness((static_cast<uint16_t>(_state.neopixelBrightnessPercent) * 255U) / 100U);
    _neopixel.fill(_neopixel.Color(255, 255, 255, 255));
    _neopixel.show();
}

void App::writeLogIfDue()
{
    if (!_state.logActive) {
        return;
    }

    const uint32_t now = millis();
    const uint32_t temperatureReadMs = _temperature.lastReadMs();
    if (temperatureReadMs == 0 || temperatureReadMs == _lastLoggedTemperatureReadMs) {
        return;
    }

    if (now - _lastLogMs < _state.logPeriodMs) {
        return;
    }
    _lastLogMs = now;
    _lastLoggedTemperatureReadMs = temperatureReadMs;

    Serial.print("LOG,");
    Serial.print(now);
    Serial.print(",");
    if (_state.temperatureValid) {
        Serial.print(_state.temperatureC, 2);
    } else {
        Serial.print("nan");
    }
    Serial.print(",");
    Serial.print(_state.heaterTargetC, 2);
    Serial.print(",");
    Serial.print(_state.heaterOutputPercent, 1);
    Serial.print(",");
    Serial.print(_heater.outputActive() ? "ON" : "OFF");
    Serial.print(",");
    Serial.print(modeText());
    Serial.print(",");
    Serial.print(_state.temperatureValid ? 1 : 0);
    Serial.print(",");
    Serial.println(_state.temperatureFault);
}

const char* App::modeText() const
{
    if (_state.safetyLevel == SafetyLevel::ERROR) {
        return "ERROR";
    }

    if (_heater.manualTestActive()) {
        return "MANUAL";
    }

    if (_heater.pidEnabled()) {
        return "PID";
    }

    if (_heater.enabled()) {
        return "ONOFF";
    }

    return "IDLE";
}
