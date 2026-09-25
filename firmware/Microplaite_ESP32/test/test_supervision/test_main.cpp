#include <Arduino.h>
#include <unity.h>

#include "../../src/services/SupervisionService.h"
#include "../../src/services/HeaterService.h"
#include "../../src/services/PumpService.h"

// Link-time hardware doubles: these tests never access GPIO or RS485.
namespace {
bool onoff, pid, manual, pumpStopFails, pumpStillRunning;
unsigned heaterStops, pumpStops;
bool heaterWasOffBeforePump;
}

HeaterService::HeaterService(uint8_t pin) : _pin(pin) {}
bool HeaterService::enabled() const { return onoff; }
bool HeaterService::pidEnabled() const { return pid; }
bool HeaterService::manualTestActive() const { return manual; }
float HeaterService::outputPercent() const { return onoff || pid || manual ? 100.0f : 0.0f; }
void HeaterService::stop()
{
    ++heaterStops;
    onoff = pid = manual = false;
}
bool PumpService::stop(AppState& state)
{
    ++pumpStops;
    heaterWasOffBeforePump = heaterStops > 0 && !onoff && !pid && !manual;
    state.pumpReadbackValid = false;
    if (pumpStopFails) return false;
    state.pumpRunning = pumpStillRunning;
    state.pumpRpm = pumpStillRunning ? 3.0f : 0.0f;
    return true;
}

// PlatformIO's existing test configuration excludes application sources.
#include "../../src/services/SupervisionService.cpp"

void setUp()
{
    onoff = pid = manual = pumpStopFails = pumpStillRunning = false;
    heaterStops = pumpStops = 0;
    heaterWasOffBeforePump = false;
}
void tearDown() {}

struct Bench {
    AppState state;
    HeaterService heater{14};
    PumpService pump;
    SupervisionService supervision{state, heater, pump};
};

void test_boot_idle_and_sync_without_actuation()
{
    Bench b;
    TEST_ASSERT_EQUAL(SystemState::BOOT, b.state.systemState);
    TEST_ASSERT_EQUAL_STRING("SYSTEM_NOT_READY", b.supervision.sync(0));
    b.supervision.begin(true);
    TEST_ASSERT_EQUAL(SystemState::IDLE, b.state.systemState);
    TEST_ASSERT_EQUAL(CommState::NO_SESSION, b.state.commState);
    TEST_ASSERT_EQUAL_STRING("NO_SESSION", b.supervision.activationError(10));
    TEST_ASSERT_NULL(b.supervision.sync(100));
    TEST_ASSERT_EQUAL(SystemState::READY, b.state.systemState);
    TEST_ASSERT_TRUE(b.supervision.sessionActive());
    TEST_ASSERT_EQUAL_UINT32(215, b.supervision.heartbeatAgeMs(315));
    TEST_ASSERT_EQUAL_UINT32(0, heaterStops + pumpStops);
}

void test_ready_running_and_stopped_ready_for_each_actuator()
{
    Bench b;
    b.supervision.begin(true);
    b.supervision.sync(100);
    onoff = true;
    b.supervision.update(101);
    TEST_ASSERT_EQUAL(SystemState::RUNNING, b.state.systemState);
    onoff = false;
    pid = true;
    b.supervision.update(102);
    TEST_ASSERT_EQUAL(SystemState::RUNNING, b.state.systemState);
    pid = false;
    manual = true;
    b.supervision.update(103);
    TEST_ASSERT_EQUAL(SystemState::RUNNING, b.state.systemState);
    manual = false;
    b.state.pumpRunning = true;
    b.state.pumpReadbackValid = false;
    b.supervision.update(104);
    TEST_ASSERT_EQUAL(SystemState::RUNNING, b.state.systemState);
    TEST_ASSERT_TRUE(b.supervision.stop());
    TEST_ASSERT_TRUE(heaterWasOffBeforePump);
    TEST_ASSERT_EQUAL(SystemState::READY, b.state.systemState);
    TEST_ASSERT_TRUE(b.supervision.stop());
    TEST_ASSERT_EQUAL(SystemState::READY, b.state.systemState);
}

