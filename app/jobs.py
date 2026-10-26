"""AWS orchestration reuses core.process/core.approve; no second image policy."""
import json
import re
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from . import core
from .imaging import decode

MAX_UPLOAD = 12 * 1024 * 1024

def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")

class Jobs:
    def __init__(self, store, workdir=None):
        self.store, self.workdir = store, workdir

    def read_json(self, key):
        return json.loads(self.store.read(key, 256 * 1024))

    def create(self, uploads, rights):
        if rights is not True or not isinstance(uploads, list) or not 1 <= len(uploads) <= 5:
            raise ValueError("Rights confirmation and 1–5 images required")
        descriptors = []
        for item in uploads:
            if not isinstance(item, dict) or set(item) != {"content_type", "size", "sha256"}:
                raise ValueError("Expected content_type, size and sha256")
            if item["content_type"] not in ("image/jpeg", "image/png"):
                raise ValueError("Only JPEG/PNG supported")
            if type(item["size"]) is not int or not 1 <= item["size"] <= MAX_UPLOAD:
                raise ValueError("Image size must be 1 byte to 12 MiB")
            if not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
                raise ValueError("Expected lowercase SHA-256")
            descriptors.append(dict(item))
        job = uuid.uuid4().hex
        for index, item in enumerate(descriptors):
            suffix = "png" if item["content_type"] == "image/png" else "jpg"
            item["key"] = f"originals/{job}/{index}.{suffix}"
        manifest = {"id": job, "uploads": descriptors, "rights_confirmed": True,
                    "created_at": core.now(), "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
        self.store.put_new(f"traces/jobs/{job}.json", encoded(manifest))
        return {"job_id": job, "published": False, "uploads": [
            self.store.prepare_upload(item["key"], item) for item in descriptors]}

    def manifest(self, job):
        core.identifier(job)
        manifest = self.read_json(f"traces/jobs/{job}.json")
        if datetime.now(timezone.utc) > datetime.fromisoformat(manifest["expires_at"]):
            raise ValueError("Job expired")
        return manifest

    def analyze(self, job):
        manifest = self.manifest(job)
        try:
            return self.read_json(f"traces/{job}.json")
        except FileNotFoundError:
            pass
        images = []
        for item in manifest["uploads"]:
            data = self.store.read(item["key"], MAX_UPLOAD)
            if len(data) != item["size"] or core.sha(data) != item["sha256"]:
                raise ValueError("Original checksum/size mismatch")
            expected_png = item["content_type"] == "image/png"
            if data.startswith(b"\x89PNG\r\n\x1a\n") != expected_png:
                raise ValueError("Image MIME mismatch")
            decode(data)  # Reject invalid/oversize images before the batch runs.
            images.append(data)
        with tempfile.TemporaryDirectory(dir=self.workdir) as directory:
            root = Path(directory)
            trace = core.process(images, True, root, batch=job)
            trace["rights_scope"] = "user confirms permission for private AWS demo processing and cat subject"
            for item in trace["items"]:
                if item["proposal"].startswith("derivatives/"):
                    data = (root / item["proposal"]).read_bytes()
                    try:
                        self.store.put_new(item["proposal"], data, "image/png")
                    except FileExistsError:
                        if self.store.read(item["proposal"]) != data:
                            raise ValueError("Derivative conflict")
            try:
                self.store.put_new(f"traces/{job}.json", encoded(trace))
            except FileExistsError:
                # Concurrent processing uses the first complete, immutable trace.
                trace = self.read_json(f"traces/{job}.json")
            return trace

    def result(self, job):
        self.manifest(job)
        trace = self.read_json(f"traces/{job}.json")
        previews = []
        if trace["selected"] is not None:
            item = trace["items"][trace["selected"]]
            previews = [self.store.preview(item["original"]), self.store.preview(item["proposal"])]
        try:
            approval = self.read_json(f"approvals/{job}.json")
        except FileNotFoundError:
            approval = None
        return {"trace": trace, "previews": previews, "approval": approval, "published": False}

    def decide(self, job, decision):
        self.manifest(job)
        trace = self.read_json(f"traces/{job}.json")
        with tempfile.TemporaryDirectory(dir=self.workdir) as directory:
            root = Path(directory)
            core.record(root / f"traces/{job}.json", trace)
            if trace["selected"] is not None:
                item = trace["items"][trace["selected"]]
                for key in set((item["original"], item["proposal"])):
                    core.write_new(root / key, self.store.read(key))
            approval = core.approve(job, decision, root)
            approval["status"] = "APPROVED_PRIVATE" if decision == "APPROVE" else "REQUEST_NEW_PHOTO"
            approval["scope"] = "Private review only; no publishing capability"
            self.store.put_new(f"approvals/{job}.json", encoded(approval))
            return approval
