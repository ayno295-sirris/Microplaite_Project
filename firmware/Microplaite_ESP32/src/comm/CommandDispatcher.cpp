#include "comm/CommandDispatcher.h"
#include "comm/JsonProtocol.h"

#include "configPID.h"
#include "configSafety.h"
#include "configSerial.h"

#include <ctype.h>
#include <cstdlib>
#include <cstring>
#include <cfloat>
#include <cstdio>

namespace {
void printJsonNumber(Print& out, float value, int decimals)
{
    if (!std::isfinite(value)) {
        out.print("null");
        return;
    }
    // Arduino Print emits "ovf" for large finite floats, which is not valid JSON.
    char buffer[48];
    snprintf(buffer, sizeof(buffer), "%.*f", decimals, static_cast<double>(value));
    out.print(buffer);
}
}

CommandDispatcher::CommandDispatcher(AppState& state, HeaterService& heater, TemperatureService& temperature, PumpService& pump, Adafruit_NeoPixel& neopixel, SupervisionService& supervision)
    : _state(state),
      _heater(heater),
      _temperature(temperature),
      _pump(pump),
      _neopixel(neopixel),
      _supervision(supervision)
{
}

void CommandDispatcher::dispatch(const char* line, Print& out)
{
    const char* trimmedLine = line;
    while (*trimmedLine != '\0' && isspace(static_cast<unsigned char>(*trimmedLine))) {
        trimmedLine++;
    }

    if (*trimmedLine != '{') {
        if (!dispatchTextCommand(line, out)) {
            out.println("ERR BAD_COMMAND");
        }
        return;
    }

    JsonProtocol::Document request(JsonProtocol::parse(line), cJSON_Delete);
    long id = 0;
    const char* cmd = "UNKNOWN";
    const char* error = JsonProtocol::envelope(request.get(), id, cmd);
    if (error) {
        sendError(id, cmd, error, out);
        return;
    }

    if (strcmp(cmd, "PING") == 0) {
        sendPing(id, out);
        return;
    }

    if (strcmp(cmd, "STATUS") == 0) {
        sendStatus(id, out);
        return;
    }

    if (strcmp(cmd, "STOP") == 0) {
        sendStop(id, out);
        return;
    }

    if (strcmp(cmd, "SYNC") == 0 || strcmp(cmd, "HEARTBEAT") == 0) {
        error = strcmp(cmd, "SYNC") == 0 ? _supervision.sync(millis()) : _supervision.heartbeat(millis());
        if (error) sendError(id, cmd, error, out);
        else sendOk(id, cmd, out);
        return;
    }

    if (strcmp(cmd, "CLEAR_ERROR") == 0) {
        error = clearError();
        syncHeaterState();
        if (error) sendError(id, cmd, error, out);
        else sendOk(id, cmd, out);
        return;
    }

    if (strcmp(cmd, "HEATER_SET_TARGET") == 0) {
        float targetC = 0.0f;
        error = JsonProtocol::number(request.get(), "target_c", SAFETY_MIN_TARGET_TEMP_C, SAFETY_MAX_TARGET_TEMP_C, targetC);
        if (error) {
            sendError(id, cmd, error, out);
            return;
        }
        _heater.setTargetC(targetC);
        _state.heaterTargetC = _heater.targetC();
        sendOk(id, cmd, out);
        return;
    }

    if (strcmp(cmd, "HEATER_SET_PID") == 0) {
        float kp = 0, ki = 0, kd = 0;
        error = JsonProtocol::number(request.get(), "kp", 0, FLT_MAX, kp);
        if (!error) error = JsonProtocol::number(request.get(), "ki", 0, FLT_MAX, ki);
        if (!error) error = JsonProtocol::number(request.get(), "kd", 0, FLT_MAX, kd);
        if (error) {
            sendError(id, cmd, error, out);
            return;
        }
        _heater.setPid(kp, ki, kd);
        sendOk(id, cmd, out);
        return;
    }

    if (strcmp(cmd, "HEATER_SET_PID_LIMIT") == 0 || strcmp(cmd, "HEATER_SET_POWER_LIMIT") == 0) {
        const bool pid = strcmp(cmd, "HEATER_SET_PID_LIMIT") == 0;
        float percent = 0;
        error = JsonProtocol::number(request.get(), "percent", pid ? 0 : CONTROL_POWER_LIMIT_MIN_PERCENT, HEATER_OUTPUT_MAX_PERCENT, percent);
        if (!error && pid && percent <= 0) error = "OUT_OF_RANGE";
        if (error) {
            sendError(id, cmd, error, out);
            return;
        }
        if (pid) _heater.setPidOutputLimitPercent(percent);
        else _heater.setControlPowerLimitPercent(percent);
        syncHeaterState();
        sendOk(id, cmd, out);
        return;
    }

    if (strcmp(cmd, "HEATER_ENABLE") == 0) {
        const char* mode = nullptr;
        error = JsonProtocol::string(request.get(), "mode", mode);
        if (!error && strcmp(mode, "PID") != 0 && strcmp(mode, "ONOFF") != 0) error = "BAD_MODE";
        if (error) {
            sendError(id, cmd, error, out);
            return;
        }
        // Same fresh-temperature check and latch behavior as legacy PID_ON / CONTROL_ON.
        error = _supervision.activationError(millis());
        if (!error) error = checkTemperatureForHeating(true);
        if (error) {
            syncHeaterState();
            sendError(id, cmd, error, out);
            return;
        }
        if (strcmp(mode, "PID") == 0) _heater.enablePid();
        else _heater.enable();
        syncHeaterState();
        sendOk(id, cmd, out);
        return;
    }

    if (strcmp(cmd, "HEATER_DISABLE") == 0) {
        _heater.disable();
        syncHeaterState();
        sendOk(id, cmd, out);
        return;
    }

    if (strcmp(cmd, "PUMP_START") == 0 || strcmp(cmd, "PUMP_SET_RPM") == 0) {
        float rpm = 0;
        error = JsonProtocol::number(request.get(), "rpm", 0, PUMP_MAX_RPM, rpm);
        if (!error) error = _supervision.activationError(millis());
        if (error) {
            sendError(id, cmd, error, out);
            return;
        }
        const bool written = strcmp(cmd, "PUMP_START") == 0 ? _pump.start(rpm, _state) : _pump.setRpm(rpm, _state);
        sendPumpResult(id, cmd, written, out);
        return;
    }

    if (strcmp(cmd, "PUMP_STOP") == 0) {
        const bool written = _pump.stop(_state);
        sendPumpResult(id, cmd, written, out);
        return;
    }

    if (strcmp(cmd, "PUMP_PRIME") == 0) {
        error = _supervision.activationError(millis());
        if (error) {
            sendError(id, cmd, error, out);
            return;
        }
        const bool written = _pump.prime(_state);
        sendPumpResult(id, cmd, written, out);
        return;
    }

    if (strcmp(cmd, "PUMP_STATUS") == 0) {
        _pump.readStatus(_state);
        sendPumpResult(id, cmd, true, out); // The readback flag reports RJ success or failure.
        return;
    }

    if (strcmp(cmd, "NEOPIXEL_SET") == 0) {
        bool enabled = false;
        float brightness = 0;
        error = JsonProtocol::boolean(request.get(), "enabled", enabled);
        if (!error) error = JsonProtocol::number(request.get(), "brightness", 0, 100, brightness);
        if (!error && enabled) error = _supervision.activationError(millis());
        if (error) {
            sendError(id, cmd, error, out);
            return;
        }
        _state.neopixelEnabled = enabled;
        _state.neopixelBrightnessPercent = static_cast<uint8_t>(brightness + 0.5f);
        applyNeoPixel();
        sendOk(id, cmd, out);
        return;
    }

    sendError(id, cmd, "UNKNOWN_COMMAND", out);
}

