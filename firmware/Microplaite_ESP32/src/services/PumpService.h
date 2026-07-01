#pragma once

#include <Arduino.h>

#include "app/AppState.h"

class PumpService {
public:
    void begin();
    bool start(float rpm, AppState& state);
    bool setRpm(float rpm, AppState& state);
    bool stop(AppState& state);
    bool prime(AppState& state);
    bool readStatus(AppState& state, uint32_t timeoutMs = 200);

private:
    bool writePump(float rpm, bool run, bool fullSpeed, AppState& state);
    float clampRpm(float rpm) const;
};
