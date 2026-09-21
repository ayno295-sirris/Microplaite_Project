#include "services/SafetyService.h"

#include <Arduino.h>

#include "configSafety.h"

void SafetyService::begin()
{
    _lastLevel = SafetyLevel::OK;
}

void SafetyService::update(AppState& state)
{
    if (state.errorLatched) {
        state.safetyLevel = SafetyLevel::ERROR;
        _lastLevel = state.safetyLevel;
        return;
    }

    if (!state.temperatureValid || isnan(state.temperatureC)) {
        if (state.heaterEnabled) {
            state.errorLatched = true;
            state.lastError = state.temperatureFault != 0 ? "MAX31856_FAULT" : "SENSOR_INVALID";
            state.safetyLevel = SafetyLevel::ERROR;
            _lastLevel = state.safetyLevel;
            return;
        }
        state.safetyLevel = SafetyLevel::OK;
        _lastLevel = state.safetyLevel;
        return;
    }

    if (isEmergencyOvertemperature(state.temperatureC)) {
        state.errorLatched = true;
        state.lastError = "OVERTEMP";
        state.safetyLevel = SafetyLevel::ERROR;
        if (_lastLevel != SafetyLevel::ERROR) {
            Serial.println("ERROR");
        }
        _lastLevel = state.safetyLevel;
        return;
    }

    if (isThermalWarning(state.temperatureC)) {
        state.safetyLevel = SafetyLevel::WARNING;
        _lastLevel = state.safetyLevel;
        return;
    }

    state.safetyLevel = SafetyLevel::OK;
    _lastLevel = state.safetyLevel;
}
