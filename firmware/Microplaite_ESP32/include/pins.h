#pragma once

constexpr int PIN_MAX31856_SCK   = 12;
constexpr int PIN_MAX31856_MISO  = 13;
constexpr int PIN_MAX31856_MOSI  = 11;
constexpr int PIN_MAX31856_CS    = 10;

constexpr int PIN_MAX31856_DRDY  = 9;
constexpr int PIN_MAX31856_FAULT = 8;

// GPIO number, not physical header pin number.
constexpr int PIN_HEATER_PWM     = 14;

constexpr int PIN_NEOPIXEL_DATA  = 15;
constexpr int NEOPIXEL_COUNT     = 16;

constexpr int PIN_PUMP_RS485_RX  = 18;
constexpr int PIN_PUMP_RS485_TX  = 21;
