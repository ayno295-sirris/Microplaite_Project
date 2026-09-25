#include "services/SupervisionService.h"

#include "services/HeaterService.h"
#include "services/PumpService.h"

SupervisionService::SupervisionService(AppState& state, HeaterService& heater, PumpService& pump)
    : _state(state), _heater(heater), _pump(pump)
{
}

void SupervisionService::begin(bool hardwareReady)
{
    _initialized = true;
    _hardwareReady = hardwareReady;
    _state.commState = CommState::NO_SESSION;
    _lastHeartbeatMs = 0;
    refreshState();
}

bool SupervisionService::actuatorsActive() const
{
    return _heater.enabled() || _heater.pidEnabled() || _heater.manualTestActive() || _state.pumpRunning;
}

void SupervisionService::refreshState()
{
    if (_state.errorLatched || _state.safetyLevel == SafetyLevel::ERROR || (_initialized && !_hardwareReady)) {
        _state.systemState = SystemState::FAULT;
    } else if (!_initialized) {
        _state.systemState = SystemState::BOOT;
    } else if (actuatorsActive()) {
        _state.systemState = SystemState::RUNNING;
    } else {
        _state.systemState = sessionActive() ? SystemState::READY : SystemState::IDLE;
    }
}

void SupervisionService::update(uint32_t now)
{
    if (sessionActive() && heartbeatAgeMs(now) > HEARTBEAT_TIMEOUT_MS) {
        _state.commState = CommState::LOST; // Revoke before any blocking pump transaction.
        if (actuatorsActive()) stop();
    }
    refreshState();
}

const char* SupervisionService::sync(uint32_t now)
{
    update(now);
    if (_state.systemState == SystemState::FAULT) return "SYSTEM_FAULT";
    if (!_initialized) return "SYSTEM_NOT_READY";
    _lastHeartbeatMs = now;
    _state.commState = CommState::ACTIVE;
    refreshState();
    return nullptr;
}

const char* SupervisionService::heartbeat(uint32_t now)
{
    update(now); // A late heartbeat cannot rescue an expired session.
    if (!sessionActive()) return "NO_SESSION";
    _lastHeartbeatMs = now;
    return nullptr; // update() preserves FAULT even while communication stays active.
}

const char* SupervisionService::activationError(uint32_t now)
{
    update(now);
    if (_state.systemState == SystemState::FAULT) return "SYSTEM_FAULT";
    if (!_initialized) return "SYSTEM_NOT_READY";
    return sessionActive() ? nullptr : "NO_SESSION";
}

bool SupervisionService::stop()
{
    _heater.stop();
    const bool written = _pump.stop(_state);
    _state.heaterEnabled = false;
    _state.heaterOutputPercent = _heater.outputPercent();
    // If the controller still reports RUNNING, never mask it with IDLE/READY.
    refreshState();
    return written;
}

bool SupervisionService::sessionActive() const
{
    return _state.commState == CommState::ACTIVE;
}

uint32_t SupervisionService::heartbeatAgeMs(uint32_t now) const
{
    return now - _lastHeartbeatMs;
}

const char* SupervisionService::systemStateText() const
{
    switch (_state.systemState) {
    case SystemState::BOOT: return "BOOT";
    case SystemState::IDLE: return "IDLE";
    case SystemState::READY: return "READY";
    case SystemState::RUNNING: return "RUNNING";
    case SystemState::FAULT: return "FAULT";
    }
    return "FAULT";
}

const char* SupervisionService::commStateText() const
{
    switch (_state.commState) {
    case CommState::NO_SESSION: return "NO_SESSION";
    case CommState::ACTIVE: return "ACTIVE";
    case CommState::LOST: return "LOST";
    }
    return "LOST";
}
