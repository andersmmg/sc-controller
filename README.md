# SC Controller

An updated and maintained fork of [kozec/sc-controller](https://github.com/kozec/sc-controller); a user-mode driver and GTK3 based GUI for the Steam Controller, Steam Controller 2 (2026) and other devices.

This fork has been ported to **Python 3**, adds support for the **2026 Steam Controller (codename "Triton")** (wired, dongle, and Bluetooth), and includes improved dark-mode visuals, joystick circularity normalization, better generic gamepad support, and assorted fixes. More to come!

[![screenshot1](docs/screenshot1-tn.png?raw=true)](docs/screenshot1.png?raw=true)
[![screenshot2](docs/screenshot2-tn.png?raw=true)](docs/screenshot2.png?raw=true)
[![screenshot3](docs/screenshot3-tn.png?raw=true)](docs/screenshot3.png?raw=true)
[![screenshot3](docs/screenshot4-tn.png?raw=true)](docs/screenshot4.png?raw=true)

## Features

- Native support for the 2026 Steam Controller (codename "Triton"), including dual sticks, separate dpad, grip sensing, and LED brightness control
- Ported to Python 3
- Much better dark mode support with SVG inversion
- Joystick output circularity normalization
- Better support for generic gamepads
- Lots of bug fixes

### Features from upstream

- Allows to setup, configure and use Steam Controller(s) without ever launching Steam
- Supports profiles switchable in GUI or with controller button
- Stick, Pads and Gyroscope input
- Haptic Feedback and in-game Rumble support
- OSD, Menus, On-Screen Keyboard for desktop *and* in games.
- Automatic profile switching based on active window.
- Macros, button cycling, rapid fire, modeshift, mouse regions...
- Emulates Xbox360 controller, mouse, trackball and keyboard.

Based on [Standalone Steam Controller Driver](https://github.com/ynsta/steamcontroller) by [Ynsta](https://github.com/ynsta).

## References

The SC2 ("Triton") driver (`scc/drivers/tritondrv.py`) is implemented using the following as references:

- [SDL3's official Triton driver](https://github.com/libsdl-org/SDL/blob/main/src/joystick/hidapi/SDL_hidapi_steam_triton.c) — Valve's own HID protocol implementation and report structures (`controller_structs.h`, `controller_constants.h`)
- [sc2-research](https://github.com/CouchTurtle/sc2-research) — community reverse-engineered documentation of the Triton protocol, settings registry and firmware

## Future plans

See [TODO.md](TODO.md) for the current maintenance and feature list.


## Contributing

Contributions are welcome! For how to set up a development environment, run the test suite, and get patches ready for review, see [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and feature requests go to the GitHub issue tracker.

## Packages

There are no official distro packages for this fork yet; install or run from source (see below).

## Building the package

### Prerequisites
  - Python 3.10 or newer, GTK 3.22 or newer and [PyGObject](https://live.gnome.org/PyGObject)
  - [python-gi-cairo](https://packages.debian.org/sid/python-gi-cairo) and [gir1.2-rsvg-2.0](https://packages.debian.org/sid/gir1.2-rsvg-2.0) on debian-based distros (included in PyGObject elsewhere)
  - [setuptools](https://pypi.org/project/setuptools/) and [packaging](https://pypi.org/project/packaging/)
  - A C toolchain (gcc, make, etc.) for the bundled C extensions
  - [python-pylibacl](http://pylibacl.k1024.org/) is recommended
  - [python-evdev](https://python-evdev.readthedocs.io/en/latest/) is strongly recommended

### Installing from source
  - Clone this repository or download the [latest release](https://github.com/andersmmg/sc-controller/releases/latest)
  - `pip install --no-build-isolation .` (or `python3 -m pip install --no-build-isolation .`)

### Running from a source checkout
  - Clone this repository
  - `./run.sh`

### Running the daemon only
  - `./daemon.sh` (foreground) or `./daemon.sh debug` (with debug logging)

### Development setup, lint and tests

The project uses [uv](https://docs.astral.sh/uv/) to manage the dev toolchain and [ruff](https://docs.astral.sh/ruff/) for linting/formatting. Type checking is handled by [ty](https://docs.astral.sh/ty/).

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run ty check
python3 -m pytest tests/ -q
```

Build and check instructions are also captured in `.github/workflows/tests.yml`.

### Packaging

An AppImage build script (`appimage-build.sh`) is provided.
