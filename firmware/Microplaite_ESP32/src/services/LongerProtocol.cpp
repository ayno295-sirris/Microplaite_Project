#include "services/LongerProtocol.h"

#include <cstring>
#include <math.h>

namespace {

constexpr uint8_t PDU_WRITE_PARAMS[] = {0x57, 0x4A};
constexpr uint8_t PDU_READ_STATE[] = {0x52, 0x4A};

uint8_t xorFcs(const uint8_t* data, size_t size)
{
    uint8_t fcs = 0;
    for (size_t i = 0; i < size; i++) {
        fcs ^= data[i];
    }
    return fcs;
}

bool appendStuffed(uint8_t value, uint8_t* out, size_t outSize, size_t& length)
{
    if (value == LongerProtocol::ESC || value == LongerProtocol::FLAG) {
        if (length + 2 > outSize) {
            return false;
        }
        out[length++] = LongerProtocol::ESC;
        out[length++] = value == LongerProtocol::ESC ? 0x00 : 0x01;
        return true;
    }

    if (length + 1 > outSize) {
        return false;
    }
    out[length++] = value;
    return true;
}

size_t buildFrame(uint8_t addr, const uint8_t* pdu, size_t pduSize, uint8_t* out, size_t outSize)
{
    if (outSize < 1 || pduSize > 255) {
        return 0;
    }

    uint8_t body[10] = {0};
    const size_t bodySize = pduSize + 3;
    if (bodySize > sizeof(body)) {
        return 0;
    }

    body[0] = addr;
    body[1] = static_cast<uint8_t>(pduSize);
    memcpy(body + 2, pdu, pduSize);
    body[bodySize - 1] = xorFcs(body, bodySize - 1);

    size_t length = 0;
    out[length++] = LongerProtocol::FLAG;
    for (size_t i = 0; i < bodySize; i++) {
        if (!appendStuffed(body[i], out, outSize, length)) {
            return 0;
        }
    }
    return length;
}

bool unstuffFrame(const uint8_t* frame, size_t frameSize, uint8_t* body, size_t bodySize, size_t& length)
{
    if (frameSize < 4 || frame[0] != LongerProtocol::FLAG) {
        return false;
    }

    length = 0;
    for (size_t i = 1; i < frameSize; i++) {
        uint8_t value = frame[i];
        if (value == LongerProtocol::ESC) {
            if (++i >= frameSize) {
                return false;
            }
            if (frame[i] == 0x00) {
                value = LongerProtocol::ESC;
            } else if (frame[i] == 0x01) {
                value = LongerProtocol::FLAG;
            } else {
                return false;
            }
        }
        if (length >= bodySize) {
            return false;
        }
        body[length++] = value;
    }
    return true;
}

uint16_t speedTenths(float rpm)
{
    if (rpm < 0.0f) {
        rpm = 0.0f;
    }
    if (rpm > 100.0f) {
        rpm = 100.0f;
    }
    return static_cast<uint16_t>(lroundf(rpm * 10.0f));
}

}

namespace LongerProtocol {

size_t buildWriteFrame(uint8_t addr, float rpm, bool run, bool fullSpeed, uint8_t* out, size_t outSize)
{
    const uint16_t speed = speedTenths(rpm);
    uint8_t pdu[] = {
        PDU_WRITE_PARAMS[0],
        PDU_WRITE_PARAMS[1],
        static_cast<uint8_t>((speed >> 8) & 0xFF),
        static_cast<uint8_t>(speed & 0xFF),
        static_cast<uint8_t>((run ? 0x01 : 0x00) | (fullSpeed ? 0x02 : 0x00)),
        0x01,
    };
    return buildFrame(addr, pdu, sizeof(pdu), out, outSize);
}

size_t buildReadFrame(uint8_t addr, uint8_t* out, size_t outSize)
{
    return buildFrame(addr, PDU_READ_STATE, sizeof(PDU_READ_STATE), out, outSize);
}

bool parseStatusFrame(const uint8_t* frame, size_t frameSize, uint8_t addr, PumpStatus& status)
{
    uint8_t body[10] = {0};
    size_t bodyLength = 0;
    if (!unstuffFrame(frame, frameSize, body, sizeof(body), bodyLength)) {
        return false;
    }
    if (bodyLength != 9 || body[0] != addr || body[1] != 6) {
        return false;
    }
    if (xorFcs(body, bodyLength - 1) != body[bodyLength - 1]) {
        return false;
    }
    if (body[2] != PDU_READ_STATE[0] || body[3] != PDU_READ_STATE[1]) {
        return false;
    }

    const uint16_t speed = (static_cast<uint16_t>(body[4]) << 8) | body[5];
    status.rpm = speed / 10.0f;
    status.running = (body[6] & 0x01) != 0;
    status.fullSpeed = (body[6] & 0x02) != 0;
    return true;
}

bool selfCheck()
{
    uint8_t frame[MAX_FRAME_SIZE] = {0};
    const uint8_t expected[] = {0xE9, 0x01, 0x06, 0x57, 0x4A, 0x00, 0x64, 0x01, 0x01, 0x7E};
    const size_t length = buildWriteFrame(1, 10.0f, true, false, frame, sizeof(frame));
    return length == sizeof(expected) && memcmp(frame, expected, sizeof(expected)) == 0;
}

}
