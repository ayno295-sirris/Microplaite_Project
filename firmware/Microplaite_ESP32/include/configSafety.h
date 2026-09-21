#pragma once

#include <Arduino.h>

constexpr bool THERMAL_TEST_MODE = true;

constexpr float NORMAL_MAX_TARGET_TEMP_C = 37.5f;
constexpr float NORMAL_WARNING_TEMP_C = 37.8f;
constexpr float NORMAL_ERROR_TEMP_C = 38.0f;

constexpr float THERMAL_TEST_MAX_TARGET_TEMP_C = 60.0f;
constexpr float THERMAL_TEST_WARNING_TEMP_C = 60.0f;
constexpr float THERMAL_TEST_ERROR_TEMP_C = 62.0f;

constexpr float maxTargetTempForMode(bool thermalTestMode)
{
    return thermalTestMode ? THERMAL_TEST_MAX_TARGET_TEMP_C : NORMAL_MAX_TARGET_TEMP_C;
}

constexpr float warningTempForMode(bool thermalTestMode)
{
    return thermalTestMode ? THERMAL_TEST_WARNING_TEMP_C : NORMAL_WARNING_TEMP_C;
}

constexpr float errorTempForMode(bool thermalTestMode)
{
    return thermalTestMode ? THERMAL_TEST_ERROR_TEMP_C : NORMAL_ERROR_TEMP_C;
}

constexpr float SAFETY_MIN_TARGET_TEMP_C = 20.0f;
constexpr float SAFETY_MAX_TARGET_TEMP_C = maxTargetTempForMode(THERMAL_TEST_MODE);
constexpr float SAFETY_WARNING_TEMP_C = warningTempForMode(THERMAL_TEST_MODE);
constexpr float SAFETY_ERROR_TEMP_C = errorTempForMode(THERMAL_TEST_MODE);
constexpr uint32_t MANUAL_ON_MAX_SECONDS = 60;
constexpr uint32_t HARD_MANUAL_ON_MAX_SECONDS = 120;

constexpr bool isTargetTemperatureAllowedForMode(float targetC, bool thermalTestMode)
{
    return targetC >= SAFETY_MIN_TARGET_TEMP_C && targetC <= maxTargetTempForMode(thermalTestMode);
}

constexpr bool isThermalWarningForMode(float temperatureC, bool thermalTestMode)
{
    return temperatureC >= warningTempForMode(thermalTestMode) && temperatureC < errorTempForMode(thermalTestMode);
}

constexpr bool isEmergencyOvertemperatureForMode(float temperatureC, bool thermalTestMode)
{
    return temperatureC >= errorTempForMode(thermalTestMode);
}

constexpr bool canClearThermalErrorForMode(float temperatureC, bool sensorValid, bool thermalTestMode)
{
    return sensorValid && !isEmergencyOvertemperatureForMode(temperatureC, thermalTestMode);
}

constexpr bool isTargetTemperatureAllowed(float targetC)
{
    return isTargetTemperatureAllowedForMode(targetC, THERMAL_TEST_MODE);
}

constexpr bool isThermalWarning(float temperatureC)
{
    return isThermalWarningForMode(temperatureC, THERMAL_TEST_MODE);
}

constexpr bool isEmergencyOvertemperature(float temperatureC)
{
    return isEmergencyOvertemperatureForMode(temperatureC, THERMAL_TEST_MODE);
}

constexpr bool canClearThermalError(float temperatureC, bool sensorValid)
{
    return canClearThermalErrorForMode(temperatureC, sensorValid, THERMAL_TEST_MODE);
}

static_assert(SAFETY_MIN_TARGET_TEMP_C < SAFETY_MAX_TARGET_TEMP_C, "Minimum target must be below maximum target");
static_assert(SAFETY_MAX_TARGET_TEMP_C <= SAFETY_WARNING_TEMP_C, "Maximum target must not exceed warning threshold");
static_assert(SAFETY_WARNING_TEMP_C < SAFETY_ERROR_TEMP_C, "Warning threshold must be below emergency cutoff");
static_assert(MANUAL_ON_MAX_SECONDS <= HARD_MANUAL_ON_MAX_SECONDS, "Manual ON limit exceeds hard limit");
