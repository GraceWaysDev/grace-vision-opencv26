from unittest.mock import patch as cat_patch
from cat_fixture import mock_detections
"""Actual OpenCV/handler coverage for one photo and the unchanged upper bound."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import core
from app.imaging import decode, measure
from app.jobs import Jobs
from app.lambda_handler import handle
from app.storage import LocalStore
from test_jobs import photo


class SinglePhotoTests(unittest.TestCase):
    def setUp(self):
        detector = cat_patch("app.cats.detections", side_effect=mock_detections)
        detector.start(); self.addCleanup(detector.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = LocalStore(self.root / "store")
        self.jobs = Jobs(self.store, self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def event(self, images):
        return {"operation": "create", "rights_confirmed": True, "uploads": [
            {"content_type": "image/png", "size": len(b), "sha256": core.sha(b)} for b in images]}

    def scenario(self, image, expected):
        created = handle(self.event([image]), self.jobs)
        self.assertEqual(created["statusCode"], 200)
        self.assertEqual(created["opencv_version"], "5.0.0")
        job = created["result"]["job_id"]
        upload = created["result"]["uploads"]
        self.assertEqual(len(upload), 1)
        self.store.put_new(upload[0]["key"], image, "image/png")
        analyzed = handle({"operation": "analyze", "job_id": job}, self.jobs)
        self.assertEqual(analyzed["statusCode"], 200)
        trace = analyzed["result"]
        self.assertEqual(trace["decision"], expected)
        self.assertEqual(len(trace["items"]), 1)
        item = trace["items"][0]
        self.assertEqual(item["metrics"], measure(decode(image)))
        self.assertEqual(item["original_sha256"], core.sha(image))
        self.assertEqual(self.store.read(item["original"]), image)
        self.assertIsNone(self.jobs.result(job)["approval"])
        self.assertFalse(trace["published"])
        derivatives = list(self.store.root.glob("derivatives/**/*.png"))
        if expected == "ENHANCE":
            self.assertEqual(len(derivatives), 1)
            self.assertNotEqual(item["proposal"], item["original"])
            saved = self.store.read(item["proposal"])
            self.assertEqual(item["after"], measure(decode(saved)))
            self.assertEqual(item["proposal_sha256"], core.sha(saved))
        else:
            self.assertEqual(derivatives, [])
            self.assertEqual(item["proposal"], item["original"])
        if expected == "REQUEST_NEW_PHOTO":
            self.assertIsNone(trace["selected"])
            self.assertEqual(handle({"operation": "decide", "job_id": job, "decision": "APPROVE"}, self.jobs)["statusCode"], 400)
        else:
            self.assertEqual(trace["selected"], 0)
        decision = "REQUEST_NEW_PHOTO" if expected == "REQUEST_NEW_PHOTO" else "APPROVE"
        approved = handle({"operation": "decide", "job_id": job, "decision": decision}, self.jobs)
        self.assertEqual(approved["statusCode"], 200)
        self.assertFalse(approved["result"]["published"])
        self.assertEqual(self.store.read(item["original"]), image)

    def test_single_suitable(self):
        self.scenario(photo(), "ACCEPT_ORIGINAL")

    def test_single_correctable(self):
        self.scenario(photo(82), "ENHANCE")

    def test_single_unusable(self):
        self.scenario(photo(blur=True), "REQUEST_NEW_PHOTO")

    def test_failed_enhancement_keeps_no_derivative(self):
        # Measure actual pixels; simulate an enhancement that cannot repair them.
        with patch("app.imaging.enhance", side_effect=lambda image, metrics: (image, [])):
            self.scenario(photo(82), "REQUEST_NEW_PHOTO")

    def test_zero_and_six_rejected_before_storage(self):
        b = photo()
        for n in (0, 6):
            with self.subTest(count=n):
                self.assertEqual(handle(self.event([b] * n), self.jobs)["statusCode"], 400)
                with self.assertRaises(ValueError):
                    core.process([b] * n, True, self.root / str(n))
        self.assertFalse(self.store.root.exists())

    def test_one_through_five_real_analysis(self):
        b = photo(blur=True)
        for n in range(1, 6):
            with self.subTest(count=n):
                t = core.process([b] * n, True, self.root / str(n))
                self.assertEqual(len(t["items"]), n)
                self.assertEqual(t["decision"], "REQUEST_NEW_PHOTO")
                self.assertFalse(t["published"])

    def test_one_photo_still_requires_rights(self):
        e = self.event([photo()])
        e["rights_confirmed"] = False
        self.assertEqual(handle(e, self.jobs)["statusCode"], 400)
