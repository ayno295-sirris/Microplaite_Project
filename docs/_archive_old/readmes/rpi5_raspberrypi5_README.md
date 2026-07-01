# Raspberry Pi 5 Project

`rpi5/raspberrypi5/` contains the Raspberry Pi 5 supervisor code.

Current milestone:

- `M1`, Raspberry Pi 5 bring-up and remote development

Current code scope:

- minimal Python configuration
- file and console logging
- no hardware access yet
- no GUI yet

Run command from this directory:

```bash
python src/main.py
```

Run tests from this directory:

```bash
python -m pytest
```

## Development workflow

Primary workflow:

1. Edit architecture, shared docs, and firmware locally in the global repository.
2. Edit and debug Raspberry Pi runtime code through VS Code Remote SSH.
3. Use Git as the official synchronization method.

Typical loop on PC:

```bash
git add .
git commit -m "Update raspberry control logic"
git push
```

Typical loop on Raspberry Pi:

```bash
cd ~/Microplate_Project
git pull
cd ~/Microplate_Project/rpi5/raspberrypi5
python src/main.py
```

If you fix something directly on the Pi:

```bash
git add .
git commit -m "Fix runtime issue on Raspberry Pi"
git push
```

Then on the PC:

```bash
git pull
```

## rsync usage

Use `rsync` only for fast one-way deployment when you explicitly want to skip a commit.

Example from the PC:

```bash
rsync -av --delete \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude ".git" \
  rpi5/raspberrypi5/ pi@raspberrypi.local:/home/pi/Microplate_Project/rpi5/raspberrypi5/
```

Then run remotely:

```bash
ssh pi@raspberrypi.local "cd /home/pi/Microplate_Project/rpi5/raspberrypi5 && python src/main.py"
```

Do not use `rsync` as the main workflow if you also modify files directly on the Pi.
