#pragma once

#include <Arduino.h>

#include "app/AppState.h"

class PumpService {
    static constexpr uint32_t RESPONSE_TIMEOUT_MS = 200;

public:
    void begin();
    // nullptr means the write succeeded; readback validity remains separate.
    const char* start(float rpm, AppState& state, bool clockwise = true);
    const char* setRpm(float rpm, AppState& state, bool clockwise = true);
    bool stop(AppState& state);
    const char* prime(AppState& state);
    bool readStatus(AppState& state, uint32_t timeoutMs = RESPONSE_TIMEOUT_MS);

private:
    bool readStatus(AppState& state, uint32_t timeoutMs, bool waitForWriteReply);
    const char* directionError(bool clockwise, const AppState& state) const;
    bool writePump(float rpm, bool run, bool fullSpeed, bool clockwise, AppState& state);
    float clampRpm(float rpm) const;
};