void CommandDispatcher::sendLineTooLong(Print& out)
{
    sendError(0, "UNKNOWN", "LINE_TOO_LONG", out);
}

void CommandDispatcher::sendMalformedJson(Print& out)
{
    sendError(0, "UNKNOWN", "MALFORMED_JSON", out);
}

bool CommandDispatcher::dispatchTextCommand(const char* line, Print& out)
{
    while (*line != '\0' && isspace(static_cast<unsigned char>(*line))) {
        line++;
    }

    char cmd[24] = {0};
    size_t length = 0;
    while (line[length] != '\0' && !isspace(static_cast<unsigned char>(line[length]))) {
        if (length >= sizeof(cmd) - 1) {
            return false;
        }
        cmd[length] = line[length];
        length++;
    }
    cmd[length] = '\0';

    const char* args = line + length;
    while (*args != '\0' && isspace(static_cast<unsigned char>(*args))) {
        args++;
    }

    if (strcmp(cmd, "MOSFET_ON") == 0) {
        sendTextMosfetOn(args, out);
        return true;
    }

    if (strcmp(cmd, "MOSFET_OFF") == 0) {
        sendTextMosfetOff(out);
        return true;
    }

    if (strcmp(cmd, "STOP") == 0) {
        sendTextStop(out);
        return true;
    }

    if (strcmp(cmd, "PUMP_START") == 0) {
        sendTextPumpStart(args, out);
        return true;
    }

    if (strcmp(cmd, "PUMP_STOP") == 0) {
        sendTextPumpStop(out);
        return true;
    }

    if (strcmp(cmd, "PUMP_SET_RPM") == 0) {
        sendTextPumpSetRpm(args, out);
        return true;
    }

    if (strcmp(cmd, "PUMP_PRIME") == 0) {
        sendTextPumpPrime(out);
        return true;
    }

    if (strcmp(cmd, "PUMP_STATUS") == 0) {
        sendTextPumpStatus(out);
        return true;
    }

    if (strcmp(cmd, "NEOPIXEL_ON") == 0) {
        sendTextNeoPixelOn(out);
        return true;
    }

    if (strcmp(cmd, "NEOPIXEL_OFF") == 0) {
        sendTextNeoPixelOff(out);
        return true;
    }

    if (strcmp(cmd, "NEOPIXEL_BRIGHTNESS") == 0) {
        sendTextNeoPixelBrightness(args, out);
        return true;
    }

    if (strcmp(cmd, "NEOPIXEL_STATUS") == 0) {
        sendTextNeoPixelStatus(out);
        return true;
    }

    if (strcmp(cmd, "SET_TARGET") == 0) {
        sendTextSetTarget(args, out);
        return true;
    }

    if (strcmp(cmd, "SET_POWER_LIMIT") == 0) {
        sendTextSetPowerLimit(args, out);
        return true;
    }

    if (strcmp(cmd, "CONTROL_ON") == 0) {
        sendTextControlOn(out);
        return true;
    }

    if (strcmp(cmd, "CONTROL_OFF") == 0) {
        sendTextControlOff(out);
        return true;
    }

    if (strcmp(cmd, "SET_PID") == 0) {
        sendTextSetPid(args, out);
        return true;
    }

    if (strcmp(cmd, "SET_PID_LIMIT") == 0) {
        sendTextSetPidLimit(args, out);
        return true;
    }

    if (strcmp(cmd, "PID_ON") == 0) {
        sendTextPidOn(out);
        return true;
    }

    if (strcmp(cmd, "PID_OFF") == 0) {
        sendTextPidOff(out);
        return true;
    }

    if (strcmp(cmd, "CLEAR_ERROR") == 0) {
        sendTextClearError(out);
        return true;
    }

    if (strcmp(cmd, "LOG_ON") == 0) {
        sendTextLogOn(args, out);
        return true;
    }

    if (strcmp(cmd, "LOG_OFF") == 0) {
        sendTextLogOff(out);
        return true;
    }

    if (strcmp(cmd, "LOG_STATUS") == 0) {
        sendTextLogStatus(out);
        return true;
    }

    if (strcmp(cmd, "READ_TEMP") == 0) {
        sendTextReadTemp(out);
        return true;
    }

    if (strcmp(cmd, "HELP") == 0) {
        sendTextHelp(out);
        return true;
    }

    if (strcmp(cmd, "STATUS") == 0) {
        sendTextStatus(out);
        return true;
    }

    return false;
}

