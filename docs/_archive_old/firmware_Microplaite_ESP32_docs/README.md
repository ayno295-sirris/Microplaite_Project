# ESP32 Documentation

Documentation specific to the ESP32 firmware project lives here.

## Index

- PlatformIO MAX31856 bring-up:
  `docs/platformio_max31856_bringup.md`
  ([open](platformio_max31856_bringup.md))
- Heater hardware/control reference:
  `docs/hardware/heater_control_system.md`
  ([open](hardware/heater_control_system.md))

The heater documentation is the authoritative hardware and control reference for
Codex sessions working in `firmware/Microplaite_ESP32/`.

## UART Protocol

The ESP32 accepts one JSON command per line over USB Serial/UART. Each command
must include `id` and `cmd`.

Minimum commands:

```json
{"id":1,"cmd":"PING"}
{"id":2,"cmd":"STATUS"}
{"id":3,"cmd":"STOP"}
{"id":4,"cmd":"HEATER_SET_TARGET","target_c":37.5}
{"id":5,"cmd":"HEATER_ENABLE"}
{"id":6,"cmd":"HEATER_DISABLE"}
```

Responses are JSON lines with `type` set to `OK`, `STATUS`, or `ERR`.

Current `STATUS` fields:

```json
{
  "id": 2,
  "type": "STATUS",
  "temp_c": 37.42,
  "temperature_available": true,
  "temperature_valid": true,
  "temperature_fault": 0,
  "heater_enabled": false,
  "heater_target_c": 37.50,
  "heater_output_percent": 0.0,
  "pump_running": false,
  "safety": "OK",
  "uptime_ms": 12345
}
```

`HEATER_ENABLE` is rejected unless `temperature_valid=true` and `safety` is not
`ERROR`.

`temperature_fault` is the MAX31856 fault mask. `0` means no active fault.
`HEATER_SET_TARGET` accepts `target_c` from 20.0 C to 37.5 C.
