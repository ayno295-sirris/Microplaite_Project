# Legacy Pump GUI Features

- Serial port selection: editable serial port used for the USB-RS485 adapter.
- Connection status: displayed pump state as stopped, running, or error.
- Tubing selection: selectable tubing profile from the configured tube list.
- uL/rev calibration: editable calibration value for the selected tubing.
- Save/reset calibration: saved the current tubing calibration or restored its default value.
- Flow-to-RPM mode: computed RPM from the requested flow and selected tubing calibration.
- RPM-to-flow mode: computed flow from the requested RPM and selected tubing calibration.
- Flow setpoint: editable target flow in uL/min.
- RPM setpoint: editable target pump speed in RPM.
- Full-speed mode: optional full-speed operation flag for pump commands.
- Start: started the pump with the current RPM/full-speed settings.
- Stop: stopped the pump immediately.
- Run 5 seconds: ran the pump for 5 seconds in a background worker, then stopped it.
- Logs: displayed timestamped GUI actions, calibration changes, starts, stops, and errors.
- Safe stop on GUI close: attempted to stop the pump when the window closed.
