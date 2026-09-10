from scc.constants import STICK
from scc.sccdaemon import SCCDaemon


def test_source_to_constant_accepts_legacy_left_stick_name():
    assert SCCDaemon.source_to_constant("LSTICK") == STICK


def test_source_to_constant_keeps_canonical_left_stick_name():
    assert SCCDaemon.source_to_constant("STICK") == STICK
