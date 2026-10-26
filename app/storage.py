"""Bounded, immutable storage. No network is used by LocalStore."""
import base64
import hashlib
import re
from pathlib import Path

MAX_OBJECT = 80 * 1024 * 1024  # A 24MP derivative may be larger than its upload.

def key_checked(key):
    if not isinstance(key, str) or not re.fullmatch(
        r"(?:originals|derivatives|traces|approvals)/[a-zA-Z0-9_./-]+", key
    ) or any(part in ("", ".", "..") for part in key.split("/")):
        raise ValueError("Invalid storage key")
    return key

class LocalStore:
    def __init__(self, root):
        self.root = Path(root)

    def read(self, key, limit=MAX_OBJECT):
        with (self.root / key_checked(key)).open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Object exceeds size limit")
        return data

    def put_new(self, key, data, content_type="application/json"):
        if len(data) > MAX_OBJECT:
            raise ValueError("Object exceeds size limit")
        path = self.root / key_checked(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)

    def prepare_upload(self, key, descriptor):
        return {"method": "LOCAL_TEST_ONLY", "key": key_checked(key),
                "expires_in": 120, "descriptor": descriptor}

    def preview(self, key):
        return {"key": key_checked(key), "local_test_only": True}

class S3Store:
    def __init__(self, client, bucket):
        self.client, self.bucket = client, bucket

    @staticmethod
    def _translate(error):
        code = getattr(error, "response", {}).get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404"):
            raise FileNotFoundError("Object not found") from error
        if code in ("PreconditionFailed", "412", "ConditionalRequestConflict", "409"):
            raise FileExistsError("Object already exists or conflicting write") from error
        raise error

    def read(self, key, limit=MAX_OBJECT):
        key_checked(key)
        # Prefix-scoped ListBucket allows reliable missing-object detection without
        # granting unrestricted bucket listing (GetObject alone returns 403).
        found = self.client.list_objects_v2(Bucket=self.bucket, Prefix=key, MaxKeys=1)
        if not any(item["Key"] == key for item in found.get("Contents", [])):
            raise FileNotFoundError("Object not found")
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key_checked(key))
        except Exception as error:
            self._translate(error)
        stream = response["Body"]
        try:
            if response["ContentLength"] > limit:
                raise ValueError("Object exceeds size limit")
            data = stream.read(limit + 1)
            if len(data) > limit:
                raise ValueError("Object exceeds size limit")
            return data
        finally:
            stream.close()

    def put_new(self, key, data, content_type="application/json"):
        if len(data) > MAX_OBJECT:
            raise ValueError("Object exceeds size limit")
        try:
            self.client.put_object(Bucket=self.bucket, Key=key_checked(key), Body=data,
                ContentType=content_type, ServerSideEncryption="AES256", IfNoneMatch="*",
                ChecksumSHA256=base64.b64encode(hashlib.sha256(data).digest()).decode())
        except Exception as error:
            self._translate(error)

    def prepare_upload(self, key, descriptor):
        checksum = base64.b64encode(bytes.fromhex(descriptor["sha256"])).decode()
        headers = {"Content-Type": descriptor["content_type"],
                   "Content-Length": str(descriptor["size"]), "If-None-Match": "*",
                   "x-amz-checksum-sha256": checksum,
                   "x-amz-server-side-encryption": "AES256"}
        url = self.client.generate_presigned_url("put_object", Params={
            "Bucket": self.bucket, "Key": key_checked(key),
            "ContentType": descriptor["content_type"], "ContentLength": descriptor["size"],
            "ChecksumSHA256": checksum, "IfNoneMatch": "*", "ServerSideEncryption": "AES256"
        }, ExpiresIn=120, HttpMethod="PUT")
        return {"method": "PUT", "url": url, "headers": headers, "expires_in": 120}

    def preview(self, key):
        return {"url": self.client.generate_presigned_url("get_object", Params={
            "Bucket": self.bucket, "Key": key_checked(key),
            "ResponseCacheControl": "no-store", "ResponseContentDisposition": "inline"
        }, ExpiresIn=60, HttpMethod="GET"), "expires_in": 60}
