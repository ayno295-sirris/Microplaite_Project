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
    for (int pending = Serial1.available(); pending > 0; --pending) {
        Serial1.read();
    }
    if (!writePump(0.0f, false, false, state)) {
        return false;
    }
    readStatus(state, RESPONSE_TIMEOUT_MS, true);
    return true; // WJ sent; pumpReadbackValid qualifies the controller state.
}

bool PumpService::prime(AppState& state)
{
    return writePump(PUMP_MAX_RPM, true, true, state);
}

bool PumpService::readStatus(AppState& state, uint32_t timeoutMs)
{
    return readStatus(state, timeoutMs, false);
}

bool PumpService::readStatus(AppState& state, uint32_t timeoutMs, bool waitForWriteReply)
{
    state.pumpReadbackValid = false;
    uint8_t tx[LongerProtocol::MAX_FRAME_SIZE] = {0};
    const size_t txLength = LongerProtocol::buildReadFrame(PUMP_ADDRESS, tx, sizeof(tx));
    if (txLength == 0) {
        return false;
    }

    if (!waitForWriteReply) {
        while (Serial1.available() > 0) {
            Serial1.read();
        }
        if (Serial1.write(tx, txLength) != txLength) {
            return false;
        }
        Serial1.flush();
    }

    uint8_t rx[LongerProtocol::MAX_FRAME_SIZE] = {0};
    size_t rxLength = 0;
    const uint32_t startMs = millis(); // STOP shares this budget between WJ and RJ replies.
    while (millis() - startMs < timeoutMs) {
        if (Serial1.available() <= 0) {
            delay(1);
            continue;
        }
        const uint8_t byte = static_cast<uint8_t>(Serial1.read());
        if (byte == LongerProtocol::FLAG) {
            // A late WJ reply must not hide the following RJ frame.
            rxLength = 0;
        } else if (rxLength == 0) {
            continue;
        }
        if (rxLength >= sizeof(rx)) {
            rxLength = 0;
            continue;
        }
        rx[rxLength++] = byte;
        if (waitForWriteReply) {
            if (!LongerProtocol::parseWriteReplyFrame(rx, rxLength, PUMP_ADDRESS)) {
                continue;
            }
            if (millis() - startMs >= timeoutMs) {
                return false;
            }
            if (Serial1.write(tx, txLength) != txLength) {
                return false;
            }
            Serial1.flush();
            waitForWriteReply = false;
            rxLength = 0;
            continue;
        }
        LongerProtocol::PumpStatus status;
        if (LongerProtocol::parseStatusFrame(rx, rxLength, PUMP_ADDRESS, status)) {
            state.pumpRunning = status.running;
            state.pumpRpm = status.rpm;
            state.pumpFullSpeed = status.fullSpeed;
            state.pumpReadbackValid = true;
            return true;
        }
    }
    return false;
}

bool PumpService::writePump(float rpm, bool run, bool fullSpeed, AppState& state)
{
    state.pumpReadbackValid = false;
    rpm = clampRpm(rpm);
    uint8_t frame[LongerProtocol::MAX_FRAME_SIZE] = {0};
    const size_t length = LongerProtocol::buildWriteFrame(PUMP_ADDRESS, rpm, run, fullSpeed, frame, sizeof(frame));
    if (length == 0) {
        return false;
    }

    if (Serial1.write(frame, length) != length) {
        return false;
    }
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
