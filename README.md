# Schedule I img-to-graffiti

Convert any image into in-game graffiti for Schedule I using mouse automation.

## Features

- 8 colors (black, white, red, green, blue, yellow, magenta, brown)
- 4 brush sizes with adaptive 3-pass drawing (fill → edge → detail)
- Resizable drawing area with contain/stretch fit modes
- Real-time resolution preview with slider
- Interactive calibration popup (CTRL+S to capture, CTRL+Z to undo)
- Global cancel with Ctrl+Shift+X
- Settings auto-saved to `config.json`

## Requirements

Python 3.8+, then:

```
pip install -r requirements.txt
```

## Usage

```
python graffiti_drawer.py
```

1. **Load** your image (PNG, JPG, JPEG)
2. **Calibrate** — click through the popup to capture color buttons, brush sizes, and draw area
3. **Tune** resolution, thickness, fit mode
4. **Draw** — countdown gives you time to focus the game window
