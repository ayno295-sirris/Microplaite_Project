"""Source wiring checks only: no firmware build, serial port or hardware access.

Run with Python; the existing test_supervision Unity suite covers runtime state
transitions separately. These checks do not establish physical actuator states.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def source(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)


def body(text, signature):
    start = text.index("{", text.index(signature))
    depth = 1
    for end in range(start + 1, len(text)):
        depth += (text[end] == "{") - (text[end] == "}")
        if depth == 0:
            return text[start + 1:end]
    raise AssertionError("Unclosed function: " + signature)


class BootContract(unittest.TestCase):
    def setUp(self):
        self.app = source("src/app/App.cpp")
        self.boot = body(self.app, "void App::begin()")
        self.state = source("src/app/AppState.h")
        self.supervision = source("src/services/SupervisionService.cpp")

    def test_heater_off_before_any_other_initialization(self):
        self.assertTrue(self.boot.lstrip().startswith("_heater.begin();"))
        heater = body(source("src/services/HeaterService.cpp"), "void HeaterService::begin()")
        for reset in ("outputOff();", "_mode = Mode::Idle;", "_manualTestEndMs = 0;"):
            self.assertIn(reset, heater)

    def test_pump_stop_once_after_uart_init_before_command_service(self):
        self.assertEqual(1, self.boot.count("_pump.stop(_state);"))
        stop = self.boot.index("_pump.stop(_state);")
        self.assertLess(self.boot.index("_heater.begin();"), stop)
        self.assertLess(self.boot.index("_pump.begin();"), stop)
        self.assertLess(stop, self.boot.index("_serialCommands.begin(Serial);"))
        self.assertLess(stop, self.boot.index("_supervision.begin("))
        self.assertNotRegex(self.boot, r"\b(?:while|for)\s*\(")

    def test_neopixel_boot_clears_pixels_and_brightness(self):
        self.assertIn("bool neopixelEnabled = false;", self.state)
        self.assertIn("uint8_t neopixelBrightnessPercent = 0;", self.state)
        pixels = body(self.app, "void App::beginNeoPixel()")
        self.assertIn("_neopixel.setBrightness(0);", pixels)
        self.assertLess(pixels.index("_neopixel.clear();"), pixels.index("_neopixel.show();"))
        self.assertNotIn(".fill(", pixels)

    def test_no_session_or_auto_activation_at_boot(self):
        begin = body(self.supervision, "void SupervisionService::begin(")
        self.assertIn("_state.commState = CommState::NO_SESSION;", begin)
        self.assertIn("refreshState();", begin)
        self.assertIn("bool pumpReadbackValid = false;", self.state)
        for text in (self.boot, begin):
            self.assertNotRegex(text, r"\.(?:start|prime|enable|enablePid|startManualTest|sync)\s*\(")
        refresh = body(self.supervision, "void SupervisionService::refreshState()")
        self.assertIn("sessionActive() ? SystemState::READY : SystemState::IDLE", refresh)

    def test_neopixel_v2_activation_requires_session_before_state_change(self):
        command = body(source("src/comm/CommandDispatcher.cpp"), 'if (strcmp(cmd, "NEOPIXEL_SET") == 0)')
        self.assertIn("if (!error && enabled) error = _supervision.activationError(millis());", command)
        self.assertLess(command.index("activationError("), command.index("if (error)"))
        self.assertLess(command.index("if (error)"), command.index("_state.neopixelEnabled = enabled;"))

    def test_existing_heartbeat_timeout_and_heater_first_stop_wiring(self):
        header = source("src/services/SupervisionService.h")
        self.assertIn("HEARTBEAT_TIMEOUT_MS = 3000;", header)
        update = body(self.supervision, "void SupervisionService::update(")
        self.assertIn("sessionActive() && heartbeatAgeMs(now) > HEARTBEAT_TIMEOUT_MS", update)
        self.assertLess(update.index("CommState::LOST"), update.index("if (actuatorsActive()) stop();"))
        stop = body(self.supervision, "bool SupervisionService::stop()")
        self.assertLess(stop.index("_heater.stop();"), stop.index("_pump.stop(_state);"))
        heartbeat = body(self.supervision, "const char* SupervisionService::heartbeat(")
        self.assertLess(heartbeat.index('if (!sessionActive()) return "NO_SESSION";'),
                        heartbeat.index("_lastHeartbeatMs = now;"))


if __name__ == "__main__":
    unittest.main()
