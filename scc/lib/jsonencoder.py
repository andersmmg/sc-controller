#!/usr/bin/env python3
"""
SC-Controller - JSON encoder

The original module was a vendored copy of the Python 2 'json.encoder' module.
Since the stdlib 'json' module provides an API-compatible JSONEncoder on
Python 3, this module now re-exports that instead.
"""
from json import JSONEncoder

__all__ = [ 'JSONEncoder' ]