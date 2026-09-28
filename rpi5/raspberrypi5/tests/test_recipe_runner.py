from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from microplaite_ui.services.recipe_runner import (
    RecipeAlreadyRunningError,
    RecipeRunner,
    RecipeRunState,
    RecipeStatusSample,
)
from microplaite_ui.services.recipes import RecipeAction, RecipeDefinition, RecipeStep


def recipe_with_steps(*steps: RecipeStep) -> RecipeDefinition:
    return RecipeDefinition("Test", tuple(steps), Path("test.json"))


def wait_until_terminal(runner: RecipeRunner, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while runner.snapshot().state is RecipeRunState.RUNNING:
        if time.monotonic() >= deadline:
            raise AssertionError("recipe did not reach a terminal state")
        time.sleep(0.005)


def wait_until_step(runner: RecipeRunner, action: RecipeAction) -> None:
    deadline = time.monotonic() + 0.5
    while runner.snapshot().current_step != action.value:
        if time.monotonic() >= deadline:
            raise AssertionError(f"recipe did not enter {action.value}")
        time.sleep(0.005)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


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


def test_only_one_recipe_runs_and_explicit_restart_begins_at_step_one() -> None:
    command_started = threading.Event()
    release_command = threading.Event()
    calls: list[str] = []

    def execute(step: RecipeStep) -> None:
        calls.append(step.action.value)
        command_started.set()
        assert release_command.wait(1.0)

    recipe = recipe_with_steps(RecipeStep(RecipeAction.HEATER_PID_ON))
    runner = RecipeRunner(execute_command=execute, global_stop=lambda: None)
    runner.start(recipe)
    assert command_started.wait(0.2)

    with pytest.raises(RecipeAlreadyRunningError):
        runner.start(recipe)

    runner.stop(request_stop=False)
    release_command.set()
    wait_until_terminal(runner)
    assert runner.snapshot().state is RecipeRunState.STOPPED

    command_started.clear()
    runner.start(recipe)
    assert command_started.wait(0.2)
    wait_until_terminal(runner)
    assert calls == ["HEATER_PID_ON", "HEATER_PID_ON"]
    assert runner.snapshot().step_number == 1


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
    runner.start(
        recipe_with_steps(
            RecipeStep(RecipeAction.HEATER_PID_ON),
            RecipeStep(RecipeAction.PUMP_START, rpm=3.0),
        )
    )
    assert first_started.wait(0.2)

    runner.stop()
    release_first.set()
    assert stop_called.wait(0.2)

    assert observed_state == [RecipeRunState.STOPPED]
    assert calls == ["HEATER_PID_ON"]


def test_wait_runs_off_caller_thread_and_stop_wakes_it_promptly() -> None:
    runner = RecipeRunner(execute_command=lambda _step: None, global_stop=lambda: None)
    recipe = recipe_with_steps(RecipeStep(RecipeAction.WAIT, seconds=30.0))

    started_at = time.monotonic()
    runner.start(recipe)
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.1
    assert runner.snapshot().state is RecipeRunState.RUNNING
    runner.stop(request_stop=False)
    wait_until_terminal(runner, timeout=0.2)
    assert runner.snapshot().state is RecipeRunState.STOPPED


def test_wait_temperature_uses_only_fresh_valid_status_samples() -> None:
    clock = FakeClock()
    runner = RecipeRunner(
        execute_command=lambda _step: None,
        global_stop=lambda: None,
        monotonic=clock,
    )
    runner.publish_status(
        RecipeStatusSample(4, clock(), temperature_valid=True, temp_c=44.3)
    )
    runner.start(
        recipe_with_steps(
            RecipeStep(
                RecipeAction.WAIT_TEMPERATURE,
                target_c=44.3,
                tolerance_c=0.3,
                timeout_s=10.0,
            )
        )
    )
    wait_until_step(runner, RecipeAction.WAIT_TEMPERATURE)

    assert runner.snapshot().state is RecipeRunState.RUNNING
    clock.advance(1.0)
    runner.publish_status(
        RecipeStatusSample(6, clock(), temperature_valid=True, temp_c=None)
    )
    assert runner.snapshot().state is RecipeRunState.RUNNING

    runner.publish_status(
        RecipeStatusSample(7, clock(), temperature_valid=True, temp_c=44.0)
    )
    wait_until_terminal(runner)
    assert runner.snapshot().state is RecipeRunState.COMPLETED


def test_wait_temperature_rejects_matching_sample_received_after_deadline() -> None:
    clock = FakeClock()
    stop_observation: list[tuple[RecipeRunState, str]] = []
    stop_called = threading.Event()
    runner: RecipeRunner

    def global_stop() -> None:
        progress = runner.snapshot()
        stop_observation.append((progress.state, progress.error))
        stop_called.set()

    runner = RecipeRunner(
        execute_command=lambda _step: None,
        global_stop=global_stop,
        monotonic=clock,
    )
    runner.start(
        recipe_with_steps(
            RecipeStep(
                RecipeAction.WAIT_TEMPERATURE,
                target_c=44.3,
                tolerance_c=0.3,
                timeout_s=5.0,
            )
        )
    )
    wait_until_step(runner, RecipeAction.WAIT_TEMPERATURE)

    clock.advance(6.0)
    runner.publish_status(
        RecipeStatusSample(1, clock(), temperature_valid=True, temp_c=44.3)
    )

    assert stop_called.wait(0.2)
    assert stop_observation[0][0] is RecipeRunState.ERROR
    assert "temperature timeout" in stop_observation[0][1]


def test_lost_interrupts_wait_without_requesting_global_stop() -> None:
    stops: list[str] = []
    runner = RecipeRunner(
        execute_command=lambda _step: None,
        global_stop=lambda: stops.append("STOP"),
    )
    runner.start(recipe_with_steps(RecipeStep(RecipeAction.WAIT, seconds=30.0)))
    wait_until_step(runner, RecipeAction.WAIT)

    runner.fail("Connection LOST", request_stop=False)
    wait_until_terminal(runner)

    assert runner.snapshot().state is RecipeRunState.ERROR
    assert runner.snapshot().error == "Connection LOST"
    assert stops == []


def test_lost_clears_pending_operator_stop_before_worker_sends_it() -> None:
    command_started = threading.Event()
    release_command = threading.Event()
    stops: list[str] = []

    def execute(_step: RecipeStep) -> None:
        command_started.set()
        assert release_command.wait(1.0)

    runner = RecipeRunner(execute, lambda: stops.append("STOP"))
    runner.start(recipe_with_steps(RecipeStep(RecipeAction.PUMP_STOP)))
    assert command_started.wait(0.2)

    runner.stop()
    runner.fail("Connection LOST", request_stop=False)
    release_command.set()
    wait_until_terminal(runner)
    time.sleep(0.01)

    assert runner.snapshot().state is RecipeRunState.ERROR
    assert stops == []


def test_fault_sets_error_before_requesting_one_global_stop() -> None:
    observation: list[tuple[RecipeRunState, str]] = []
    stop_called = threading.Event()
    runner: RecipeRunner

    def global_stop() -> None:
        progress = runner.snapshot()
        observation.append((progress.state, progress.error))
        stop_called.set()

    runner = RecipeRunner(lambda _step: None, global_stop)
    runner.start(recipe_with_steps(RecipeStep(RecipeAction.WAIT, seconds=30.0)))
    wait_until_step(runner, RecipeAction.WAIT)

    runner.fail("ESP32 FAULT", request_stop=True)

    assert stop_called.wait(0.2)
    assert observation == [(RecipeRunState.ERROR, "ESP32 FAULT")]


def test_command_error_stops_once_and_skips_remaining_steps() -> None:
    calls: list[str] = []
    stops: list[RecipeRunState] = []
    runner: RecipeRunner

    def execute(step: RecipeStep) -> None:
        calls.append(step.action.value)
        raise RuntimeError("pump rejected")

    def global_stop() -> None:
        stops.append(runner.snapshot().state)

    runner = RecipeRunner(execute, global_stop)
    runner.start(
        recipe_with_steps(
            RecipeStep(RecipeAction.PUMP_START, rpm=3.0),
            RecipeStep(RecipeAction.HEATER_OFF),
        )
    )
    wait_until_terminal(runner)

    assert calls == ["PUMP_START"]
    assert stops == [RecipeRunState.ERROR]
    assert runner.snapshot().error == "pump rejected"


def test_terminal_error_does_not_resume_without_explicit_start() -> None:
    calls: list[str] = []
    runner = RecipeRunner(
        execute_command=lambda step: calls.append(step.action.value),
        global_stop=lambda: None,
    )
    recipe = recipe_with_steps(RecipeStep(RecipeAction.HEATER_OFF))
    runner.start(recipe_with_steps(RecipeStep(RecipeAction.WAIT, seconds=30.0)))
    wait_until_step(runner, RecipeAction.WAIT)
    runner.fail("Connection LOST", request_stop=False)
    wait_until_terminal(runner)

    runner.publish_status(
        RecipeStatusSample(1, time.monotonic(), temperature_valid=True, temp_c=44.3)
    )
    time.sleep(0.01)
    assert calls == []
    assert runner.snapshot().state is RecipeRunState.ERROR

    runner.start(recipe)
    wait_until_terminal(runner)
    assert calls == ["HEATER_OFF"]
    assert runner.snapshot().step_number == 1


def test_close_cancels_wait_without_global_stop() -> None:
    stops: list[str] = []
    runner = RecipeRunner(
        execute_command=lambda _step: None,
        global_stop=lambda: stops.append("STOP"),
    )
    runner.start(recipe_with_steps(RecipeStep(RecipeAction.WAIT, seconds=30.0)))
    wait_until_step(runner, RecipeAction.WAIT)

    started_at = time.monotonic()
    runner.close()

    assert time.monotonic() - started_at < 0.2
    assert runner.snapshot().state is RecipeRunState.STOPPED
    assert stops == []
