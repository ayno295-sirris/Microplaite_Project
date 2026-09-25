"""RPi-side lifecycle and heartbeat supervision for protocol V2."""

from __future__ import annotations

import threading
from enum import Enum

from microplaite_ui.esp32.v2_client import V2Client, V2ClientError, V2Status
from microplaite_ui.esp32.v2_transport import V2TransportError

DEFAULT_HEARTBEAT_PERIOD_S = 0.5


class SessionState(Enum):
    DISCONNECTED = "DISCONNECTED"
    READY = "READY"
    LOST = "LOST"


class V2Session:
    def __init__(
        self,
        client: V2Client,
        heartbeat_period_s: float = DEFAULT_HEARTBEAT_PERIOD_S,
    ) -> None:
        if heartbeat_period_s <= 0:
            raise ValueError("heartbeat_period_s must be positive")
        self.client = client
        self.heartbeat_period_s = float(heartbeat_period_s)
        self.last_status: V2Status | None = None
        self._state = SessionState.DISCONNECTED
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    @property
    def state(self) -> SessionState:
        with self._state_lock:
            return self._state

    @property
    def heartbeat_running(self) -> bool:
        with self._state_lock:
            thread = self._heartbeat_thread
        return thread is not None and thread.is_alive()

    def open(self) -> V2Status:
        previous_state = self.state
        if previous_state is SessionState.READY:
            raise RuntimeError("V2 session is already READY")
        self._stop_heartbeat()
        if previous_state is SessionState.LOST and self.client.is_open:
            self.client.close()
        try:
            self.client.open()
            self.client.ping()
            status = self.client.status()
            self.client.sync()
        except (V2ClientError, V2TransportError):
            self._set_state(SessionState.LOST)
            raise

        self.last_status = status
        self._stop_event.clear()
        thread = threading.Thread(
            target=self._heartbeat_loop,
            name="MicroplaiteV2Heartbeat",
            daemon=True,
        )
        with self._state_lock:
            self._state = SessionState.READY
            self._heartbeat_thread = thread
        try:
            thread.start()
        except Exception:
            self._stop_event.set()
            with self._state_lock:
                self._state = SessionState.LOST
                self._heartbeat_thread = None
            raise
        return status

    def stop(self) -> None:
        self._stop_heartbeat()
        try:
            self.client.close()
        finally:
            self._set_state(SessionState.DISCONNECTED)

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self.heartbeat_period_s):
            try:
                self.client.heartbeat()
            except (V2ClientError, V2TransportError):
                self._stop_event.set()
                with self._state_lock:
                    self._state = SessionState.LOST
                    self._heartbeat_thread = None
                return

    def _stop_heartbeat(self) -> None:
        self._stop_event.set()
        with self._state_lock:
            thread = self._heartbeat_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join()
        with self._state_lock:
            if self._heartbeat_thread is thread:
                self._heartbeat_thread = None

    def _set_state(self, state: SessionState) -> None:
        with self._state_lock:
            self._state = state
