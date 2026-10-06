#include <Arduino.h>
#include <unity.h>
#include <deque>
#include <string>
#include <vector>

#include "../../src/comm/CommandDispatcher.h"
#include "../../src/comm/JsonProtocol.h"
#include "../../src/services/LongerProtocol.h"

namespace {
using Frame = std::vector<uint8_t>;
const Frame WJ_REPLY{0xE9, 0x01, 0x02, 0x57, 0x4A, 0x1E};
const Frame RJ_STOP_CW{0xE9, 0x01, 0x06, 0x52, 0x4A, 0x00, 0x00, 0x00, 0x01, 0x1E};
const Frame RJ_STOP_CCW{0xE9, 0x01, 0x06, 0x52, 0x4A, 0x00, 0x00, 0x00, 0x00, 0x1F};
const Frame RJ_RUN_CCW{0xE9, 0x01, 0x06, 0x52, 0x4A, 0x00, 0x64, 0x01, 0x00, 0x7A};
const Frame STOP_CW{0xE9, 0x01, 0x06, 0x57, 0x4A, 0x00, 0x00, 0x00, 0x01, 0x1B};
const Frame STOP_CCW{0xE9, 0x01, 0x06, 0x57, 0x4A, 0x00, 0x00, 0x00, 0x00, 0x1A};
const Frame RJ_REQUEST{0xE9, 0x01, 0x02, 0x52, 0x4A, 0x1B};
uint32_t nowMs;
bool heaterGpioOn;

// Scripted complete manufacturer replies only; no pump dynamics simulator.
struct TestSerial {
    std::vector<Frame> writes;
    std::deque<uint8_t> rx;
    Frame rjReply = RJ_STOP_CW;
    bool wjReply = true;
    bool writeFails = false;
    bool heaterOnAtStop = false;
    void begin(uint32_t, uint32_t, int, int) {}
    int available() { return rx.size(); }
    int read() { const uint8_t value = rx.front(); rx.pop_front(); return value; }
    void flush() {}
    size_t write(const uint8_t* bytes, size_t length)
    {
        if (writeFails) return 0;
        writes.emplace_back(bytes, bytes + length);
        if (length > 3 && bytes[3] == 0x57) {
            if (length == 10 && bytes[7] == 0) heaterOnAtStop = heaterGpioOn;
            if (wjReply) rx.insert(rx.end(), WJ_REPLY.begin(), WJ_REPLY.end());
        } else if (length > 3 && bytes[3] == 0x52) {
            rx.insert(rx.end(), rjReply.begin(), rjReply.end());
        }
        return length;
    }
} testSerial;

uint32_t testMillis() { return nowMs; }
void testDelay(uint32_t ms) { nowMs += ms; }
void testPinMode(uint8_t, uint8_t) {}
void testDigitalWrite(uint8_t, uint8_t value) { heaterGpioOn = value != LOW; }
}

// Exercise real services/dispatcher with only UART, clock and heater GPIO doubled.
// The temperature service is never initialized: no SPI or sensor access occurs.
#define Serial1 testSerial
#define millis testMillis
#define delay testDelay
#define pinMode testPinMode
#define digitalWrite testDigitalWrite
#include "../../src/services/LongerProtocol.cpp"
#include "../../src/services/PumpService.cpp"
#include "../../src/services/HeaterService.cpp"
#include "../../src/services/TemperatureService.cpp"
#include "../../src/services/SupervisionService.cpp"
#include "../../src/comm/CommandDispatcher.cpp"
#undef Serial1
#undef millis
#undef delay
#undef pinMode
#undef digitalWrite

namespace {
struct Output : Print {
    std::string text;
    size_t write(uint8_t byte) override { text += static_cast<char>(byte); return 1; }
};

struct Bench {
    AppState state;
    HeaterService heater{14};
    TemperatureService temperature;
    PumpService pump;
    Adafruit_NeoPixel pixel;
    SupervisionService supervision{state, heater, pump};
    CommandDispatcher dispatcher{state, heater, temperature, pump, pixel, supervision};

    void boot()
    {
        heater.begin();
        pump.begin();
        TEST_ASSERT_TRUE(pump.stop(state));
        supervision.begin(true);
    }

