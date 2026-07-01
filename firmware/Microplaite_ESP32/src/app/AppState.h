#pragma once

#include <Arduino.h>

enum class SafetyLevel {
    OK,
    WARNING,
    ERROR
};

struct AppState {
    bool heaterEnabled = false;
    float heaterTargetC = 37.5f;
    float heaterOutputPercent = 0.0f;
    float temperatureC = NAN;
    bool temperatureAvailable = false;
    bool temperatureValid = false;
    uint8_t temperatureFault = 0;

    bool pumpRunning = false;
    float pumpRpm = 0.0f;
    bool pumpFullSpeed = false;

    bool neopixelEnabled = true;
    uint8_t neopixelBrightnessPercent = 50;

    SafetyLevel safetyLevel = SafetyLevel::OK;
    bool errorLatched = false;
    const char* lastError = "NONE";
    uint32_t uptimeMs = 0;
    bool logActive = false;
    uint32_t logPeriodMs = 0;
};
