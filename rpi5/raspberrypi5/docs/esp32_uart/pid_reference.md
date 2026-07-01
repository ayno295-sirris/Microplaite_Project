# PID Reference

This document records the PID parameters validated on the bench for autonomous ESP32 heating at `37.50 C`.

## Validated Reference Parameters

| Parameter | Reference value |
| --- | ---: |
| Target | 37.50 °C |
| Kp | 8.00 |
| Ki | 0.03 |
| Kd | 20.00 |
| PID output limit | 15.0 % |
| Recommended log period | 200 ms |
| Current safety limit | 38.00 °C |

## Validation Context

These values were validated on the current bench setup with the ESP32 firmware in autonomous heating mode. The functional validation covered temperature reading, status reporting, logging, timed MOSFET activation, ON/OFF control, PID enable/disable, `STOP`, `CLEAR_ERROR`, fixed white NeoPixel indication, short PID testing, and long PID testing.

The current priority is autonomous ESP32 heating at `37.50 C`, without UART control from Raspberry Pi software and without a graphical interface.

## Why PID Limit Is 15 %

The PID output is limited to `15.0 %` to reduce the risk of overshoot while heating toward `37.50 C`. The system has strong thermal inertia: temperature can continue rising after power is reduced or stopped. A conservative output limit gives the controller time to react and keeps the heating behavior within the validated bench envelope.

Do not increase `PID_LIMIT` abruptly. If tuning is required later, change the limit in small steps, monitor logs closely, and keep the safety limit active.

## Recommended PID Startup Procedure

Use this sequence from a safe initial state:

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
```

Confirm that:

- the temperature reading is plausible before enabling PID;
- no error is active before heating;
- the target is `37.50 C`;
- the PID gains are `Kp=8.00`, `Ki=0.03`, `Kd=20.00`;
- the PID output limit is `15.0 %`;
- logs are active at `200 ms`.

## Recommended Shutdown Procedure

Use this sequence to stop a PID run:

```text
STOP
PID_OFF
LOG_OFF
STATUS
```

Confirm that heating output has stopped and that the final status is safe.