    JsonProtocol::Document request(const char* line)
    {
        Output out;
        dispatcher.dispatch(line, out);
        JsonProtocol::Document result(cJSON_Parse(out.text.c_str()), cJSON_Delete);
        TEST_ASSERT_NOT_NULL(result.get());
        return result;
    }
};

void assertFrame(const Frame& expected, const Frame& actual)
{
    TEST_ASSERT_EQUAL_UINT(expected.size(), actual.size());
    TEST_ASSERT_EQUAL_HEX8_ARRAY(expected.data(), actual.data(), expected.size());
}

void assertString(const cJSON* response, const char* field, const char* expected)
{
    const cJSON* value = cJSON_GetObjectItemCaseSensitive(response, field);
    TEST_ASSERT_TRUE(cJSON_IsString(value));
    TEST_ASSERT_EQUAL_STRING(expected, value->valuestring);
}
}

void setUp()
{
    nowMs = 0;
    heaterGpioOn = false;
    testSerial = TestSerial{};
}
void tearDown() {}

void test_wj_direction_speed_fcs_and_escaping()
{
    const struct { float rpm; bool cw; Frame expected; } cases[] = {
        {10, true,  {0xE9,1,6,0x57,0x4A,0,0x64,1,1,0x7E}},
        {10, false, {0xE9,1,6,0x57,0x4A,0,0x64,1,0,0x7F}},
        {0.1f, true,  {0xE9,1,6,0x57,0x4A,0,1,1,1,0x1B}},
        {0.1f, false, {0xE9,1,6,0x57,0x4A,0,1,1,0,0x1A}},
        {100, true,  {0xE9,1,6,0x57,0x4A,3,0xE8,0,1,1,0xF1}},
        {100, false, {0xE9,1,6,0x57,0x4A,3,0xE8,0,1,0,0xF0}},
        {23.3f, true,  {0xE9,1,6,0x57,0x4A,0,0xE8,1,1,1,0xF3}},
        {23.3f, false, {0xE9,1,6,0x57,0x4A,0,0xE8,1,1,0,0xF2}},
        {24.2f, true,  {0xE9,1,6,0x57,0x4A,0,0xF2,1,1,0xE8,0}},
        {24.2f, false, {0xE9,1,6,0x57,0x4A,0,0xF2,1,0,0xE8,1}},
        {24.3f, true,  {0xE9,1,6,0x57,0x4A,0,0xF3,1,1,0xE8,1}},
        {24.3f, false, {0xE9,1,6,0x57,0x4A,0,0xF3,1,0,0xE8,0}},
    };
    for (const auto& c : cases) {
        uint8_t bytes[LongerProtocol::MAX_FRAME_SIZE];
        const size_t length = LongerProtocol::buildWriteFrame(1, c.rpm, true, false, c.cw, bytes, sizeof(bytes));
        assertFrame(c.expected, Frame(bytes, bytes + length));
    }
    TEST_ASSERT_TRUE(LongerProtocol::selfCheck());
}

void test_rj_direction_flags_and_bad_fcs()
{
    LongerProtocol::PumpStatus status;
    const Frame cw{0xE9,1,6,0x52,0x4A,0,0x64,3,1,0x79};
    TEST_ASSERT_TRUE(LongerProtocol::parseStatusFrame(cw.data(), cw.size(), 1, status));
    TEST_ASSERT_TRUE(status.clockwise);
    TEST_ASSERT_TRUE(status.running);
    TEST_ASSERT_TRUE(status.fullSpeed);
    TEST_ASSERT_EQUAL_FLOAT(10, status.rpm);
    TEST_ASSERT_TRUE(LongerProtocol::parseStatusFrame(RJ_RUN_CCW.data(), RJ_RUN_CCW.size(), 1, status));
    TEST_ASSERT_FALSE(status.clockwise);
    const Frame escapedCw{0xE9,1,6,0x52,0x4A,0,0xE8,0,1,1,0xF7};
    TEST_ASSERT_TRUE(LongerProtocol::parseStatusFrame(escapedCw.data(), escapedCw.size(), 1, status));
    TEST_ASSERT_EQUAL_FLOAT(23.2f, status.rpm);
    TEST_ASSERT_TRUE(status.clockwise);
    TEST_ASSERT_FALSE(status.fullSpeed);
    Frame bad = RJ_RUN_CCW;
    bad.back() ^= 1;
    TEST_ASSERT_FALSE(LongerProtocol::parseStatusFrame(bad.data(), bad.size(), 1, status));
    const Frame escaped{0xE9,1,6,0x52,0x4A,0,0xE8,1,1,0,0xF7};
    TEST_ASSERT_TRUE(LongerProtocol::parseStatusFrame(escaped.data(), escaped.size(), 1, status));
    TEST_ASSERT_EQUAL_FLOAT(23.3f, status.rpm);
    TEST_ASSERT_FALSE(status.clockwise);
    TEST_ASSERT_TRUE(LongerProtocol::parseWriteReplyFrame(WJ_REPLY.data(), WJ_REPLY.size(), 1));
    bad = WJ_REPLY;
    bad.back() ^= 1;
    TEST_ASSERT_FALSE(LongerProtocol::parseWriteReplyFrame(bad.data(), bad.size(), 1));
}

