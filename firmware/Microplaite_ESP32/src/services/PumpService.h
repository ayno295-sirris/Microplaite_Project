#pragma once

#include <Arduino.h>

#include "app/AppState.h"

class PumpService {
    static constexpr uint32_t RESPONSE_TIMEOUT_MS = 200;

public:
    void begin();
    bool start(float rpm, AppState& state);
    bool setRpm(float rpm, AppState& state);
    bool stop(AppState& state);
    bool prime(AppState& state);
    bool readStatus(AppState& state, uint32_t timeoutMs = RESPONSE_TIMEOUT_MS);

private:
    bool readStatus(AppState& state, uint32_t timeoutMs, bool waitForWriteReply);
    bool writePump(float rpm, bool run, bool fullSpeed, AppState& state);
    float clampRpm(float rpm) const;
};