bool CommandDispatcher::parseUint32Arg(const char* args, uint32_t& value) const
{
    if (*args == '\0') {
        return false;
    }

    char* end = nullptr;
    const unsigned long parsed = strtoul(args, &end, 10);
    if (end == args || parsed == 0) {
        return false;
    }

    while (*end != '\0') {
        if (!isspace(static_cast<unsigned char>(*end))) {
            return false;
        }
        end++;
    }

    value = static_cast<uint32_t>(parsed);
    return true;
}

bool CommandDispatcher::parseFloatArg(const char* args, float& value) const
{
    if (*args == '\0') {
        return false;
    }

    char* end = nullptr;
    value = strtof(args, &end);
    if (end == args || isnan(value)) {
        return false;
    }

    while (*end != '\0') {
        if (!isspace(static_cast<unsigned char>(*end))) {
            return false;
        }
        end++;
    }

    return true;
}

bool CommandDispatcher::parsePidValues(const char* args, float& kp, float& ki, float& kd) const
{
    if (*args == '\0') {
        return false;
    }

    char* end = nullptr;
    kp = strtof(args, &end);
    if (end == args || isnan(kp)) {
        return false;
    }

    args = end;
    ki = strtof(args, &end);
    if (end == args || isnan(ki)) {
        return false;
    }

    args = end;
    kd = strtof(args, &end);
    if (end == args || isnan(kd)) {
        return false;
    }

    while (*end != '\0') {
        if (!isspace(static_cast<unsigned char>(*end))) {
            return false;
        }
        end++;
    }

    return kp >= 0.0f && ki >= 0.0f && kd >= 0.0f;
}