void test_json_direction_default_and_unsigned_amplitude()
{
    Bench b;
    b.boot();
    TEST_ASSERT_NULL(b.supervision.sync(nowMs));
    auto response = b.request("{\"v\":2,\"id\":12,\"cmd\":\"PUMP_START\",\"rpm\":10}");
    assertString(response.get(), "type", "OK");
    TEST_ASSERT_TRUE(b.state.pumpCommandedClockwise);
    TEST_ASSERT_EQUAL_FLOAT(10, b.state.pumpRpm);
    response = b.request("{\"v\":2,\"id\":13,\"cmd\":\"PUMP_START\",\"rpm\":-10,\"direction\":\"CCW\"}");
    assertString(response.get(), "error", "OUT_OF_RANGE");
    TEST_ASSERT_EQUAL_UINT(3, testSerial.writes.size());
}

void test_json_bad_direction_never_writes()
{
    Bench b;
    b.boot();
    TEST_ASSERT_NULL(b.supervision.sync(nowMs));
    for (const char* command : {"PUMP_START", "PUMP_SET_RPM"}) {
        for (const char* value : {"null", "true", "1", "[]", "{}", "\"cw\"", "\"\"", "\"OTHER\""}) {
            const std::string request = std::string("{\"v\":2,\"id\":12,\"cmd\":\"") + command + "\",\"rpm\":10,\"direction\":" + value + "}";
            auto response = b.request(request.c_str());
            assertString(response.get(), "type", "ERR");
            assertString(response.get(), "error", "BAD_DIRECTION");
            TEST_ASSERT_EQUAL_INT(12, cJSON_GetObjectItemCaseSensitive(response.get(), "id")->valueint);
        }
    }
    TEST_ASSERT_EQUAL_UINT(2, testSerial.writes.size());
}

void test_json_ccw_and_rj_independent_from_command()
{
    Bench b;
    b.boot();
    TEST_ASSERT_NULL(b.supervision.sync(nowMs));
    auto response = b.request("{\"v\":2,\"id\":12,\"cmd\":\"PUMP_START\",\"rpm\":10,\"direction\":\"CCW\"}");
    assertString(response.get(), "type", "OK");
    TEST_ASSERT_FALSE(b.state.pumpCommandedClockwise);
    TEST_ASSERT_TRUE(cJSON_IsNull(cJSON_GetObjectItemCaseSensitive(response.get(), "pump_direction")));
    testSerial.rjReply = RJ_RUN_CCW;
    response = b.request("{\"v\":2,\"id\":13,\"cmd\":\"PUMP_STATUS\"}");
    assertString(response.get(), "pump_direction", "CCW");
    TEST_ASSERT_TRUE(b.state.pumpReadbackValid);
    b.state.pumpCommandedClockwise = true; // Controller readback must never overwrite this.
    TEST_ASSERT_TRUE(b.pump.readStatus(b.state));
    TEST_ASSERT_TRUE(b.state.pumpCommandedClockwise);
    TEST_ASSERT_FALSE(b.state.pumpClockwise);
    response = b.request("{\"v\":2,\"id\":14,\"cmd\":\"STATUS\"}");
    assertString(response.get(), "pump_direction", "CCW");
    TEST_ASSERT_TRUE(cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(response.get(), "pump_bidirectional_supported")));
    testSerial.rjReply.clear();
    response = b.request("{\"v\":2,\"id\":15,\"cmd\":\"PUMP_STATUS\"}");
    TEST_ASSERT_TRUE(cJSON_IsNull(cJSON_GetObjectItemCaseSensitive(response.get(), "pump_direction")));
    response = b.request("{\"v\":2,\"id\":16,\"cmd\":\"STATUS\"}");
    TEST_ASSERT_TRUE(cJSON_IsNull(cJSON_GetObjectItemCaseSensitive(response.get(), "pump_direction")));
}

