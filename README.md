# Microplaite Project

Global repository for the microfluidic test bench.

## Working layout

Target workspace layout:

- Window 1, local VS Code: `Microplate_Project/`
- Window 2, local VS Code: `Microplate_Project/esp32_platformio/`
- Window 3, VS Code Remote SSH: `/home/pi/Microplate_Project/raspberrypi5/`

Repository content:

- `raspberrypi5/`: Raspberry Pi 5 code and system docs
- `esp32_platformio/`: ESP32-S3 PlatformIO firmware

Note:

- the GitHub repository name is still `Microplaite_Project`
- if you keep that spelling on disk, adapt only the root folder name in your local paths

## Synchronization strategy

Official synchronization:

- Git = official synchronization and history
- Remote SSH = live development on the Raspberry Pi
- rsync = fast one-way deployment when needed

Recommended rule:

- avoid two divergent versions of `raspberrypi5/`
- if you modify on the Pi, commit on the Pi
- if you modify on the PC, pull on the Pi before testing
