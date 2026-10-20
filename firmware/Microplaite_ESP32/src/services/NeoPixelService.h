#pragma once

#include <Adafruit_NeoPixel.h>

#include "app/AppState.h"

class NeoPixelService {
public:
    static constexpr uint32_t AUTO_OFF_MS = 120000;

    NeoPixelService(AppState& state, Adafruit_NeoPixel& pixels);
    void begin();
    void set(bool enabled, uint8_t brightness, bool keepOn, uint32_t now);
    void stop();
    void update(uint32_t now);
    bool on() const;

private:
    AppState& _state;
    Adafruit_NeoPixel& _pixels;
    uint32_t _onSinceMs = 0;

    void apply();
};
