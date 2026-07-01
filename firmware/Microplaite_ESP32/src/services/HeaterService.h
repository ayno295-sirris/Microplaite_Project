#pragma once

#include <Arduino.h>

#include "app/AppState.h"
#include "configPID.h"

class HeaterService {
public:
    explicit HeaterService(uint8_t pin);

    void begin();
    void update(float temperatureC, bool temperatureValid, SafetyLevel safetyLevel);
    void enable();
    void disable();
    void stop();
    void startManualTest(uint32_t durationMs);
    void enablePid();
    void setTargetC(float targetC);
    void setControlPowerLimitPercent(float percent);
    void setPid(float kp, float ki, float kd);
    void setPidOutputLimitPercent(float percent);

    bool enabled() const;
    bool pidEnabled() const;
    bool manualTestActive() const;
    bool outputActive() const;
    uint32_t manualTestRemainingMs() const;
    float targetC() const;
    float outputPercent() const;
    float controlPowerLimitPercent() const;
    float pidKp() const;
    float pidKi() const;
    float pidKd() const;
    float pidOutputLimitPercent() const;
    float pidIntegral() const;

private:
    enum class Mode {
        Idle,
        OnOff,
        Pid,
        Manual
    };

    uint8_t _pin;
    Mode _mode = Mode::Idle;
    bool _outputActive = false;
    bool _onoffHeatDemand = false;
    float _targetC = 37.5f;
    float _controlPowerLimitPercent = CONTROL_POWER_LIMIT_PERCENT;
    float _pidKp = PID_KP;
    float _pidKi = PID_KI;
    float _pidKd = PID_KD;
    float _pidOutputLimitPercent = PID_OUTPUT_LIMIT_PERCENT;
    float _pidIntegral = 0.0f;
    float _pidLastTemperatureC = NAN;
    float _outputPercent = 0.0f;
    uint32_t _windowStartMs = 0;
    uint32_t _manualTestEndMs = 0;
    uint32_t _pidLastComputeMs = 0;

    void resetPidState();
    void updatePid(float temperatureC);
    void outputOff();
    void writeWindowedOutput(float percent);
};
