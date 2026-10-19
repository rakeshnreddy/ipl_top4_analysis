from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock

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

    def test_pruning_keeps_only_the_newest_dated_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            for name in ("2026-05-02", "2026-05-03", "2026-05-04", "not-a-date"):
                write_png(output_root / name / "slide-01-overview.png")

            removed = carousel.prune_old_carousels(output_root)

            self.assertEqual([path.name for path in removed], ["2026-05-02", "2026-05-03"])
            self.assertEqual(carousel.carousel_dates(output_root), ["2026-05-04"])
            self.assertTrue((output_root / "not-a-date").exists())

    def test_manifest_generation_lists_latest_slides_and_source(self) -> None:
        payload = {
            "metadata": {
                "generated_at": "2026-05-04T08:06:47Z",
                "source": "CricketData",
                "source_url": "https://cricketdata.org/",
                "warnings": ["Test source warning."],
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
            self.assertEqual(manifest["slides"][0]["previewPath"], "social/instagram-carousel/2026-05-04/slide-01-overview.webp")
            self.assertEqual(manifest["slides"][0]["previewWidth"], 720)
            self.assertEqual(manifest["slides"][0]["previewHeight"], 1280)
            with Image.open(output_root / "2026-05-04" / "slide-01-overview.webp") as preview:
                self.assertEqual(preview.size, (720, 1280))
                self.assertEqual(preview.format, "WEBP")
            self.assertEqual(manifest["generatedAt"], "2026-05-04T09:00:00Z")
            self.assertEqual(manifest["source"]["name"], "CricketData")
            self.assertIn("Test source warning", manifest["warnings"][0])

    def test_completed_season_leaves_the_pack_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "ipl-2026.json"
            data_path.write_text('{"metadata": {"season_status": "complete"}}')
            output_root = Path(tmp) / "carousel"

            with mock.patch.object(carousel, "DATA_PATH", data_path), mock.patch.object(carousel, "OUTPUT_ROOT", output_root):
                carousel.main()

            self.assertFalse(output_root.exists())

    def test_completed_archive_adds_only_previews_and_preserves_provenance_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "ipl-2026.json"
            data_path.write_text('{"metadata": {"season_status": "complete", "generated_at": "2026-10-19T00:00:00Z"}}')
            output_root = root / "carousel"
            png = output_root / "2026-05-24" / "slide-01-overview.png"
            write_png(png)
            original_png = png.read_bytes()
            old = {
                "latestDate": "2026-05-24", "dates": ["2026-05-24"],
                "generatedAt": "2026-05-24T12:00:00Z",
                "source": {"name": "Archived source", "dataGeneratedAt": "2026-05-24T10:00:00Z"},
                "warnings": ["Historical warning"],
                "slides": [{"path": "social/instagram-carousel/2026-05-24/slide-01-overview.png", "downloadName": "original.png"}],
            }
            manifest_path = output_root / "manifest.json"
            manifest_path.write_text(json.dumps(old, indent=2) + "\n")
            with mock.patch.object(carousel, "DATA_PATH", data_path), mock.patch.object(carousel, "OUTPUT_ROOT", output_root):
                carousel.main()
                updated = json.loads(manifest_path.read_text())
                preview = png.with_suffix(".webp")
                self.assertTrue(preview.exists())
                self.assertEqual(png.read_bytes(), original_png)
                for key in ("generatedAt", "source", "warnings", "latestDate", "dates"):
                    self.assertEqual(updated[key], old[key])
                self.assertEqual(updated["slides"][0]["path"], old["slides"][0]["path"])
                self.assertEqual(updated["slides"][0]["downloadName"], "original.png")
                before = (manifest_path.read_bytes(), manifest_path.stat().st_mtime_ns, preview.read_bytes(), preview.stat().st_mtime_ns)
                carousel.main()
                after = (manifest_path.read_bytes(), manifest_path.stat().st_mtime_ns, preview.read_bytes(), preview.stat().st_mtime_ns)
                self.assertEqual(after, before)
                self.assertEqual(carousel.carousel_dates(output_root), ["2026-05-24"])

    def test_completed_archive_without_manifest_does_not_create_a_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "ipl-2026.json"
            data_path.write_text('{"metadata": {"season_status": "complete"}}')
            output_root = root / "carousel"
            png = output_root / "2026-05-24" / "slide-01-overview.png"
            write_png(png)
            with mock.patch.object(carousel, "DATA_PATH", data_path), mock.patch.object(carousel, "OUTPUT_ROOT", output_root):
                carousel.main()
            self.assertFalse(png.with_suffix(".webp").exists())
            self.assertFalse((output_root / "manifest.json").exists())

    def test_damaged_preview_is_rebuilt_from_the_preserved_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            png = root / "2026-05-24" / "slide-01-overview.png"
            write_png(png)
            original = png.read_bytes()
            png.with_suffix(".webp").write_bytes(b"damaged preview")
            metadata = carousel.slide_preview_metadata(png, root)
            self.assertEqual(metadata["previewWidth"], 720)
            with Image.open(png.with_suffix(".webp")) as preview:
                self.assertEqual(preview.size, (720, 1280))
            self.assertEqual(png.read_bytes(), original)

    def test_the_pack_follows_the_newest_ipl_season(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "leagues.json").write_text('{"default": "hub", "ipl": "ipl-2027", "leagues": []}')

            with mock.patch.object(carousel, "DATA_DIR", data_dir):
                self.assertEqual(carousel.current_ipl_payload_path(), data_dir / "ipl-2027.json")
                (data_dir / "leagues.json").write_text("not json")
                self.assertEqual(carousel.current_ipl_payload_path(), data_dir / "ipl-2026.json")

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
