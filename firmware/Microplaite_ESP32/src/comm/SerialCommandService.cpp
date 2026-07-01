#include "comm/SerialCommandService.h"

SerialCommandService::SerialCommandService(CommandDispatcher& dispatcher)
    : _dispatcher(dispatcher)
{
}

void SerialCommandService::begin(Stream& serial)
{
    _serial = &serial;
    resetLine();
}

void SerialCommandService::update()
{
    if (_serial == nullptr) {
        return;
    }

    while (_serial->available() > 0) {
        handleChar(static_cast<char>(_serial->read()));
    }
}

void SerialCommandService::handleChar(char c)
{
    if (c == '\r') {
        return;
    }

    if (c == '\n') {
        finishLine();
        return;
    }

    if (_overflow) {
        return;
    }

    if (_length >= SERIAL_COMMAND_MAX_LINE_LENGTH) {
        _overflow = true;
        _length = 0;
        _line[0] = '\0';
        return;
    }

    _line[_length] = c;
    _length++;
    _line[_length] = '\0';
}

void SerialCommandService::finishLine()
{
    if (_serial == nullptr) {
        resetLine();
        return;
    }

    if (_overflow) {
        _dispatcher.sendLineTooLong(*_serial);
        resetLine();
        return;
    }

    if (_length > 0) {
        _dispatcher.dispatch(_line, *_serial);
    }

    resetLine();
}

void SerialCommandService::resetLine()
{
    _length = 0;
    _overflow = false;
    _line[0] = '\0';
}
