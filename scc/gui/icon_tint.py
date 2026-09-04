"""
Controller icon tinting.

Controller icons are grayscale SVGs and the color
is applied at render time by keeping the lightness of every gray and
applying the target color's hue and saturation.

Per-controller color is stored in scc config as "icon_color" (#rrggbb).
"""

from __future__ import unicode_literals

import colorsys
import logging
import os
import re

from scc.paths import get_controller_icons_path, get_default_controller_icons_path
from scc.tools import _

log = logging.getLogger("IconTint")

PRESET_COLORS = (
    "#00ff00",  # green
    "#ff0000",  # red
    "#0000ff",  # blue
    "#ffff00",  # yellow
    "#ff00ff",  # magenta
    "#00ffff",  # cyan
    "#ff8000",  # orange
    "#8000ff",  # purple
)

DEFAULT_COLOR = PRESET_COLORS[0]

SHAPE_NAMES = {
    "sc": _("Steam Controller"),
    "scbt": _("Steam Controller (Bluetooth)"),
    "sc2": _("Steam Controller 2026"),
    "deck": _("Steam Deck"),
    "ds4": _("DualShock 4"),
    "hid": _("Generic Gamepad"),
    "fake": _("Generic Outline"),
    "rpad": _("Remote Pad"),
    "unknown": _("Unknown"),
}


def shape_name(controller_type):
    """Returns display name for icon shape, falling back to type name"""
    return SHAPE_NAMES.get(controller_type, controller_type)


def _parse_hex(color):
    """'#rrggbb' -> (r, g, b) floats, or None on parse error"""
    h = color.strip("#")
    if len(h) == 3:
        h = "".join(x * 2 for x in h)
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None


def tint_gray(gray_hex, color):
    """
    Maps a grayscale fill ('#rrggbb' with r == g == b) to a shade of color.

    Colored accents should be untouched.
    """
    rgb = _parse_hex(gray_hex)
    crgb = _parse_hex(color)
    if rgb is None:
        return gray_hex
    if crgb is None:
        log.warning("Failed to parse tint color '%s', leaving gray", color)
        return gray_hex
    ih, il, isat = colorsys.rgb_to_hls(*rgb)
    if isat > 0.02:
        return gray_hex
    h, _, s = colorsys.rgb_to_hls(*crgb)
    if s == 0.0:
        return gray_hex
    l = rgb[0]
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


_COLOR_PREFIX_RE = r'((?:fill|stroke|stop-color)\s*[:=]\s*["\']?)#([0-9a-fA-F]{6})'


def tint_svg(svg_text, color):
    """
    Applies tint to every gray color in SVG text.
    Returns (new_text, {original_gray: tinted_color}).
    """
    import re

    mapping = {}

    def repl(m):
        prefix, hexdigits = m.group(1), m.group(2)
        if hexdigits not in mapping:
            mapping[hexdigits] = tint_gray("#" + hexdigits, color)[1:]
        return "%s#%s" % (prefix, mapping[hexdigits])

    return re.sub(_COLOR_PREFIX_RE, repl, svg_text), mapping


def find_base_icon(controller_type, imagepath=None):
    """
    Returns filename of tintable base icon for given controller type,
    or None if there is none.

    Searches user icons dir first, then built-in images dir, mirroring
    old find_controller_icon()
    """
    name = "%s.svg" % (controller_type,)
    for p in (get_controller_icons_path(), get_default_controller_icons_path()):
        path = os.path.join(p, name)
        if os.path.exists(path):
            return path
    if imagepath:
        path = os.path.join(imagepath, "controller-icons", name)
        if os.path.exists(path):
            return path
    return None


def get_icon_color(config, controller_id):
    """Returns configured icon color for controller, or default"""
    cfg = config.get_controller_config(controller_id)
    return cfg.get("icon_color") or DEFAULT_COLOR


def get_icon_shape(config, controller_id, controller_type):
    """
    Returns controller type whose icon shape should be displayed,
    honoring optional per-controller 'icon_shape' override.
    """
    cfg = config.get_controller_config(controller_id)
    return cfg.get("icon_shape") or controller_type


def available_shapes(imagepath=None):
    """
    Returns sorted list of controller type names that have a tintable
    base icon and can be used as icon shape override.
    Symlinked aliases are skipped
    """
    pattern = re.compile(r"([a-z0-9]+)\.svg$", re.IGNORECASE)
    types = set()
    for d in (
        get_controller_icons_path(),
        get_default_controller_icons_path(),
        os.path.join(imagepath, "controller-icons") if imagepath else None,
    ):
        if not d or not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            m = pattern.match(name)
            if m and not os.path.islink(os.path.join(d, name)):
                types.add(m.group(1).lower())
    return sorted(types)


def auto_assign_color(config, controller_id):
    """
    Chooses color for a controller that doesn't have one yet by picking the first
    preset color not used by any other controller and storing it.

    Returns controller's color.
    """
    cfg = config.get_controller_config(controller_id)
    if cfg.get("icon_color"):
        return cfg["icon_color"]
    used = set()
    for cid, ccfg in config.values.get("controllers", {}).items():
        if cid != controller_id and ccfg.get("icon_color"):
            used.add(ccfg["icon_color"].lower())
    for color in PRESET_COLORS:
        if color not in used:
            break
    else:
        # All presets used - just take the default
        color = DEFAULT_COLOR
    cfg["icon_color"] = color
    config.save()
    return color
