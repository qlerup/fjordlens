import tempfile
import unittest
from pathlib import Path

import piexif
from PIL import Image

import app as fjordlens


def _build_exif_bytes() -> bytes:
    zeroth = {
        piexif.ImageIFD.Make: b"TestPhone",
        piexif.ImageIFD.Model: b"TestModel",
        piexif.ImageIFD.Orientation: 1,
    }
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: b"2023:07:15 10:30:00",
        piexif.ExifIFD.LensModel: b"TestLens",
        piexif.ExifIFD.ISOSpeedRatings: 100,
        piexif.ExifIFD.FNumber: (28, 10),
        piexif.ExifIFD.FocalLength: (26, 1),
    }
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: ((55, 1), (40, 1), (0, 1)),
        piexif.GPSIFD.GPSLongitudeRef: b"E",
        piexif.GPSIFD.GPSLongitude: ((12, 1), (34, 1), (0, 1)),
    }
    return piexif.dump({"0th": zeroth, "Exif": exif_ifd, "GPS": gps_ifd, "1st": {}, "thumbnail": None})


class ExifSubIfdExtractionTests(unittest.TestCase):
    """Regression coverage for a bug where DateTimeOriginal/LensModel/GPS silently
    never made it into the DB: Pillow's Exif.items() only yields the 0th IFD, and
    the GPS sub-IFD fallback used the wrong ExifTags.IFD attribute name (.GPS
    instead of .GPSInfo), so it always raised AttributeError inside a swallowed
    try/except. This affected every JPEG, not just HEIC/MOV conversions."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.jpg_path = Path(self.tempdir.name) / "photo.jpg"
        img = Image.new("RGB", (40, 30), color="blue")
        img.save(self.jpg_path, format="JPEG", exif=_build_exif_bytes())
        self._previous_geocode_enable = fjordlens.GEOCODE_ENABLE
        fjordlens.GEOCODE_ENABLE = False  # keep these tests offline/deterministic

    def tearDown(self):
        fjordlens.GEOCODE_ENABLE = self._previous_geocode_enable
        self.tempdir.cleanup()

    def test_parse_exif_pulls_in_exif_and_gps_sub_ifds(self):
        with Image.open(self.jpg_path) as img:
            exif_map = fjordlens.parse_exif(img)
        self.assertEqual(exif_map.get("DateTimeOriginal"), "2023:07:15 10:30:00")
        self.assertEqual(exif_map.get("LensModel"), "TestLens")
        self.assertAlmostEqual(exif_map.get("_gps_lat"), 55.6667, places=3)
        self.assertAlmostEqual(exif_map.get("_gps_lon"), 12.5667, places=3)

    def test_captured_at_uses_real_exif_date_not_file_mtime(self):
        with Image.open(self.jpg_path) as img:
            exif_map = fjordlens.parse_exif(img)
        captured_at = fjordlens.parse_captured_at(exif_map, self.jpg_path.stat().st_mtime)
        self.assertEqual(captured_at, "2023-07-15T10:30:00")

    def test_extract_metadata_surfaces_gps_and_lens(self):
        meta = fjordlens.extract_metadata(self.jpg_path, "uploads/originals/photo.jpg", generate_thumb=False)
        self.assertEqual(meta.get("captured_at"), "2023-07-15T10:30:00")
        self.assertEqual(meta.get("lens_model"), "TestLens")
        self.assertIsNotNone(meta.get("gps_lat"))
        self.assertIsNotNone(meta.get("gps_lon"))
        self.assertAlmostEqual(meta["gps_lat"], 55.6667, places=3)
        self.assertAlmostEqual(meta["gps_lon"], 12.5667, places=3)


if __name__ == "__main__":
    unittest.main()
