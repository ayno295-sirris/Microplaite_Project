# Simple V2 Recipe Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single-worker Raspberry Pi recipe orchestrator that executes validated JSON steps through the existing V2 controller without blocking Qt, heartbeat, or creating another STATUS loop.

**Architecture:** A recipe module validates JSON files from `~/MicroplaiteData/recipes/`; a focused runner owns one cancellable worker and consumes new V2 STATUS notifications; `AppController` maps recipe actions to existing V2 commands and enforces STOP/LOST/FAULT ordering; the existing Qt timer renders a minimal Recipes page. The ESP32 remains authoritative for real-time control and safe stop after communication loss.

**Tech Stack:** Python 3.11+, standard-library `json`, `dataclasses`, `threading`, `time`, PySide6, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-25-simple-v2-recipe-orchestration-design.md`

## Global Constraints

- Raspberry Pi changes stay inside `rpi5/raspberrypi5/`; the design and plan remain under root `docs/`.
- Do not modify ESP32 firmware, legacy serial protocol behavior, camera, timelapse, or CSV logging lifecycle.
- Use only the existing V2 client/session and its single-request lock; do not create another client, port, heartbeat, or STATUS request loop.
- Execute exactly one recipe at a time, strictly in step order.
- Record cancellation before requesting global STOP.
- LOST is terminal and must never request STOP, reconnect, retry, resume, or replay a command.
- WAIT and WAIT_TEMPERATURE use monotonic time and remain cancellable without blocking Qt or heartbeat.
- WAIT_TEMPERATURE accepts only structurally valid V2 STATUS samples received after the wait begins.
- Recipe completion does not implicitly change hardware outputs.
- Default recipe directory is exactly `~/MicroplaiteData/recipes/`.
- Do not add dependencies.
- The final UI/integration commit is exactly `Add simple V2 recipe orchestration`.

## Review Focus

- JSON booleans must not pass numeric validation (`true` is an `int` subclass in Python); Task 1 tests explicit rejection.
- A STOP racing with a command completion must set cancellation before global STOP and prevent the following step; Task 2 tests a blocked first command followed by a forbidden second command.
- WAIT_TEMPERATURE must not reuse stale AppState values or a STATUS missing its own temperature fields; Task 2 tests both cases with sequence-numbered samples.
- LOST during WAIT or WAIT_TEMPERATURE must wake the worker and terminate without a global STOP request; Tasks 2 and 3 test this exact path.
- Recipe discovery must not overwrite a user-edited `test_simple.json`, and one malformed file must not prevent other files from appearing; Task 1 tests preservation and per-file loading errors.

---

### Task 1: Recipe model, validation, and storage

**Files:**
- Create: `rpi5/raspberrypi5/src/microplaite_ui/services/recipes.py`
- Create: `rpi5/raspberrypi5/tests/test_recipes.py`

**Interfaces:**
- Consumes: `microplaite_ui.config.THERMAL_TEST_MAX_TARGET_C`.
- Produces: `RecipeAction`, `RecipeStep`, `RecipeDefinition`, `RecipeValidationError`, `RecipeStore.list_files()`, and `RecipeStore.load(path)`.

- [ ] **Step 1: Write failing tests for valid JSON and immutable models**

Create tests using literal JSON and expected values:

```python
def test_loads_valid_recipe_with_all_supported_actions(tmp_path: Path) -> None:
    path = tmp_path / "all-actions.json"
    path.write_text(json.dumps({
        "name": "All actions",
        "steps": [
            {"action": "SET_TEMPERATURE", "target_c": 44.3},
            {"action": "HEATER_PID_ON"},
            {"action": "HEATER_OFF"},
            {"action": "PUMP_START", "rpm": 3.0},
            {"action": "PUMP_SET_RPM", "rpm": 4.0},
            {"action": "PUMP_STOP"},
            {"action": "PUMP_PRIME"},
            {"action": "WAIT", "seconds": 0.5},
            {
                "action": "WAIT_TEMPERATURE",
                "target_c": 44.3,
                "tolerance_c": 0.3,
                "timeout_s": 600,
            },
            {"action": "NEOPIXEL", "enabled": True, "brightness": 35},
        ],
    }), encoding="utf-8")

    recipe = RecipeStore(tmp_path).load(path)

    assert recipe.name == "All actions"
    assert tuple(step.action.value for step in recipe.steps) == (
        "SET_TEMPERATURE", "HEATER_PID_ON", "HEATER_OFF", "PUMP_START",
        "PUMP_SET_RPM", "PUMP_STOP", "PUMP_PRIME", "WAIT",
        "WAIT_TEMPERATURE", "NEOPIXEL",
    )
    assert recipe.steps[0].target_c == 44.3
    assert recipe.steps[-1].enabled is True
    assert recipe.steps[-1].brightness == 35
