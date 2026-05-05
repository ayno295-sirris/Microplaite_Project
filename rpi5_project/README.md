# RPI5 Project

`rpi5_project` is the Raspberry Pi 5 supervisor subproject for the microplaite bench.

Current milestone:

- `M1`, Raspberry Pi 5 bring-up and remote development

Current code scope:

- minimal Python configuration
- file and console logging
- no hardware access yet
- no GUI yet

Launch command:

- `python -m app.main`

Relationship to the firmware:

- the ESP32-S3 firmware lives in the sibling directory `../esp32_project`
- all firmware work is done with PlatformIO in that directory

Development flow:

- open `rpi5_project/` from VS Code through Remote SSH on the Raspberry Pi 5
- keep the Raspberry Pi code minimal until the milestone requires more layers
