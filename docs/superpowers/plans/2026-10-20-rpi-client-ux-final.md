# RPi Client UX Final Implementation Plan

> **Task:** `RPI-CLIENT-UX-FINAL-001`
>
> **Baseline:** `3237e5720818af190095d08445cf6627424c4cc2`
>
> **Branch:** `software-v2/rpi-client-ux-final-001`

## Execution rules

- Work only in the isolated worktree.
- Do not edit or build ESP32 firmware.
- Write a failing focused test before each production behavior change.
- Do not activate pump or heating hardware.
- Keep each requested block in its own commit.
- Preserve the production checkout and its unrelated local document.

## Task 1: Timelapse stabilization and monotonic cadence

**Files:**

- Modify: `rpi5/raspberrypi5/src/microplaite_ui/services/timelapse.py`
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/services/preferences.py`
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/ui/main_window.py`
- Modify: `rpi5/raspberrypi5/tests/test_timelapse.py`
- Modify: `rpi5/raspberrypi5/tests/test_preferences.py`
- Modify: `rpi5/raspberrypi5/tests/test_main.py`

1. Add failing tests for a 2500 ms default, millisecond preference persistence,
   exact single conversion, incompatible interval rejection, ON/wait/capture/OFF,
   cancellation OFF, 10-second monotonic deadlines, skipped overruns, and repeated
   lifecycle cleanup.
2. Replace the UI seconds field with the tactile millisecond field and a new
   preference key.
3. Split pre-light scheduling from capture execution so the light starts before a
   fixed capture deadline.
4. Keep the existing camera open and capture lock; reject conflicts and skip late
   slots without concurrent capture.
5. Run the three focused test modules and commit:
   `Fix timelapse stabilization and capture cadence`.

## Task 2: Dynamic and safely reversible pump setpoint

**Files:**

- Modify: `rpi5/raspberrypi5/src/microplaite_ui/core/controller.py`
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/core/state.py`
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/ui/main_window.py`
- Modify: `rpi5/raspberrypi5/tests/test_v2_ui_integration.py`
- Modify: `rpi5/raspberrypi5/tests/test_main.py`

1. Add failing controller tests for same-direction CW/CCW changes, fresh confirmed
   reversal both ways, zero crossing, zero final value, STOP/LOST/FAULT cancellation,
   missing or invalid readback, rapid latest-value replacement, old capability, and
   reconnect non-resume.
2. Add a controller-owned latest-value dispatcher with a 200 ms minimum dispatch
   interval and explicit cancellation generation.
3. Extend the existing direction-change path to perform the single guarded reverse
   START after fresh post-STOP confirmation.
4. Add failing UI tests for relative slider gestures preserving decimal fractions,
   numeric commit behavior, explicit START from stopped, and nonblocking updates.
5. Wire slider gesture lifecycle and committed decimal edits to the controller
   dispatcher; retain synchronous recipe commands and STOP priority.
6. Run focused controller/UI tests and commit:
   `Add safe dynamic pump setpoint control`.

## Task 3: Touch-first Pump Control layout

**Files:**

- Modify: `rpi5/raspberrypi5/src/microplaite_ui/ui/main_window.py`
- Modify if required: `rpi5/raspberrypi5/src/microplaite_ui/ui/styles.py`
- Modify: `rpi5/raspberrypi5/tests/test_main.py`

1. Add failing geometry/content tests for the wide slider, signed target, large
   controls, and retained critical status.
2. Replace the two-card detailed page with a single wide touch-first composition,
   without altering home cards or navigation.
3. Run focused UI tests and commit:
   `Improve Pump Control touch layout`.

## Task 4: Explicit dashboard camera states

**Files:**

- Modify: `rpi5/raspberrypi5/src/microplaite_ui/ui/main_window.py`
- Modify: `rpi5/raspberrypi5/tests/test_main.py`

1. Add failing tests for exact idle text with no stale image, waiting-before-first
   timelapse text, current-session timelapse image, live priority, and successful
   capture refresh.
2. Add a dashboard-specific preview selector/renderer while preserving detailed
   camera preview, capture storage, and the single existing acquisition.
3. Run focused camera tests and commit:
   `Clarify dashboard camera preview states`.

## Task 5: NeoPixel live policy and Keep On capability

**Files:**

- Modify: `rpi5/raspberrypi5/src/microplaite_ui/esp32/v2_client.py`
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/esp32/v2_ui_client.py`
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/core/state.py`
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/core/controller.py`
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/ui/main_window.py`
- Modify: `rpi5/raspberrypi5/tests/test_v2_client.py`
- Modify: `rpi5/raspberrypi5/tests/test_v2_ui_integration.py`
- Modify: `rpi5/raspberrypi5/tests/test_main.py`

1. Add failing protocol tests for optional `keep_on`, exact STATUS fields, request
   size enforcement, and old-firmware omission.
2. Extend `V2Status`, `V2Client.neopixel_set`, and `V2UiClient` without adding a new
   command or timer.
3. Add state/controller tests for capability gating, local selection while OFF,
   transmitting changes while ON, reported auto-off, and timelapse forcing false.
4. Add ON/OFF and Keep On controls to both live-control surfaces, synchronized
   through existing state and methods; make START/STOP LIVE enforce the approved
   policy.
5. Run focused protocol/controller/UI tests and commit:
   `Add NeoPixel live keep-on controls`.

## Task 6: Client operating guide

**Files:**

- Add: `docs/MICROPLAITE_CLIENT_GUIDE.md`
- Modify if useful: `docs/README.md`

1. Verify implemented labels, paths, safety limits, and storage behavior from code.
2. Document startup/reconnect, thermal operation, dynamic/reversing pump control,
   STOP, live/video, timelapse, NeoPixel, files, recipes, maintenance, shutdown, and
   limitations without describing unavailable firmware behavior as validated.
3. Commit: `Add Microplaite client operating guide`.

## Task 7: Final verification and delivery

1. Run the full Python suite once and capture the terminal summary.
2. Run Ruff on every touched Python file and `git diff --check`.
3. Verify no firmware changes, branch history, distinct commits, upstream state,
   launcher/autostart paths, and the production checkout preservation.
4. Create a temporary clean checkout/worktree of the final commit and run import and
   offscreen startup smoke checks; remove only that temporary verification worktree.
5. Push `software-v2/rpi-client-ux-final-001` without merging or tagging.
6. Report automated evidence separately from user-supervised physical validation.
