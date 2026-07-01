#include "services/HeaterService.h"

#include "configPID.h"

constexpr uint8_t HEATER_ON = HIGH;
constexpr uint8_t HEATER_OFF = LOW;

HeaterService::HeaterService(uint8_t pin)
    : _pin(pin)
{
}

void HeaterService::begin()
{
    pinMode(_pin, OUTPUT);
    outputOff();
    _mode = Mode::Idle;
    _onoffHeatDemand = false;
    _targetC = TARGET_TEMP_C;
    _controlPowerLimitPercent = CONTROL_POWER_LIMIT_PERCENT;
    _pidKp = PID_KP;
    _pidKi = PID_KI;
    _pidKd = PID_KD;
    _pidOutputLimitPercent = PID_OUTPUT_LIMIT_PERCENT;
    resetPidState();
    _windowStartMs = millis();
    _manualTestEndMs = 0;
}

void HeaterService::update(float temperatureC, bool temperatureValid, SafetyLevel safetyLevel)
{
    if (safetyLevel == SafetyLevel::ERROR) {
        disable();
        return;
    }

    if (_mode == Mode::Manual) {
        if (!temperatureValid || isnan(temperatureC) || millis() >= _manualTestEndMs) {
            disable();
            return;
        }

        digitalWrite(_pin, HEATER_ON);
        _outputActive = true;
        _outputPercent = 100.0f;
        return;
    }

    if (_mode == Mode::Pid) {
        if (!temperatureValid || isnan(temperatureC)) {
            disable();
            return;
        }

        updatePid(temperatureC);
        return;
    }

    if (_mode != Mode::OnOff) {
        outputOff();
        return;
    }

    if (!temperatureValid || isnan(temperatureC)) {
        disable();
        return;
    }

    if (temperatureC < _targetC - ONOFF_HYSTERESIS_C) {
        _onoffHeatDemand = true;
    }

    if (temperatureC > _targetC + ONOFF_HYSTERESIS_C) {
        _onoffHeatDemand = false;
    }

    if (_onoffHeatDemand) {
        writeWindowedOutput(_controlPowerLimitPercent);
    } else {
        outputOff();
    }
}

void HeaterService::enable()
{
    _mode = Mode::OnOff;
    _onoffHeatDemand = false;
    _windowStartMs = millis();
}

void HeaterService::enablePid()
{
    _mode = Mode::Pid;
    _onoffHeatDemand = false;
    resetPidState();
    _windowStartMs = millis();
}

void HeaterService::disable()
{
    _mode = Mode::Idle;
    _onoffHeatDemand = false;
    resetPidState();
    outputOff();
}

void HeaterService::stop()
{
    disable();
}

void HeaterService::setTargetC(float targetC)
{
    _targetC = targetC;
}

void HeaterService::setControlPowerLimitPercent(float percent)
{
    _controlPowerLimitPercent = constrain(percent, CONTROL_POWER_LIMIT_MIN_PERCENT, CONTROL_POWER_LIMIT_MAX_PERCENT);
}

void HeaterService::setPid(float kp, float ki, float kd)
{
    _pidKp = kp;
    _pidKi = ki;
    _pidKd = kd;
    resetPidState();
}

void HeaterService::setPidOutputLimitPercent(float percent)
{
    _pidOutputLimitPercent = constrain(percent, HEATER_OUTPUT_MIN_PERCENT, HEATER_OUTPUT_MAX_PERCENT);
    if (_outputPercent > _pidOutputLimitPercent) {
        _outputPercent = _pidOutputLimitPercent;
    }
}

void HeaterService::startManualTest(uint32_t durationMs)
{
    _mode = Mode::Manual;
    _onoffHeatDemand = false;
    resetPidState();
    _manualTestEndMs = millis() + durationMs;
    digitalWrite(_pin, HEATER_ON);
    _outputActive = true;
    _outputPercent = 100.0f;
}

bool HeaterService::enabled() const
{
    return _mode == Mode::OnOff;
}

