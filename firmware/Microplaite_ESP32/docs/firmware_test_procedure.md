# Firmware Test Procedure

This procedure is a short operational checklist for the validated ESP32 firmware behavior. It does not require code changes, compilation, flashing, or hardware automation.

## 1. Hardware Preparation

- Connect the ESP32 firmware target using the validated bench wiring.
- Verify the temperature sensor is connected and returns plausible ambient values.
- Verify the heater power path and MOSFET wiring before enabling any heating command.
- Keep the system supervised during heating tests.
- Keep the serial terminal ready to send `STOP`.

## 2. Temperature Reading Test

1. Send `READ_TEMP`.
2. Confirm that the returned temperature is plausible and stable.
3. Send `STATUS`.
4. Confirm that there is no unexpected active error before heating.

## 3. Logging Test

1. Send `LOG_ON 200`.
2. Confirm that periodic log lines are received.
3. Send `LOG_STATUS`.
4. Confirm that logging is enabled with a `200 ms` period.
5. Send `LOG_OFF`.
6. Confirm that periodic log lines stop.

## 4. Timed MOSFET Test

1. Send `MOSFET_ON 1` or another short validated duration.
2. Confirm that the MOSFET activation is time-limited.
3. Confirm that the output turns off automatically.
4. Send `MOSFET_OFF` if needed.

Safety: keep the activation short and monitor temperature.

## 5. Short PID Test

Recommended command sequence:

```text
READ_TEMP
STATUS
CLEAR_ERROR
SET_TARGET 37.50
SET_PID 8 0.03 20
SET_PID_LIMIT 15
LOG_ON 200
PID_ON
STATUS
STOP
PID_OFF
LOG_OFF
```

Validation points:

- PID starts without error.
- Logs show coherent temperature and output behavior.
- PID output remains limited by `SET_PID_LIMIT 15`.
- `STOP` stops heating.

## 6. Long PID Test

1. Start from a safe, stable initial temperature.
2. Apply the same PID startup sequence as the short PID test.
3. Let the system approach `37.50 C` under supervision.
4. Monitor the logs for overshoot, oscillation, or safety limit behavior.
5. Stop using the recommended shutdown sequence.

Safety: the system has strong thermal inertia. Do not increase `PID_LIMIT` abruptly during a long test.

## 7. STOP Test

1. While heating or PID is active, send `STOP`.
2. Confirm that active heating output stops.
3. Send `STATUS`.
4. Confirm that the reported state is safe.

## 8. CLEAR_ERROR Test

1. If an error is latched, remove the cause first.
2. Send `CLEAR_ERROR`.
3. Send `STATUS`.
4. Confirm that the error is cleared only when the underlying condition is safe.

## 9. NeoPixel Validation

- Confirm that the NeoPixel shows the expected fixed white state during the validated firmware run.
- If the indication changes, verify the firmware state with `STATUS` before continuing heating tests.

## 10. Success Criteria

- `READ_TEMP` returns plausible temperature data.
- `STATUS` reports coherent firmware state.
- `LOG_ON`, `LOG_OFF`, and `LOG_STATUS` behave as expected.
- `MOSFET_ON <seconds>` is time-limited and `MOSFET_OFF` works.
- `CONTROL_ON` and `CONTROL_OFF` operate without unexpected errors.
- `PID_ON` and `PID_OFF` operate with the reference PID settings.
- `STOP` reliably stops heating output.
- `CLEAR_ERROR` clears errors only after safe recovery.
- NeoPixel fixed white indication is validated.
- No safety limit violation occurs during the validated test procedure.
