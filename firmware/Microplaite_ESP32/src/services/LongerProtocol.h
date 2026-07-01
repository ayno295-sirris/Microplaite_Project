#pragma once

#include <Arduino.h>

namespace LongerProtocol {

constexpr uint8_t FLAG = 0xE9;
constexpr uint8_t ESC = 0xE8;
constexpr size_t MAX_FRAME_SIZE = 20;

struct PumpStatus {
    bool running = false;
    float rpm = 0.0f;
    bool fullSpeed = false;
};

size_t buildWriteFrame(uint8_t addr, float rpm, bool run, bool fullSpeed, uint8_t* out, size_t outSize);
size_t buildReadFrame(uint8_t addr, uint8_t* out, size_t outSize);
bool parseStatusFrame(const uint8_t* frame, size_t frameSize, uint8_t addr, PumpStatus& status);
bool selfCheck();

}
