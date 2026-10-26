import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class InfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads((ROOT / "infrastructure/template.json").read_text())
        self.resources = self.template["Resources"]

    def test_private_encrypted_bucket_and_lifecycle(self):
        properties = self.resources["DataBucket"]["Properties"]
        self.assertTrue(all(properties["PublicAccessBlockConfiguration"].values()))
        self.assertEqual(properties["OwnershipControls"]["Rules"][0]["ObjectOwnership"], "BucketOwnerEnforced")
        encryption = properties["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]
        self.assertEqual(encryption["ServerSideEncryptionByDefault"]["SSEAlgorithm"], "AES256")
        rules = properties["LifecycleConfiguration"]["Rules"]
        self.assertEqual({r["Prefix"] for r in rules}, {"originals/", "derivatives/", "traces/", "approvals/"})
        self.assertTrue(all(r["ExpirationInDays"] == 7 for r in rules))

    def test_compute_bounds_and_no_public_endpoint(self):
        function = self.resources["AnalysisFunction"]["Properties"]
        self.assertEqual(function["ReservedConcurrentExecutions"], 2)
        self.assertEqual(function["Timeout"], 180)
        self.assertEqual(function["MemorySize"], 2048)
        self.assertEqual(function["Environment"]["Variables"]["GRACEVISION_STORAGE"], "s3")
        self.assertFalse(any("ApiGateway" in r["Type"] or r["Type"] in ("AWS::Lambda::Url", "AWS::Lambda::Permission") for r in self.resources.values()))

    def test_role_is_prefix_scoped_without_delete(self):
        statements = self.resources["ExecutionRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        self.assertEqual(set(statements[0]["Action"]), {"s3:GetObject", "s3:PutObject"})
        self.assertEqual(len(statements[0]["Resource"]), 4)
        self.assertEqual(statements[1]["Action"], ["s3:ListBucket"])
        self.assertEqual(len(statements[1]["Condition"]["StringLike"]["s3:prefix"]), 4)
        self.assertNotIn("DeleteObject", json.dumps(statements))

    def test_bucket_requires_transport_and_conditional_writes(self):
        statements = self.resources["BucketPolicy"]["Properties"]["PolicyDocument"]["Statement"]
        self.assertEqual(statements[0]["Condition"]["Bool"]["aws:SecureTransport"], "false")
        self.assertEqual(statements[1]["Condition"]["Null"]["s3:if-none-match"], "true")
        self.assertTrue(all(s["Effect"] == "Deny" for s in statements))

    def test_digest_and_hash_pins(self):
        dockerfile = (ROOT / "infrastructure/Dockerfile").read_text()
        bases = re.findall(r"^FROM (public\.ecr\.aws/\S+)", dockerfile, re.M)
        self.assertEqual(len(bases), 2)
        self.assertTrue(all(re.search(r"@sha256:[0-9a-f]{64}$", base) for base in bases))
        lock = (ROOT / "infrastructure/requirements-linux.lock").read_text()
        self.assertIn("opencv-python-headless==5.0.0.93 --hash=sha256:", lock)
        self.assertEqual(lock.count("--hash=sha256:"), 3)

if __name__ == "__main__":
    unittest.main()
