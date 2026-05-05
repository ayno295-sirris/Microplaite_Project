# Communication Protocols

## Raspberry Pi to ESP32 serial protocol

### M7 scope
M7 defines and implements the first usable serial protocol between the Raspberry Pi and the ESP32.
It is the first active protocol milestone, focused on heating control and safe status exchange.

### Goals
- validate the serial link
- request a simple structured status
- provide a minimal safety stop command
- transmit a temperature setpoint to the ESP32
- keep the format extensible for later milestones

### Format
- Each message is one JSON object per line.
- The official line terminator is `\n`.
- Parsers may tolerate `\r\n`, but `\n` is the specification.
- The `id` field is required on every message.
- Responses use a `type` field with one of: `OK`, `ERR`, `STATUS`.

### Protocol version
The protocol version is explicit in responses.

Example:
```json
{"id":1,"type":"OK","proto":"M7.0"}
```

### Active M7 commands
- `PING`
- `STATUS`
- `STOP`
- `SET_TEMPERATURE`

### Command to response

| Command | Expected response |
| --- | --- |
| `PING` | `OK` |
| `STATUS` | `STATUS` |
| `STOP` | `OK` or `ERR` |
| `SET_TEMPERATURE` | `OK` or `ERR` |

### Reserved future command
- `SET_PUMP`
- This command is reserved for a later milestone and is not part of the active M7 scope.

### Request examples
```json
{"id":1,"cmd":"PING"}
{"id":2,"cmd":"STATUS"}
{"id":3,"cmd":"STOP"}
{"id":4,"cmd":"SET_TEMPERATURE","setpoint_c":37.0}
```

### Response examples
```json
{"id":1,"type":"OK","proto":"M7.0"}
{"id":2,"type":"STATUS","proto":"M7.0","state":"idle"}
{"id":3,"type":"ERR","code":"BAD_COMMAND","message":"Unknown command"}
{"id":4,"type":"OK","proto":"M7.0"}
```

### Timeouts and retries
These are documented for the Raspberry Pi side only.
- response timeout: 500 ms
- retry count: 2
- after retries fail, raise a communication error

### Notes
- Keep commands minimal and readable.
- M7 is an implementation milestone, not a documentation-only placeholder.
- Pump control remains out of scope for M7.
- The Raspberry Pi implementation lives in `rpi5_project`.
- The ESP32 implementation lives in `esp32_project`.

---

## Placeholder sections
The sections below are reserved for later milestones and remain out of scope for M7.

## ESP32 to pump RS485 protocol

## Camera interface

## Message format decisions

## Open questions