```

- [ ] **Step 2: Run the valid-recipe test and verify RED**

Run:

```bash
cd rpi5/raspberrypi5
.venv/bin/pytest -q tests/test_recipes.py::test_loads_valid_recipe_with_all_supported_actions
```

Expected: FAIL because `microplaite_ui.services.recipes` does not exist.

- [ ] **Step 3: Implement the recipe types and strict action-specific validation**

Create these public types and signatures:

```python
class RecipeAction(StrEnum):
    SET_TEMPERATURE = "SET_TEMPERATURE"
    HEATER_PID_ON = "HEATER_PID_ON"
    HEATER_OFF = "HEATER_OFF"
    PUMP_START = "PUMP_START"
    PUMP_SET_RPM = "PUMP_SET_RPM"
    PUMP_STOP = "PUMP_STOP"
    PUMP_PRIME = "PUMP_PRIME"
    WAIT = "WAIT"
    WAIT_TEMPERATURE = "WAIT_TEMPERATURE"
    NEOPIXEL = "NEOPIXEL"


@dataclass(frozen=True, slots=True)
class RecipeStep:
    action: RecipeAction
    target_c: float | None = None
    tolerance_c: float | None = None
    timeout_s: float | None = None
    rpm: float | None = None
    seconds: float | None = None
    enabled: bool | None = None
    brightness: int | None = None


@dataclass(frozen=True, slots=True)
class RecipeDefinition:
    name: str
    steps: tuple[RecipeStep, ...]
    source: Path


class RecipeValidationError(ValueError):
    pass
```

Implement `RecipeStore.load(path)` with `json.loads`, exact allowed-key sets per action, `math.isfinite`, explicit `isinstance(value, bool)` rejection for numeric values, configured target/rpm/brightness ranges, and error messages containing the file name and failing step number.

- [ ] **Step 4: Run the valid-recipe test and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Add failing validation parameter cases**

Add parameterized cases for malformed JSON, non-object root, empty name, empty steps, unknown action, missing parameter, extra parameter, boolean numeric value, non-finite number, temperature above `THERMAL_TEST_MAX_TARGET_C`, RPM above 100, negative WAIT, non-positive timeout, negative tolerance, non-boolean `enabled`, non-integer brightness, and brightness outside 0–100.

Each case must assert `RecipeValidationError` and a stable semantic fragment such as `unknown action`, `missing`, `unexpected`, or `must be` rather than the entire message.

- [ ] **Step 6: Run validation tests and verify RED, then implement the missing branches**

Run:

```bash
.venv/bin/pytest -q tests/test_recipes.py
```

Expected before implementation: one or more parameter cases FAIL for the unimplemented branch. Add only the validation needed for those cases, rerun, and expect all tests in the file to PASS.

- [ ] **Step 7: Add failing store discovery and example-preservation tests**

```python
def test_list_files_creates_directory_and_default_example(tmp_path: Path) -> None:
    directory = tmp_path / "recipes"
    store = RecipeStore(directory)

    files = store.list_files()

    assert [path.name for path in files] == ["test_simple.json"]
    assert store.load(files[0]).name == "Test simple"


def test_list_files_never_overwrites_existing_example(tmp_path: Path) -> None:
    directory = tmp_path / "recipes"
    directory.mkdir()
    example = directory / "test_simple.json"
    original = '{"name":"User recipe","steps":[{"action":"WAIT","seconds":1}]}'
    example.write_text(original, encoding="utf-8")

    RecipeStore(directory).list_files()

    assert example.read_text(encoding="utf-8") == original


