"""Main PySide6 window."""

from __future__ import annotations

import math
import os
import threading
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtMultimedia import (
    QCamera,
    QMediaCaptureSession,
    QMediaDevices,
    QVideoFrame,
    QVideoSink,
)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from microplaite_ui.config import DEFAULT_LOG_PERIOD_MS, SCREEN_HEIGHT, SCREEN_WIDTH
from microplaite_ui.core.controller import AppController
from microplaite_ui.core.state import AppState, derive_system_status
from microplaite_ui.services.timelapse import TimelapseService, TimelapseSettings
from microplaite_ui.ui.styles import QSS


class ClickableCard(QFrame):
    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class NeoRingPreview(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.enabled = True
        self.brightness_percent = 80
        self.setMinimumSize(260, 220)

    def set_state(self, enabled: bool, brightness_percent: int) -> None:
        self.enabled = enabled
        self.brightness_percent = brightness_percent
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center_x = self.width() / 2
        center_y = self.height() / 2 + 8
        radius = min(self.width(), self.height()) * 0.34
        dot_radius = 7
        level = max(0.15, self.brightness_percent / 100)
        color = QColor("#149653" if self.enabled else "#9aa9b8")
        color.setAlphaF(level)
        painter.setPen(QPen(QColor("#c9d8e8"), 1))
        painter.setBrush(color)
        for index in range(16):
            angle = 2 * math.pi * index / 16 - math.pi / 2
            x = center_x + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius
            painter.drawEllipse(
                int(x - dot_radius),
                int(y - dot_radius),
                dot_radius * 2,
                dot_radius * 2,
            )


class MainWindow(QMainWindow):
    PAGE_HOME = 0
    PAGE_TEMPERATURE = 1
    PAGE_THERMAL = 2
    PAGE_PUMP = 3
    PAGE_TIMELAPSE = 4
    PAGE_CAMERA = 5

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self._port_labels: list[QLabel] = []
        self._status_pills: list[QLabel] = []
        self._plot_curves: list[pg.PlotDataItem] = []
        self._target_lines: list[pg.InfiniteLine] = []
        self._camera: QCamera | None = None
        self._camera_session: QMediaCaptureSession | None = None
        self._camera_sink: QVideoSink | None = None
        self._camera_mode = "idle"
        self._camera_image = QImage()
        self._camera_image_lock = threading.Lock()
        self._timelapse_notice = ""
        self.timelapse_service = TimelapseService(
            capture_image=self._save_camera_image,
            neopixel_on=self.controller.timelapse_neopixel_on,
            neopixel_off=self.controller.timelapse_neopixel_off,
            set_neopixel_brightness=self.controller.timelapse_neopixel_brightness,
            log=self.controller.logs.append,
        )
        self._build()
        self.setWindowTitle("Microplaite Control")
        self.setFixedSize(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.setStyleSheet(QSS)
        self._refresh()
        if self.controller.state.connected:
            self.controller.start_live_updates()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_serial)
        self.timer.start(DEFAULT_LOG_PERIOD_MS)

    def _build(self) -> None:
        self.pages = QStackedWidget()
        self.home_page = self._build_home_page()
        self.temperature_page = self._build_temperature_page()
        self.thermal_page = self._build_thermal_page()
        self.pump_page = self._build_pump_page()
        self.timelapse_page = self._build_timelapse_page()
        self.camera_page = self._build_camera_page()
        for page in (
            self.home_page,
            self.temperature_page,
            self.thermal_page,
            self.pump_page,
            self.timelapse_page,
            self.camera_page,
        ):
            self.pages.addWidget(page)
        self.setCentralWidget(self.pages)

    def _build_home_page(self) -> QWidget:
        root, layout = self._page_root()
        layout.addLayout(self._header("Microplaite Control"))

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._home_temperature_card())

        middle = QVBoxLayout()
        middle.setSpacing(10)
        preview_row = QHBoxLayout()
        preview_row.setSpacing(14)
        preview_row.addWidget(self._home_pump_card())
        preview_row.addWidget(self._home_timelapse_card())
        middle.addLayout(preview_row)
        middle.addWidget(self._home_camera_card())
        middle.addStretch()
        body.addLayout(middle)
        layout.addLayout(body)
        layout.addLayout(self._home_actions())

        self.bottom_status = QLabel()
        self.bottom_status.setObjectName("bottomStatus")
        layout.addWidget(self.bottom_status)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logBox")
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(54)
        layout.addWidget(self.log_view)
        return root

    def _home_temperature_card(self) -> ClickableCard:
        card = self._clickable_card("temperatureCard", 500, 456)
        card.clicked.connect(self.show_temperature_page)
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(self._caption("Thermal control"))
        top.addStretch()
        self.home_thermo_dot = self._status_dot()
        self.home_thermo_label = self._small_text("Thermocouple --")
        top.addWidget(self.home_thermo_dot)
        top.addWidget(self.home_thermo_label)
        box.addLayout(top)
        summary = QVBoxLayout()
        summary.setSpacing(8)
        temp_box = QVBoxLayout()
        temp_box.setSpacing(12)
        temp_box.addWidget(self._small_text("Current temperature"))

        self.home_temp_value = QLabel("--.- °C")
        self.home_temp_value.setObjectName("temperatureValue")
        self.home_temp_value.setMinimumWidth(420)
        temp_box.addWidget(self.home_temp_value)
        summary.addLayout(temp_box)

        controls = QVBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(self._small_text("Setpoint"))
        self.home_setpoint = QLabel("--.-- Â°C")
        self.home_setpoint.setObjectName("mediumValue")
        self.home_setpoint.setMinimumWidth(240)
        self.home_setpoint.setFixedHeight(38)
        controls.addWidget(self.home_setpoint)
        nudge = QHBoxLayout()
        nudge.setSpacing(12)
        nudge.addWidget(self._setpoint_button("-", lambda: self._nudge_target(-0.1)))
        nudge.addWidget(self._setpoint_button("+", lambda: self._nudge_target(0.1)))
        nudge.addStretch()
        controls.addLayout(nudge)
        controls.addStretch()
        control_row = QHBoxLayout()
        control_row.setSpacing(22)
        action = QVBoxLayout()
        action.setSpacing(10)
        self.start_button = self._button("START", "primaryButton", 200, 54)
        self.start_button.clicked.connect(self._toggle_pid)
        action.addWidget(self.start_button)
        action.addSpacing(18)
        action.addWidget(self._small_text("Heater output"))
        self.home_heater = QLabel("--.- %")
        self.home_heater.setObjectName("metricValue")
        self.home_heater.setFixedHeight(30)
        action.addWidget(self.home_heater)
        self.home_heater_bar = self._progress()
        self.home_heater_bar.setFixedWidth(170)
        action.addWidget(self.home_heater_bar)
        action.addStretch()
        control_row.addLayout(action)
        control_row.addLayout(controls)
        control_row.addStretch()
        summary.addLayout(control_row)
        box.addLayout(summary)

        trend = self._small_text("Temperature trend")
        trend.setObjectName("trendLabel")
        box.addWidget(trend)
        self.home_temp_plot, _, _ = self._plot(mini=True)
        self.home_temp_plot.setFixedHeight(125)
        box.addWidget(self.home_temp_plot)
        return card

    def _home_thermal_card(self) -> ClickableCard:
        card = self._clickable_card("thermalCard", 432, 162)
        card.clicked.connect(self.show_thermal_page)
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 14, 18, 14)
        box.setSpacing(7)
        top = QHBoxLayout()
        top.addWidget(self._caption("Thermal control"))
        top.addStretch()
        top.addWidget(self._small_text("Tap for PID settings"))
        box.addLayout(top)

        setpoint = QHBoxLayout()
        value_box = QVBoxLayout()
        value_box.addWidget(self._small_text("Setpoint"))
        self.home_setpoint = QLabel("--.-- °C")
        self.home_setpoint.setObjectName("mediumValue")
        value_box.addWidget(self.home_setpoint)
        setpoint.addLayout(value_box)
        setpoint.addStretch()
        setpoint.addWidget(self._small_button("-", lambda: self._nudge_target(-0.1)))
        setpoint.addWidget(self._small_button("+", lambda: self._nudge_target(0.1)))
        box.addLayout(setpoint)

        heater = QHBoxLayout()
        heater.addWidget(self._small_text("Heater output"))
        self.home_heater = QLabel("--.- %")
        self.home_heater.setObjectName("metricValue")
        heater.addWidget(self.home_heater)
        self.home_heater_bar = self._progress()
        self.home_heater_bar.setFixedWidth(122)
        heater.addWidget(self.home_heater_bar)
        box.addLayout(heater)
        return card

    def _home_pump_card(self) -> ClickableCard:
        card = self._clickable_card("pumpCard", 206, 94)
        card.clicked.connect(self.show_pump_page)
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 12, 16, 10)
        box.setSpacing(4)
        top = QHBoxLayout()
        top.addWidget(self._caption("Peristaltic pump"))
        top.addStretch()
        top.addWidget(self._tiny_text("Tap"))
        box.addLayout(top)
        row = QHBoxLayout()
        self.home_pump_dot = self._status_dot()
        self.home_pump_status = self._small_text("Stopped")
        self.home_pump_rpm = QLabel("0 RPM")
        self.home_pump_rpm.setObjectName("metricValue")
        row.addWidget(self.home_pump_dot)
        row.addWidget(self.home_pump_status)
        row.addStretch()
        row.addWidget(self.home_pump_rpm)
        box.addLayout(row)
        return card

    def _home_timelapse_card(self) -> ClickableCard:
        card = self._clickable_card("timelapseCard", 206, 94)
        card.clicked.connect(self.show_timelapse_page)
        box = QVBoxLayout(card)
        box.setContentsMargins(16, 12, 16, 10)
        box.setSpacing(4)
        box.addWidget(self._caption("Timelapse"))
        row = QHBoxLayout()
        self.home_timelapse_dot = self._status_dot()
        self.home_timelapse_status = self._small_text("Stopped")
        self.home_timelapse_count = QLabel("0")
        self.home_timelapse_count.setObjectName("metricValue")
        row.addWidget(self.home_timelapse_dot)
        row.addWidget(self.home_timelapse_status)
        row.addStretch()
        row.addWidget(self.home_timelapse_count)
        box.addLayout(row)
        return card

    def _home_camera_card(self) -> ClickableCard:
        card = self._clickable_card("cameraCard", 724, 348)
        card.clicked.connect(self.show_camera_page)
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 14, 18, 16)
        box.setSpacing(8)
        row = QHBoxLayout()
        row.addWidget(self._caption("Camera preview"))
        row.addStretch()
        row.addWidget(self._small_text("Tap to open camera screen"))
        box.addLayout(row)
        self.home_camera_preview = self._camera_view("USB camera not connected", "cameraPreview")
        box.addWidget(self.home_camera_preview, 1)
        return card

    def _home_actions(self) -> QHBoxLayout:
        actions = QHBoxLayout()
        actions.setSpacing(14)
        self.stop_button = self._button("STOP", "stopButtonCompact", 330, 62)
        self.clear_button = self._button("CLEAR ERROR", "secondaryButton", 260, 62)
        self.refresh_button = self._button("REFRESH STATUS", "secondaryButton", 286, 62)
        self.stop_button.clicked.connect(self._stop)
        self.clear_button.clicked.connect(self._clear_error)
        self.refresh_button.clicked.connect(self._refresh)
        for button in (self.stop_button, self.clear_button, self.refresh_button):
            actions.addWidget(button)
        actions.addStretch()
        return actions

    def _build_temperature_page(self) -> QWidget:
        root, layout = self._page_root()
        layout.addWidget(self._detail_header("Temperature dashboard"))

        row = QHBoxLayout()
        row.setSpacing(16)
        self.temperature_temp_value = QLabel("--.- °C")
        self.temperature_temp_value.setObjectName("detailTempValue")
        self.temperature_thermo_dot = self._status_dot()
        self.temperature_thermo_label = self._small_text("Thermocouple --")
        row.addWidget(
            self._card(
                "card",
                [self._caption("Current temperature"), self.temperature_thermo_dot, self.temperature_thermo_label],
                [self.temperature_temp_value],
                width=430,
                height=142,
            )
        )
        self.temperature_target_value = QLabel("--.-- °C")
        self.temperature_target_value.setObjectName("mediumValue")
        target_card = self._plain_card("card", width=340, height=142)
        target_box = QVBoxLayout(target_card)
        target_box.setContentsMargins(18, 14, 18, 14)
        target_box.setSpacing(8)
        target_box.addWidget(self._caption("Target"))
        target_row = QHBoxLayout()
        target_row.setSpacing(10)
        target_row.addWidget(self.temperature_target_value)
        self.temperature_target_minus_button = self._setpoint_compact_button("-", lambda: self._nudge_target(-0.1))
        self.temperature_target_plus_button = self._setpoint_compact_button("+", lambda: self._nudge_target(0.1))
        target_row.addWidget(self.temperature_target_minus_button)
        target_row.addWidget(self.temperature_target_plus_button)
        target_box.addLayout(target_row)
        row.addWidget(target_card)

        self.temperature_heater_value = QLabel("--.- %")
        self.temperature_heater_value.setObjectName("mediumValue")
        control_card = self._plain_card("card", width=330, height=142)
        control_box = QVBoxLayout(control_card)
        control_box.setContentsMargins(18, 14, 18, 14)
        control_box.setSpacing(8)
        control_box.addWidget(self._caption("PID control"))
        control_row = QHBoxLayout()
        self.temperature_start_button = self._button("START", "primaryButton", 176, 54)
        self.temperature_start_button.clicked.connect(self._toggle_pid)
        control_row.addWidget(self.temperature_start_button)
        heater_box = QVBoxLayout()
        heater_box.setSpacing(2)
        heater_box.addWidget(self._small_text("Heater output"))
        heater_box.addWidget(self.temperature_heater_value)
        control_row.addLayout(heater_box)
        control_row.addStretch()
        control_box.addLayout(control_row)
        row.addWidget(control_card)
        row.addStretch()
        layout.addLayout(row)

        graph_card = self._plain_card("card")
        graph_box = QVBoxLayout(graph_card)
        graph_box.setContentsMargins(22, 16, 22, 16)
        graph_box.addWidget(self._title_small("Live temperature · last 5 minutes"))
        self.temperature_plot, _, _ = self._plot(mini=False)
        self.temperature_plot.setFixedHeight(360)
        graph_box.addWidget(self.temperature_plot)
        layout.addWidget(graph_card, 1)
        layout.addStretch()
        return root

    def _build_thermal_page(self) -> QWidget:
        root, layout = self._page_root()
        layout.addWidget(self._detail_header("Thermal control"))

        top = QHBoxLayout()
        top.setSpacing(16)
        self.thermal_temp_value = QLabel("--.- °C")
        self.thermal_temp_value.setObjectName("detailTempValue")
        self.thermal_thermo_dot = self._status_dot()
        self.thermal_thermo_label = self._small_text("Thermocouple --")
        self.thermal_mode_small = self._small_text("IDLE")
        self.thermal_hero_card = self._plain_card("card", width=420, height=150)
        hero_box = QVBoxLayout(self.thermal_hero_card)
        hero_box.setContentsMargins(24, 16, 24, 16)
        line = QHBoxLayout()
        line.addWidget(self._caption("Temperature control"))
        line.addStretch()
        line.addWidget(self.thermal_thermo_dot)
        line.addWidget(self.thermal_thermo_label)
        hero_box.addLayout(line)
        hero_box.addWidget(self.thermal_temp_value)
        hero_box.addWidget(self.thermal_mode_small)
        top.addWidget(self.thermal_hero_card)

        self.thermal_setpoint_value = QLabel("--.-- °C")
        self.thermal_setpoint_value.setObjectName("mediumValue")
        setpoint_card = self._plain_card("card", width=250, height=150)
        setpoint_box = QVBoxLayout(setpoint_card)
        setpoint_box.setContentsMargins(18, 14, 18, 14)
        setpoint_box.addWidget(self._caption("Setpoint"))
        setpoint_box.addWidget(self.thermal_setpoint_value)
        buttons = QHBoxLayout()
        buttons.addWidget(self._small_button("-", lambda: self._nudge_target(-0.1)))
        buttons.addWidget(self._small_button("+", lambda: self._nudge_target(0.1)))
        buttons.addStretch()
        setpoint_box.addLayout(buttons)
        top.addWidget(setpoint_card)

        self.thermal_heater_value = QLabel("--.- %")
        self.thermal_heater_value.setObjectName("mediumValue")
        self.thermal_heater_bar = self._progress()
        heater_card = self._plain_card("card", width=250, height=150)
        heater_box = QVBoxLayout(heater_card)
        heater_box.setContentsMargins(18, 14, 18, 14)
        heater_box.addWidget(self._caption("Heater output"))
        heater_box.addWidget(self.thermal_heater_value)
        heater_box.addWidget(self.thermal_heater_bar)
        top.addWidget(heater_card)
        top.addStretch()
        layout.addLayout(top)

        middle = QHBoxLayout()
        middle.setSpacing(16)
        self.pid_card = self._plain_card("card", width=450, height=290)
        pid_box = QVBoxLayout(self.pid_card)
        pid_box.setContentsMargins(22, 18, 22, 18)
        pid_box.setSpacing(10)
        pid_box.addWidget(self._title_small("PID parameters"))
        pid_grid = QGridLayout()
        pid_grid.setHorizontalSpacing(28)
        pid_grid.setVerticalSpacing(6)
        self.pid_value_labels: dict[str, QLabel] = {}
        for row, (key, label) in enumerate(
            (
                ("kp", "Kp"),
                ("ki", "Ki"),
                ("kd", "Kd"),
                ("pid_limit", "PID limit"),
                ("power_limit", "Power limit"),
                ("safety_limit", "Safety limit"),
                ("integral", "PID integral"),
                ("error", "Last error"),
            )
        ):
            name = QLabel(label)
            name.setObjectName("pidName")
            value = QLabel("--")
            value.setObjectName("pidValue")
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.pid_value_labels[key] = value
            pid_grid.addWidget(name, row, 0)
            pid_grid.addWidget(value, row, 1)
        pid_grid.setColumnStretch(0, 1)
        pid_grid.setColumnStretch(1, 1)
        pid_box.addLayout(pid_grid)
        pid_box.addStretch()
        self.pid_values = QLabel()
        middle.addWidget(self.pid_card)

        self.thermal_graph_card = self._plain_card("card", width=770, height=290)
        graph_box = QVBoxLayout(self.thermal_graph_card)
        graph_box.setContentsMargins(18, 14, 18, 14)
        graph_box.setSpacing(8)
        graph_box.addWidget(self._title_small("Live response preview"))
        self.thermal_plot, _, _ = self._plot(mini=False)
        self.thermal_plot.setFixedHeight(230)
        graph_box.addWidget(self.thermal_plot, 1)
        middle.addWidget(self.thermal_graph_card)
        layout.addLayout(middle)

        footer = QHBoxLayout()
        footer.setSpacing(14)
        self.thermal_sensor = QLabel("--")
        self.thermal_fault = QLabel("--")
        self.thermal_gpio = QLabel("--")
        self.thermal_error = QLabel("--")
        for label, widget, width in (
            ("Sensor", self.thermal_sensor, 170),
            ("Fault", self.thermal_fault, 170),
            ("GPIO14", self.thermal_gpio, 170),
            ("Last error", self.thermal_error, 250),
        ):
            widget.setObjectName("footerValue")
            footer.addWidget(self._metric_card(label, widget, width=width, height=56))
        footer.addStretch()
        layout.addLayout(footer)
        layout.addStretch()
        return root

    def _build_pump_page(self) -> QWidget:
        root, layout = self._page_root()
        layout.addWidget(self._detail_header("Peristaltic pump"))

        body = QHBoxLayout()
        body.setSpacing(20)
        main = self._plain_card("card", width=700, height=430)
        box = QVBoxLayout(main)
        box.setContentsMargins(24, 22, 24, 20)
        box.addWidget(self._caption_large("Pump control"))
        status = QHBoxLayout()
        self.pump_dot = self._status_dot()
        self.pump_status = self._small_text("Stopped")
        status.addWidget(self.pump_dot)
        status.addWidget(self.pump_status)
        status.addStretch()
        box.addLayout(status)
        self.pump_actual_rpm = QLabel("0 RPM")
        self.pump_actual_rpm.setObjectName("hugeValue")
        box.addWidget(self.pump_actual_rpm)
        speed_row = QHBoxLayout()
        speed_row.addWidget(self._caption_large("Rotation speed setpoint"))
        speed_row.addStretch()
        self.pump_target_rpm = QLabel("50 RPM")
        self.pump_target_rpm.setObjectName("mediumValue")
        speed_row.addWidget(self.pump_target_rpm)
        box.addLayout(speed_row)
        self.pump_slider = QSlider(Qt.Horizontal)
        self.pump_slider.setObjectName("rpmSlider")
        self.pump_slider.setRange(0, 100)
        self.pump_slider.setValue(50)
        self.pump_slider.valueChanged.connect(self._set_pump_target_rpm)
        box.addWidget(self.pump_slider)

        rpm_control = QHBoxLayout()
        rpm_control.setSpacing(12)
        self.pump_minus_button = self._button("-", "rpmStepButton", 98, 74)
        self.pump_plus_button = self._button("+", "rpmStepButton", 98, 74)
        self.pump_spin = QDoubleSpinBox()
        self.pump_spin.setObjectName("rpmSpinBox")
        self.pump_spin.setRange(0.0, 100.0)
        self.pump_spin.setDecimals(1)
        self.pump_spin.setSingleStep(0.1)
        self.pump_spin.setSuffix(" RPM")
        self.pump_spin.setValue(50.0)
        self.pump_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.pump_spin.valueChanged.connect(self._set_pump_target_rpm)
        self.pump_minus_button.clicked.connect(lambda: self._nudge_pump_target(-1))
        self.pump_plus_button.clicked.connect(lambda: self._nudge_pump_target(1))
        rpm_control.addWidget(self.pump_minus_button)
        rpm_control.addWidget(self.pump_spin, 1)
        rpm_control.addWidget(self.pump_plus_button)
        box.addLayout(rpm_control)
        controls = QHBoxLayout()
        for text, name, handler in (
            ("START PUMP", "primaryButton", self._start_pump),
            ("STOP PUMP", "stopButtonSmall", self._stop_pump),
            ("PRIME", "secondaryButton", self._prime_pump),
        ):
            button = self._button(text, name, 160, 58)
            button.clicked.connect(handler)
            controls.addWidget(button)
        controls.addStretch()
        box.addLayout(controls)
        body.addWidget(main)

        info = self._plain_card("card", width=386, height=430)
        info_box = QVBoxLayout(info)
        info_box.setContentsMargins(24, 24, 24, 24)
        info_box.addWidget(self._caption_large("Live pump status"))
        self.pump_info = QLabel()
        self.pump_info.setObjectName("infoText")
        self.pump_info.setWordWrap(True)
        info_box.addWidget(self.pump_info)
        info_box.addStretch()
        body.addWidget(info)
        body.addStretch()
        layout.addLayout(body)
        layout.addStretch()
        return root

    def _build_timelapse_page(self) -> QWidget:
        root, layout = self._page_root()
        layout.addWidget(self._detail_header("Timelapse"))

        tab_row = QHBoxLayout()
        tab_row.setSpacing(10)
        self.timelapse_acquisition_tab = self._button("ACQUISITION", "tabButtonActive", 168, 46)
        self.timelapse_test_tab = self._button("TEST PHOTO", "tabButton", 168, 46)
        self.timelapse_acquisition_tab.clicked.connect(lambda: self._show_timelapse_tab(0))
        self.timelapse_test_tab.clicked.connect(lambda: self._show_timelapse_tab(1))
        self.start_timelapse_button = self._button("START TIMELAPSE", "primaryButton", 206, 46)
        self.start_timelapse_button.clicked.connect(self._start_timelapse)
        self.stop_timelapse_button = self._button("STOP TIMELAPSE", "stopButtonSmall", 206, 46)
        self.stop_timelapse_button.clicked.connect(self._stop_timelapse)
        tab_row.addWidget(self.timelapse_acquisition_tab)
        tab_row.addWidget(self.timelapse_test_tab)
        tab_row.addWidget(self.start_timelapse_button)
        tab_row.addWidget(self.stop_timelapse_button)
        tab_row.addStretch()
        layout.addLayout(tab_row)

        self.timelapse_error = QLabel("")
        self.timelapse_error.setObjectName("infoText")
        self.timelapse_error.setFixedHeight(22)
        self.timelapse_error.setWordWrap(True)
        layout.addWidget(self.timelapse_error)

        self.timelapse_stack = QStackedWidget()
        self.timelapse_stack.addWidget(self._build_timelapse_acquisition_tab())
        self.timelapse_stack.addWidget(self._build_timelapse_test_tab())
        layout.addWidget(self.timelapse_stack, 1)
        return root

    def _build_timelapse_acquisition_tab(self) -> QWidget:
        root = QWidget()
        body = QHBoxLayout(root)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)

        self.timelapse_acquisition_card = self._plain_card("card", width=604, height=420)
        box = QVBoxLayout(self.timelapse_acquisition_card)
        box.setContentsMargins(18, 14, 18, 14)
        box.setSpacing(6)
        box.addWidget(self._caption_large("Acquisition settings"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self.storage_combo = QComboBox()
        self.storage_combo.addItem("Internal Raspberry Pi", "internal")
        self.storage_combo.addItem("External disk", "external")
        self.storage_combo.currentIndexChanged.connect(self._refresh_timelapse_storage)
        grid.addWidget(self._small_text("Storage"), 0, 0)
        grid.addWidget(self.storage_combo, 0, 1, 1, 2)

        self.interval_spin = QSpinBox()
        self.interval_spin.setObjectName("touchSpinBox")
        self.interval_spin.setRange(1, 86400)
        self.interval_spin.setValue(10)
        self.interval_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.interval_unit = QComboBox()
        self.interval_unit.addItem("seconds", 1)
        self.interval_unit.addItem("minutes", 60)
        self.interval_spin.valueChanged.connect(self._render)
        self.interval_unit.currentIndexChanged.connect(self._render)
        interval_control = QHBoxLayout()
        interval_control.setSpacing(8)
        self.interval_minus_button = self._button("-", "fieldStepButton", 56, 44)
        self.interval_plus_button = self._button("+", "fieldStepButton", 56, 44)
        self.interval_minus_button.clicked.connect(lambda: self._nudge_numeric_field(self.interval_spin, -1))
        self.interval_plus_button.clicked.connect(lambda: self._nudge_numeric_field(self.interval_spin, 1))
        interval_control.addWidget(self.interval_minus_button)
        interval_control.addWidget(self.interval_spin)
        interval_control.addWidget(self.interval_plus_button)
        interval_control.addWidget(self.interval_unit)
        grid.addWidget(self._small_text("Interval"), 1, 0)
        grid.addLayout(interval_control, 1, 1, 1, 2)

        self.timelapse_brightness_spin = QSpinBox()
        self.timelapse_brightness_spin.setObjectName("touchSpinBox")
        self.timelapse_brightness_spin.setRange(0, 100)
        self.timelapse_brightness_spin.setSuffix(" %")
        self.timelapse_brightness_spin.setValue(80)
        self.timelapse_brightness_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.timelapse_brightness_spin.valueChanged.connect(
            lambda value: self._set_timelapse_brightness_value(value, send_to_esp32=False)
        )
        brightness_control = QHBoxLayout()
        brightness_control.setSpacing(8)
        self.timelapse_brightness_minus_button = self._button("-", "fieldStepButton", 56, 44)
        self.timelapse_brightness_plus_button = self._button("+", "fieldStepButton", 56, 44)
        self.timelapse_brightness_minus_button.clicked.connect(
            lambda: self._nudge_numeric_field(self.timelapse_brightness_spin, -1)
        )
        self.timelapse_brightness_plus_button.clicked.connect(
            lambda: self._nudge_numeric_field(self.timelapse_brightness_spin, 1)
        )
        brightness_control.addWidget(self.timelapse_brightness_minus_button)
        brightness_control.addWidget(self.timelapse_brightness_spin)
        brightness_control.addWidget(self.timelapse_brightness_plus_button)
        grid.addWidget(self._small_text("NeoPixel power"), 2, 0)
        grid.addLayout(brightness_control, 2, 1, 1, 2)

        self.light_duration_spin = QDoubleSpinBox()
        self.light_duration_spin.setObjectName("touchSpinBox")
        self.light_duration_spin.setRange(0.0, 60.0)
        self.light_duration_spin.setSingleStep(0.1)
        self.light_duration_spin.setDecimals(1)
        self.light_duration_spin.setSuffix(" s")
        self.light_duration_spin.setValue(1.0)
        self.light_duration_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.light_duration_spin.valueChanged.connect(self._render)
        light_duration_control = QHBoxLayout()
        light_duration_control.setSpacing(8)
        self.light_duration_minus_button = self._button("-", "fieldStepButton", 56, 44)
        self.light_duration_plus_button = self._button("+", "fieldStepButton", 56, 44)
        self.light_duration_minus_button.clicked.connect(
            lambda: self._nudge_numeric_field(self.light_duration_spin, -0.1)
        )
        self.light_duration_plus_button.clicked.connect(
            lambda: self._nudge_numeric_field(self.light_duration_spin, 0.1)
        )
        light_duration_control.addWidget(self.light_duration_minus_button)
        light_duration_control.addWidget(self.light_duration_spin)
        light_duration_control.addWidget(self.light_duration_plus_button)
        grid.addWidget(self._small_text("Light duration"), 3, 0)
        grid.addLayout(light_duration_control, 3, 1, 1, 2)

        self.total_duration_spin = QSpinBox()
        self.total_duration_spin.setObjectName("touchSpinBox")
        self.total_duration_spin.setRange(1, 10080)
        self.total_duration_spin.setSuffix(" min")
        self.total_duration_spin.setValue(60)
        self.total_duration_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.total_duration_spin.valueChanged.connect(self._render)
        self.infinite_check = QCheckBox("Infinite")
        self.infinite_check.toggled.connect(self._toggle_infinite)
        total_duration_control = QHBoxLayout()
        total_duration_control.setSpacing(8)
        self.total_duration_minus_button = self._button("-", "fieldStepButton", 56, 44)
        self.total_duration_plus_button = self._button("+", "fieldStepButton", 56, 44)
        self.total_duration_minus_button.clicked.connect(
            lambda: self._nudge_numeric_field(self.total_duration_spin, -1)
        )
        self.total_duration_plus_button.clicked.connect(
            lambda: self._nudge_numeric_field(self.total_duration_spin, 1)
        )
        total_duration_control.addWidget(self.total_duration_minus_button)
        total_duration_control.addWidget(self.total_duration_spin)
        total_duration_control.addWidget(self.total_duration_plus_button)
        grid.addWidget(self._small_text("Total duration"), 4, 0)
        grid.addLayout(total_duration_control, 4, 1)
        grid.addWidget(self.infinite_check, 4, 2)
        grid.setColumnStretch(1, 1)
        box.addLayout(grid)

        self.timelapse_path = QLabel("")
        self.timelapse_path.setObjectName("infoText")
        self.timelapse_path.setWordWrap(True)
        box.addWidget(self.timelapse_path)

        body.addWidget(self.timelapse_acquisition_card)

        self.timelapse_status_card = self._plain_card("card", width=604, height=420)
        status_box = QVBoxLayout(self.timelapse_status_card)
        status_box.setContentsMargins(22, 16, 22, 16)
        status_box.setSpacing(8)
        status_box.addWidget(self._caption_large("Acquisition status"))
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(6)
        self.timelapse_status = QLabel("Stopped")
        self.timelapse_status.setObjectName("mediumValue")
        self.timelapse_frames = QLabel("0")
        self.timelapse_frames.setObjectName("mediumValue")
        self.timelapse_free = QLabel("--")
        self.timelapse_free.setObjectName("footerValue")
        self.timelapse_estimate = QLabel("--")
        self.timelapse_estimate.setObjectName("footerValue")
        for row, (label, widget) in enumerate(
            (
                ("Status", self.timelapse_status),
                ("Frames", self.timelapse_frames),
                ("Disk free", self.timelapse_free),
                ("Estimate", self.timelapse_estimate),
            )
        ):
            metrics.addWidget(self._small_text(label), row, 0)
            metrics.addWidget(widget, row, 1)
        status_box.addLayout(metrics)

        self.timelapse_last_file = QLabel("Last file: -")
        self.timelapse_last_file.setObjectName("infoText")
        self.timelapse_last_file.setWordWrap(True)
        status_box.addWidget(self.timelapse_last_file)
        status_box.addStretch()
        body.addWidget(self.timelapse_status_card)
        body.addStretch()
        return root

    def _build_timelapse_test_tab(self) -> QWidget:
        root = QWidget()
        body = QHBoxLayout(root)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)

        self.test_photo_controls_card = self._plain_card("card", width=440, height=420)
        controls = QVBoxLayout(self.test_photo_controls_card)
        controls.setContentsMargins(22, 16, 22, 16)
        controls.setSpacing(8)
        controls.addWidget(self._caption_large("Test photo"))

        live_controls = QHBoxLayout()
        self.start_live_button = self._button("START LIVE", "okButton", 190, 50)
        self.stop_live_button = self._button("STOP LIVE", "secondaryButton", 190, 50)
        self.start_live_button.clicked.connect(self._start_live_video)
        self.stop_live_button.clicked.connect(self._stop_live_video)
        live_controls.addWidget(self.start_live_button)
        live_controls.addWidget(self.stop_live_button)
        controls.addLayout(live_controls)

        controls.addWidget(self._small_text("NeoPixel"))
        self.test_neopixel_status = QLabel("NeoPixel ON")
        self.test_neopixel_status.setObjectName("footerValue")
        controls.addWidget(self.test_neopixel_status)
        neo_buttons = QHBoxLayout()
        self.test_neopixel_on_button = self._button("ON", "okButton", 190, 48)
        self.test_neopixel_off_button = self._button("OFF", "secondaryButton", 190, 48)
        self.test_neopixel_on_button.clicked.connect(lambda: self._set_neopixel_enabled(True))
        self.test_neopixel_off_button.clicked.connect(lambda: self._set_neopixel_enabled(False))
        neo_buttons.addWidget(self.test_neopixel_on_button)
        neo_buttons.addWidget(self.test_neopixel_off_button)
        controls.addLayout(neo_buttons)

        self.test_brightness_spin = QSpinBox()
        self.test_brightness_spin.setObjectName("touchSpinBox")
        self.test_brightness_spin.setRange(0, 100)
        self.test_brightness_spin.setSuffix(" %")
        self.test_brightness_spin.setValue(80)
        self.test_brightness_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.test_brightness_spin.valueChanged.connect(
            lambda value: self._set_timelapse_brightness_value(value, send_to_esp32=True)
        )
        test_brightness_control = QHBoxLayout()
        test_brightness_control.setSpacing(8)
        self.test_brightness_minus_button = self._button("-", "fieldStepButton", 78, 48)
        self.test_brightness_plus_button = self._button("+", "fieldStepButton", 78, 48)
        self.test_brightness_minus_button.clicked.connect(
            lambda: self._nudge_numeric_field(self.test_brightness_spin, -1)
        )
        self.test_brightness_plus_button.clicked.connect(
            lambda: self._nudge_numeric_field(self.test_brightness_spin, 1)
        )
        test_brightness_control.addWidget(self.test_brightness_minus_button)
        test_brightness_control.addWidget(self.test_brightness_spin, 1)
        test_brightness_control.addWidget(self.test_brightness_plus_button)
        controls.addWidget(self._small_text("Intensity"))
        controls.addLayout(test_brightness_control)

        self.test_capture_button = self._button("TEST CAPTURE", "primaryButton", 392, 54)
        self.test_capture_button.clicked.connect(self._test_capture)
        controls.addWidget(self.test_capture_button)
        body.addWidget(self.test_photo_controls_card)

        self.test_photo_preview_card = self._plain_card("card", width=768, height=420)
        preview_box = QVBoxLayout(self.test_photo_preview_card)
        preview_box.setContentsMargins(18, 18, 18, 18)
        preview_box.setSpacing(8)
        preview_box.addWidget(self._caption_large("Live camera"))
        self.timelapse_live_preview = self._camera_view("Live video stopped", "cameraPreview")
        preview_box.addWidget(self.timelapse_live_preview, 1)
        body.addWidget(self.test_photo_preview_card)
        body.addStretch()
        return root

    def _show_timelapse_tab(self, index: int) -> None:
        self.timelapse_stack.setCurrentIndex(index)
        self._set_object_name(
            self.timelapse_acquisition_tab,
            "tabButtonActive" if index == 0 else "tabButton",
        )
        self._set_object_name(
            self.timelapse_test_tab,
            "tabButtonActive" if index == 1 else "tabButton",
        )

    def _build_camera_page(self) -> QWidget:
        root, layout = self._page_root()
        nav = QHBoxLayout()
        self.camera_back_button = self._button("BACK", "secondaryButton", 120, 56)
        self.camera_back_button.clicked.connect(self.show_home_page)
        nav.addWidget(self.camera_back_button)
        nav.addStretch()
        layout.addLayout(nav)
        self.camera_preview = self._camera_view("USB camera not connected", "cameraFullPreview")
        layout.addWidget(self.camera_preview, 1)
        return root

    def _page_root(self) -> tuple[QWidget, QVBoxLayout]:
        root = QWidget()
        root.setObjectName("appRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        return root, layout

    def _header(self, title: str) -> QHBoxLayout:
        row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        port = QLabel()
        port.setObjectName("portLabel")
        status = QLabel("DISCONNECTED")
        status.setObjectName("statusPillIdle")
        status.setFixedSize(150, 40)
        self._port_labels.append(port)
        self._status_pills.append(status)
        row.addWidget(title_label)
        row.addStretch()
        row.addWidget(port)
        row.addWidget(status)
        return row

    def _detail_header(self, title: str) -> QWidget:
        bar = QWidget()
        bar.setObjectName("detailTopBar")
        bar.setFixedHeight(72)
        row = QHBoxLayout(bar)
        row.setSpacing(12)
        row.setContentsMargins(0, 0, 0, 0)
        back = self._button("BACK", "secondaryButton", 118, 54)
        back.clicked.connect(self.show_home_page)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        port = QLabel()
        port.setObjectName("portLabel")
        status = QLabel("DISCONNECTED")
        status.setObjectName("statusPillIdle")
        status.setFixedSize(150, 40)
        stop = self._button("STOP", "stopButtonCompact", 158, 64)
        stop.clicked.connect(self._stop)
        self._port_labels.append(port)
        self._status_pills.append(status)
        row.addWidget(back)
        row.addWidget(title_label)
        row.addStretch()
        row.addWidget(port)
        row.addWidget(status)
        row.addWidget(stop)
        return bar

    def _detail_nav(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        back = self._button("← BACK", "secondaryButton", 118, 56)
        stop = self._button("STOP", "stopButton", 226, 104)
        back.clicked.connect(self.show_home_page)
        stop.clicked.connect(self._stop)
        row.addWidget(back)
        row.addStretch()
        row.addWidget(stop)
        return row

    def _clickable_card(self, object_name: str, width: int, height: int) -> ClickableCard:
        card = ClickableCard()
        card.setObjectName(object_name)
        card.setCursor(Qt.PointingHandCursor)
        card.setFixedSize(width, height)
        return card

    def _plain_card(self, object_name: str, width: int | None = None, height: int | None = None) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        if width is not None:
            card.setFixedWidth(width)
        if height is not None:
            card.setFixedHeight(height)
        return card

    def _card(
        self,
        object_name: str,
        top_widgets: list[QWidget],
        body_widgets: list[QWidget],
        width: int,
        height: int,
    ) -> QFrame:
        card = self._plain_card(object_name, width, height)
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 14, 18, 14)
        top = QHBoxLayout()
        for widget in top_widgets:
            top.addWidget(widget)
        top.addStretch()
        box.addLayout(top)
        for widget in body_widgets:
            box.addWidget(widget)
        return card

    def _metric_card(self, caption: str, widget: QLabel, width: int, height: int) -> QFrame:
        card = self._plain_card("card", width, height)
        box = QVBoxLayout(card)
        box.setContentsMargins(14, 10, 14, 10)
        box.setSpacing(2)
        box.addWidget(self._caption(caption))
        box.addWidget(widget)
        return card

    def _button(self, text: str, object_name: str, width: int, height: int) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setFixedSize(width, height)
        return button

    def _small_button(self, text: str, handler) -> QPushButton:
        button = self._button(text, "smallDarkButton", 58, 46)
        button.clicked.connect(handler)
        return button

    def _setpoint_button(self, text: str, handler) -> QPushButton:
        button = self._button(text, "setpointButton", 78, 58)
        button.clicked.connect(handler)
        return button

    def _setpoint_compact_button(self, text: str, handler) -> QPushButton:
        button = self._button(text, "setpointButtonCompact", 58, 52)
        button.clicked.connect(handler)
        return button

    def _caption(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("caption")
        return label

    def _caption_large(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("captionLarge")
        return label

    def _small_text(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("smallText")
        return label

    def _tiny_text(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("tinyText")
        return label

    def _title_small(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _status_dot(self) -> QFrame:
        dot = QFrame()
        dot.setObjectName("statusDotError")
        dot.setFixedSize(12, 12)
        return dot

    def _progress(self) -> QProgressBar:
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setTextVisible(False)
        progress.setFixedHeight(14)
        return progress

    def _plot(self, mini: bool) -> tuple[pg.PlotWidget, pg.PlotDataItem, pg.InfiniteLine]:
        plot = pg.PlotWidget()
        plot.setBackground("#ffffff")
        plot.setMouseEnabled(x=False, y=False)
        plot.setMenuEnabled(False)
        plot.hideButtons()
        plot.showGrid(x=True, y=True, alpha=0.12 if mini else 0.18)
        if mini:
            plot.getPlotItem().hideAxis("bottom")
            plot.getPlotItem().hideAxis("left")
        else:
            plot.setLabel("left", "Temperature", units="°C")
            plot.setLabel("bottom", "Time", units="s")
        plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        curve = plot.plot([], [], pen=pg.mkPen("#216ee5", width=3))
        target = pg.InfiniteLine(pos=37.5, angle=0, movable=False, pen=pg.mkPen("#149653", width=1))
        plot.addItem(target)
        self._plot_curves.append(curve)
        self._target_lines.append(target)
        return plot, curve, target

    def _camera_view(self, text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return label

    def _start_usb_camera(self, mode: str) -> bool:
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            self._set_camera_text("Camera disabled in test mode")
            return False
        devices = QMediaDevices.videoInputs()
        if not devices:
            self._set_camera_text("No USB camera detected")
            return False
        self._camera_sink = QVideoSink()
        self._camera_sink.videoFrameChanged.connect(self._show_camera_frame)
        self._camera_session = QMediaCaptureSession()
        self._camera = QCamera(devices[0])
        self._camera.errorOccurred.connect(lambda *_: self._set_camera_text("Camera error"))
        self._camera_session.setCamera(self._camera)
        self._camera_session.setVideoSink(self._camera_sink)
        self._set_camera_text(f"USB camera: {devices[0].description()}")
        self._camera.start()
        self._camera_mode = mode
        self.controller.logs.append("live video started" if mode == "live" else "timelapse camera started")
        return True

    def _stop_camera(self, text: str, log_message: str | None = None) -> None:
        if self._camera is not None:
            self._camera.stop()
        if log_message:
            self.controller.logs.append(log_message)
        self._camera = None
        self._camera_session = None
        self._camera_sink = None
        self._camera_mode = "idle"
        with self._camera_image_lock:
            self._camera_image = QImage()
        self._set_camera_text(text)

    def _set_camera_text(self, text: str) -> None:
        previews = (
            self.home_camera_preview,
            self.camera_preview,
            getattr(self, "timelapse_live_preview", None),
        )
        for preview in previews:
            if preview is None:
                continue
            preview.clear()
            preview.setText(text)

    def _show_camera_frame(self, frame: QVideoFrame) -> None:
        image = frame.toImage()
        if image.isNull():
            return
        with self._camera_image_lock:
            self._camera_image = image.copy()
        self._paint_camera_image()

    def _paint_camera_image(self) -> None:
        with self._camera_image_lock:
            image = self._camera_image.copy()
        if image.isNull():
            return
        pixmap = QPixmap.fromImage(image)
        previews = (
            self.home_camera_preview,
            self.camera_preview,
            getattr(self, "timelapse_live_preview", None),
        )
        for preview in previews:
            if preview is None:
                continue
            if preview.size().isEmpty():
                continue
            scaled = pixmap.scaled(preview.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = max(0, (scaled.width() - preview.width()) // 2)
            y = max(0, (scaled.height() - preview.height()) // 2)
            preview.setText("")
            preview.setPixmap(scaled.copy(x, y, preview.width(), preview.height()))

    def _save_camera_image(self, destination: Path) -> Path:
        with self._camera_image_lock:
            image = self._camera_image.copy()
        if image.isNull():
            raise RuntimeError("no camera frame available; start live video and wait for an image")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(destination), "JPG"):
            raise RuntimeError(f"camera image save failed: {destination}")
        return destination

    def show_home_page(self) -> None:
        self.pages.setCurrentIndex(self.PAGE_HOME)

    def show_temperature_page(self) -> None:
        self.pages.setCurrentIndex(self.PAGE_TEMPERATURE)

    def show_thermal_page(self) -> None:
        self.pages.setCurrentIndex(self.PAGE_THERMAL)

    def show_pump_page(self) -> None:
        self.pages.setCurrentIndex(self.PAGE_PUMP)

    def show_timelapse_page(self) -> None:
        self.pages.setCurrentIndex(self.PAGE_TIMELAPSE)

    def show_neopixel_page(self) -> None:
        self.show_timelapse_page()

    def show_camera_page(self) -> None:
        self.pages.setCurrentIndex(self.PAGE_CAMERA)

    def _start_pid(self) -> None:
        self.controller.start_pid()
        if self.controller.state.connected:
            self.controller.start_live_updates()
        self._render()

    def _toggle_pid(self) -> None:
        if self.controller.state.mode == "PID":
            self.controller.stop_pid()
        else:
            self._start_pid()
            return
        self._render()

    def _stop(self) -> None:
        self.timelapse_service.stop()
        self._stop_live_video()
        self.controller.timelapse_neopixel_off()
        self.controller.stop()
        self._render()

    def _clear_error(self) -> None:
        self.controller.clear_error()
        self._render()

    def _refresh(self) -> None:
        self.controller.refresh_status()
        self._render()

    def _poll_serial(self) -> None:
        self.controller.poll_serial()
        self._render()

    def _nudge_target(self, delta: float) -> None:
        target = max(0.0, min(80.0, self.controller.state.target_c + delta))
        self.controller.set_target_from_ui(target)
        self._render()

    def _unsupported_action(self, action) -> None:
        action()
        self._render()

    def _set_neopixel_enabled(self, enabled: bool) -> None:
        self.controller.set_neopixel_enabled(enabled)
        self._render()

    def _set_neopixel_brightness(self, percent: int) -> None:
        self.controller.set_neopixel_brightness(percent)
        self._render()

    def _set_timelapse_brightness_value(self, percent: int, send_to_esp32: bool) -> None:
        percent = max(0, min(100, int(percent)))
        for widget in (
            getattr(self, "timelapse_brightness_spin", None),
            getattr(self, "test_brightness_spin", None),
        ):
            if widget is None or widget.value() == percent:
                continue
            blocked = widget.blockSignals(True)
            widget.setValue(percent)
            widget.blockSignals(blocked)
        if send_to_esp32:
            self.controller.set_neopixel_brightness(percent)
        self._render()

    def _nudge_numeric_field(self, spinbox: QSpinBox | QDoubleSpinBox, delta: float) -> None:
        value = spinbox.value() + delta
        if isinstance(spinbox, QDoubleSpinBox):
            value = round(value, spinbox.decimals())
        spinbox.setValue(value)

    def _timelapse_settings(self) -> TimelapseSettings:
        interval_multiplier = int(self.interval_unit.currentData())
        return TimelapseSettings(
            storage_mode=str(self.storage_combo.currentData()),
            interval_s=float(self.interval_spin.value() * interval_multiplier),
            brightness_percent=int(self.timelapse_brightness_spin.value()),
            light_duration_s=float(self.light_duration_spin.value()),
            total_duration_s=float(self.total_duration_spin.value() * 60),
            infinite=self.infinite_check.isChecked(),
        )

    def _toggle_infinite(self, checked: bool) -> None:
        self.total_duration_spin.setEnabled(not checked)
        self._render()

    def _refresh_timelapse_storage(self) -> None:
        self._render()

    def _set_timelapse_notice(self, message: str) -> None:
        self._timelapse_notice = message
        if message:
            self.controller.logs.append(message)

    def _start_timelapse_camera(self) -> bool:
        snap = self.timelapse_service.snapshot()
        if snap.live_running or self._camera_mode == "live":
            self._set_timelapse_notice("Stop live video before starting timelapse")
            return False
        if self._camera is not None:
            return self._camera_mode == "timelapse"
        if self._start_usb_camera("timelapse"):
            return True
        self._set_timelapse_notice("Camera unavailable; timelapse not started")
        return False

    def _start_timelapse(self) -> None:
        self._timelapse_notice = ""
        if not self._start_timelapse_camera():
            self._render()
            return
        started = self.timelapse_service.start(self._timelapse_settings())
        if not started and self._camera_mode == "timelapse":
            self._stop_camera("Timelapse camera stopped", "timelapse camera stopped")
        self._render()

    def _stop_timelapse(self) -> None:
        self.timelapse_service.stop()
        if self._camera_mode == "timelapse":
            self._stop_camera("Timelapse camera stopped", "timelapse camera stopped")
        self._timelapse_notice = ""
        self._render()

    def _test_capture(self) -> None:
        if self._camera_mode != "live" or not self.timelapse_service.snapshot().live_running:
            self._set_timelapse_notice("Start live video before test capture")
            self._render()
            return
        self._timelapse_notice = ""
        self.timelapse_service.test_capture(self._timelapse_settings())
        self._render()

    def _start_live_video(self) -> None:
        snap = self.timelapse_service.snapshot()
        if snap.running or self._camera_mode == "timelapse":
            if snap.running:
                self.timelapse_service.set_live_running(True)
            self._set_timelapse_notice("Stop timelapse before starting live video")
            self._render()
            return
        if self._camera is not None and self._camera_mode == "live":
            if self.timelapse_service.set_live_running(True):
                self._timelapse_notice = ""
            self._render()
            return
        if self._camera is not None:
            self._set_timelapse_notice("Camera already active")
            self._render()
            return
        if self._start_usb_camera("live"):
            if self.timelapse_service.set_live_running(True):
                self._timelapse_notice = ""
        else:
            self.timelapse_service.set_live_running(False)
            self._set_timelapse_notice("Camera unavailable; live video not started")
        self._render()

    def _stop_live_video(self) -> None:
        if self.timelapse_service.snapshot().running:
            self._set_timelapse_notice("Live video cannot be stopped while timelapse is running")
            self._render()
            return
        if self._camera_mode == "timelapse":
            self._stop_camera("Timelapse camera stopped", "timelapse camera stopped")
        elif self._camera_mode == "live":
            self._stop_camera("Live video stopped", "live video stopped")
        elif self._camera is not None:
            self._stop_camera("Live video stopped")
        self.timelapse_service.set_live_running(False)
        self._timelapse_notice = ""
        self._render()

    def _set_pump_target_rpm(self, rpm: float) -> None:
        self.controller.set_pump_target_rpm(rpm)
        self._render()

    def _nudge_pump_target(self, direction: int) -> None:
        current = float(self.controller.state.pump.target_rpm)
        fine_step = current < 10.0 or (direction < 0 and current <= 10.0)
        step = 0.1 if fine_step else 1.0
        self._set_pump_target_rpm(current + (step * direction))

    def _start_pump(self) -> None:
        self.controller.start_pump()
        self._render()

    def _stop_pump(self) -> None:
        self.controller.stop_pump()
        self._render()

    def _prime_pump(self) -> None:
        self.controller.prime_pump()
        self._render()

    def _render(self) -> None:
        state = self.controller.state
        status = derive_system_status(state)
        self._render_header(state, status)
        self._render_home(state)
        self._render_temperature(state)
        self._render_thermal(state)
        self._render_pump(state)
        self._render_timelapse()
        self._render_camera(state)
        self._render_plots(state)
        for button in (self.start_button, self.temperature_start_button):
            button.setEnabled(status not in {"DISCONNECTED", "ERROR"})
            button.setText("STOP PID" if state.mode == "PID" else "START")
        self.log_view.setPlainText("\n".join(self.controller.logs))
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def _render_header(self, state: AppState, status: str) -> None:
        port_status = "connected" if state.connected else "disconnected"
        for label in self._port_labels:
            label.setText(f"{state.port or '-'} {port_status}")
        for pill in self._status_pills:
            pill.setText(status)
            object_name = {
                "RUNNING": "statusPillRunning",
                "IDLE": "statusPillIdle",
                "ERROR": "statusPillError",
                "DISCONNECTED": "statusPillDisconnected",
            }[status]
            self._set_object_name(pill, object_name)

    def _render_home(self, state: AppState) -> None:
        self.home_temp_value.setText(_temp(state.temp_c))
        self.home_setpoint.setText(_temp(state.target_c))
        self.home_heater.setText(_percent(state.heater_output_percent))
        self.home_heater_bar.setValue(round(state.heater_output_percent))
        self._set_dot(self.home_thermo_dot, bool(state.sensor_valid))
        self.home_thermo_label.setText(f"Thermocouple {_flag(state.sensor_valid, 'OK', 'Invalid')}")
        self._set_dot(self.home_pump_dot, state.pump.running)
        self.home_pump_status.setText("Running" if state.pump.running else "Stopped")
        self.home_pump_rpm.setText(_rpm(state.pump.actual_rpm))
        self.bottom_status.setText(
            "Thermocouple {thermo}  |  Pump {pump}  |  Sensor {sensor}  |  "
            "Fault {fault}  |  GPIO14 {gpio}  |  Last error {error}".format(
                thermo=_flag(state.sensor_valid, "OK", "Invalid"),
                pump="running" if state.pump.running else "stopped",
                sensor=_flag(state.sensor_valid, "OK", "Invalid"),
                fault=_flag(not state.fault if state.fault is not None else None, "OK", "Fault"),
                gpio=_gpio(state.gpio14),
                error=_error_text(state.last_error),
            )
        )

    def _render_temperature(self, state: AppState) -> None:
        self.temperature_temp_value.setText(_temp(state.temp_c))
        self.temperature_target_value.setText(_temp(state.target_c))
        self.temperature_heater_value.setText(_percent(state.heater_output_percent))
        self._set_dot(self.temperature_thermo_dot, bool(state.sensor_valid))
        self.temperature_thermo_label.setText(f"Thermocouple {_flag(state.sensor_valid, 'OK', 'Invalid')}")

    def _render_thermal(self, state: AppState) -> None:
        self.thermal_temp_value.setText(_temp(state.temp_c))
        self.thermal_setpoint_value.setText(_temp(state.target_c))
        self.thermal_heater_value.setText(_percent(state.heater_output_percent))
        self.thermal_heater_bar.setValue(round(state.heater_output_percent))
        self.thermal_mode_small.setText("PID running" if state.mode == "PID" else state.mode)
        self.thermal_sensor.setText(_flag(state.sensor_valid, "OK", "Invalid"))
        self.thermal_fault.setText(_flag(not state.fault if state.fault is not None else None, "OK", "Fault"))
        self.thermal_gpio.setText(_gpio(state.gpio14))
        self.thermal_error.setText(_error_text(state.last_error))
        self._set_dot(self.thermal_thermo_dot, bool(state.sensor_valid))
        self.thermal_thermo_label.setText(f"Thermocouple {_flag(state.sensor_valid, 'OK', 'Invalid')}")
        self.pid_values.setText(
            "Kp      {kp}\n"
            "Ki      {ki}\n"
            "Kd      {kd}\n"
            "PID limit      {pid_limit}\n"
            "Power limit   {power_limit}\n"
            "Safety limit  {safety_limit}\n"
            "PID integral  {integral}\n"
            "Last error    {error}".format(
                kp=_number(state.kp if state.kp is not None else state.pid_kp, 2),
                ki=_number(state.ki if state.ki is not None else state.pid_ki, 3),
                kd=_number(state.kd if state.kd is not None else state.pid_kd, 2),
                pid_limit=_number(state.pid_limit, 1, " %"),
                power_limit=_number(state.power_limit, 1, " %"),
                safety_limit=_number(state.safety_limit, 2, " °C"),
                integral=_number(state.pid_integral, 3),
                error=_error_text(state.last_error),
            )
        )
        self.pid_value_labels["kp"].setText(_number(state.kp if state.kp is not None else state.pid_kp, 2))
        self.pid_value_labels["ki"].setText(_number(state.ki if state.ki is not None else state.pid_ki, 3))
        self.pid_value_labels["kd"].setText(_number(state.kd if state.kd is not None else state.pid_kd, 2))
        self.pid_value_labels["pid_limit"].setText(_number(state.pid_limit, 1, " %"))
        self.pid_value_labels["power_limit"].setText(_number(state.power_limit, 1, " %"))
        self.pid_value_labels["safety_limit"].setText(_number(state.safety_limit, 2, " Â°C"))
        self.pid_value_labels["integral"].setText(_number(state.pid_integral, 3))
        self.pid_value_labels["error"].setText(_error_text(state.last_error))

    def _render_pump(self, state: AppState) -> None:
        self._set_dot(self.pump_dot, state.pump.running)
        self.pump_status.setText("Running" if state.pump.running else "Stopped")
        self.pump_actual_rpm.setText(_rpm(state.pump.actual_rpm))
        self.pump_target_rpm.setText(_rpm(state.pump.target_rpm))
        self.pump_slider.blockSignals(True)
        self.pump_spin.blockSignals(True)
        self.pump_slider.setValue(round(state.pump.target_rpm))
        self.pump_spin.setValue(state.pump.target_rpm)
        self.pump_slider.blockSignals(False)
        self.pump_spin.blockSignals(False)
        self.pump_info.setText(
            "Status: {status}\n"
            "Actual speed: {actual} RPM\n"
            "Target speed: {target} RPM\n"
            "Direction: {direction}\n"
            "Full speed: {full_speed}\n"
            "Readback: {readback}\n"
            "Tubing: not configured\n"
            "Flow rate: future calibration".format(
                status="running" if state.pump.running else "stopped",
                actual=_rpm_value(state.pump.actual_rpm),
                target=_rpm_value(state.pump.target_rpm),
                direction=state.pump.direction,
                full_speed="yes" if state.pump.full_speed else "no",
                readback=_flag(state.pump.readback, "OK", "No response"),
            )
        )

    def _render_timelapse(self) -> None:
        settings = self._timelapse_settings()
        snap = self.timelapse_service.snapshot(settings)
        if self._camera_mode == "timelapse" and not snap.running and not snap.capture_in_progress:
            self._stop_camera("Timelapse camera stopped", "timelapse camera stopped")
            snap = self.timelapse_service.snapshot(settings)
        live_active = snap.live_running and self._camera_mode == "live"
        status = snap.status
        if snap.capture_in_progress:
            status = "capture in progress"
        elif live_active and not snap.running:
            status = "live video active"
        self._set_dot(self.home_timelapse_dot, snap.running or live_active)
        self.home_timelapse_status.setText("Running" if snap.running else ("Live" if live_active else "Stopped"))
        self.home_timelapse_count.setText(str(snap.frames_captured))
        self.timelapse_path.setText(f"Path: {snap.storage_path}")
        self.timelapse_status.setText(status.title())
        self.timelapse_frames.setText(str(snap.frames_captured))
        self.timelapse_free.setText(_bytes(snap.disk_free_bytes))
        if settings.infinite:
            estimate = "Infinite"
        else:
            estimate = f"{snap.estimated_frames} images, ~{_bytes(snap.estimated_bytes)}"
        self.timelapse_estimate.setText(estimate)
        self.timelapse_last_file.setText(f"Last file: {snap.last_file or '-'}")
        if settings.storage_mode == "external" and not snap.external_available:
            message = "External disk absent or not writable"
        else:
            message = self._timelapse_notice or snap.error
        self.timelapse_error.setText(message)

        controls_enabled = not snap.running
        for widget in (
            self.storage_combo,
            self.interval_spin,
            self.interval_unit,
            self.interval_minus_button,
            self.interval_plus_button,
            self.timelapse_brightness_spin,
            self.timelapse_brightness_minus_button,
            self.timelapse_brightness_plus_button,
            self.light_duration_spin,
            self.light_duration_minus_button,
            self.light_duration_plus_button,
            self.total_duration_spin,
            self.infinite_check,
        ):
            widget.setEnabled(controls_enabled)
        for widget in (
            self.total_duration_spin,
            self.total_duration_minus_button,
            self.total_duration_plus_button,
        ):
            widget.setEnabled(controls_enabled and not settings.infinite)

        self.start_timelapse_button.setEnabled(controls_enabled and not live_active)
        self.stop_timelapse_button.setEnabled(snap.running or snap.capture_in_progress)
        self.start_live_button.setEnabled(not live_active and not snap.running and self._camera_mode != "timelapse")
        self.stop_live_button.setEnabled(live_active)
        self.test_capture_button.setEnabled(live_active and not snap.running and not snap.capture_in_progress)
        for widget in (
            self.test_neopixel_on_button,
            self.test_neopixel_off_button,
            self.test_brightness_spin,
            self.test_brightness_minus_button,
            self.test_brightness_plus_button,
        ):
            widget.setEnabled(not snap.running)
        self.test_neopixel_status.setText(
            "NeoPixel ON" if self.controller.state.neopixel.enabled else "NeoPixel OFF"
        )

    def _render_camera(self, state: AppState) -> None:
        self._paint_camera_image()

    def _render_plots(self, state: AppState) -> None:
        history = list(state.temp_history)
        if not history and state.temp_c is not None:
            history = [(state.time_ms or 0, state.temp_c)]
        if history:
            first = history[0][0]
            xs = [(time_ms - first) / 1000 for time_ms, _ in history]
            ys = [temp for _, temp in history]
            y_values = ys + [state.target_c]
            low = min(y_values) - 1.0
            high = max(y_values) + 1.0
        else:
            xs, ys = [], []
            low, high = state.target_c - 5, state.target_c + 5
        for curve in self._plot_curves:
            curve.setData(xs, ys)
        for target in self._target_lines:
            target.setValue(state.target_c)
        for plot in (self.home_temp_plot, self.temperature_plot, self.thermal_plot):
            plot.setYRange(low, high, padding=0)
            if xs:
                plot.setXRange(max(0, xs[-1] - 300), max(10, xs[-1]), padding=0)
        if ys:
            home_low = min(ys)
            home_high = max(ys)
            if home_high - home_low < 1.0:
                middle = (home_low + home_high) / 2
                home_low, home_high = middle - 0.5, middle + 0.5
            else:
                home_low -= 0.25
                home_high += 0.25
            self.home_temp_plot.setYRange(home_low, home_high, padding=0)

    def _set_dot(self, dot: QFrame, ok: bool) -> None:
        self._set_object_name(dot, "statusDotOk" if ok else "statusDotError")

    def _set_object_name(self, widget: QWidget, object_name: str) -> None:
        if widget.objectName() == object_name:
            return
        widget.setObjectName(object_name)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def closeEvent(self, event) -> None:
        self.timelapse_service.stop()
        self._stop_live_video()
        self.controller.timelapse_neopixel_off()
        self.controller.shutdown()
        super().closeEvent(event)


def _temp(value: float | None) -> str:
    return "--.- °C" if value is None else f"{value:.2f} °C"


def _rpm_value(value: float) -> str:
    return f"{round(float(value), 1):g}"


def _rpm(value: float) -> str:
    return f"{_rpm_value(value)} RPM"


def _percent(value: float | None) -> str:
    return "--.- %" if value is None else f"{value:.1f} %"


def _number(value: float | None, decimals: int, suffix: str = "") -> str:
    if value is None:
        return f"--{suffix}"
    return f"{value:.{decimals}f}{suffix}"


def _flag(value: bool | None, true_text: str, false_text: str) -> str:
    if value is None:
        return "Unknown"
    return true_text if value else false_text


def _error_text(value: str) -> str:
    if not value or value.upper() == "NONE":
        return "None"
    return value


def _gpio(value: str | bool | None) -> str:
    if value is None:
        return "Unknown"
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return value


def _bytes(value: int) -> str:
    if value <= 0:
        return "--"
    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(value)
    index = 0
    while amount >= 1024 and index < len(units) - 1:
        amount /= 1024
        index += 1
    return f"{amount:.1f} {units[index]}"