bool HeaterService::pidEnabled() const
{
    return _mode == Mode::Pid;
}

bool HeaterService::manualTestActive() const
{
    return _mode == Mode::Manual;
}

bool HeaterService::outputActive() const
{
    return _outputActive;
}

uint32_t HeaterService::manualTestRemainingMs() const
{
    if (_mode != Mode::Manual) {
        return 0;
    }

    const uint32_t now = millis();
    if (now >= _manualTestEndMs) {
        return 0;
    }

    return _manualTestEndMs - now;
}

float HeaterService::targetC() const
{
    return _targetC;
}

float HeaterService::outputPercent() const
{
    return _outputPercent;
}

float HeaterService::controlPowerLimitPercent() const
{
    return _controlPowerLimitPercent;
}

float HeaterService::pidKp() const
{
    return _pidKp;
}

float HeaterService::pidKi() const
{
    return _pidKi;
}

float HeaterService::pidKd() const
{
    return _pidKd;
}

float HeaterService::pidOutputLimitPercent() const
{
    return _pidOutputLimitPercent;
}

float HeaterService::pidIntegral() const
{
    return _pidIntegral;
}

void HeaterService::resetPidState()
{
    _pidIntegral = 0.0f;
    _pidLastTemperatureC = NAN;
    _pidLastComputeMs = 0;
}

void HeaterService::updatePid(float temperatureC)
{
    const float errorC = _targetC - temperatureC;
    if (errorC <= 0.0f) {
        _pidIntegral = 0.0f;
        outputOff();
        return;
    }

    const uint32_t now = millis();
    if (_pidLastComputeMs == 0) {
        _pidLastComputeMs = now;
        _pidLastTemperatureC = temperatureC;
    }

    if (now - _pidLastComputeMs >= PID_CONTROL_SAMPLE_TIME_MS) {
        const float dtS = static_cast<float>(now - _pidLastComputeMs) / 1000.0f;
        const float dTemperatureCPerS = (temperatureC - _pidLastTemperatureC) / dtS;
        const float candidateIntegral = _pidIntegral + (_pidKi * errorC * dtS);
        const float proportional = _pidKp * errorC;
        const float derivative = -_pidKd * dTemperatureCPerS;
        const float unclamped = proportional + candidateIntegral + derivative;
        const float limited = constrain(unclamped, HEATER_OUTPUT_MIN_PERCENT, _pidOutputLimitPercent);

        if (unclamped == limited || (unclamped > _pidOutputLimitPercent && errorC < 0.0f) || (unclamped < 0.0f && errorC > 0.0f)) {
            _pidIntegral = candidateIntegral;
        }

        _outputPercent = constrain(proportional + _pidIntegral + derivative, HEATER_OUTPUT_MIN_PERCENT, _pidOutputLimitPercent);
        _pidLastTemperatureC = temperatureC;
        _pidLastComputeMs = now;
    }

    if (_outputPercent <= 0.0f) {
        outputOff();
        return;
    }

    writeWindowedOutput(_outputPercent);
}

void HeaterService::outputOff()
{
    digitalWrite(_pin, HEATER_OFF);
    _outputActive = false;
    _outputPercent = 0.0f;
}

void HeaterService::writeWindowedOutput(float percent)
{
    const uint32_t now = millis();
    if (now - _windowStartMs >= HEATER_CONTROL_WINDOW_MS) {
        _windowStartMs = now;
    }

    _outputPercent = constrain(percent, HEATER_OUTPUT_MIN_PERCENT, HEATER_OUTPUT_MAX_PERCENT);
    const uint32_t onTimeMs = static_cast<uint32_t>((_outputPercent / 100.0f) * HEATER_CONTROL_WINDOW_MS);
    const bool outputOn = (now - _windowStartMs) < onTimeMs;
    digitalWrite(_pin, outputOn ? HEATER_ON : HEATER_OFF);
    _outputActive = outputOn;
}