void test_zero_commands_use_stop_ack_then_rj_and_keep_ccw()
{
    for (bool start : {false, true}) {
        for (float rpm : {0.0f, -0.0f, 0.04f}) {
            Bench b;
            b.state.pumpRunning = true;
            b.state.pumpCommandedClockwise = false;
            testSerial = TestSerial{};
            testSerial.rjReply = RJ_STOP_CCW;
            const char* error = start ? b.pump.start(rpm, b.state, true) : b.pump.setRpm(rpm, b.state, true);
            TEST_ASSERT_NULL(error);
            TEST_ASSERT_EQUAL_UINT(2, testSerial.writes.size());
            assertFrame(STOP_CCW, testSerial.writes[0]);
            assertFrame(RJ_REQUEST, testSerial.writes[1]);
            TEST_ASSERT_FALSE(b.state.pumpRunning);
            TEST_ASSERT_FALSE(b.state.pumpFullSpeed);
            TEST_ASSERT_TRUE(b.state.pumpReadbackValid);
            TEST_ASSERT_FALSE(b.state.pumpClockwise);
            TEST_ASSERT_FALSE(b.state.pumpCommandedClockwise);
        }
    }
}

void test_running_reversal_is_rejected_for_start_set_and_prime()
{
    for (bool cw : {false, true}) {
        Bench b;
        b.state.pumpRunning = true;
        b.state.pumpCommandedClockwise = cw;
        b.state.pumpReadbackValid = false;
        TEST_ASSERT_EQUAL_STRING("PUMP_DIRECTION_CHANGE_REQUIRES_STOP", b.pump.start(10, b.state, !cw));
        TEST_ASSERT_EQUAL_STRING("PUMP_DIRECTION_CHANGE_REQUIRES_STOP", b.pump.setRpm(10, b.state, !cw));
        if (!cw) TEST_ASSERT_EQUAL_STRING("PUMP_DIRECTION_CHANGE_REQUIRES_STOP", b.pump.prime(b.state));
    }
    TEST_ASSERT_EQUAL_UINT(0, testSerial.writes.size());
}

void test_reported_running_direction_also_prevents_reversal()
{
    Bench b;
    b.state.pumpRunning = true;
    b.state.pumpReadbackValid = true;
    b.state.pumpCommandedClockwise = true;
    b.state.pumpClockwise = false;
    TEST_ASSERT_EQUAL_STRING("PUMP_DIRECTION_CHANGE_REQUIRES_STOP", b.pump.start(10, b.state, true));
    TEST_ASSERT_EQUAL_UINT(0, testSerial.writes.size());
}

void test_confirmed_stop_allows_opposite_explicit_start()
{
    for (bool cw : {false, true}) {
        Bench b;
        b.state.pumpRunning = true;
        b.state.pumpCommandedClockwise = cw;
        testSerial.rjReply = cw ? RJ_STOP_CW : RJ_STOP_CCW;
        TEST_ASSERT_TRUE(b.pump.stop(b.state));
        TEST_ASSERT_FALSE(b.state.pumpRunning);
        TEST_ASSERT_TRUE(b.state.pumpReadbackValid);
        const size_t stoppedWrites = testSerial.writes.size();
        TEST_ASSERT_NULL(b.pump.start(10, b.state, !cw));
        TEST_ASSERT_EQUAL_UINT(stoppedWrites + 1, testSerial.writes.size());
        TEST_ASSERT_EQUAL(!cw, b.state.pumpCommandedClockwise);
    }
}

void test_unconfirmed_stop_blocks_opposite_start_set_and_prime()
{
    Bench b;
    b.state.pumpRunning = true;
    b.state.pumpCommandedClockwise = false;
    testSerial.rjReply.clear();
    TEST_ASSERT_TRUE(b.pump.stop(b.state));
    TEST_ASSERT_FALSE(b.state.pumpReadbackValid);
    TEST_ASSERT_FALSE(b.state.pumpRunning); // A commanded stop is not confirmation.
    TEST_ASSERT_EQUAL_UINT32(200, nowMs);
    const size_t stoppedWrites = testSerial.writes.size();
    TEST_ASSERT_EQUAL_STRING("PUMP_STOP_NOT_CONFIRMED", b.pump.start(10, b.state, true));
    TEST_ASSERT_EQUAL_STRING("PUMP_STOP_NOT_CONFIRMED", b.pump.setRpm(10, b.state, true));
    TEST_ASSERT_EQUAL_STRING("PUMP_STOP_NOT_CONFIRMED", b.pump.prime(b.state));
    TEST_ASSERT_EQUAL_UINT(stoppedWrites, testSerial.writes.size());
}

