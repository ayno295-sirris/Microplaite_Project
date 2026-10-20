# RPi Client UX Final Design

**Task:** `RPI-CLIENT-UX-FINAL-001`

**Status:** Approved on 2026-10-20

## Baseline and boundaries

Development starts from the reproducible client snapshot
`release/client-rpi-2026-10-20` at
`3237e5720818af190095d08445cf6627424c4cc2` in an isolated worktree. The
production checkout and its unrelated untracked design document remain untouched.

All implementation stays in `rpi5/raspberrypi5/`, except this design, the execution
plan, and the client guide in `docs/`. The ESP32 firmware is read-only. No physical
pump or heater activation is part of software verification.

## Timelapse stabilization and cadence

The existing one-second pre-lighting delay becomes a user-visible total LED
stabilization delay in milliseconds. Its new default is 2500 ms. A new preference
key is used so an old persisted one-second value cannot silently override the new
default; the obsolete seconds key remains harmless input and is not rewritten as a
second hidden addition.

The internal service continues to use seconds at the camera boundary, converted
exactly once from the millisecond UI value. Each nominal capture deadline is based
on one monotonic session origin:

1. calculate `capture_deadline = origin + n * interval`;
2. start lighting at `capture_deadline - stabilization`;
3. wait until the capture deadline;
4. capture once and turn the LEDs off in `finally`;
5. advance to the next nominal deadline without adding capture duration.

An interval that is not greater than the stabilization duration is rejected before
the worker starts. If acquisition overruns a later slot, that slot is skipped and
logged; no concurrent catch-up capture is started. The already-open camera remains
active during stabilization, so its existing frame acquisition continues to feed
auto-exposure/autofocus.

## Dynamic pump control

`AppController` remains the only pump orchestrator. A small latest-value dispatcher
owned by the controller accepts UI setpoint requests without blocking the Qt event
loop, coalesces rapid changes, and starts at most one update every 200 ms. Existing
synchronous methods remain available to the sequential recipe runner.

When stopped, a new target only prepares the setpoint. When running in the same
direction, the dispatcher sends `PUMP_SET_RPM(abs(rpm), direction)`. A direction
change performs this guarded sequence:

1. mark a direction transition pending;
2. send `PUMP_STOP`;
3. request a fresh `PUMP_STATUS` after that STOP;
4. require valid readback and `pump_running=false`;
5. re-check session, fault state, cancellation generation, capability, and the
   latest requested target;
6. send exactly one `PUMP_START(abs(latest), latest_direction)` only when still
   authorized;
7. request confirmation.

Operator STOP, global STOP, LOST, FAULT, shutdown, reconnect, and session
cancellation invalidate pending and queued activation. Invalid, absent, stale, or
contradictory readback never permits the reverse START.

The slider uses a gesture-relative integer delta over the signed decimal target.
Starting from 3.5, slider deltas of +1, +2, and +7 yield 4.5, 5.5, and 10.5. A
gesture that began while the pump was running may cross zero and retain its intent;
ending at zero remains stopped. A gesture that began while stopped never starts the
pump. Numeric edits are committed as decimal values instead of dispatching every
intermediate keystroke.

## Pump Control layout

Only the detailed Pump Control page is rearranged. One wide touch-first card uses
the available 1280 x 720 area for a large signed target, a wide slider, decimal
field and fine-step buttons, large START/STOP controls, PRIME, and a compact status
row. Confirmed direction/readback, faults, and transition state stay visible; future
calibration placeholders and redundant secondary copy are removed.

## Dashboard camera states

The dashboard card has an explicit three-state renderer independent of previously
saved pictures:

- live: display the current live frame;
- active timelapse: display only the latest successful image from the current
  timelapse session, or `Waiting for first time-lapse image...` before it exists;
- idle: clear the pixmap and display `No active preview` plus
  `Start Live Preview or a Time-lapse to view images.`

Live and timelapse remain mutually exclusive under the existing camera service.
Detailed capture files and the camera acquisition path are unchanged.

## NeoPixel live controls

The existing `NEOPIXEL_SET` command is extended, not replaced:

```json
{"v":2,"id":1,"cmd":"NEOPIXEL_SET","enabled":true,"brightness":80,"keep_on":false}
```

`keep_on` is optional and defaults to false. `V2Status` adds
`neopixel_keep_on` and `neopixel_auto_off_supported`; it retains
`neopixel_enabled` and `neopixel_brightness` and does not introduce
`neopixel_on`.

For an older firmware, commands omit `keep_on`, historical ON/OFF remains usable,
and the Keep On checkbox is disabled. The checkbox is enabled only when
`neopixel_auto_off_supported is true`. Its local requested value defaults to false.
Changing it while LEDs are off only records the next-live policy; changing it while
LEDs are on transmits the updated command. START LIVE turns the LEDs on once with
the selected policy. Manual OFF remains effective during live. STOP LIVE always
turns LEDs off immediately even when Keep On was selected.

There is no Raspberry Pi 120-second timer. Reported LED state remains authoritative
after an ESP32 auto-off. Timelapse lighting always uses the independent
ON/stabilize/capture/OFF policy and never inherits live Keep On.

## Client guide and validation

The guide documents only shipped behavior: startup, reconnect, thermal controls,
pump operation and reversal, camera/video, timelapse stabilization, NeoPixel policy,
storage, recipes, global STOP, maintenance, and active thermal limits.

Each functional block is test-driven and committed separately. Final verification
includes the full Python suite, Ruff on touched Python files, `git diff --check`, a
clean-checkout import/startup smoke test, and inspection of launcher/autostart paths.
Physical touchscreen, camera, NeoPixel auto-off, pump, and heater behavior remain
explicitly pending user-supervised hardware validation.
