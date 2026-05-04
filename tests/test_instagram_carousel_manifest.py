from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PIL import Image

from scripts import create_instagram_carousel as carousel


def write_png(path: Path, size: tuple[int, int] = (carousel.WIDTH, carousel.HEIGHT)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "#07111f").save(path)


class InstagramCarouselManifestTests(unittest.TestCase):
    def test_latest_folder_detection_uses_newest_dated_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            (output_root / "2026-05-02").mkdir()
            (output_root / "not-a-date").mkdir()
            (output_root / "2026-05-04").mkdir()

            latest = carousel.latest_carousel_folder(output_root)

            self.assertEqual(latest, output_root / "2026-05-04")

    def test_manifest_generation_lists_latest_slides_and_source(self) -> None:
        payload = {
            "metadata": {
                "generated_at": "2026-05-04T08:06:47Z",
                "source": "CricketData",
                "source_url": "https://cricketdata.org/",
                "warnings": ["CricketData standings omitted NRR; NRR was enriched from Cricbuzz."],
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            write_png(output_root / "2026-05-03" / "slide-01-overview.png")
            write_png(output_root / "2026-05-04" / "slide-01-overview.png")
            write_png(output_root / "2026-05-04" / "slide-02-pbks.png")
            write_png(output_root / "2026-05-04" / "contact-sheet.png")

            manifest = carousel.build_manifest(payload, output_root, generated_at="2026-05-04T09:00:00Z")

            self.assertEqual(manifest["latestDate"], "2026-05-04")
            self.assertEqual(manifest["dates"], ["2026-05-03", "2026-05-04"])
            self.assertEqual(len(manifest["slides"]), 2)
            self.assertEqual(manifest["slides"][0]["path"], "social/instagram-carousel/2026-05-04/slide-01-overview.png")
            self.assertEqual(manifest["slides"][0]["imageWidth"], 1080)
            self.assertEqual(manifest["slides"][0]["imageHeight"], 1920)
            self.assertEqual(manifest["generatedAt"], "2026-05-04T09:00:00Z")
            self.assertEqual(manifest["source"]["name"], "CricketData")
            self.assertIn("CricketData standings omitted NRR", manifest["warnings"][0])

    def test_png_dimension_validation_reports_wrong_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "slide-01-overview.png"
            bad = Path(tmp) / "slide-02-pbks.png"
            write_png(good)
            write_png(bad, (1200, 1920))

            warnings = carousel.validate_png_dimensions([good, bad])

            self.assertEqual(len(warnings), 1)
            self.assertIn("slide-02-pbks.png is 1200x1920, expected 1080x1920", warnings[0])


if __name__ == "__main__":
    unittest.main()