def test_malformed_file_does_not_hide_other_recipe_paths(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    (tmp_path / "good.json").write_text(
        '{"name":"Good","steps":[{"action":"WAIT","seconds":1}]}',
        encoding="utf-8",
    )

    files = RecipeStore(tmp_path).list_files()

    assert [path.name for path in files] == ["bad.json", "good.json", "test_simple.json"]
    with pytest.raises(RecipeValidationError):
        RecipeStore(tmp_path).load(tmp_path / "bad.json")
```

- [ ] **Step 8: Run discovery tests RED, implement directory/example creation, then verify GREEN**

Implement `DEFAULT_RECIPE_DIRECTORY = Path.home() / "MicroplaiteData" / "recipes"`, an embedded JSON example constant, sorted `*.json` discovery, and exclusive non-overwriting example creation.

Run:

```bash
.venv/bin/pytest -q tests/test_recipes.py
```

Expected: PASS.

- [ ] **Step 9: Commit the independently verified format/store increment**

```bash
git add rpi5/raspberrypi5/src/microplaite_ui/services/recipes.py rpi5/raspberrypi5/tests/test_recipes.py
git commit -m "Add V2 recipe JSON format"
```

### Task 2: Sequential, cancellable recipe runner

**Files:**
- Create: `rpi5/raspberrypi5/src/microplaite_ui/services/recipe_runner.py`
- Create: `rpi5/raspberrypi5/tests/test_recipe_runner.py`

**Interfaces:**
- Consumes: `RecipeDefinition`, `RecipeStep`, and `RecipeAction` from Task 1.
- Produces: `RecipeRunState`, `RecipeProgress`, `RecipeStatusSample`, `RecipeAlreadyRunningError`, `RecipeExecutionError`, and `RecipeRunner` methods `start`, `stop`, `fail`, `publish_status`, `snapshot`, and `close`.

`RecipeRunner.__init__` has the exact signature `RecipeRunner(execute_command: Callable[[RecipeStep], None], global_stop: Callable[[], None], monotonic: Callable[[], float] = time.monotonic)`. Its public methods are `start(self, recipe: RecipeDefinition) -> None`, `stop(self, reason: str = "Stopped by operator", *, request_stop: bool = True) -> None`, `fail(self, reason: str, *, request_stop: bool) -> None`, `publish_status(self, sample: RecipeStatusSample) -> None`, `snapshot(self) -> RecipeProgress`, and `close(self) -> None`.

- [ ] **Step 1: Write a failing strict-sequence and completion test**

Use real thread synchronization events rather than sleeping to infer order:

```python
def recipe_with_steps(*steps: RecipeStep) -> RecipeDefinition:
    return RecipeDefinition("Test", tuple(steps), Path("test.json"))


def wait_until_terminal(runner: RecipeRunner, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while runner.snapshot().state is RecipeRunState.RUNNING:
        if time.monotonic() >= deadline:
            raise AssertionError("recipe did not reach a terminal state")
        time.sleep(0.005)


def test_commands_execute_strictly_in_order_and_complete() -> None:
    calls: list[str] = []
    recipe = recipe_with_steps(
        RecipeStep(RecipeAction.HEATER_PID_ON),
        RecipeStep(RecipeAction.PUMP_STOP),
        RecipeStep(RecipeAction.HEATER_OFF),
    )
    runner = RecipeRunner(
        execute_command=lambda step: calls.append(step.action.value),
        global_stop=lambda: calls.append("GLOBAL_STOP"),
    )

    runner.start(recipe)
    wait_until_terminal(runner)

    assert calls == ["HEATER_PID_ON", "PUMP_STOP", "HEATER_OFF"]
    assert runner.snapshot().state is RecipeRunState.COMPLETED
    assert runner.snapshot().step_number == 3
    assert runner.snapshot().total_steps == 3
```

- [ ] **Step 2: Run the sequence test and verify RED**

Run:

```bash
.venv/bin/pytest -q tests/test_recipe_runner.py::test_commands_execute_strictly_in_order_and_complete
```

Expected: FAIL because `recipe_runner` does not exist.

- [ ] **Step 3: Implement runner state, snapshot, one worker, and command dispatch**

Create these public contracts:

```python
class RecipeRunState(StrEnum):
    STOPPED = "Stopped"
    RUNNING = "Running"
    COMPLETED = "Completed"
    ERROR = "Error"


@dataclass(frozen=True, slots=True)
class RecipeProgress:
    recipe_name: str = ""
    state: RecipeRunState = RecipeRunState.STOPPED
    step_number: int = 0
    total_steps: int = 0
    current_step: str = ""
    error: str = ""


@dataclass(frozen=True, slots=True)
class RecipeStatusSample:
    sequence: int
    received_monotonic: float
    temperature_valid: bool | None
    temp_c: float | None


class RecipeAlreadyRunningError(RuntimeError):
    pass


class RecipeExecutionError(RuntimeError):
    pass


class RecipeRunner:
    def __init__(
        self,
        execute_command: Callable[[RecipeStep], None],
        global_stop: Callable[[], None],
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._execute_command = execute_command
        self._global_stop = global_stop
        self._monotonic = monotonic
        self._condition = threading.Condition()
        self._progress = RecipeProgress()
        self._thread: threading.Thread | None = None
        self._cancelled = False
        self._stop_requested = False
        self._cancel_event = threading.Event()
```

Build the listed public methods around these initialized fields. Protect mutable state with the condition, return a copied immutable progress snapshot, start one daemon worker per explicit `start`, reject concurrent start with `RecipeAlreadyRunningError`, and check cancellation under the condition immediately before each command and after it returns.

- [ ] **Step 4: Verify sequence GREEN and add the one-active-recipe RED test**

Assert a second `start()` while RUNNING raises `RecipeAlreadyRunningError`; stopping and explicitly starting again begins at step one. Implement the missing guard and rerun the runner file.

- [ ] **Step 5: Write failing non-blocking WAIT and cancellation-order tests**

Use a blocked first command to expose the step-boundary race:

```python
def test_stop_sets_terminal_flag_before_global_stop_and_skips_next_step() -> None:
    first_started = threading.Event()
    release_first = threading.Event()
    calls: list[str] = []
    observed_state: list[RecipeRunState] = []
    stop_called = threading.Event()

    def execute(step: RecipeStep) -> None:
        calls.append(step.action.value)
        first_started.set()
        assert release_first.wait(1.0)

    runner: RecipeRunner
    def global_stop() -> None:
        observed_state.append(runner.snapshot().state)
        stop_called.set()

    runner = RecipeRunner(execute_command=execute, global_stop=global_stop)
    runner.start(recipe_with_steps(
        RecipeStep(RecipeAction.HEATER_PID_ON),
        RecipeStep(RecipeAction.PUMP_START, rpm=3.0),
    ))
    assert first_started.wait(0.2)

    runner.stop()
    release_first.set()
    assert stop_called.wait(0.2)

    assert observed_state == [RecipeRunState.STOPPED]
    assert calls == ["HEATER_PID_ON"]
```

Also assert `runner.start(recipe_with WAIT)` returns within 100 ms, another Python event can be serviced while waiting, and STOP wakes a long WAIT promptly.

- [ ] **Step 6: Run WAIT/STOP tests RED, implement cancellable monotonic WAIT and deferred global STOP, then verify GREEN**

The worker must call `cancel_event.wait(remaining)` rather than `time.sleep`. `stop()` records terminal state and `_stop_requested=True` under the condition, notifies, and returns. The worker sends global STOP only after observing cancellation, ensuring flag-before-STOP ordering.

- [ ] **Step 7: Write failing fresh-STATUS WAIT_TEMPERATURE tests**

Cover these literal sequences:

1. Publish sequence 4 at target before starting WAIT_TEMPERATURE; it must not complete.
3. Publish sequence 6 with `temperature_valid=True` but `temp_c=None`; it must not complete.
4. Publish sequence 7 at `44.0` for target `44.3 ± 0.3`; it must complete.
5. Publish an in-range sample whose `received_monotonic` is after the deadline; it must timeout.

Use an injected fake monotonic clock plus condition notifications so tests do not wait real timeout durations.

- [ ] **Step 8: Implement sequence-bound WAIT_TEMPERATURE and verify GREEN**

At wait entry, record the latest published sequence under the same condition used by `publish_status`. Store the active target/tolerance/deadline. `publish_status` evaluates every later sample immediately and records a reached flag, so a matching sample cannot be lost when another sample arrives before the worker wakes.

On timeout, set `ERROR` and cancellation first, then request global STOP. Assert the stop callback observes `RecipeRunState.ERROR` and error text containing `temperature timeout`.

- [ ] **Step 9: Add LOST, FAULT, runtime-error, and no-auto-resume tests**

Verify:

- `fail("Connection LOST", request_stop=False)` wakes WAIT, reaches ERROR, and never calls global STOP;
- LOST clears a previously pending STOP request, so STOP followed by LOST before the callback runs still sends no STOP;
- `fail("ESP32 FAULT", request_stop=True)` reaches ERROR before one global STOP call;
- command exception reaches ERROR, sends one global STOP, and skips later steps;
- publishing READY-like STATUS samples after terminal ERROR does not restart anything;
- only a new explicit `start(recipe)` begins again from step one;
- `close()` cancels without global STOP and joins the worker within a bounded timeout.

- [ ] **Step 10: Run the runner suite and commit the verified increment**

```bash
.venv/bin/pytest -q tests/test_recipe_runner.py
git add rpi5/raspberrypi5/src/microplaite_ui/services/recipe_runner.py rpi5/raspberrypi5/tests/test_recipe_runner.py
git commit -m "Add sequential V2 recipe runner"
```

### Task 3: AppController V2 command and supervision integration

**Files:**
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/core/controller.py`
- Modify: `rpi5/raspberrypi5/tests/test_v2_ui_integration.py`
- Modify: `rpi5/raspberrypi5/tests/test_status_csv_logger.py`

**Interfaces:**
- Consumes: all runner/model interfaces from Tasks 1–2 and existing `V2UiClient` command methods.
- Produces: `AppController.start_recipe(recipe)`, `cancel_recipe()`, `stop_recipe()`, `recipe_progress`, STATUS publication, command mapping, and safety cancellation hooks.

The exact controller interfaces are `start_recipe(self, recipe: RecipeDefinition) -> None`, `cancel_recipe(self, reason: str = "Stopped by operator") -> None`, `stop_recipe(self) -> None`, and read-only property `recipe_progress(self) -> RecipeProgress`.

- [ ] **Step 1: Write failing controller tests for every action mapping**

Extend the existing recording V2 client and use a runner recipe containing one command at a time. Assert exact client calls:

```python
expected = {
    RecipeAction.SET_TEMPERATURE: ("heater_set_target", 44.3),
    RecipeAction.HEATER_OFF: ("heater_disable",),
    RecipeAction.PUMP_START: ("pump_start", 3.0),
    RecipeAction.PUMP_SET_RPM: ("pump_set_rpm", 4.0),
    RecipeAction.PUMP_STOP: ("pump_stop",),
    RecipeAction.PUMP_PRIME: ("pump_prime",),
    RecipeAction.NEOPIXEL: ("neopixel_set", True, 35),
}
```

For each pump action, include the expected existing `pump_status` confirmation call. For HEATER_PID_ON, assert the existing PID start sequence remains ordered and uses the recipe target already stored by SET_TEMPERATURE.

- [ ] **Step 2: Run mapping tests RED and implement recipe ownership/dispatch**

Instantiate one `RecipeRunner` in `AppController.__init__` with callbacks `_execute_recipe_command` and `_send_recipe_global_stop`. Add:

```python
def start_recipe(self, recipe: RecipeDefinition) -> None:
    if not self._is_v2 or not self.activation_allowed:
        raise RecipeExecutionError("V2 session is not READY/ACTIVE")
    self._recipe_runner.start(recipe)


def stop_recipe(self) -> None:
    self._recipe_runner.stop(request_stop=True)


def cancel_recipe(self, reason: str = "Stopped by operator") -> None:
    self._recipe_runner.stop(reason, request_stop=False)


@property
def recipe_progress(self) -> RecipeProgress:
    return self._recipe_runner.snapshot()
```

Dispatch WAIT actions only in the runner; the controller dispatcher must reject them defensively. Implement explicit PUMP_SET_RPM behavior that sends the V2 command even when the pump was previously stopped. Implement NEOPIXEL as one `neopixel_set(enabled, brightness)` call.

Add a test proving a connected legacy client is rejected before any recipe thread or hardware command starts. After each command, raise a recipe execution error if V2 is no longer connected/READY/ACTIVE or a new FAULT was applied. Run mapping tests and expect PASS.

- [ ] **Step 3: Write failing STATUS publication tests**

Feed controller messages directly through the existing V2 adapter path and assert:

- only V2 `is_status=True` messages increment the recipe STATUS sequence;
- a PING/command response and legacy LOG do not increment it;
- a STATUS missing `temp_c` publishes `temp_c=None`, never the stale AppState temperature;
- a STATUS missing `temperature_valid` publishes `None`;
- two V2 STATUS messages produce strictly increasing sequences;
- an in-range pre-wait STATUS cannot satisfy a later WAIT_TEMPERATURE, while the next in-range STATUS can.

- [ ] **Step 4: Implement immutable STATUS sample publication and verify GREEN**

In `_apply`, after accepting a V2 STATUS with `message.ok is True`, increment a controller-local integer and publish `RecipeStatusSample` using only fields present in that message plus local `time.monotonic()`. Do not read fallback temperature values from AppState for the sample.

- [ ] **Step 5: Write failing STOP, LOST, and FAULT integration tests**

Verify exact ordering with recording callbacks/events:

- `controller.stop_recipe()` sets runner STOPPED before client `stop` executes;
- existing `controller.stop()` also cancels a running recipe before client `stop`;
- `_mark_connection_lost` sets runner ERROR and sends no client `stop`;
- a V2 `read_available` transport error cancels the recipe as LOST and sends no client `stop`;
- a new V2 STATUS with `system_state="FAULT"`, `safety="ERROR"`, or `error_latched=True` sets runner ERROR before global STOP and skips remaining recipe commands;
- reconnecting the session leaves the runner terminal and does not issue a recipe command;
- `shutdown()` closes the runner worker before closing the ESP32 client and does not itself request hardware STOP.

- [ ] **Step 6: Implement safety hooks and verify GREEN**

Use `runner.fail("Connection LOST", request_stop=False)` in LOST and V2 transport-error paths. Use `request_stop=True` only while transport remains available for FAULT/runtime error. Ensure public STOP first calls runner cancellation and only then sends global STOP. Call `runner.close()` during controller shutdown before the client closes. Keep reconnect free of runner start/reset calls.

- [ ] **Step 7: Add CSV coexistence regression test**

Start the real `StatusCsvLogger` in a temporary directory, start a recipe waiting for temperature, feed multiple V2 STATUS messages through `AppController`, complete the recipe, and stop logging. Assert the CSV contains all STATUS rows and recipe execution never calls `start_logging` or `stop_logging`.

- [ ] **Step 8: Run controller/logging integration suites and commit**

```bash
.venv/bin/pytest -q tests/test_v2_ui_integration.py tests/test_status_csv_logger.py
git add rpi5/raspberrypi5/src/microplaite_ui/core/controller.py rpi5/raspberrypi5/tests/test_v2_ui_integration.py rpi5/raspberrypi5/tests/test_status_csv_logger.py
git commit -m "Integrate V2 recipes with Raspberry controller"
```

### Task 4: Minimal Recipes UI

**Files:**
- Modify: `rpi5/raspberrypi5/src/microplaite_ui/ui/main_window.py`
- Modify: `rpi5/raspberrypi5/tests/test_main.py`

**Interfaces:**
- Consumes: `RecipeStore`, `RecipeDefinition`, `RecipeValidationError`, and `AppController` recipe methods/progress from Tasks 1–3.
- Produces: home Recipes navigation, recipe selection/start/stop controls, and progress/error rendering through the existing Qt timer.

- [ ] **Step 1: Write failing UI construction and discovery tests**

Construct `MainWindow(controller, recipe_store=RecipeStore(tmp_path))` with two JSON files. Assert:

- a visible `RECIPES` home button fits the existing 1280×720 action row;
- clicking it selects `PAGE_RECIPES`;
- the selector contains sorted JSON filenames;
- selecting a valid file displays its recipe name;
- selecting malformed JSON displays Error and keeps START disabled;
- the existing STOP and START LOGGING controls remain present.

- [ ] **Step 2: Run UI construction test RED and add the Recipes page**

Add optional `recipe_store` injection to `MainWindow.__init__`, `PAGE_RECIPES = 6`, page construction, home navigation, selector loading, and these stable widget attributes for tests:

```python
self.recipes_button
self.recipe_combo
self.recipe_name_label
self.recipe_step_label
self.recipe_progress_label
self.recipe_state_label
self.recipe_error_label
self.recipe_start_button
self.recipe_stop_button
```

Use existing buttons, cards, labels, layout helpers, and `_detail_header`; add no new style system.

- [ ] **Step 3: Write failing START/STOP and progress rendering tests**

Use a real runner with recording controller commands and assert:

- START begins the selected recipe once and renders `Running` plus `step 1 / N`;
- START is disabled while RUNNING;
- manual heater, pump, and NeoPixel activation controls are disabled while RUNNING, while every global STOP control remains enabled;
- STOP RECIPE calls `controller.stop_recipe`, renders `Stopped`, and no remaining step runs;
- completion renders `Completed` and `step N / N`;
- timeout/FAULT/LOST renders `Error` and the runner error text;
- reconnect and subsequent Qt timer ticks do not resume the recipe;
- logging active before START remains active during and after normal completion;
- the existing global `_stop` UI handler calls `controller.cancel_recipe()` before timelapse/video/NeoPixel cleanup and before `controller.stop()` sends global STOP.

- [ ] **Step 4: Implement UI handlers and render path, then verify GREEN**

Add `_select_recipe`, `_start_recipe`, `_stop_recipe`, and `_render_recipe`. Call `_render_recipe` from existing `_render`; do not create a QTimer. Enable START only when a valid recipe is selected, `controller.activation_allowed` is true, and runner state is not RUNNING. Enable STOP RECIPE only while RUNNING. While RUNNING, reuse the existing render enablement list to disable manual heater, pump, and NeoPixel activation controls; do not disable STOP controls. At the beginning of the existing global `_stop` handler, call `controller.cancel_recipe()` so cancellation is recorded before any UI cleanup or hardware command; the later `controller.stop()` call remains the sole synchronous global STOP for that handler.

- [ ] **Step 5: Verify no general layout regression**

Run:

```bash
.venv/bin/pytest -q tests/test_main.py
```

Expected: PASS, including existing 1280×720 layout, camera, timelapse, pump, reconnect, and logging tests.

- [ ] **Step 6: Commit the completed feature with the required message**

```bash
git add rpi5/raspberrypi5/src/microplaite_ui/ui/main_window.py rpi5/raspberrypi5/tests/test_main.py
git commit -m "Add simple V2 recipe orchestration"
```

### Task 5: Whole-feature verification and push

**Files:**
- Verify all files changed since `c3a3b1fbc0cd74b42529ba4e33ab18011a580403`.
- Do not add `docs/superpowers/specs/2026-07-17-raspberry-hmi-redesign-design.md`.

**Interfaces:**
- Consumes: completed Tasks 1–4.
- Produces: verified and pushed `software-v2/recipes-v2-rpi-001` branch.

- [ ] **Step 1: Run all targeted recipe tests**

```bash
cd rpi5/raspberrypi5
.venv/bin/pytest -q \
  tests/test_recipes.py \
  tests/test_recipe_runner.py \
  tests/test_v2_ui_integration.py \
  tests/test_status_csv_logger.py \
  tests/test_main.py
```

Expected: all selected tests PASS with no warnings attributable to recipe work.

- [ ] **Step 2: Run the full Python suite**

```bash
.venv/bin/pytest -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run Ruff on new files and critical checks on touched baseline files**

```bash
.venv/bin/ruff check \
  src/microplaite_ui/services/recipes.py \
  src/microplaite_ui/services/recipe_runner.py \
  tests/test_recipes.py \
  tests/test_recipe_runner.py
.venv/bin/ruff check --select E9,F63,F7,F82,I \
  src/microplaite_ui/core/controller.py \
  src/microplaite_ui/ui/main_window.py \
  tests/test_v2_ui_integration.py \
  tests/test_status_csv_logger.py
.venv/bin/ruff check --select E9,F63,F7,F82 tests/test_main.py
```

Expected: all checks PASS. The narrower checks on historical files avoid unrelated existing camera/test lint findings while still detecting syntax, import, and undefined-name regressions.

- [ ] **Step 4: Check whitespace, scope, and protected untracked file**

```bash
cd ../..
git diff --check c3a3b1fbc0cd74b42529ba4e33ab18011a580403..HEAD
git diff --name-status c3a3b1fbc0cd74b42529ba4e33ab18011a580403..HEAD
git status --short --branch --untracked-files=all
sha256sum docs/superpowers/specs/2026-07-17-raspberry-hmi-redesign-design.md
```

Expected:

- only the approved design/plan plus Raspberry recipe source/tests differ from the base;
- `docs/superpowers/specs/2026-07-17-raspberry-hmi-redesign-design.md` remains untracked;
- its checksum remains `e33cf1ded854132c47346850e02090e30a08c00de16bcd4075ff68e48bfbd210`;
- no unstaged recipe implementation changes remain.

- [ ] **Step 5: Push only the requested branch and verify remote parity**

```bash
git push -u origin software-v2/recipes-v2-rpi-001
git rev-parse HEAD
git rev-parse origin/software-v2/recipes-v2-rpi-001
git rev-list --left-right --count @{upstream}...HEAD
```

Expected: local and remote HEAD match and ahead/behind is `0 0`.
