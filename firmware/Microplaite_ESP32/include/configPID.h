#pragma once

#include <Arduino.h>
#include "configSafety.h"

constexpr float TARGET_TEMP_C  = 37.5f;

constexpr float PID_KP = 8.0f;
constexpr float PID_KI = 0.03f;
constexpr float PID_KD = 20.0f;
constexpr float PID_OUTPUT_LIMIT_PERCENT = 15.0f;

constexpr uint32_t PID_SAMPLE_TIME_MS = 200;
constexpr uint32_t PID_CONTROL_SAMPLE_TIME_MS = 1000;

constexpr float ONOFF_HYSTERESIS_C = 0.25f;
constexpr float CONTROL_POWER_LIMIT_PERCENT = 30.0f;
constexpr float CONTROL_POWER_LIMIT_MIN_PERCENT = 1.0f;
constexpr float CONTROL_POWER_LIMIT_MAX_PERCENT = 100.0f;

constexpr float HEATER_OUTPUT_MIN_PERCENT = 0.0f;
constexpr float HEATER_OUTPUT_MAX_PERCENT = 100.0f;

constexpr uint32_t HEATER_CONTROL_WINDOW_MS = 2000;
