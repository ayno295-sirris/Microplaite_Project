#include "comm/CommandDispatcher.h"

#include "configPID.h"
#include "configSafety.h"
#include "configSerial.h"

#include <ctype.h>
#include <cstdlib>
#include <cstring>

CommandDispatcher::CommandDispatcher(AppState& state, HeaterService& heater, TemperatureService& temperature, PumpService& pump, Adafruit_NeoPixel& neopixel)
    : _state(state),
      _heater(heater),
      _temperature(temperature),
      _pump(pump),
      _neopixel(neopixel)
{
}

void CommandDispatcher::dispatch(const char* line, Print& out)
{
    long id = 0;
    char cmd[24] = {0};
    const char* error = "MALFORMED_COMMAND";

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

    if (!parseCommand(line, id, cmd, sizeof(cmd), error)) {
        sendError(id, "UNKNOWN", error, out);
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

    if (strcmp(cmd, "HEATER_SET_TARGET") == 0) {
        float targetC = 0.0f;
        if (!readFloatField(line, "target_c", targetC)) {
            sendError(id, cmd, "MISSING_TARGET_C", out);
            return;
        }
        if (targetC < SAFETY_MIN_TARGET_TEMP_C || targetC > SAFETY_MAX_TARGET_TEMP_C) {
            sendError(id, cmd, "TARGET_UNSAFE", out);
            return;
        }
        _heater.setTargetC(targetC);
        _state.heaterTargetC = _heater.targetC();
        sendOk(id, cmd, out);
        return;
    }

    if (strcmp(cmd, "HEATER_ENABLE") == 0) {
        if (!_state.temperatureValid || _state.safetyLevel == SafetyLevel::ERROR) {
            sendError(id, cmd, "HEATER_UNSAFE", out);
            return;
        }
        _heater.enable();
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

    sendError(id, cmd, "UNKNOWN_COMMAND", out);
}

void CommandDispatcher::sendLineTooLong(Print& out)
{
    sendError(0, "UNKNOWN", "LINE_TOO_LONG", out);
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

bool CommandDispatcher::parseCommand(const char* line, long& id, char* cmd, size_t cmdSize, const char*& error) const
{
    if (!looksLikeJsonObject(line)) {
        error = "MALFORMED_JSON";
        return false;
    }

    if (!readId(line, id)) {
        error = "MISSING_ID";
        return false;
    }

    if (!readCmd(line, cmd, cmdSize)) {
        error = "MISSING_CMD";
        return false;
    }

    return true;
}

bool CommandDispatcher::looksLikeJsonObject(const char* line) const
{
    while (*line != '\0' && isspace(static_cast<unsigned char>(*line))) {
        line++;
    }

    if (*line != '{') {
        return false;
    }

    const char* end = line + strlen(line);
    while (end > line && isspace(static_cast<unsigned char>(*(end - 1)))) {
        end--;
    }

    return end > line && *(end - 1) == '}';
}

bool CommandDispatcher::readId(const char* line, long& id) const
{
    const char* key = strstr(line, "\"id\"");
    if (key == nullptr) {
        return false;
    }

    const char* colon = strchr(key, ':');
    if (colon == nullptr) {
        return false;
    }

    char* end = nullptr;
    id = strtol(colon + 1, &end, 10);
    return end != colon + 1;
}

bool CommandDispatcher::readCmd(const char* line, char* cmd, size_t cmdSize) const
{
    const char* key = strstr(line, "\"cmd\"");
    if (key == nullptr) {
        return false;
    }

    const char* colon = strchr(key, ':');
    if (colon == nullptr) {
        return false;
    }

    const char* start = strchr(colon, '"');
    if (start == nullptr) {
        return false;
    }
    start++;

    const char* end = strchr(start, '"');
    if (end == nullptr || end == start) {
        return false;
    }

    const size_t length = static_cast<size_t>(end - start);
    if (length >= cmdSize) {
        return false;
    }

    memcpy(cmd, start, length);
    cmd[length] = '\0';
    return true;
}

bool CommandDispatcher::readFloatField(const char* line, const char* key, float& value) const
{
    char quotedKey[24] = {0};
    snprintf(quotedKey, sizeof(quotedKey), "\"%s\"", key);

    const char* found = strstr(line, quotedKey);
    if (found == nullptr) {
        return false;
    }

    const char* colon = strchr(found, ':');
    if (colon == nullptr) {
        return false;
    }

    char* end = nullptr;
    value = strtof(colon + 1, &end);
    return end != colon + 1;
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
    if (_state.errorLatched) {
        _heater.disable();
        out.println("ERR OVERTEMP");
        return false;
    }

    if (!readTemperatureIntoState()) {
        if (latchSensorError) {
            _state.errorLatched = true;
        }
        _state.lastError = _temperature.fault() != 0 ? "MAX31856_FAULT" : "SENSOR_INVALID";
        _heater.disable();
        out.println("ERR SENSOR_INVALID");
        return false;
    }

    if (_state.temperatureC >= SAFETY_ERROR_TEMP_C) {
        _state.errorLatched = true;
        _state.lastError = "OVERTEMP";
        _heater.disable();
        out.println("ERR OVERTEMP");
        return false;
    }

    return true;
}

void CommandDispatcher::sendPing(long id, Print& out) const
{
    sendOk(id, "PING", out);
}

void CommandDispatcher::sendOk(long id, const char* cmd, Print& out) const
{
    out.print("{\"id\":");
    out.print(id);
    out.print(",\"type\":\"OK\",\"cmd\":\"");
    out.print(cmd);
    out.println("\"}");
}

void CommandDispatcher::sendStatus(long id, Print& out) const
{
    out.print("{\"id\":");
    out.print(id);
    out.print(",\"type\":\"STATUS\",\"temp_c\":");
    if (_state.temperatureValid) {
        out.print(_state.temperatureC, 2);
    } else {
        out.print("null");
    }
    out.print(",\"temperature_available\":");
    out.print(_state.temperatureAvailable ? "true" : "false");
    out.print(",\"temperature_valid\":");
    out.print(_state.temperatureValid ? "true" : "false");
    out.print(",\"temperature_fault\":");
    out.print(_state.temperatureFault);
    out.print(",\"heater_enabled\":");
    out.print(_state.heaterEnabled ? "true" : "false");
    out.print(",\"heater_target_c\":");
    out.print(_state.heaterTargetC, 2);
    out.print(",\"heater_output_percent\":");
    out.print(_state.heaterOutputPercent, 1);
    out.print(",\"power_limit_percent\":");
    out.print(_heater.controlPowerLimitPercent(), 1);
    out.print(",\"pid_kp\":");
    out.print(_heater.pidKp(), 2);
    out.print(",\"pid_ki\":");
    out.print(_heater.pidKi(), 3);
    out.print(",\"pid_kd\":");
    out.print(_heater.pidKd(), 2);
    out.print(",\"pid_output_limit_percent\":");
    out.print(_heater.pidOutputLimitPercent(), 1);
    out.print(",\"pid_integral\":");
    out.print(_heater.pidIntegral(), 3);
    out.print(",\"last_error\":\"");
    out.print(_state.lastError);
    out.print("\"");
    out.print(",\"pump_running\":");
    out.print(_state.pumpRunning ? "true" : "false");
    out.print(",\"pump_rpm\":");
    out.print(_state.pumpRpm, 1);
    out.print(",\"pump_full_speed\":");
    out.print(_state.pumpFullSpeed ? "true" : "false");
    out.print(",\"neopixel_enabled\":");
    out.print(_state.neopixelEnabled ? "true" : "false");
    out.print(",\"neopixel_brightness\":");
    out.print(_state.neopixelBrightnessPercent);
    out.print(",\"safety\":\"");
    out.print(safetyText());
    out.print("\",\"uptime_ms\":");
    out.print(_state.uptimeMs);
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
    out.print("% SAFETY_LIMIT ");
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
    _heater.stop();
    _pump.stop(_state);
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

    if (targetC < SAFETY_MIN_TARGET_TEMP_C || targetC > SAFETY_MAX_TARGET_TEMP_C) {
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
    if (!readTemperatureIntoState()) {
        _heater.disable();
        out.println("ERR SENSOR_INVALID");
        return;
    }

    if (_state.temperatureC >= SAFETY_ERROR_TEMP_C) {
        _heater.disable();
        out.println("ERR OVERTEMP");
        return;
    }

    _state.errorLatched = false;
    _state.lastError = "NONE";
    _state.safetyLevel = SafetyLevel::OK;
    out.println("OK ERROR CLEARED");
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
    const bool readback = _pump.readStatus(_state);
    out.print("OK PUMP_STATUS");
    printPumpFields(out);
    out.print(" PUMP_READBACK ");
    out.println(readback ? 1 : 0);
}

void CommandDispatcher::printPumpFields(Print& out) const
{
    out.print(" PUMP_RUNNING ");
    out.print(_state.pumpRunning ? 1 : 0);
    out.print(" PUMP_RPM ");
    out.print(_state.pumpRpm, 1);
    out.print(" PUMP_FULL_SPEED ");
    out.print(_state.pumpFullSpeed ? 1 : 0);
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
    _heater.stop();
    _pump.stop(_state);
    syncHeaterState();

    sendOk(id, "STOP", out);
}

void CommandDispatcher::sendError(long id, const char* cmd, const char* error, Print& out) const
{
    out.print("{\"id\":");
    out.print(id);
    out.print(",\"type\":\"ERR\",\"cmd\":\"");
    out.print(cmd);
    out.print("\",\"error\":\"");
    out.print(error);
    out.println("\"}");
}
