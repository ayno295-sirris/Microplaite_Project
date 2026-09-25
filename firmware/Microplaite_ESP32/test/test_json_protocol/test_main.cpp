#include <Arduino.h>
#include <unity.h>

#include "../../src/comm/JsonProtocol.h"

void setUp() {}
void tearDown() {}

void test_envelope_rejects_ambiguous_or_invalid_requests()
{
    const struct { const char* line; const char* error; } cases[] = {
        {"{\"v\":2,\"id\":7,\"cmd\":\"PING\"}", nullptr},
        {"{\"v\":2,\"id\":7,\"cmd\":\"\\u0050ING\"}", nullptr},
        {"{\"cmd\":\"PING\",\"id\":-2147483648,\"v\":2}", nullptr},
        {"{\"v\":2,\"id\":2147483647,\"cmd\":\"PING\"}", nullptr},
        {"{\"id\":7,\"cmd\":\"PING\"}", "MISSING_VERSION"},
        {"{\"v\":1,\"id\":7,\"cmd\":\"PING\"}", "UNSUPPORTED_VERSION"},
        {"{\"v\":\"2\",\"id\":7,\"cmd\":\"PING\"}", "BAD_VERSION"},
        {"{\"v\":2,\"cmd\":\"PING\"}", "MISSING_ID"},
        {"{\"v\":2,\"id\":1.5,\"cmd\":\"PING\"}", "BAD_ID"},
        {"{\"v\":2,\"id\":2147483648,\"cmd\":\"PING\"}", "BAD_ID"},
        {"{\"v\":2,\"id\":true,\"cmd\":\"PING\"}", "BAD_ID"},
        {"{\"v\":2,\"id\":\"7\",\"cmd\":\"PING\"}", "BAD_ID"},
        {"{\"v\":2,\"id\":7}", "MISSING_CMD"},
        {"{\"v\":2,\"id\":7,\"cmd\":false}", "BAD_CMD"},
        {"{\"v\":2,\"id\":7,\"cmd\":\"\"}", "BAD_CMD"},
        {"{\"v\":2,\"id\":7,\"cmd\":\"PING\\\"\"}", "BAD_CMD"},
        {"{\"v\":2,\"id\":7,\"cmd\":\"PING\",\"id\":8}", "DUPLICATE_FIELD"},
        {"{\"v\":2,\"id\":7 \"cmd\":\"PING\"}", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\":7,\"cmd\":\"PING\"} garbage", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\":01,\"cmd\":\"PING\"}", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\":1.,\"cmd\":\"PING\"}", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\":1e,\"cmd\":\"PING\"}", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\":7,\"cmd\":\"PING\\u0000STOP\"}", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\":7,\"cmd\":\"PING\\uZZZZ\"}", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\\uZZZZ\":7,\"cmd\":\"PING\"}", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\":7,\"cmd\":\"PING\\u00\"}", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\":7,\"cmd\":\"PING\\uD800\"}", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\":7,\"cmd\":\"PI\tNG\"}", "MALFORMED_JSON"},
        {"{\"v\":2,\"id\":7,\"cmd\":\"\xc0\xaf\"}", "MALFORMED_JSON"},
    };
    for (const auto& item : cases) {
        JsonProtocol::Document request(JsonProtocol::parse(item.line), cJSON_Delete);
        long id = 0;
        const char* cmd = "UNKNOWN";
        const char* error = JsonProtocol::envelope(request.get(), id, cmd);
        if (item.error) {
            TEST_ASSERT_EQUAL_STRING_MESSAGE(item.error, error, item.line);
        } else {
            TEST_ASSERT_NULL_MESSAGE(error, item.line);
            TEST_ASSERT_EQUAL_STRING("PING", cmd);
        }
    }
}

void test_argument_validation_checks_types_bounds_and_finite_values()
{
    const struct { const char* line; const char* error; float value; } cases[] = {
        {"{\"rpm\":0}", nullptr, 0.0f},
        {"{\"rpm\":100}", nullptr, 100.0f},
        {"{\"rpm\":3.25}", nullptr, 3.25f},
        {"{}", "MISSING_ARGUMENT", 0},
        {"{\"rpm\":\"3\"}", "BAD_ARGUMENT_TYPE", 0},
        {"{\"rpm\":true}", "BAD_ARGUMENT_TYPE", 0},
        {"{\"rpm\":null}", "BAD_ARGUMENT_TYPE", 0},
        {"{\"rpm\":-0.1}", "OUT_OF_RANGE", 0},
        {"{\"rpm\":100.01}", "OUT_OF_RANGE", 0},
        {"{\"rpm\":1e999}", "OUT_OF_RANGE", 0},
    };
    for (const auto& item : cases) {
        JsonProtocol::Document request(JsonProtocol::parse(item.line), cJSON_Delete);
        float rpm = -1;
        const char* error = JsonProtocol::number(request.get(), "rpm", 0, 100, rpm);
        if (item.error) {
            TEST_ASSERT_EQUAL_STRING_MESSAGE(item.error, error, item.line);
        } else {
            TEST_ASSERT_NULL_MESSAGE(error, item.line);
            TEST_ASSERT_FLOAT_WITHIN(0.0001f, item.value, rpm);
        }
    }
}

void test_known_id_and_command_survive_a_version_error()
{
    JsonProtocol::Document request(JsonProtocol::parse(
        "{\"v\":3,\"id\":42,\"cmd\":\"PING\"}"), cJSON_Delete);
    long id = 0;
    const char* cmd = "UNKNOWN";
    TEST_ASSERT_EQUAL_STRING("UNSUPPORTED_VERSION", JsonProtocol::envelope(request.get(), id, cmd));
    TEST_ASSERT_EQUAL_INT32(42, id);
    TEST_ASSERT_EQUAL_STRING("PING", cmd);
}

void test_boolean_and_string_arguments_are_not_coerced()
{
    JsonProtocol::Document request(JsonProtocol::parse(
        "{\"enabled\":false,\"number\":1,\"mode\":\"PID\"}"), cJSON_Delete);
    bool enabled = true;
    const char* mode = nullptr;
    TEST_ASSERT_NULL(JsonProtocol::boolean(request.get(), "enabled", enabled));
    TEST_ASSERT_FALSE(enabled);
    TEST_ASSERT_EQUAL_STRING("BAD_ARGUMENT_TYPE", JsonProtocol::boolean(request.get(), "number", enabled));
    TEST_ASSERT_EQUAL_STRING("MISSING_ARGUMENT", JsonProtocol::boolean(request.get(), "absent", enabled));
    TEST_ASSERT_NULL(JsonProtocol::string(request.get(), "mode", mode));
    TEST_ASSERT_EQUAL_STRING("PID", mode);
    TEST_ASSERT_EQUAL_STRING("BAD_ARGUMENT_TYPE", JsonProtocol::string(request.get(), "number", mode));
}

void setup()
{
    UNITY_BEGIN();
    RUN_TEST(test_envelope_rejects_ambiguous_or_invalid_requests);
    RUN_TEST(test_argument_validation_checks_types_bounds_and_finite_values);
    RUN_TEST(test_known_id_and_command_survive_a_version_error);
    RUN_TEST(test_boolean_and_string_arguments_are_not_coerced);
    UNITY_END();
}

void loop() {}
