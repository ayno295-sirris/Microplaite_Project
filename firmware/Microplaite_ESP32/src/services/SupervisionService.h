#pragma once

#include "app/AppState.h"

class HeaterService;
class PumpService;

class SupervisionService {
public:
    static constexpr uint32_t HEARTBEAT_NOMINAL_MS = 500;
    static constexpr uint32_t HEARTBEAT_WARNING_MS = 1000; // Informative only; no stop here.
    static constexpr uint32_t HEARTBEAT_TIMEOUT_MS = 3000;

    SupervisionService(AppState& state, HeaterService& heater, PumpService& pump);
    void begin(bool hardwareReady);
    void update(uint32_t now);
    void refreshState();
    const char* sync(uint32_t now);
    const char* heartbeat(uint32_t now);
    const char* activationError(uint32_t now);
    bool stop();

    bool sessionActive() const;
    uint32_t heartbeatAgeMs(uint32_t now) const;
    const char* systemStateText() const;
    const char* commStateText() const;

private:
    AppState& _state;
    HeaterService& _heater;
    PumpService& _pump;
    bool _initialized = false;
    bool _hardwareReady = false;
    uint32_t _lastHeartbeatMs = 0;

    bool actuatorsActive() const;
};
