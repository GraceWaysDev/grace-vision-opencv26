from unittest.mock import patch as cat_patch
from cat_fixture import mock_detections
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
import numpy as np
from app import core
from app.imaging import png_bytes, decode, measure
from app.jobs import Jobs, MAX_UPLOAD
from app.storage import LocalStore, S3Store
from app.lambda_handler import handle, CV_VERSION

ROOT = Path(__file__).resolve().parents[1]

def photo(mean=130, blur=False):
    gray = np.clip(np.random.default_rng(7).normal(mean, 45, (640, 800)), 0, 255).astype(np.uint8)
    if blur:
        gray[:] = 125
    return png_bytes(np.repeat(gray[:, :, None], 3, axis=2))

class JobTests(unittest.TestCase):
    def setUp(self):
        detector = cat_patch("app.cats.detections", side_effect=mock_detections)
        detector.start(); self.addCleanup(detector.stop)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "evaluation")
        self.root = Path(self.temp.name)
        self.store = LocalStore(self.root / "store")
        self.jobs = Jobs(self.store, self.root)

    def tearDown(self):
        self.temp.cleanup()

    def create(self, images):
        result = handle({"operation": "create", "rights_confirmed": True, "uploads": [
            {"content_type": "image/png", "size": len(data), "sha256": core.sha(data)} for data in images]}, self.jobs)
        self.assertEqual(result["statusCode"], 200)
        job = result["result"]["job_id"]
        for image, upload in zip(images, result["result"]["uploads"]):
            self.store.put_new(upload["key"], image, "image/png")
        return job

    def test_real_runtime_exact(self):
        self.assertEqual(CV_VERSION, "5.0.0")

    def test_full_accept_original_bytes_and_sha(self):
        data = photo()
        job = self.create([data, photo(blur=True)])
        trace = self.jobs.analyze(job)
        self.assertEqual(trace["decision"], "ACCEPT_ORIGINAL")
        self.assertEqual(trace["id"], job)
        self.assertEqual(self.store.read(trace["items"][0]["original"]), data)
        self.assertEqual(trace["items"][0]["original_sha256"], core.sha(data))
        self.assertIsNone(self.jobs.result(job)["approval"])
        self.assertFalse(trace["published"])
        approval = self.jobs.decide(job, "APPROVE")
        self.assertEqual(approval["status"], "APPROVED_PRIVATE")
        self.assertFalse(approval["published"])
        self.assertEqual(self.jobs.result(job)["approval"], approval)

    def test_enhance_remeasures_saved_bytes(self):
        job = self.create([photo(82), photo(blur=True)])
        trace = self.jobs.analyze(job)
        self.assertEqual(trace["decision"], "ENHANCE")
        item = trace["items"][trace["selected"]]
        self.assertTrue(item["operations"])
        self.assertEqual(item["after"], measure(decode(self.store.read(item["proposal"]))))
        self.assertEqual(item["proposal_sha256"], core.sha(self.store.read(item["proposal"])))

    def test_rejected_image_cannot_be_approved(self):
        job = self.create([photo(blur=True)] * 2)
        self.assertEqual(self.jobs.analyze(job)["decision"], "REQUEST_NEW_PHOTO")
        response = handle({"operation": "decide", "job_id": job, "decision": "APPROVE"}, self.jobs)
        self.assertEqual(response["statusCode"], 400)
        self.assertIsNone(self.jobs.result(job)["approval"])
        self.assertFalse(self.jobs.decide(job, "REQUEST_NEW_PHOTO")["published"])

    def test_repeat_analysis_and_first_decision_immutable(self):
        job = self.create([photo()] * 2)
        first = self.jobs.analyze(job)
        self.assertEqual(self.jobs.analyze(job), first)
        self.jobs.decide(job, "APPROVE")
        result = handle({"operation": "decide", "job_id": job, "decision": "REQUEST_NEW_PHOTO"}, self.jobs)
        self.assertEqual(result["statusCode"], 409)

    def test_count_rights_type_and_size_limits(self):
        descriptor = {"content_type": "image/png", "size": 10, "sha256": "a" * 64}
        for uploads, rights in [([], True), ([descriptor]*6, True), ([descriptor]*2, False),
                               ([dict(descriptor, size=MAX_UPLOAD+1)]*2, True),
                               ([dict(descriptor, content_type="text/html")]*2, True)]:
            with self.assertRaises(ValueError):
                self.jobs.create(uploads, rights)

    def test_original_tamper_blocks_analysis(self):
        job = self.create([photo()] * 2)
        key = self.jobs.manifest(job)["uploads"][0]["key"]
        (self.store.root / key).write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            self.jobs.analyze(job)
        with self.assertRaises(FileNotFoundError):
            self.store.read(f"traces/{job}.json")

    def test_derivative_tamper_blocks_approval(self):
        job = self.create([photo(82), photo(blur=True)])
        trace = self.jobs.analyze(job)
        (self.store.root / trace["items"][0]["proposal"]).write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            self.jobs.decide(job, "APPROVE")

    def test_invalid_image_bytes_not_processed(self):
        job = self.create([b"not a photo"] * 2)
        self.assertEqual(handle({"operation": "analyze", "job_id": job}, self.jobs)["statusCode"], 400)

    def test_path_event_and_missing_errors(self):
        for event in [{"operation": "publish"}, {"operation": "result", "job_id": "../bad"},
                      {"operation": "result", "job_id": "a"*32, "extra": "unexpected"}]:
            self.assertEqual(handle(event, self.jobs)["statusCode"], 400)
        self.assertEqual(handle({"operation": "result", "job_id": "a"*32}, self.jobs)["statusCode"], 404)
        with self.assertRaises(ValueError):
            self.store.put_new("originals/../../escape", b"no")

    def test_oversize_pixels_rejected(self):
        from PIL import Image
        stream = io.BytesIO()
        Image.new("RGB", (6000, 4001)).save(stream, "PNG")
        with self.assertRaises(ValueError):
            decode(stream.getvalue())