const char* CommandDispatcher::safetyText() const
{
    switch (_state.safetyLevel) {
    case SafetyLevel::OK:
        return "OK";
    case SafetyLevel::WARNING:
        return "WARNING";
    case SafetyLevel::ERROR:
        return "ERROR";
    }

    return "ERROR";
}

const char* CommandDispatcher::heaterModeText() const
{
    if (_heater.manualTestActive()) return "MANUAL";
    if (_heater.pidEnabled()) return "PID";
    if (_heater.enabled()) return "ONOFF";
    return "IDLE";
}

void CommandDispatcher::syncTemperatureState()
{
    _state.temperatureAvailable = _temperature.available();
    _state.temperatureValid = _temperature.ready();
    _state.temperatureC = _temperature.temperatureC();
    _state.temperatureFault = _temperature.fault();
}

void CommandDispatcher::syncHeaterState()
{
    _state.heaterEnabled = _heater.enabled() || _heater.pidEnabled();
    _state.heaterOutputPercent = _heater.outputPercent();
}

bool CommandDispatcher::readTemperatureIntoState()
{
    const bool ok = _temperature.available() && _temperature.readNow();
    syncTemperatureState();
    return ok;
}

bool CommandDispatcher::ensureSafeTemperatureForHeating(Print& out, bool latchSensorError)
{
    const char* error = checkTemperatureForHeating(latchSensorError);
    if (!error) return true;
    out.print("ERR ");
    out.println(error);
    return false;
}

const char* CommandDispatcher::checkTemperatureForHeating(bool latchSensorError)
{
    if (_state.errorLatched) {
        _heater.disable();
        return "OVERTEMP";
    }

    if (!readTemperatureIntoState()) {
        if (latchSensorError) {
            _state.errorLatched = true;
        }
        _state.lastError = _temperature.fault() != 0 ? "MAX31856_FAULT" : "SENSOR_INVALID";
        _heater.disable();
        return "SENSOR_INVALID";
    }

    if (isEmergencyOvertemperature(_state.temperatureC)) {
        _state.errorLatched = true;
        _state.lastError = "OVERTEMP";
        _heater.disable();
        return "OVERTEMP";
    }

    return nullptr;
}

void CommandDispatcher::sendPing(long id, Print& out) const
{
    sendOk(id, "PING", out);
}

void CommandDispatcher::sendOk(long id, const char* cmd, Print& out) const
{
    out.print("{\"v\":2,\"id\":");
    out.print(id);
    out.print(",\"type\":\"OK\",\"cmd\":\"");
    out.print(cmd);
    out.println("\"}");
}

void CommandDispatcher::sendStatus(long id, Print& out) const
{
    out.print("{\"v\":2,\"id\":");
    out.print(id);
    out.print(",\"type\":\"STATUS\",\"cmd\":\"STATUS\",\"temp_c\":");
    if (_state.temperatureValid) {
        printJsonNumber(out, _state.temperatureC, 2);
    } else {
        out.print("null");
    }
    out.print(",\"temperature_available\":");
    out.print(_state.temperatureAvailable ? "true" : "false");
    out.print(",\"temperature_valid\":");
    out.print(_state.temperatureValid ? "true" : "false");
    out.print(",\"temperature_fault\":");
    out.print(_state.temperatureFault);
    out.print(",\"heater_mode\":\"");
    out.print(heaterModeText());
    out.print("\",\"heater_gpio_on\":");
    out.print(_heater.outputActive() ? "true" : "false");
    out.print(",\"heater_target_c\":");
    printJsonNumber(out, _heater.targetC(), 2);
    out.print(",\"thermal_test_mode\":");
    out.print(THERMAL_TEST_MODE ? "true" : "false");
    out.print(",\"max_target_c\":");
    out.print(SAFETY_MAX_TARGET_TEMP_C, 2);
    out.print(",\"warning_temp_c\":");
    out.print(SAFETY_WARNING_TEMP_C, 2);
    out.print(",\"emergency_cutoff_c\":");
    out.print(SAFETY_ERROR_TEMP_C, 2);
    out.print(",\"heater_output_percent\":");
    printJsonNumber(out, _heater.outputPercent(), 1);
    out.print(",\"power_limit_percent\":");
    printJsonNumber(out, _heater.controlPowerLimitPercent(), 1);
    out.print(",\"pid_kp\":");
    printJsonNumber(out, _heater.pidKp(), 2);
    out.print(",\"pid_ki\":");
    printJsonNumber(out, _heater.pidKi(), 3);
    out.print(",\"pid_kd\":");
    printJsonNumber(out, _heater.pidKd(), 2);
    out.print(",\"pid_output_limit_percent\":");
    printJsonNumber(out, _heater.pidOutputLimitPercent(), 1);
    out.print(",\"pid_integral\":");
    printJsonNumber(out, _heater.pidIntegral(), 3);
    out.print(",\"last_error\":\"");
    out.print(_state.lastError);
    out.print("\"");
    out.print(",\"error_latched\":");
    out.print(_state.errorLatched ? "true" : "false");
    printJsonPumpFields(out);
    out.print(",\"neopixel_enabled\":");
    out.print(_state.neopixelEnabled ? "true" : "false");
    out.print(",\"neopixel_brightness\":");
    out.print(_state.neopixelBrightnessPercent);
    out.print(",\"safety\":\"");
    out.print(safetyText());
    out.print("\",\"uptime_ms\":");
    out.print(millis());
    out.print(",\"system_state\":\"");
    out.print(_supervision.systemStateText());
    out.print("\",\"comm_state\":\"");
    out.print(_supervision.commStateText());
    out.print("\",\"session_active\":");
    out.print(_supervision.sessionActive() ? "true" : "false");
    out.print(",\"heartbeat_age_ms\":");
    if (_supervision.sessionActive()) out.print(_supervision.heartbeatAgeMs(millis()));
    else out.print("null");
    out.println("}");
}