void test_legacy_running_is_observed_by_sync_and_stop_without_session()
{
    Bench b;
    b.supervision.begin(true);
    manual = true;
    b.supervision.update(5000);
    TEST_ASSERT_EQUAL(SystemState::RUNNING, b.state.systemState);
    TEST_ASSERT_EQUAL(CommState::NO_SESSION, b.state.commState);
    TEST_ASSERT_EQUAL_UINT32(0, heaterStops + pumpStops);
    b.supervision.stop();
    TEST_ASSERT_EQUAL(SystemState::IDLE, b.state.systemState);
    b.state.pumpRunning = true;
    TEST_ASSERT_NULL(b.supervision.sync(6000));
    TEST_ASSERT_EQUAL(SystemState::RUNNING, b.state.systemState);
    TEST_ASSERT_TRUE(b.state.pumpRunning);
}

void test_heartbeat_refresh_and_strict_timeout_boundary()
{
    Bench b;
    b.supervision.begin(true);
    b.supervision.sync(100);
    manual = true;
    b.supervision.update(1101); // Informative threshold: no stop.
    TEST_ASSERT_EQUAL_UINT32(0, pumpStops);
    TEST_ASSERT_NULL(b.supervision.heartbeat(1500));
    TEST_ASSERT_EQUAL_UINT32(200, b.supervision.heartbeatAgeMs(1700));
    b.supervision.update(4500); // Exactly 3000 ms: session remains active.
    TEST_ASSERT_TRUE(b.supervision.sessionActive());
    TEST_ASSERT_EQUAL_UINT32(0, pumpStops);
    b.supervision.update(4501);
    TEST_ASSERT_EQUAL(CommState::LOST, b.state.commState);
    TEST_ASSERT_EQUAL(SystemState::IDLE, b.state.systemState);
    TEST_ASSERT_EQUAL_UINT32(1, heaterStops);
    TEST_ASSERT_EQUAL_UINT32(1, pumpStops);
    TEST_ASSERT_TRUE(heaterWasOffBeforePump);
}

void test_pump_run_without_readback_is_stopped_on_timeout()
{
    Bench b;
    b.supervision.begin(true);
    b.supervision.sync(0);
    b.state.pumpRunning = true;
    b.state.pumpReadbackValid = false;
    b.supervision.update(3001);
    TEST_ASSERT_EQUAL_UINT32(1, pumpStops);
    TEST_ASSERT_TRUE(heaterWasOffBeforePump);
    TEST_ASSERT_FALSE(b.state.pumpRunning);
    TEST_ASSERT_EQUAL(SystemState::IDLE, b.state.systemState);
}

void test_idle_timeout_does_not_send_pump_stop()
{
    Bench b;
    b.supervision.begin(true);
    b.supervision.sync(0);
    b.supervision.update(3001);
    TEST_ASSERT_EQUAL(CommState::LOST, b.state.commState);
    TEST_ASSERT_EQUAL(SystemState::IDLE, b.state.systemState);
    TEST_ASSERT_EQUAL_UINT32(0, heaterStops + pumpStops);
}

void test_late_heartbeat_cannot_resume_without_sync()
{
    Bench b;
    b.supervision.begin(true);
    b.supervision.sync(0);
    pid = true;
    TEST_ASSERT_EQUAL_STRING("NO_SESSION", b.supervision.heartbeat(3001));
    TEST_ASSERT_EQUAL_UINT32(1, pumpStops);
    TEST_ASSERT_EQUAL_STRING("NO_SESSION", b.supervision.activationError(4000));
    b.supervision.update(8000);
    TEST_ASSERT_EQUAL_UINT32(1, pumpStops); // No repeated stop or automatic resume.
    TEST_ASSERT_FALSE(pid);
    TEST_ASSERT_NULL(b.supervision.sync(9000));
    TEST_ASSERT_EQUAL(SystemState::READY, b.state.systemState);
    TEST_ASSERT_FALSE(pid);
    TEST_ASSERT_FALSE(b.state.pumpRunning);
    TEST_ASSERT_NULL(b.supervision.activationError(9001));
}

