#pragma once

#include <Adafruit_NeoPixel.h>

#include "app/AppState.h"
#include "comm/CommandDispatcher.h"
#include "comm/SerialCommandService.h"
#include "services/HeaterService.h"
#include "services/PumpService.h"
#include "services/SafetyService.h"
#include "services/TemperatureService.h"

class App {
public:
    App();

    void begin();
    void update();

private:
    AppState _state;
    Adafruit_NeoPixel _neopixel;
    HeaterService _heater;
    PumpService _pump;
    TemperatureService _temperature;
    SafetyService _safety;
    CommandDispatcher _dispatcher;
    SerialCommandService _serialCommands;
    uint32_t _lastLogMs = 0;
    uint32_t _lastLoggedTemperatureReadMs = 0;

    void updateState();
    void beginNeoPixel();
    void writeLogIfDue();
    const char* modeText() const;
};
