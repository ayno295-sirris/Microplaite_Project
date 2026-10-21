"""Rendered checkbox dimensions and touch layout at the production resolution."""

import pytest
from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QWidget,
)

from microplaite_ui.core.controller import AppController
from microplaite_ui.esp32.fake_client import FakeEsp32Client
from microplaite_ui.ui import styles
from microplaite_ui.ui.main_window import MainWindow


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    view = MainWindow(AppController(FakeEsp32Client()))
    view.timer.stop()
    view.show()
    app.processEvents()
    yield view
    view.close()
    app.processEvents()


@pytest.mark.parametrize("attribute", [
    "camera_keep_neopixel_on_check",
    "test_keep_neopixel_on_check",
    "camera_record_video_check",
    "test_record_video_check",
    "infinite_check",
])
@pytest.mark.parametrize("enabled,checked", [(True, False), (True, True), (False, True)])
def test_all_checkbox_indicators_use_the_global_touch_size(window, attribute, enabled, checked):
    checkbox = getattr(window, attribute)
    checkbox.setEnabled(enabled)
    checkbox.blockSignals(True)
    checkbox.setChecked(checked)
    checkbox.blockSignals(False)
    option = QStyleOptionButton()
    checkbox.initStyleOption(option)

    indicator = checkbox.style().subElementRect(QStyle.SE_CheckBoxIndicator, option, checkbox)

    assert indicator.width() == indicator.height() == 28
    assert indicator.width() == styles.CHECKBOX_INDICATOR_SIZE_PX
    assert checkbox.minimumSizeHint().height() >= 36
    assert checkbox.isChecked() is checked


@pytest.mark.parametrize("page,tab", [("camera", None), ("timelapse", 0), ("timelapse", 1)])
def test_camera_and_timelapse_touch_controls_fit_without_overlap(window, page, tab):
    if page == "camera":
        window.show_camera_page()
    else:
        window.show_timelapse_page()
        window._show_timelapse_tab(tab)
    QApplication.processEvents()
    assert (window.width(), window.height()) == (1280, 720)
    controls = [
        widget
        for widget in window.findChildren(QWidget)
        if isinstance(widget, (QCheckBox, QPushButton, QComboBox, QAbstractSpinBox))
        and widget.isVisibleTo(window)
    ]
    rectangles = []
    for widget in controls:
        rect = QRect(widget.mapTo(window, QPoint()), widget.size())
        assert window.rect().contains(rect), (widget, rect)
        parent = widget.parentWidget()
        while parent is not window:
            parent_rect = QRect(parent.mapTo(window, QPoint()), parent.size())
            assert parent_rect.contains(rect), (widget, parent, rect, parent_rect)
            parent = parent.parentWidget()
        for previous, previous_rect in rectangles:
            assert not rect.intersects(previous_rect), (widget, previous, rect, previous_rect)
        rectangles.append((widget, rect))


def test_global_style_keeps_checkbox_touch_toggle_and_disabled_behavior():
    app = QApplication.instance() or QApplication([])
    checkbox = QCheckBox("Touch option")
    checkbox.setStyleSheet(styles.QSS)
    checkbox.show()
    app.processEvents()
    option = QStyleOptionButton()
    checkbox.initStyleOption(option)
    indicator = checkbox.style().subElementRect(QStyle.SE_CheckBoxIndicator, option, checkbox)

    _click(checkbox, indicator.center())
    assert checkbox.isChecked() is True
    _click(checkbox, indicator.center())
    assert checkbox.isChecked() is False
    checkbox.setEnabled(False)
    _click(checkbox, indicator.center())
    assert checkbox.isChecked() is False
    checkbox.close()


def _click(widget, position):
    for event_type, buttons in (
        (QEvent.MouseButtonPress, Qt.LeftButton),
        (QEvent.MouseButtonRelease, Qt.NoButton),
    ):
        event = QMouseEvent(
            event_type, position, widget.mapToGlobal(position), Qt.LeftButton,
            buttons, Qt.NoModifier,
        )
        QApplication.sendEvent(widget, event)