void CommandDispatcher::sendTextHelp(Print& out) const
{
    out.println("OK COMMANDS READ_TEMP SET_TARGET <temp_c> SET_POWER_LIMIT <percent> SET_PID <kp> <ki> <kd> SET_PID_LIMIT <percent> CONTROL_ON CONTROL_OFF PID_ON PID_OFF CLEAR_ERROR MOSFET_ON <seconds> MOSFET_OFF STOP PUMP_START <rpm> PUMP_STOP PUMP_SET_RPM <rpm> PUMP_PRIME PUMP_STATUS NEOPIXEL_ON NEOPIXEL_OFF NEOPIXEL_BRIGHTNESS <percent> NEOPIXEL_STATUS STATUS LOG_ON <period_ms> LOG_OFF LOG_STATUS HELP");
}

void CommandDispatcher::sendTextStatus(Print& out) const
{
    out.print("OK STATUS TEMP ");
    if (_state.temperatureValid) {
        out.print(_state.temperatureC, 2);
        out.print("C");
    } else {
        out.print("NA");
    }
    out.print(" SENSOR_VALID ");
    out.print(_state.temperatureValid ? 1 : 0);
    out.print(" FAULT ");
    out.print(_state.temperatureFault);
    out.print(" GPIO14 ");
    out.print(_heater.outputActive() ? "ON" : "OFF");
    out.print(" MODE ");
    if (_state.safetyLevel == SafetyLevel::ERROR) {
        out.print("ERROR");
    } else if (_heater.manualTestActive()) {
        out.print("MANUAL");
    } else if (_heater.pidEnabled()) {
        out.print("PID");
    } else if (_heater.enabled()) {
        out.print("ONOFF");
    } else {
        out.print("IDLE");
    }
    out.print(" TARGET ");
    out.print(_heater.targetC(), 2);
    out.print("C HYSTERESIS ");
    out.print(ONOFF_HYSTERESIS_C, 2);
    out.print("C HEATER_OUTPUT ");
    out.print(_heater.outputPercent(), 1);
    out.print("% THERMAL_TEST_MODE ");
    out.print(THERMAL_TEST_MODE ? 1 : 0);
    out.print(" MAX_TARGET ");
    out.print(SAFETY_MAX_TARGET_TEMP_C, 2);
    out.print("C WARNING_TEMP ");
    out.print(SAFETY_WARNING_TEMP_C, 2);
    out.print("C SAFETY_LIMIT ");
    out.print(SAFETY_ERROR_TEMP_C, 2);
    out.print("C POWER_LIMIT ");
    out.print(_heater.controlPowerLimitPercent(), 1);
    out.print("% PID ");
    out.print(_heater.pidKp(), 2);
    out.print(" ");
    out.print(_heater.pidKi(), 3);
    out.print(" ");
    out.print(_heater.pidKd(), 2);
    out.print(" PID_LIMIT ");
    out.print(_heater.pidOutputLimitPercent(), 1);
    out.print("% PID_INTEGRAL ");
    out.print(_heater.pidIntegral(), 3);
    out.print(" LAST_ERROR ");
    out.print(_state.lastError);
    printPumpFields(out);
    printNeoPixelFields(out);
    if (_heater.manualTestActive()) {
        out.print(" TIMEOUT_REMAINING ");
        out.print((_heater.manualTestRemainingMs() + 999U) / 1000U);
        out.println("S");
    } else {
        out.println(" TIMEOUT_REMAINING 0S");
    }
}