void test_fault_has_priority_over_sync_heartbeat_timeout_and_stop()
{
    Bench b;
    b.supervision.begin(true);
    b.supervision.sync(0);
    b.state.errorLatched = true;
    b.state.lastError = "OVERTEMP";
    b.state.pumpRunning = true;
    TEST_ASSERT_NULL(b.supervision.heartbeat(100));
    TEST_ASSERT_EQUAL(SystemState::FAULT, b.state.systemState);
    TEST_ASSERT_EQUAL_STRING("SYSTEM_FAULT", b.supervision.sync(200));
    TEST_ASSERT_EQUAL_UINT32(100, b.supervision.heartbeatAgeMs(200));
    TEST_ASSERT_EQUAL_STRING("SYSTEM_FAULT", b.supervision.activationError(200));
    b.supervision.update(3101);
    TEST_ASSERT_EQUAL(CommState::LOST, b.state.commState);
    TEST_ASSERT_EQUAL(SystemState::FAULT, b.state.systemState);
    TEST_ASSERT_TRUE(b.state.errorLatched);
    TEST_ASSERT_EQUAL_STRING("OVERTEMP", b.state.lastError);
    b.supervision.stop();
    TEST_ASSERT_EQUAL(SystemState::FAULT, b.state.systemState);
    b.state.errorLatched = false;
    b.state.safetyLevel = SafetyLevel::ERROR;
    b.supervision.update(4000);
    TEST_ASSERT_EQUAL(SystemState::FAULT, b.state.systemState);
    b.state.safetyLevel = SafetyLevel::OK;
    b.supervision.update(4001);
    TEST_ASSERT_EQUAL(SystemState::IDLE, b.state.systemState);
    TEST_ASSERT_FALSE(b.supervision.sessionActive());
}

void test_hardware_init_failure_blocks_sync()
{
    Bench b;
    b.supervision.begin(false);
    TEST_ASSERT_EQUAL(SystemState::FAULT, b.state.systemState);
    TEST_ASSERT_EQUAL_STRING("SYSTEM_FAULT", b.supervision.sync(100));
    TEST_ASSERT_FALSE(b.supervision.sessionActive());
}

void test_failed_pump_stop_cannot_report_idle()
{
    Bench b;
    b.supervision.begin(true);
    b.supervision.sync(0);
    b.state.pumpRunning = true;
    pumpStopFails = true;
    b.supervision.update(3001);
    TEST_ASSERT_EQUAL(CommState::LOST, b.state.commState);
    TEST_ASSERT_EQUAL(SystemState::RUNNING, b.state.systemState);
    TEST_ASSERT_TRUE(heaterWasOffBeforePump);
    pumpStopFails = false;
    pumpStillRunning = true;
    b.supervision.stop();
    TEST_ASSERT_EQUAL(SystemState::RUNNING, b.state.systemState);
}

void test_timeout_handles_millis_wraparound()
{
    Bench b;
    b.supervision.begin(true);
    b.supervision.sync(UINT32_MAX - 500U);
    TEST_ASSERT_EQUAL_UINT32(501, b.supervision.heartbeatAgeMs(0));
    b.supervision.update(2499);
    TEST_ASSERT_TRUE(b.supervision.sessionActive());
    b.supervision.update(2500);
    TEST_ASSERT_EQUAL(CommState::LOST, b.state.commState);
}

void setup()
{
    UNITY_BEGIN();
    RUN_TEST(test_boot_idle_and_sync_without_actuation);
    RUN_TEST(test_ready_running_and_stopped_ready_for_each_actuator);
    RUN_TEST(test_legacy_running_is_observed_by_sync_and_stop_without_session);
    RUN_TEST(test_heartbeat_refresh_and_strict_timeout_boundary);
    RUN_TEST(test_pump_run_without_readback_is_stopped_on_timeout);
    RUN_TEST(test_idle_timeout_does_not_send_pump_stop);
    RUN_TEST(test_late_heartbeat_cannot_resume_without_sync);
    RUN_TEST(test_fault_has_priority_over_sync_heartbeat_timeout_and_stop);
    RUN_TEST(test_hardware_init_failure_blocks_sync);
    RUN_TEST(test_failed_pump_stop_cannot_report_idle);
    RUN_TEST(test_timeout_handles_millis_wraparound);
    UNITY_END();
}

void loop() {}
