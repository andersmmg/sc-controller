import scc
import pkgutil
import tomllib


class TestSetup(object):
	"""
	Tests if SCC should be installable.
	"""

	def _pyproject(self):
		with open("pyproject.toml", "rb") as f:
			return tomllib.load(f)

	def test_packages(self):
		"""
		Every scc subpackage must be listed in pyproject.toml
		"""
		try:
			import gi
			gi.require_version('Gtk', '3.0')
			gi.require_version('GdkX11', '3.0')
			gi.require_version('Rsvg', '2.0')
		except ImportError:
			pass

		packages = self._pyproject()["tool"]["setuptools"]["packages"]
		for importer, modname, ispkg in pkgutil.walk_packages(path=scc.__path__, prefix="scc.", onerror=lambda x: None):
			if ispkg:
				assert modname in packages, "Package '%s' is not being installed by pyproject.toml" % (modname,)

	def test_version_matches_pyproject(self):
		config = self._pyproject()
		from scc.constants import DAEMON_VERSION
		assert DAEMON_VERSION == config["project"]["version"]