void CommandDispatcher::sendTextReadTemp(Print& out)
{
    if (!_temperature.available()) {
        out.println("ERR MAX31856_NOT_FOUND");
        return;
    }

    if (!_temperature.readNow()) {
        syncTemperatureState();

        out.print("ERR SENSOR_INVALID");
        if (_temperature.fault() != 0) {
            out.print(" FAULT ");
            out.print(_temperature.fault());
        }
        out.println();
        return;
    }

    syncTemperatureState();

    out.print("OK TEMP ");
    out.print(_temperature.temperatureC(), 2);
    out.println("C SENSOR_VALID 1");
}

void CommandDispatcher::sendTextMosfetOn(const char* args, Print& out)
{
    uint32_t seconds = 0;
    if (!parseUint32Arg(args, seconds)) {
        out.println("ERR MISSING_DURATION");
        return;
    }

    if (seconds > MANUAL_ON_MAX_SECONDS) {
        out.print("ERR DURATION_TOO_LONG MAX ");
        out.print(MANUAL_ON_MAX_SECONDS);
        out.println("S");
        return;
    }

    if (!ensureSafeTemperatureForHeating(out, false)) {
        return;
    }

    _heater.startManualTest(seconds * 1000UL);
    syncHeaterState();

    out.print("OK MOSFET ON ");
    out.print(seconds);
    out.println("S");
}

void CommandDispatcher::sendTextMosfetOff(Print& out)
{
    _heater.disable();
    syncHeaterState();
    out.println("OK MOSFET OFF");
}

void CommandDispatcher::sendTextStop(Print& out)
{
    _supervision.stop();
    syncHeaterState();
    out.print("OK STOP HEATER_OFF");
    printPumpFields(out);
    out.println();
}

void CommandDispatcher::sendTextLogOn(const char* args, Print& out)
{
    uint32_t periodMs = 0;
    if (*args == '\0') {
        out.println("ERR MISSING_PERIOD");
        return;
    }

    if (!parseUint32Arg(args, periodMs)) {
        out.print("ERR BAD_PERIOD MIN_PERIOD_MS ");
        out.println(SERIAL_LOG_MIN_PERIOD_MS);
        return;
    }

    bool effective = false;
    if (periodMs < SERIAL_LOG_MIN_PERIOD_MS) {
        periodMs = SERIAL_LOG_MIN_PERIOD_MS;
        effective = true;
    }

    _state.logActive = true;
    _state.logPeriodMs = periodMs;

    out.print("OK LOG ON ");
    out.print(periodMs);
    out.print("MS");
    if (effective) {
        out.print(" EFFECTIVE");
    }
    out.println();
    out.println("LOG,time_ms,temp_c,target_c,heater_output_percent,gpio14,mode,sensor_valid,fault");
}

void CommandDispatcher::sendTextLogOff(Print& out)
{
    _state.logActive = false;
    out.println("OK LOG OFF");
}

void CommandDispatcher::sendTextLogStatus(Print& out) const
{
    out.print("OK LOG STATUS ACTIVE ");
    out.print(_state.logActive ? 1 : 0);
    out.print(" PERIOD_MS ");
    out.println(_state.logPeriodMs);
}

void CommandDispatcher::sendTextSetTarget(const char* args, Print& out)
{
    float targetC = 0.0f;
    if (!parseFloatArg(args, targetC)) {
        out.println("ERR BAD_TARGET");
        return;
    }

    if (!isTargetTemperatureAllowed(targetC)) {
        out.println("ERR BAD_TARGET");
        return;
    }

    _heater.setTargetC(targetC);
    _state.heaterTargetC = _heater.targetC();

    out.print("OK TARGET ");
    out.print(_heater.targetC(), 2);
    out.println("C");
}

