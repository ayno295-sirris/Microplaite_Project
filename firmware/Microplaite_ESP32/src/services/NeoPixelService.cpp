#include "services/NeoPixelService.h"

NeoPixelService::NeoPixelService(AppState& state, Adafruit_NeoPixel& pixels)
    : _state(state), _pixels(pixels)
{
}

void NeoPixelService::begin()
{
    _pixels.begin();
    _state.neopixelBrightnessPercent = 0;
    stop();
}

void NeoPixelService::set(bool enabled, uint8_t brightness, bool keepOn, uint32_t now)
{
    const bool wasOn = on();
    const bool wasKeepOn = _state.neopixelKeepOn;
    _state.neopixelEnabled = enabled;
    _state.neopixelBrightnessPercent = brightness;
    _state.neopixelKeepOn = enabled && keepOn;

    if (!on()) _onSinceMs = 0;
    else if (!wasOn || (wasKeepOn && !_state.neopixelKeepOn)) _onSinceMs = now;
    apply();
}

void NeoPixelService::stop()
{
    _state.neopixelEnabled = false;
    _state.neopixelKeepOn = false;
    _onSinceMs = 0;
    apply();
}

void NeoPixelService::update(uint32_t now)
{
    if (on() && !_state.neopixelKeepOn && now - _onSinceMs >= AUTO_OFF_MS) stop();
}

bool NeoPixelService::on() const
{
    return _state.neopixelEnabled && _state.neopixelBrightnessPercent > 0;
}

void NeoPixelService::apply()
{
    const uint8_t brightness = static_cast<uint8_t>((static_cast<uint16_t>(_state.neopixelBrightnessPercent) * 255U) / 100U);
    _pixels.setBrightness(brightness);
    if (on()) {
        _pixels.fill(_pixels.Color(255, 255, 255, 255));
    } else {
        _pixels.clear();
    }
    _pixels.show();
}
