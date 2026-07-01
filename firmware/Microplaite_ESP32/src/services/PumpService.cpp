#include "services/PumpService.h"

#include "configSerial.h"
#include "pins.h"
#include "services/LongerProtocol.h"

#include <math.h>

void PumpService::begin()
{
    Serial1.begin(PUMP_SERIAL_BAUD, SERIAL_8E1, PIN_PUMP_RS485_RX, PIN_PUMP_RS485_TX);
}

bool PumpService::start(float rpm, AppState& state)
{
    return writePump(rpm, true, false, state);
}

bool PumpService::setRpm(float rpm, AppState& state)
{
    return writePump(rpm, state.pumpRunning, state.pumpFullSpeed, state);
}

bool PumpService::stop(AppState& state)
{
    return writePump(0.0f, false, false, state);
}

bool PumpService::prime(AppState& state)
{
    return writePump(PUMP_MAX_RPM, true, true, state);
}

bool PumpService::readStatus(AppState& state, uint32_t timeoutMs)
{
    uint8_t tx[LongerProtocol::MAX_FRAME_SIZE] = {0};
    const size_t txLength = LongerProtocol::buildReadFrame(PUMP_ADDRESS, tx, sizeof(tx));
    if (txLength == 0) {
        return false;
    }

    while (Serial1.available() > 0) {
        Serial1.read();
    }
    Serial1.write(tx, txLength);
    Serial1.flush();

    uint8_t rx[LongerProtocol::MAX_FRAME_SIZE] = {0};
    size_t rxLength = 0;
    const uint32_t startMs = millis();
    while (millis() - startMs < timeoutMs && rxLength < sizeof(rx)) {
        if (Serial1.available() <= 0) {
            delay(1);
            continue;
        }
        rx[rxLength++] = static_cast<uint8_t>(Serial1.read());
        LongerProtocol::PumpStatus status;
        if (LongerProtocol::parseStatusFrame(rx, rxLength, PUMP_ADDRESS, status)) {
            state.pumpRunning = status.running;
            state.pumpRpm = status.rpm;
            state.pumpFullSpeed = status.fullSpeed;
            return true;
        }
    }
    return false;
}

bool PumpService::writePump(float rpm, bool run, bool fullSpeed, AppState& state)
{
    rpm = clampRpm(rpm);
    uint8_t frame[LongerProtocol::MAX_FRAME_SIZE] = {0};
    const size_t length = LongerProtocol::buildWriteFrame(PUMP_ADDRESS, rpm, run, fullSpeed, frame, sizeof(frame));
    if (length == 0) {
        return false;
    }

    Serial1.write(frame, length);
    Serial1.flush();
    state.pumpRunning = run;
    state.pumpRpm = run ? rpm : 0.0f;
    state.pumpFullSpeed = run && fullSpeed;
    return true;
}

float PumpService::clampRpm(float rpm) const
{
    if (isnan(rpm) || rpm < 0.0f) {
        return 0.0f;
    }
    if (rpm > PUMP_MAX_RPM) {
        return PUMP_MAX_RPM;
    }
    return roundf(rpm * 10.0f) / 10.0f;
}
