"""Fetch only pinned official PyPI wheels for Lambda Linux amd64/Python 3.12."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_dependencies import OfficialRedirect
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PINS = {"opencv-python-headless": "5.0.0.93", "numpy": "2.3.5", "pillow": "12.3.0"}

def main():
    opener = urllib.request.build_opener(OfficialRedirect)
    target = ROOT / "vendor/linux"
    target.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, version in PINS.items():
        metadata_url = f"https://pypi.org/pypi/{name}/{version}/json"
        with opener.open(metadata_url, timeout=60) as response:
            metadata = json.load(response)
        candidates = [f for f in metadata["urls"] if f["filename"].endswith("x86_64.whl")
                      and "manylinux" in f["filename"]
                      and ("cp37-abi3" if name.startswith("opencv") else "cp312-cp312") in f["filename"]]
        # Prefer the oldest glibc baseline if PyPI supplies several manylinux wheels.
        candidates.sort(key=lambda f: f["filename"])
        if not candidates:
            raise RuntimeError(f"No Linux wheel for {name}")
        artifact = candidates[0]
        if artifact["yanked"] or not artifact["url"].startswith("https://files.pythonhosted.org/"):
            raise RuntimeError("Unacceptable artifact")
        with opener.open(artifact["url"], timeout=180) as response:
            data = response.read()
        digest = hashlib.sha256(data).hexdigest()
        if digest != artifact["digests"]["sha256"]:
            raise RuntimeError("Checksum mismatch")
        (target / artifact["filename"]).write_bytes(data)
        entries.append({"name": name, "version": version, "filename": artifact["filename"],
                        "metadata_url": metadata_url, "url": artifact["url"],
                        "sha256": digest, "bytes": len(data),
                        "license": metadata["info"].get("license_expression") or metadata["info"].get("license")})
        print(name, version, artifact["filename"], digest)
    (ROOT / "infrastructure/dependencies-linux.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    (ROOT / "infrastructure/requirements-linux.lock").write_text("\n".join(
        f"{e['name']}=={e['version']} --hash=sha256:{e['sha256']}" for e in entries) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