void CommandDispatcher::sendTextSetPowerLimit(const char* args, Print& out)
{
    float percent = 0.0f;
    if (!parseFloatArg(args, percent)) {
        out.println("ERR BAD_POWER_LIMIT");
        return;
    }

    if (percent < CONTROL_POWER_LIMIT_MIN_PERCENT || percent > CONTROL_POWER_LIMIT_MAX_PERCENT) {
        out.println("ERR BAD_POWER_LIMIT");
        return;
    }

    _heater.setControlPowerLimitPercent(percent);

    out.print("OK POWER_LIMIT ");
    out.print(_heater.controlPowerLimitPercent(), 1);
    out.println("%");
}

void CommandDispatcher::sendTextControlOn(Print& out)
{
    if (!ensureSafeTemperatureForHeating(out, true)) {
        return;
    }

    _heater.enable();
    syncHeaterState();

    out.println("OK CONTROL ON MODE ONOFF");
}

void CommandDispatcher::sendTextControlOff(Print& out)
{
    _heater.disable();
    syncHeaterState();
    out.println("OK CONTROL OFF HEATER_OFF");
}

void CommandDispatcher::sendTextClearError(Print& out)
{
    const char* error = clearError();
    if (error) {
        out.print("ERR ");
        out.println(error);
    } else {
        out.println("OK ERROR CLEARED");
    }
}

const char* CommandDispatcher::clearError()
{
    if (!readTemperatureIntoState()) {
        _heater.disable();
        return "SENSOR_INVALID";
    }

    if (!canClearThermalError(_state.temperatureC, _state.temperatureValid)) {
        _heater.disable();
        return "OVERTEMP";
    }

    _state.errorLatched = false;
    _state.lastError = "NONE";
    _state.safetyLevel = SafetyLevel::OK;
    return nullptr;
}

void CommandDispatcher::sendTextSetPid(const char* args, Print& out)
{
    float kp = 0.0f;
    float ki = 0.0f;
    float kd = 0.0f;
    if (!parsePidValues(args, kp, ki, kd)) {
        out.println("ERR BAD_PID");
        return;
    }

    _heater.setPid(kp, ki, kd);

    out.print("OK PID ");
    out.print(_heater.pidKp(), 2);
    out.print(" ");
    out.print(_heater.pidKi(), 2);
    out.print(" ");
    out.println(_heater.pidKd(), 2);
}

void CommandDispatcher::sendTextSetPidLimit(const char* args, Print& out)
{
    float percent = 0.0f;
    if (!parseFloatArg(args, percent)) {
        out.println("ERR BAD_PID_LIMIT");
        return;
    }

    if (percent <= 0.0f || percent > HEATER_OUTPUT_MAX_PERCENT) {
        out.println("ERR BAD_PID_LIMIT");
        return;
    }

    _heater.setPidOutputLimitPercent(percent);

    out.print("OK PID_LIMIT ");
    out.print(_heater.pidOutputLimitPercent(), 1);
    out.println("%");
}

void CommandDispatcher::sendTextPidOn(Print& out)
{
    if (!ensureSafeTemperatureForHeating(out, true)) {
        return;
    }

    _heater.enablePid();
    syncHeaterState();

    out.println("OK PID ON");
}

void CommandDispatcher::sendTextPidOff(Print& out)
{
    _heater.disable();
    syncHeaterState();
    out.println("OK PID OFF HEATER_OFF");
}

void CommandDispatcher::sendTextPumpStart(const char* args, Print& out)
{
    float rpm = 0.0f;
    if (!parseFloatArg(args, rpm)) {
        out.println("ERR BAD_PUMP_RPM");
        return;
    }

    if (!_pump.start(rpm, _state)) {
        out.println("ERR PUMP_WRITE_FAILED");
        return;
    }

    out.print("OK PUMP_START");
    printPumpFields(out);
    out.println();
}

void CommandDispatcher::sendTextPumpStop(Print& out)
{
    if (!_pump.stop(_state)) {
        out.println("ERR PUMP_WRITE_FAILED");
        return;
    }

    out.print("OK PUMP_STOP");
    printPumpFields(out);
    out.println();
}

void CommandDispatcher::sendTextPumpSetRpm(const char* args, Print& out)
{
    float rpm = 0.0f;
    if (!parseFloatArg(args, rpm)) {
        out.println("ERR BAD_PUMP_RPM");
        return;
    }

    if (!_pump.setRpm(rpm, _state)) {
        out.println("ERR PUMP_WRITE_FAILED");
        return;
    }

    out.print("OK PUMP_SET_RPM");
    printPumpFields(out);
    out.println();
}

void CommandDispatcher::sendTextPumpPrime(Print& out)
{
    if (!_pump.prime(_state)) {
        out.println("ERR PUMP_WRITE_FAILED");
        return;
    }

    out.print("OK PUMP_PRIME");
    printPumpFields(out);
    out.println();
}

