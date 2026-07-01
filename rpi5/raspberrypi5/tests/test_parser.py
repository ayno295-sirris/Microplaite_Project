from microplaite_ui.esp32.parser import parse_line


def test_parse_status_fields() -> None:
    msg = parse_line(
        "OK STATUS temp=24.5 target=37.5 mode=PID sensor_valid=1 "
        "fault=0 gpio14=1 heater_output=12.3 safety_limit=38 "
        "kp=1 ki=0.03 kd=20 pid_limit=15 pid_integral=0.125"
    )

    assert msg.ok is True
    assert msg.fields["temp_c"] == 24.5
    assert msg.fields["target_c"] == 37.5
    assert msg.fields["mode"] == "PID"
    assert msg.fields["sensor_valid"] is True
    assert msg.fields["fault"] is False
    assert msg.fields["gpio14"] == "1"
    assert msg.fields["heater_output_percent"] == 12.3
    assert msg.fields["safety_limit"] == 38.0
    assert msg.fields["kp"] == 1.0
    assert msg.fields["ki"] == 0.03
    assert msg.fields["kd"] == 20.0
    assert msg.fields["pid_limit"] == 15.0
    assert msg.fields["pid_integral"] == 0.125


def test_parse_real_esp32_status_line() -> None:
    msg = parse_line(
        "OK STATUS TEMP 24.46C SENSOR_VALID 1 FAULT 0 GPIO14 OFF MODE PID "
        "TARGET 37.50C HYSTERESIS 0.25C HEATER_OUTPUT 15.0% "
        "SAFETY_LIMIT 38.00C POWER_LIMIT 30.0% PID 8.00 0.030 20.00 "
        "PID_LIMIT 15.0% PID_INTEGRAL 0.000 LAST_ERROR NONE "
        "TIMEOUT_REMAINING 0S"
    )

    assert msg.ok is True
    assert msg.fields["temp_c"] == 24.46
    assert msg.fields["target_c"] == 37.50
    assert msg.fields["mode"] == "PID"
    assert msg.fields["sensor_valid"] is True
    assert msg.fields["fault"] is False
    assert msg.fields["gpio14"] == "OFF"
    assert msg.fields["heater_output_percent"] == 15.0
    assert msg.fields["safety_limit"] == 38.00
    assert msg.fields["power_limit"] == 30.0
    assert msg.fields["pid_kp"] == 8.0
    assert msg.fields["pid_ki"] == 0.03
    assert msg.fields["pid_kd"] == 20.0
    assert msg.fields["pid_limit"] == 15.0
    assert msg.fields["pid_integral"] == 0.0
    assert msg.fields["last_error"] == "NONE"
    assert msg.fields["timeout_remaining_s"] == 0


def test_parse_log_line() -> None:
    msg = parse_line(
        "LOG TEMP 24.80C SENSOR_VALID 1 FAULT 0 GPIO14 ON MODE PID "
        "TARGET 37.50C HEATER_OUTPUT 12.0% LAST_ERROR NONE"
    )

    assert msg.is_log is True
    assert msg.fields["temp_c"] == 24.80
    assert msg.fields["mode"] == "PID"
    assert msg.fields["sensor_valid"] is True
    assert msg.fields["fault"] is False
    assert msg.fields["gpio14"] == "ON"
    assert msg.fields["heater_output_percent"] == 12.0
    assert msg.fields["last_error"] == "NONE"


def test_parse_csv_log_line() -> None:
    msg = parse_line("LOG,799678,34.70,37.50,15.0,ON,PID,1,0")

    assert msg.is_log is True
    assert msg.fields["time_ms"] == 799678
    assert msg.fields["temp_c"] == 34.70
    assert msg.fields["target_c"] == 37.50
    assert msg.fields["heater_output_percent"] == 15.0
    assert msg.fields["gpio14"] == "ON"
    assert msg.fields["mode"] == "PID"
    assert msg.fields["sensor_valid"] is True
    assert msg.fields["fault"] is False


def test_parse_error_without_crash() -> None:
    msg = parse_line("ERR SENSOR_DISCONNECTED")

    assert msg.ok is False
    assert msg.error == "SENSOR_DISCONNECTED"


def test_parse_pump_status_fields() -> None:
    msg = parse_line("OK PUMP_STATUS PUMP_RUNNING 1 PUMP_RPM 10.5 PUMP_FULL_SPEED 0 PUMP_READBACK 0")

    assert msg.ok is True
    assert msg.fields["pump_running"] is True
    assert msg.fields["pump_rpm"] == 10.5
    assert msg.fields["pump_full_speed"] is False
    assert msg.fields["pump_readback"] is False


def test_parse_neopixel_status_fields() -> None:
    msg = parse_line("OK NEOPIXEL_STATUS NEOPIXEL_ENABLED 1 NEOPIXEL_BRIGHTNESS 35")

    assert msg.ok is True
    assert msg.fields["neopixel_enabled"] is True
    assert msg.fields["neopixel_brightness_percent"] == 35
