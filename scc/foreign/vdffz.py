#!/usr/bin/env python3
"""
Imports VDFFZ profile and converts it to Profile object.
VDFFZ is just VDF encapsulated in json, so this just gets one value and calls
VDFProfile to decode rest.
"""

import json
import logging

from vdf import VDFProfile

from scc.lib.vdf import parse_vdf

log = logging.getLogger("import.vdffz")


class VDFFZProfile(VDFProfile):
	def load(self, filename):
		try:
			with open(filename) as fh:
				data = json.loads(fh.read())
		except Exception:
			raise ValueError("Failed to parse JSON") from None
		if "ConfigData" not in data:
			raise ValueError("ConfigData missing in JSON")
		self.load_data(parse_vdf(data["ConfigData"].encode("utf-8")))