void CommandDispatcher::sendTextPumpStatus(Print& out)
{
    _pump.readStatus(_state);
    out.print("OK PUMP_STATUS");
    printPumpFields(out);
    out.println();
}

void CommandDispatcher::printPumpFields(Print& out) const
{
    out.print(" PUMP_RUNNING ");
    out.print(_state.pumpRunning ? 1 : 0);
    out.print(" PUMP_RPM ");
    out.print(_state.pumpRpm, 1);
    out.print(" PUMP_FULL_SPEED ");
    out.print(_state.pumpFullSpeed ? 1 : 0);
    out.print(" PUMP_READBACK ");
    out.print(_state.pumpReadbackValid ? 1 : 0);
}

void CommandDispatcher::sendTextNeoPixelOn(Print& out)
{
    _state.neopixelEnabled = true;
    applyNeoPixel();
    out.print("OK NEOPIXEL_ON");
    printNeoPixelFields(out);
    out.println();
}

void CommandDispatcher::sendTextNeoPixelOff(Print& out)
{
    _state.neopixelEnabled = false;
    applyNeoPixel();
    out.print("OK NEOPIXEL_OFF");
    printNeoPixelFields(out);
    out.println();
}

void CommandDispatcher::sendTextNeoPixelBrightness(const char* args, Print& out)
{
    float percent = 0.0f;
    if (!parseFloatArg(args, percent) || percent < 0.0f || percent > 100.0f) {
        out.println("ERR BAD_NEOPIXEL_BRIGHTNESS");
        return;
    }

    _state.neopixelBrightnessPercent = static_cast<uint8_t>(percent + 0.5f);
    applyNeoPixel();
    out.print("OK NEOPIXEL_BRIGHTNESS");
    printNeoPixelFields(out);
    out.println();
}

void CommandDispatcher::sendTextNeoPixelStatus(Print& out) const
{
    out.print("OK NEOPIXEL_STATUS");
    printNeoPixelFields(out);
    out.println();
}

void CommandDispatcher::applyNeoPixel()
{
    const uint8_t brightness = static_cast<uint8_t>((static_cast<uint16_t>(_state.neopixelBrightnessPercent) * 255U) / 100U);
    _neopixel.setBrightness(brightness);
    if (_state.neopixelEnabled && _state.neopixelBrightnessPercent > 0) {
        _neopixel.fill(_neopixel.Color(255, 255, 255, 255));
    } else {
        _neopixel.clear();
    }
    _neopixel.show();
}

void CommandDispatcher::printNeoPixelFields(Print& out) const
{
    out.print(" NEOPIXEL_ENABLED ");
    out.print(_state.neopixelEnabled ? 1 : 0);
    out.print(" NEOPIXEL_BRIGHTNESS ");
    out.print(_state.neopixelBrightnessPercent);
}

void CommandDispatcher::sendStop(long id, Print& out)
{
    const bool written = _supervision.stop();
    syncHeaterState();

    sendPumpResult(id, "STOP", written, out);
}

void CommandDispatcher::printJsonPumpFields(Print& out) const
{
    out.print(",\"pump_running\":");
    out.print(_state.pumpRunning ? "true" : "false");
    out.print(",\"pump_rpm\":");
    printJsonNumber(out, _state.pumpRpm, 1);
    out.print(",\"pump_full_speed\":");
    out.print(_state.pumpFullSpeed ? "true" : "false");
    out.print(",\"pump_readback_valid\":");
    out.print(_state.pumpReadbackValid ? "true" : "false");
}

void CommandDispatcher::sendPumpResult(long id, const char* cmd, bool written, Print& out) const
{
    if (!written) {
        sendError(id, cmd, "PUMP_WRITE_FAILED", out);
        return;
    }
    out.print("{\"v\":2,\"id\":");
    out.print(id);
    out.print(",\"type\":\"OK\",\"cmd\":\"");
    out.print(cmd);
    out.print("\"");
    printJsonPumpFields(out);
    out.println("}");
}

void CommandDispatcher::sendError(long id, const char* cmd, const char* error, Print& out) const
{
    out.print("{\"v\":2,\"id\":");
    out.print(id);
    out.print(",\"type\":\"ERR\",\"cmd\":\"");
    out.print(cmd);
    out.print("\",\"error\":\"");
    out.print(error);
    out.print("\"");
    if (strncmp(cmd, "PUMP_", 5) == 0 || strcmp(cmd, "STOP") == 0) printJsonPumpFields(out);
    out.println("}");
}
