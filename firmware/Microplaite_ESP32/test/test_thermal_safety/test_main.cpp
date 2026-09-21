#include <Arduino.h>
#include <unity.h>

#include "configSafety.h"

static_assert(maxTargetTempForMode(false) == 37.5f, "Normal maximum target changed");
static_assert(warningTempForMode(false) == 37.8f, "Normal warning threshold changed");
static_assert(errorTempForMode(false) == 38.0f, "Normal emergency cutoff changed");

static_assert(maxTargetTempForMode(true) == 60.0f, "Thermal-test maximum target changed");
static_assert(warningTempForMode(true) == 60.0f, "Thermal-test warning threshold changed");
static_assert(errorTempForMode(true) == 62.0f, "Thermal-test emergency cutoff changed");

static_assert(isTargetTemperatureAllowedForMode(60.00f, true), "60.00 C target must be accepted");
static_assert(!isTargetTemperatureAllowedForMode(60.01f, true), "60.01 C target must be rejected");
static_assert(!isEmergencyOvertemperatureForMode(59.99f, true), "59.99 C must not trigger OVERTEMP");
static_assert(isThermalWarningForMode(60.00f, true), "60.00 C must produce a warning");
static_assert(!isEmergencyOvertemperatureForMode(60.00f, true), "60.00 C must not trigger the emergency cutoff");
static_assert(!isEmergencyOvertemperatureForMode(61.99f, true), "61.99 C must not trigger the emergency cutoff");
static_assert(isEmergencyOvertemperatureForMode(62.00f, true), "62.00 C must trigger OVERTEMP");
static_assert(!canClearThermalErrorForMode(62.00f, true, true), "OVERTEMP must stay latched at the cutoff");
static_assert(!canClearThermalErrorForMode(61.99f, false, true), "An invalid sensor must block CLEAR_ERROR");
static_assert(canClearThermalErrorForMode(61.99f, true, true), "A valid reading below cutoff must permit CLEAR_ERROR");

static_assert(isTargetTemperatureAllowedForMode(37.50f, false), "Normal maximum target must be accepted");
static_assert(!isTargetTemperatureAllowedForMode(37.51f, false), "Target above normal maximum must be rejected");
static_assert(isThermalWarningForMode(37.80f, false), "Normal warning threshold changed");
static_assert(!isEmergencyOvertemperatureForMode(37.99f, false), "Normal cutoff must remain above 37.99 C");
static_assert(isEmergencyOvertemperatureForMode(38.00f, false), "Normal cutoff must remain at 38.00 C");

void setUp() {}
void tearDown() {}

void test_active_limits_match_selected_mode()
{
    TEST_ASSERT_FLOAT_WITHIN(0.001f, maxTargetTempForMode(THERMAL_TEST_MODE), SAFETY_MAX_TARGET_TEMP_C);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, warningTempForMode(THERMAL_TEST_MODE), SAFETY_WARNING_TEMP_C);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, errorTempForMode(THERMAL_TEST_MODE), SAFETY_ERROR_TEMP_C);
}

void setup()
{
    UNITY_BEGIN();
    RUN_TEST(test_active_limits_match_selected_mode);
    UNITY_END();
}

void loop() {}
