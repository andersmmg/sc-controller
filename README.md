# SC Controller

An updated and maintained fork of [kozec/sc-controller](https://github.com/kozec/sc-controller); a user-mode driver and GTK3 based GUI for Steam Controller and other devices

[![screenshot1](docs/screenshot1-tn.png?raw=true)](docs/screenshot1.png?raw=true)
[![screenshot2](docs/screenshot2-tn.png?raw=true)](docs/screenshot2.png?raw=true)
[![screenshot3](docs/screenshot3-tn.png?raw=true)](docs/screenshot3.png?raw=true)
[![screenshot3](docs/screenshot4-tn.png?raw=true)](docs/screenshot4.png?raw=true)

## Features
- Allows to setup, configure and use Steam Controller(s) without ever launching Steam
- Supports profiles switchable in GUI or with controller button
- Stick, Pads and Gyroscope input
- Haptic Feedback and in-game Rumble support
- OSD, Menus, On-Screen Keyboard for desktop *and* in games.
- Automatic profile switching based on active window.
- Macros, button cycling, rapid fire, modeshift, mouse regions...
- Emulates Xbox360 controller, mouse, trackball and keyboard.

Based on [Standalone Steam Controller Driver](https://github.com/ynsta/steamcontroller) by [Ynsta](https://github.com/ynsta).

## Like what I'm doing?

Contributions are welcome! Whether it's code, bug reports, or feature suggestions, your input is appreciated. Feel free to open an issue or submit a pull request.

I will consider allowing donations in the future depending on my available free time.

## Packages

Packaging is not yet ready, AUR is planned first.


## Building the package by yourself

### Dependencies
  - python 2.7, GTK 3.22 or newer and [PyGObject](https://live.gnome.org/PyGObject)
  - [python-gi-cairo](https://packages.debian.org/sid/python-gi-cairo) and [gir1.2-rsvg-2.0](https://packages.debian.org/sid/gir1.2-rsvg-2.0) on debian based distros (included in PyGObject elsewhere)
  - [setuptools](https://pypi.python.org/pypi/setuptools)
  - [python-pylibacl](http://pylibacl.k1024.org/) is recommended
  - [python-evdev](https://python-evdev.readthedocs.io/en/latest/) is strongly recommended

### Installing
  - Download and extract  [latest release](https://github.com/kozec/sc-controller/releases/latest)
  - `python2 setup.py build`
  - `python2 setup.py install`


## Running with non distro-specific package          
  - Download and extract [latest release](https://github.com/kozec/sc-controller/releases/latest)
  - Navigate to extracted directory and execute `./run.sh`