class S3ContractTests(unittest.TestCase):
    def test_upload_signature_is_bounded_and_immutable(self):
        client = Mock()
        store = S3Store(client, "private-demo")
        result = store.prepare_upload("originals/job/0.png", {"size": 12, "sha256": "a"*64, "content_type": "image/png"})
        args = client.generate_presigned_url.call_args.kwargs
        self.assertEqual(args["ExpiresIn"], 120)
        self.assertEqual(args["Params"]["ContentLength"], 12)
        self.assertEqual(args["Params"]["IfNoneMatch"], "*")
        self.assertEqual(args["Params"]["ServerSideEncryption"], "AES256")
        self.assertIn("x-amz-checksum-sha256", result["headers"])

    def test_put_has_checksum_encryption_and_precondition(self):
        client = Mock()
        S3Store(client, "private-demo").put_new("traces/test.json", b"{}")
        args = client.put_object.call_args.kwargs
        self.assertEqual(args["IfNoneMatch"], "*")
        self.assertEqual(args["ServerSideEncryption"], "AES256")
        self.assertEqual(len(args["ChecksumSHA256"]), 44)

    def test_get_stream_is_bounded_and_closed(self):
        client = Mock()
        stream = io.BytesIO(b"12345")
        client.list_objects_v2.return_value = {"Contents": [{"Key": "originals/job/x"}]}
        client.get_object.return_value = {"ContentLength": 5, "Body": stream}
        with self.assertRaises(ValueError):
            S3Store(client, "private-demo").read("originals/job/x", 4)
        self.assertTrue(stream.closed)
        self.assertEqual(client.list_objects_v2.call_args.kwargs["Prefix"], "originals/job/x")
        self.assertEqual(client.list_objects_v2.call_args.kwargs["MaxKeys"], 1)

    def test_missing_object(self):
        client = Mock()
        client.list_objects_v2.return_value = {}
        with self.assertRaises(FileNotFoundError):
            S3Store(client, "private-demo").read("traces/missing.json")
        client.get_object.assert_not_called()

    def test_private_preview_expiry(self):
        client = Mock()
        S3Store(client, "private-demo").preview("derivatives/job/0.png")
        self.assertEqual(client.generate_presigned_url.call_args.kwargs["ExpiresIn"], 60)

if __name__ == "__main__":
    unittest.main()
