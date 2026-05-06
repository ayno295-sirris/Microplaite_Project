# Hardware

## Raspberry Pi with screen
- Raspberry Pi 5 hostname during bring-up: `sirrispi`.
- Wi-Fi is active and SSH works from the development PC.
- Current project path on the Pi: `/home/nayo/Microplate_Project/raspberrypi5`.

## ESP32 embedded controller
- ESP32-S3 dev board is connected to the Raspberry Pi 5 over USB.
- USB bridge detected on the Pi as Silicon Labs CP2102N.
- Current serial device on the Pi: `/dev/ttyUSB0`.
- Linux driver: `cp210x`.
- User `nayo` belongs to the `dialout` group and can access the serial port without `sudo`.
- Current firmware heartbeat is readable from the Pi with `pyserial` miniterm at `115200` baud.

Temporary M4 communication link:
- Raspberry Pi 5 -> USB cable -> CP2102N bridge -> ESP32-S3 UART.
- This is the official development link until the project explicitly needs another wiring path.
- Do not wire Raspberry Pi GPIO UART to the ESP32 while USB serial is being used for bring-up.

## Thermocouple K
- Not wired yet.

## MOSFET DFR0457
- Not wired yet.

## Longer T100/WX10 RS485 pump
- Not wired yet.

## RS485 transceiver
- Not wired yet.

## NeoPixel
- Not wired yet.

## Raspberry Pi HQ Camera / Arducam
- Not wired yet.

## Power supply
- Raspberry Pi 5 is powered separately.
- ESP32-S3 is currently powered over USB from the Raspberry Pi 5 during bring-up.
- DIN rail power distribution is not finalized yet.

## Open questions
- Final DIN rail power architecture.
- Whether ESP32 remains USB-powered during early heater bring-up or gets its own regulated rail.
- Cable retention and strain relief for the USB link inside the bench.
