#pragma once

#include <Adafruit_NeoPixel.h>
#include <Arduino.h>

#include "app/AppState.h"
#include "services/HeaterService.h"
#include "services/PumpService.h"
#include "services/TemperatureService.h"

class CommandDispatcher {
public:
    CommandDispatcher(AppState& state, HeaterService& heater, TemperatureService& temperature, PumpService& pump, Adafruit_NeoPixel& neopixel);

    void dispatch(const char* line, Print& out);
    void sendLineTooLong(Print& out);

private:
    AppState& _state;
    HeaterService& _heater;
    TemperatureService& _temperature;
    PumpService& _pump;
    Adafruit_NeoPixel& _neopixel;

    bool dispatchTextCommand(const char* line, Print& out);
    bool parseUint32Arg(const char* args, uint32_t& value) const;
    bool parseFloatArg(const char* args, float& value) const;
    bool parsePidValues(const char* args, float& kp, float& ki, float& kd) const;
    bool parseCommand(const char* line, long& id, char* cmd, size_t cmdSize, const char*& error) const;
    bool looksLikeJsonObject(const char* line) const;
    bool readId(const char* line, long& id) const;
    bool readCmd(const char* line, char* cmd, size_t cmdSize) const;
    bool readFloatField(const char* line, const char* key, float& value) const;
    const char* safetyText() const;
    void syncTemperatureState();
    void syncHeaterState();
    bool readTemperatureIntoState();
    bool ensureSafeTemperatureForHeating(Print& out, bool latchSensorError);

    void sendPing(long id, Print& out) const;
    void sendOk(long id, const char* cmd, Print& out) const;
    void sendStatus(long id, Print& out) const;
    void sendTextHelp(Print& out) const;
    void sendTextStatus(Print& out) const;
    void sendTextReadTemp(Print& out);
    void sendTextMosfetOn(const char* args, Print& out);
    void sendTextMosfetOff(Print& out);
    void sendTextStop(Print& out);
    void sendTextLogOn(const char* args, Print& out);
    void sendTextLogOff(Print& out);
    void sendTextLogStatus(Print& out) const;
    void sendTextSetTarget(const char* args, Print& out);
    void sendTextSetPowerLimit(const char* args, Print& out);
    void sendTextControlOn(Print& out);
    void sendTextControlOff(Print& out);
    void sendTextClearError(Print& out);
    void sendTextSetPid(const char* args, Print& out);
    void sendTextSetPidLimit(const char* args, Print& out);
    void sendTextPidOn(Print& out);
    void sendTextPidOff(Print& out);
    void sendTextPumpStart(const char* args, Print& out);
    void sendTextPumpStop(Print& out);
    void sendTextPumpSetRpm(const char* args, Print& out);
    void sendTextPumpPrime(Print& out);
    void sendTextPumpStatus(Print& out);
    void printPumpFields(Print& out) const;
    void sendTextNeoPixelOn(Print& out);
    void sendTextNeoPixelOff(Print& out);
    void sendTextNeoPixelBrightness(const char* args, Print& out);
    void sendTextNeoPixelStatus(Print& out) const;
    void applyNeoPixel();
    void printNeoPixelFields(Print& out) const;
    void sendStop(long id, Print& out);
    void sendError(long id, const char* cmd, const char* error, Print& out) const;
};
