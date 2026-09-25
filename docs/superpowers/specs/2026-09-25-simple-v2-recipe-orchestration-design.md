# Simple V2 Recipe Orchestration Design

Date: 2026-09-25

Task: `RECIPES-V2-RPI-001`

Base: `software-v2/logging-v2-rpi-001` at `c3a3b1fbc0cd74b42529ba4e33ab18011a580403`

## Objective

Add a small Raspberry Pi recipe orchestrator that executes a validated JSON recipe strictly in sequence using the existing V2 application commands. The orchestrator must not move real-time control or safety responsibility away from the ESP32.

The operator can select, start, monitor, and stop one recipe. Waiting and command execution must not block the Qt event loop or the V2 heartbeat. The existing periodic V2 STATUS flow remains the only telemetry source.

## Non-goals

- No ESP32 firmware changes.
- No workflow graph, branching, loops, variables, persistence, pause, or resume.
- No automatic restart after STOP, LOST, FAULT, reconnect, or application restart.
- No second STATUS request loop, serial port, V2 client, or session.
- No automatic CSV logging start.
- No legacy protocol recipe execution.
- No recipe editor or recipe creation UI.

## Recipe storage and discovery

Recipes are JSON files stored in:

```text
~/MicroplaiteData/recipes/
```

The directory is created when recipe discovery first runs. A `test_simple.json` example is created only when it does not already exist. Existing recipe files are never overwritten.

The UI lists valid `*.json` files from this directory. Loading or validation errors are displayed without starting a runner or sending a hardware command.

## JSON format

The root object contains a non-empty `name` string and a non-empty `steps` array. Each step is an object with an `action` string and only the parameters required by that action.

```json
{
  "name": "Test simple",
  "steps": [
    {"action": "SET_TEMPERATURE", "target_c": 44.3},
    {"action": "HEATER_PID_ON"},
    {
      "action": "WAIT_TEMPERATURE",
      "target_c": 44.3,
      "tolerance_c": 0.3,
      "timeout_s": 600
    },
    {"action": "PUMP_START", "rpm": 3.0},
    {"action": "WAIT", "seconds": 30},
    {"action": "PUMP_STOP"},
    {"action": "HEATER_OFF"}
  ]
}
```

All numeric values must be finite JSON numbers; booleans are not accepted as numbers. Validation occurs before execution.

| Action | Required parameters | Validation |
| --- | --- | --- |
| `SET_TEMPERATURE` | `target_c` | `0 <= target_c <= THERMAL_TEST_MAX_TARGET_C` |
| `HEATER_PID_ON` | none | none |
| `HEATER_OFF` | none | none |
| `PUMP_START` | `rpm` | `0 <= rpm <= 100` |
| `PUMP_SET_RPM` | `rpm` | `0 <= rpm <= 100` |
| `PUMP_STOP` | none | none |
| `PUMP_PRIME` | none | none |
| `WAIT` | `seconds` | `seconds >= 0` |
| `WAIT_TEMPERATURE` | `target_c`, `tolerance_c`, `timeout_s` | target in range, `tolerance_c >= 0`, `timeout_s > 0` |
| `NEOPIXEL` | `enabled`, `brightness` | boolean enabled, integer brightness from 0 to 100 |

Unknown actions, missing parameters, invalid parameter types, out-of-range values, an empty step list, or malformed JSON reject the whole recipe before it starts.

## Components

### Recipe model and store

A focused recipe module provides immutable recipe and step models plus JSON validation. A small store discovers files, creates the default directory and example, and loads the selected recipe.

It performs no command execution and has no Qt dependency.

### Recipe runner

The runner owns:

- the current recipe;
- a single daemon worker thread;
- a cancellation event;
- a lock/condition for state and incoming STATUS notifications;
- current step index and description;
- terminal status and error text.

Minimum runner states are:

```text
STOPPED
RUNNING
COMPLETED
ERROR
```

`start()` succeeds only when no recipe is running. It resets prior terminal information but does not restore or replay any previous step. There is no persisted cursor.

The worker executes one step at a time. It checks cancellation at every step boundary, immediately before launching a command, and immediately after each command returns. The next step is never launched after cancellation has been recorded.

### AppController integration

`AppController` owns one runner and remains the only path from UI actions to the ESP32 client. It provides the runner with narrowly scoped callbacks that map validated actions onto the existing V2 methods.

The existing controller and V2 client locks serialize recipe commands with UI commands, STATUS transactions, and heartbeat traffic. No second client or port is created.

Every accepted V2 `ParsedMessage` with `is_status=True` is assigned an increasing local STATUS sequence number and passed to the runner as an immutable sample. Legacy messages are never passed to recipe waiting logic.

### UI integration

A `RECIPES` button is added to the home action row and opens a minimal Recipes page. The page uses the existing 200 ms render/poll timer; it creates no new timer or telemetry loop.

The page contains:

- recipe selector;
- selected recipe name;
- `START RECIPE`;
- `STOP RECIPE`;
- current step label;
- `step X / N` progress;
- `Running`, `Stopped`, `Completed`, or `Error` status;
- concise error text.

Start is enabled only for a valid selected recipe while the V2 session is READY/ACTIVE and no recipe is running. Stop is enabled while a recipe is running.

