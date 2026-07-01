#pragma once

#include "app/AppState.h"

class SafetyService {
public:
    void begin();
    void update(AppState& state);

private:
    SafetyLevel _lastLevel = SafetyLevel::OK;
};
