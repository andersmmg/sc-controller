import xml.etree.ElementTree as ET
from pathlib import Path

ASSET_ROOT = Path(__file__).parents[1] / "images"
SVG_ASSET_DIRECTORIES = (
	ASSET_ROOT / "controller-images",
	ASSET_ROOT / "button-images",
)


def _has_text_element(path):
	root = ET.parse(path).getroot()
	return any(element.tag.rsplit("}", 1)[-1] == "text" for element in root.iter())


def test_controller_artwork_has_no_text_objects():
	text_assets = sorted(
		path.relative_to(ASSET_ROOT).as_posix()
		for directory in SVG_ASSET_DIRECTORIES
		for path in directory.glob("*.svg")
		if _has_text_element(path)
	)

	assert not text_assets, "Live SVG text found; convert it to paths: " + ", ".join(text_assets)