void test_missing_wj_reply_does_not_send_rj_or_wait_unbounded()
{
    Bench b;
    testSerial.wjReply = false;
    TEST_ASSERT_TRUE(b.pump.stop(b.state));
    TEST_ASSERT_FALSE(b.state.pumpReadbackValid);
    TEST_ASSERT_EQUAL_UINT(1, testSerial.writes.size());
    assertFrame(STOP_CW, testSerial.writes[0]);
    TEST_ASSERT_EQUAL_UINT32(200, nowMs);
}

void test_stop_rj_still_running_cannot_allow_opposite_start()
{
    Bench b;
    b.state.pumpCommandedClockwise = false;
    testSerial.rjReply = RJ_RUN_CCW;
    TEST_ASSERT_TRUE(b.pump.stop(b.state));
    TEST_ASSERT_TRUE(b.state.pumpReadbackValid);
    TEST_ASSERT_TRUE(b.state.pumpRunning);
    TEST_ASSERT_EQUAL_STRING("PUMP_DIRECTION_CHANGE_REQUIRES_STOP", b.pump.start(10, b.state, true));
    TEST_ASSERT_EQUAL_UINT(2, testSerial.writes.size());
}

void test_prime_and_normal_set_clear_full_speed()
{
    Bench b;
    TEST_ASSERT_NULL(b.pump.prime(b.state));
    assertFrame({0xE9,1,6,0x57,0x4A,3,0xE8,0,3,1,0xF3}, testSerial.writes.back());
    TEST_ASSERT_TRUE(b.state.pumpFullSpeed);
    TEST_ASSERT_NULL(b.pump.setRpm(10, b.state));
    assertFrame({0xE9,1,6,0x57,0x4A,0,0x64,1,1,0x7E}, testSerial.writes.back());
    TEST_ASSERT_FALSE(b.state.pumpFullSpeed);
    TEST_ASSERT_TRUE(b.state.pumpRunning);
    TEST_ASSERT_TRUE(b.pump.stop(b.state));
    TEST_ASSERT_FALSE(b.state.pumpFullSpeed);
    TEST_ASSERT_NULL(b.pump.setRpm(10, b.state));
    TEST_ASSERT_FALSE(b.state.pumpRunning);
    TEST_ASSERT_FALSE(b.state.pumpFullSpeed);
}

void test_write_failure_does_not_record_new_direction()
{
    Bench b;
    b.state.pumpReadbackValid = true;
    testSerial.writeFails = true;
    TEST_ASSERT_EQUAL_STRING("PUMP_WRITE_FAILED", b.pump.start(10, b.state, false));
    TEST_ASSERT_TRUE(b.state.pumpCommandedClockwise);
    TEST_ASSERT_FALSE(b.state.pumpReadbackValid);
    TEST_ASSERT_FALSE(b.state.pumpRunning);
}

void test_legacy_commands_share_the_reversal_guard()
{
    Bench b;
    b.state.pumpRunning = true;
    b.state.pumpCommandedClockwise = false;
    for (const char* command : {"PUMP_START 10", "PUMP_SET_RPM 10", "PUMP_PRIME"}) {
        Output out;
        b.dispatcher.dispatch(command, out);
        TEST_ASSERT_EQUAL_STRING("ERR PUMP_DIRECTION_CHANGE_REQUIRES_STOP\r\n", out.text.c_str());
    }
    TEST_ASSERT_EQUAL_UINT(0, testSerial.writes.size());
}

void test_global_stop_keeps_direction_and_no_resume()
{
    Bench b;
    b.boot();
    TEST_ASSERT_NULL(b.supervision.sync(nowMs));
    TEST_ASSERT_NULL(b.pump.start(10, b.state, false));
    b.heater.startManualTest(10000);
    testSerial.rjReply = RJ_STOP_CCW;
    auto response = b.request("{\"v\":2,\"id\":12,\"cmd\":\"STOP\"}");
    assertString(response.get(), "type", "OK");
    TEST_ASSERT_FALSE(testSerial.heaterOnAtStop);
    TEST_ASSERT_FALSE(heaterGpioOn);
    TEST_ASSERT_FALSE(b.heater.manualTestActive());
    TEST_ASSERT_FALSE(b.state.pumpRunning);
    assertFrame(STOP_CCW, testSerial.writes[testSerial.writes.size() - 2]);
    TEST_ASSERT_EQUAL(SystemState::READY, b.state.systemState);
    const size_t stoppedWrites = testSerial.writes.size();
    TEST_ASSERT_NULL(b.supervision.sync(nowMs));
    b.supervision.update(nowMs);
    TEST_ASSERT_EQUAL_UINT(stoppedWrites, testSerial.writes.size());
    TEST_ASSERT_FALSE(b.state.pumpRunning);
}

