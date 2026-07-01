#pragma once

#include <Arduino.h>

constexpr uint32_t SERIAL_BAUD = 115200;
constexpr size_t SERIAL_COMMAND_MAX_LINE_LENGTH = 160;
constexpr uint32_t SERIAL_LOG_MIN_PERIOD_MS = 200;

constexpr uint32_t PUMP_SERIAL_BAUD = 9600;
constexpr uint8_t PUMP_ADDRESS = 1;
constexpr float PUMP_MAX_RPM = 100.0f;
