#pragma once

#include <Arduino.h>

#include "comm/CommandDispatcher.h"
#include "configSerial.h"

class SerialCommandService {
public:
    explicit SerialCommandService(CommandDispatcher& dispatcher);

    void begin(Stream& serial);
    void update();

private:
    CommandDispatcher& _dispatcher;
    Stream* _serial = nullptr;
    char _line[SERIAL_COMMAND_MAX_LINE_LENGTH + 1] = {0};
    size_t _length = 0;
    bool _overflow = false;

    void handleChar(char c);
    void finishLine();
    void resetLine();
};
