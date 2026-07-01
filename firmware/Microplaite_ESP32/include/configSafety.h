#pragma once

#include <Arduino.h>

constexpr float SAFETY_WARNING_TEMP_C = 37.8f;
constexpr float SAFETY_ERROR_TEMP_C = 38.0f;
constexpr float SAFETY_MIN_TARGET_TEMP_C = 20.0f;
constexpr float SAFETY_MAX_TARGET_TEMP_C = 37.5f;
constexpr uint32_t MANUAL_ON_MAX_SECONDS = 60;
constexpr uint32_t HARD_MANUAL_ON_MAX_SECONDS = 120;

static_assert(MANUAL_ON_MAX_SECONDS <= HARD_MANUAL_ON_MAX_SECONDS, "Manual ON limit exceeds hard limit");
