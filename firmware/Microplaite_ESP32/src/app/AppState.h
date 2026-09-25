#pragma once

#include <Arduino.h>

enum class SafetyLevel {
    OK,
    WARNING,
    ERROR
};

enum class SystemState { BOOT, IDLE, READY, RUNNING, FAULT };
enum class CommState { NO_SESSION, ACTIVE, LOST };

struct AppState {
    SystemState systemState = SystemState::BOOT;
    CommState commState = CommState::NO_SESSION;

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
    bool pumpReadbackValid = false; // Only a valid RJ confirms the pump fields.

    bool neopixelEnabled = false;
    uint8_t neopixelBrightnessPercent = 0;

    SafetyLevel safetyLevel = SafetyLevel::OK;
    bool errorLatched = false;
    const char* lastError = "NONE";
    uint32_t uptimeMs = 0;
    bool logActive = false;
    uint32_t logPeriodMs = 0;
};
