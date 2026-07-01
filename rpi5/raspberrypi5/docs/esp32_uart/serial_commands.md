# Serial Commands

This document lists the existing ESP32 firmware serial commands. It documents the current command surface only and does not change the firmware behavior.

## General Notes

- Commands are sent as plain text over the serial interface.
- Parameters are separated by spaces.
- Typical responses can vary slightly depending on the current firmware state, temperature, error status, and logging mode.
- For heating commands, keep the hardware supervised and stay within the validated test setup.

## Commands

### HELP

- Role: prints the list of available commands or a short help message.
- Example: `HELP`
- Typical response: a multi-line list of supported serial commands.
- Safety note: none.

### READ_TEMP

- Role: reads and returns the current measured temperature.
- Example: `READ_TEMP`
- Typical response: current temperature value, for example `TEMP 24.50`.
- Safety note: verify that the sensor reading is plausible before enabling heating.

### STATUS

- Role: prints the current firmware status, including temperature, target, heater/control state, PID state, limits, and error state.
- Example: `STATUS`
- Typical response: status line or multi-line status report with the current operating state.
- Safety note: use before and during heating tests to confirm that limits and states are correct.

### LOG_ON <period_ms>

- Role: enables periodic serial logging with the requested period in milliseconds.
- Example: `LOG_ON 200`
- Typical response: acknowledgement that logging is enabled, with the selected period.
- Safety note: use a reasonable period to avoid flooding the serial link.

### LOG_OFF

- Role: disables periodic serial logging.
- Example: `LOG_OFF`
- Typical response: acknowledgement that logging is disabled.
- Safety note: none.

### LOG_STATUS

- Role: reports whether periodic serial logging is enabled and the active logging period.
- Example: `LOG_STATUS`
- Typical response: logging state and period, for example enabled at `200 ms` or disabled.
- Safety note: none.

### MOSFET_ON <seconds>

- Role: turns the MOSFET on for a limited duration in seconds.
- Example: `MOSFET_ON 2`
- Typical response: acknowledgement that the MOSFET timed activation has started.
- Safety note: use only short validated durations during manual tests. Monitor temperature and be ready to send `STOP`.

### MOSFET_OFF

- Role: turns the MOSFET off.
- Example: `MOSFET_OFF`
- Typical response: acknowledgement that the MOSFET is off.
- Safety note: use to end a manual MOSFET test if needed.

### SET_TARGET <temp_c>

- Role: sets the target temperature in degrees Celsius for control and PID modes.
- Example: `SET_TARGET 37.50`
- Typical response: acknowledgement with the new target temperature.
- Safety note: do not set a target above the validated safety limit for the current bench setup.

### SET_POWER_LIMIT <percent>

- Role: sets the power limit used by the non-PID control path.
- Example: `SET_POWER_LIMIT 15`
- Typical response: acknowledgement with the new power limit percentage.
- Safety note: increase power limits gradually because the heater has strong thermal inertia.

### CONTROL_ON

- Role: enables the ON/OFF temperature control mode.
- Example: `CONTROL_ON`
- Typical response: acknowledgement that control mode is enabled.
- Safety note: confirm the target temperature and safety state before enabling control.

### CONTROL_OFF

- Role: disables the ON/OFF temperature control mode.
- Example: `CONTROL_OFF`
- Typical response: acknowledgement that control mode is disabled.
- Safety note: none.

### SET_PID <kp> <ki> <kd>

- Role: sets the PID gains.
- Example: `SET_PID 8 0.03 20`
- Typical response: acknowledgement with the configured `Kp`, `Ki`, and `Kd` values.
- Safety note: use the validated reference gains unless a controlled tuning test is planned.

### SET_PID_LIMIT <percent>

- Role: sets the maximum PID output as a percentage.
- Example: `SET_PID_LIMIT 15`
- Typical response: acknowledgement with the configured PID output limit.
- Safety note: do not increase this value abruptly. The thermal system reacts slowly and can overshoot after power has already been applied.

### PID_ON

- Role: enables PID temperature control.
- Example: `PID_ON`
- Typical response: acknowledgement that PID control is enabled.
- Safety note: verify `SET_TARGET`, `SET_PID`, `SET_PID_LIMIT`, and sensor readings before enabling PID.

### PID_OFF

- Role: disables PID temperature control.
- Example: `PID_OFF`
- Typical response: acknowledgement that PID control is disabled.
- Safety note: use as part of the normal shutdown sequence after `STOP`.

### STOP

- Role: immediately stops active heating/control outputs and puts the firmware in a safe stopped state.
- Example: `STOP`
- Typical response: acknowledgement that outputs/control have stopped.
- Safety note: primary command to stop heating during a test or unexpected behavior.

### CLEAR_ERROR

- Role: clears a latched error state when the underlying condition has been removed.
- Example: `CLEAR_ERROR`
- Typical response: acknowledgement that the error state has been cleared, or a message indicating that clearing is not possible yet.
- Safety note: do not clear an error until the cause has been understood and the hardware is safe.