void test_heartbeat_loss_keeps_stop_and_requires_new_sync()
{
    Bench b;
    b.boot();
    TEST_ASSERT_NULL(b.supervision.sync(nowMs));
    TEST_ASSERT_NULL(b.pump.start(10, b.state, false));
    b.heater.enablePid();
    testSerial.rjReply = RJ_STOP_CCW;
    nowMs = 3000;
    b.supervision.update(nowMs);
    TEST_ASSERT_TRUE(b.state.pumpRunning);
    nowMs = 3001;
    b.supervision.update(nowMs);
    TEST_ASSERT_EQUAL(CommState::LOST, b.state.commState);
    TEST_ASSERT_FALSE(b.state.pumpRunning);
    TEST_ASSERT_FALSE(b.heater.pidEnabled());
    const size_t stoppedWrites = testSerial.writes.size();
    TEST_ASSERT_EQUAL_STRING("NO_SESSION", b.supervision.heartbeat(nowMs));
    auto response = b.request("{\"v\":2,\"id\":12,\"cmd\":\"PUMP_START\",\"rpm\":10,\"direction\":\"CCW\"}");
    assertString(response.get(), "error", "NO_SESSION");
    TEST_ASSERT_NULL(b.supervision.sync(nowMs));
    TEST_ASSERT_EQUAL_UINT(stoppedWrites, testSerial.writes.size());
    TEST_ASSERT_FALSE(b.state.pumpRunning);
    TEST_ASSERT_EQUAL(SystemState::READY, b.state.systemState);
}

void test_reboot_stops_without_restoring_direction_or_session()
{
    Bench old;
    old.boot();
    TEST_ASSERT_NULL(old.supervision.sync(nowMs));
    TEST_ASSERT_NULL(old.pump.start(10, old.state, false));
    old.heater.enablePid();
    old.state.neopixelEnabled = true;
    const size_t beforeBoot = testSerial.writes.size();
    Bench rebooted;
    rebooted.boot();
    assertFrame(STOP_CW, testSerial.writes[beforeBoot]);
    TEST_ASSERT_EQUAL_UINT(beforeBoot + 2, testSerial.writes.size());
    TEST_ASSERT_FALSE(rebooted.state.pumpRunning);
    TEST_ASSERT_TRUE(rebooted.state.pumpCommandedClockwise);
    TEST_ASSERT_FALSE(rebooted.heater.enabled());
    TEST_ASSERT_FALSE(rebooted.heater.pidEnabled());
    TEST_ASSERT_FALSE(rebooted.state.neopixelEnabled);
    TEST_ASSERT_EQUAL(CommState::NO_SESSION, rebooted.state.commState);
    TEST_ASSERT_EQUAL(SystemState::IDLE, rebooted.state.systemState);
}

void setup()
{
    UNITY_BEGIN();
    RUN_TEST(test_wj_direction_speed_fcs_and_escaping);
    RUN_TEST(test_rj_direction_flags_and_bad_fcs);
    RUN_TEST(test_json_direction_default_and_unsigned_amplitude);
    RUN_TEST(test_json_bad_direction_never_writes);
    RUN_TEST(test_json_ccw_and_rj_independent_from_command);
    RUN_TEST(test_zero_commands_use_stop_ack_then_rj_and_keep_ccw);
    RUN_TEST(test_running_reversal_is_rejected_for_start_set_and_prime);
    RUN_TEST(test_reported_running_direction_also_prevents_reversal);
    RUN_TEST(test_confirmed_stop_allows_opposite_explicit_start);
    RUN_TEST(test_unconfirmed_stop_blocks_opposite_start_set_and_prime);
    RUN_TEST(test_missing_wj_reply_does_not_send_rj_or_wait_unbounded);
    RUN_TEST(test_stop_rj_still_running_cannot_allow_opposite_start);
    RUN_TEST(test_prime_and_normal_set_clear_full_speed);
    RUN_TEST(test_write_failure_does_not_record_new_direction);
    RUN_TEST(test_legacy_commands_share_the_reversal_guard);
    RUN_TEST(test_global_stop_keeps_direction_and_no_resume);
    RUN_TEST(test_heartbeat_loss_keeps_stop_and_requires_new_sync);
    RUN_TEST(test_reboot_stops_without_restoring_direction_or_session);
    UNITY_END();
}
void loop() {}