## Action mapping

The controller dispatches command actions as follows:

| Recipe action | Existing V2 path |
| --- | --- |
| `SET_TEMPERATURE` | set controller target, then `HEATER_SET_TARGET` |
| `HEATER_PID_ON` | existing PID start path |
| `HEATER_OFF` | `HEATER_DISABLE` through the existing PID-off path |
| `PUMP_START` | set recipe RPM locally, then `PUMP_START rpm` and existing confirmation path |
| `PUMP_SET_RPM` | explicit `PUMP_SET_RPM rpm` and existing confirmation path |
| `PUMP_STOP` | existing pump stop and confirmation path |
| `PUMP_PRIME` | existing pump prime and confirmation path |
| `NEOPIXEL` | one V2 `NEOPIXEL_SET enabled brightness` request |

The recipe dispatcher refuses activation commands unless the normal V2 activation gate is satisfied. Command failure moves the recipe to `ERROR`; no later recipe step is executed.

## Non-blocking waits

### WAIT

`WAIT seconds` uses the runner cancellation event with a monotonic deadline. The wait occurs only in the worker thread and wakes immediately when cancellation is requested. Qt and heartbeat threads remain free.

### WAIT_TEMPERATURE

On entry, the runner records the latest V2 STATUS sequence number as its minimum boundary. Existing AppState values and STATUS samples received before the wait are not eligible, even if their temperature is already within tolerance.

The step only evaluates structurally valid V2 STATUS samples delivered after entry, identified by a sequence number greater than the boundary. A qualifying sample requires:

- `temperature_valid is True`;
- a finite `temp_c` value;
- `abs(temp_c - target_c) <= tolerance_c`;
- sample arrival no later than the monotonic deadline.

Each new sample is evaluated when the controller publishes it, so a qualifying sample cannot be lost if another STATUS arrives before the worker wakes. The worker waits on the condition and does not send STATUS requests.

If no qualifying new sample arrives before the deadline, the runner first records `ERROR` and cancellation, then requests a global V2 STOP. The error text identifies the temperature timeout.

## Cancellation and safety ordering

### Operator STOP

Both the recipe STOP button and the existing global STOP path use this order:

1. acquire the runner state lock;
2. set the cancellation flag and terminal `STOPPED` state;
3. wake any WAIT or WAIT_TEMPERATURE;
4. return from runner cancellation;
5. send the global V2 STOP through `AppController`.

The cancellation flag is therefore visible before hardware STOP is attempted. A worker completing its current command sees cancellation before it can launch the next recipe step.

### LOST

When the V2 session becomes LOST, the controller immediately records a terminal recipe `ERROR`, sets cancellation, and wakes the worker.

The LOST path must not send STOP, retry, reopen the port, resynchronize, or run another recipe command. Hardware safe stop remains the responsibility of the ESP32 heartbeat timeout.

### FAULT

When a new STATUS reports ESP32 FAULT or a latched safety error, the controller immediately cancels the recipe with terminal `ERROR`. If the V2 transport remains available, it requests a global STOP after cancellation. No later step runs.

### Other execution errors

A runtime command or protocol error cancels the recipe and moves it to `ERROR`. If communication remains available, a global STOP is requested after cancellation. A validation error before start does not send STOP because no recipe command has run.

## Completion and reconnect behavior

After the last step, the runner enters `COMPLETED`. Completion does not implicitly change heater, pump, or NeoPixel state; the recipe must explicitly contain the required shutdown actions.

STOPPED, COMPLETED, and ERROR are terminal. Manual reconnect only restores the V2 session. It never restarts a recipe, restores a recipe cursor, or replays a command. Starting again is always an explicit operator action from step one.

## CSV logging

Recipe execution does not start, stop, pause, or reconfigure CSV logging. If logging is active, existing V2 STATUS rows continue to be written normally during the recipe. Existing LOST behavior still flushes and closes the CSV file.

## Error reporting

The runner exposes a concise error string for the UI and records the same event in the controller diagnostic log. Errors distinguish at least:

- invalid recipe;
- activation unavailable;
- command failure;
- temperature timeout;
- ESP32 FAULT;
- connection LOST.

## Test strategy

Tests use a real runner with deterministic clock/status inputs and a recording command adapter. They verify behavior rather than thread implementation details.

Minimum coverage:

- valid JSON loading and default example creation;
- invalid JSON, unknown action, missing and invalid parameters;
- every supported command mapping;
- strict sequential execution and one active recipe limit;
- cancellable WAIT without blocking the caller/UI;
- WAIT_TEMPERATURE ignores pre-existing and invalid temperature samples;
- WAIT_TEMPERATURE accepts a new qualifying V2 STATUS;
- WAIT_TEMPERATURE timeout records cancellation before global STOP;
- operator STOP records cancellation before global STOP and prevents the next step;
- LOST becomes terminal without sending STOP;
- FAULT becomes terminal and prevents later steps;
- normal completion;
- no automatic resume after reconnect;
- UI selection, start, stop, progress, completion, and error rendering;
- active CSV logging continues to receive STATUS rows during a recipe.

The targeted recipe tests, full Python suite, Ruff on modified files, and `git diff --check` must pass before the implementation commit is created.
