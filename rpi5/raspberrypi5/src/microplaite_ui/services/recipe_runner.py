"""Single-worker orchestration for validated V2 recipes."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum

from microplaite_ui.services.recipes import RecipeAction, RecipeDefinition, RecipeStep


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
    """Raised when starting a recipe while another one is active."""


class RecipeExecutionError(RuntimeError):
    """Raised when a recipe step cannot be executed safely."""


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
        self._lifecycle_lock = threading.Lock()
        self._progress = RecipeProgress()
        self._thread: threading.Thread | None = None
        self._cancelled = False
        self._stop_requested = False
        self._cancel_event = threading.Event()
        self._latest_status_sequence = 0
        self._wait_after_sequence = 0
        self._wait_last_sequence = 0
        self._wait_started = 0.0
        self._wait_deadline = 0.0
        self._wait_target: float | None = None
        self._wait_tolerance: float | None = None
        self._wait_reached = False

    def start(self, recipe: RecipeDefinition) -> None:
        with self._lifecycle_lock:
            with self._condition:
                if self._progress.state is RecipeRunState.RUNNING:
                    raise RecipeAlreadyRunningError("a recipe is already running")
                previous = self._thread
            if previous is not None and previous.is_alive():
                previous.join(timeout=1.0)
                if previous.is_alive():
                    raise RecipeAlreadyRunningError("previous recipe is still stopping")
            with self._condition:
                self._cancelled = False
                self._stop_requested = False
                self._cancel_event.clear()
                self._progress = RecipeProgress(
                    recipe_name=recipe.name,
                    state=RecipeRunState.RUNNING,
                    total_steps=len(recipe.steps),
                )
                self._thread = threading.Thread(
                    target=self._run,
                    args=(recipe,),
                    name="microplaite-recipe",
                    daemon=True,
                )
                self._thread.start()

    def stop(
        self,
        reason: str = "Stopped by operator",
        *,
        request_stop: bool = True,
    ) -> None:
        del reason
        with self._condition:
            if self._progress.state is not RecipeRunState.RUNNING:
                return
            self._cancelled = True
            self._stop_requested = request_stop
            self._progress = replace(
                self._progress,
                state=RecipeRunState.STOPPED,
                current_step="",
                error="",
            )
            self._cancel_event.set()
            self._condition.notify_all()

    def fail(self, reason: str, *, request_stop: bool) -> None:
        with self._condition:
            thread_alive = self._thread is not None and self._thread.is_alive()
            if self._progress.state is not RecipeRunState.RUNNING and not thread_alive:
                return
            self._cancelled = True
            self._stop_requested = request_stop
            self._progress = replace(
                self._progress,
                state=RecipeRunState.ERROR,
                current_step="",
                error=reason,
            )
            self._cancel_event.set()
            self._condition.notify_all()

    def publish_status(self, sample: RecipeStatusSample) -> None:
        with self._condition:
            self._latest_status_sequence = max(
                self._latest_status_sequence,
                sample.sequence,
            )
            if self._wait_target is None or self._wait_tolerance is None:
                return
            if sample.sequence <= max(
                self._wait_after_sequence,
                self._wait_last_sequence,
            ):
                return
            self._wait_last_sequence = sample.sequence
            if not self._wait_started <= sample.received_monotonic <= self._wait_deadline:
                self._condition.notify_all()
                return
            if sample.temperature_valid is not True or sample.temp_c is None:
                self._condition.notify_all()
                return
            if abs(sample.temp_c - self._wait_target) <= self._wait_tolerance:
                self._wait_reached = True
            self._condition.notify_all()

    def snapshot(self) -> RecipeProgress:
        with self._condition:
            return replace(self._progress)

    def close(self) -> None:
        self.stop(request_stop=False)
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _run(self, recipe: RecipeDefinition) -> None:
        for index, step in enumerate(recipe.steps, start=1):
            if self._finish_if_cancelled():
                return
            with self._condition:
                cancelled_at_boundary = self._cancelled
                if not cancelled_at_boundary:
                    self._progress = replace(
                        self._progress,
                        step_number=index,
                        current_step=step.action.value,
                    )
                    wait_temperature_ready = (
                        self._prepare_temperature_wait(step)
                        if step.action is RecipeAction.WAIT_TEMPERATURE
                        else True
                    )
            if cancelled_at_boundary:
                self._finish_if_cancelled()
                return
            if step.action is RecipeAction.WAIT:
                self._wait_duration(step.seconds or 0.0)
            elif step.action is RecipeAction.WAIT_TEMPERATURE:
                if not wait_temperature_ready or not self._wait_temperature():
                    self._finish_if_cancelled()
                    return
            else:
                try:
                    self._execute_command(step)
                except Exception as exc:  # noqa: BLE001 - contain worker failures safely
                    self.fail(str(exc) or exc.__class__.__name__, request_stop=True)
            if self._finish_if_cancelled():
                return
        with self._condition:
            cancelled_at_completion = self._cancelled
            if not cancelled_at_completion:
                self._progress = replace(
                    self._progress,
                    state=RecipeRunState.COMPLETED,
                    current_step="",
                )
        if cancelled_at_completion:
            self._finish_if_cancelled()

    def _wait_duration(self, seconds: float) -> None:
        deadline = self._monotonic() + seconds
        while not self._cancel_event.is_set():
            remaining = deadline - self._monotonic()
            if remaining <= 0.0:
                return
            self._cancel_event.wait(remaining)

    def _prepare_temperature_wait(self, step: RecipeStep) -> bool:
        target = step.target_c
        tolerance = step.tolerance_c
        timeout = step.timeout_s
        if target is None or tolerance is None or timeout is None:
            self._cancelled = True
            self._stop_requested = True
            self._cancel_event.set()
            self._progress = replace(
                self._progress,
                state=RecipeRunState.ERROR,
                current_step="",
                error="invalid WAIT_TEMPERATURE step",
            )
            return False
        self._wait_after_sequence = self._latest_status_sequence
        self._wait_last_sequence = self._wait_after_sequence
        self._wait_started = self._monotonic()
        self._wait_deadline = self._wait_started + timeout
        self._wait_target = target
        self._wait_tolerance = tolerance
        self._wait_reached = False
        return True

    def _wait_temperature(self) -> bool:
        with self._condition:
            while not self._cancelled and not self._wait_reached:
                remaining = self._wait_deadline - self._monotonic()
                if remaining <= 0.0:
                    self._clear_temperature_wait()
                    self._cancelled = True
                    self._stop_requested = True
                    self._cancel_event.set()
                    self._progress = replace(
                        self._progress,
                        state=RecipeRunState.ERROR,
                        current_step="",
                        error="temperature timeout",
                    )
                    return False
                self._condition.wait(timeout=remaining)
            reached = self._wait_reached and not self._cancelled
            self._clear_temperature_wait()
            return reached

    def _clear_temperature_wait(self) -> None:
        self._wait_target = None
        self._wait_tolerance = None
        self._wait_reached = False

    def _finish_if_cancelled(self) -> bool:
        with self._condition:
            if not self._cancelled:
                return False
            request_stop = self._stop_requested
            self._stop_requested = False
        if request_stop:
            self._global_stop()
        return True
