# Grace Vision for GraceWays Animals

Grace Vision is an explainable, human-in-the-loop photo triage workflow for animal-adoption listings. It preserves the uploaded original, measures visible image evidence with **OpenCV 5.0.0**, chooses one bounded next action, optionally creates a conservative derivative, measures that derivative again, and asks a person to approve or reject the proposal.

**Public jury demo:** https://gracevision-opencv26-jury-demo.black-term-967a.workers.dev/

The public demo is a separate competition system. It is not connected to GraceWays Animals production records and it has no publishing route.

> **Public repository note:** This review repository intentionally omits the large
> ONNX model, offline Python wheels and CC0 test image. Their exact versions,
> SHA-256 hashes, provenance and licenses remain documented in the included lock
> and metadata files. The deployed jury workflow uses the pinned artifacts.

## What the system does

1. Accepts one to five rights-cleared JPEG or PNG images.
2. Stores each original separately and records its SHA-256.
3. Measures resolution, Laplacian sharpness, exposure, clipped-pixel shares and luminance contrast with OpenCV.
4. Runs a pinned OpenCV Zoo YOLOX-S model through OpenCV DNN on CPU for cat-framing evidence.
5. Selects exactly one bounded action: `ACCEPT_ORIGINAL`, `ENHANCE`, `TRY_NEXT_IMAGE` or `REQUEST_NEW_PHOTO`.
6. Uses only limited gamma/contrast adjustment, denoising, sharpening and a conservative crop. It does not inpaint, reconstruct or generate visual detail.
7. Re-decodes and remeasures the exact saved derivative bytes.
8. Requires explicit human review. Approval changes only the demo selection; it does not publish an image.

## Material OpenCV and AWS use

The AWS Lambda container performs the material workload: OpenCV decoding, measurements, OpenCV DNN inference, policy selection, optional correction and remeasurement. Originals, derivatives, traces and review decisions use separate private Amazon S3 prefixes. API Gateway exposes four fixed operations to the Cloudflare jury Worker: create, analyze, result and decide.

OpenCV is not used as a decorative dependency. Its measurements and DNN result determine which next action the workflow takes and whether a derivative can be shown.

## Repository map

| Path | Purpose |
| --- | --- |
| `app/` | Shared OpenCV analysis, cat-framing policy, storage abstraction and Lambda handler |
| `tests/` | Python unit, policy, infrastructure and real-model tests |
| `infrastructure/` | Pinned Lambda container and CloudFormation templates |
| `integration/jury-worker/` | Public jury UI, security boundary, Gateway contract and tests |
| `vendor/models/yolox-s/` | Pinned-model metadata, provenance and Apache-2.0 license; large ONNX binary omitted here |
| `vendor/linux/` | Dependency lock and provenance; large offline wheel files omitted here |
| `docs/` | Current architecture, evaluation, security, build and deployment notes |

## Reproduce the OpenCV container tests from the full offline archive

Requirements: Docker with a Linux/amd64 engine and at least 2 GiB available.
The commands below apply to the full verified offline archive after checking the
model, wheel and fixture hashes against the included provenance records. Those
large binary artifacts are deliberately not stored in this compact public
repository.

Linux/macOS shell:

```bash
docker build --platform linux/amd64 --provenance=false \
  --target tests -f infrastructure/Dockerfile \
  -t gracevision-jury-tests .

docker run --rm --network none --memory 2g --cpus 2 \
  --mount "type=bind,source=$PWD/tests/fixtures/cc0-cat.jpg,target=/fixtures/cc0-cat.jpg,readonly" \
  gracevision-jury-tests
```

PowerShell:

```powershell
$fixture = (Resolve-Path tests/fixtures/cc0-cat.jpg).Path
docker build --platform linux/amd64 --provenance=false `
  --target tests -f infrastructure/Dockerfile `
  -t gracevision-jury-tests .
docker run --rm --network none --memory 2g --cpus 2 `
  --mount "type=bind,source=$fixture,target=/fixtures/cc0-cat.jpg,readonly" `
  gracevision-jury-tests
```

Confirm the runtime and model pins:

```bash
docker build --platform linux/amd64 --provenance=false \
  --target runtime -f infrastructure/Dockerfile \
  -t gracevision-jury-runtime .
docker run --rm --network none --entrypoint python gracevision-jury-runtime \
  -c "import cv2; from app.cats import MODEL_SHA256; print(cv2.__version__, MODEL_SHA256); assert cv2.__version__ == '5.0.0'"
```

Run the non-browser Worker contract and security tests with Node.js 22 or later:

```bash
node --test \
  integration/jury-worker/test/cats.test.mjs \
  integration/jury-worker/test/gateway-permission.test.cjs \
  integration/jury-worker/test/single-photo.test.mjs \
  integration/jury-worker/test/worker-tests.mjs
```

See [Build, test and deploy](docs/BUILD_TEST_DEPLOY.md) for the complete reproducibility path and [Evaluation](docs/EVALUATION.md) for demonstrated results.

## Verified evidence and honest limits

- AWS control traces demonstrated accept, enhance and safe-reject branches with OpenCV 5.0.0.
- Phase 4H recorded 358 tests and 437 browser assertions for the cat-framing release.
- This cleaned archive was reverified with 56 Python/OpenCV tests and 56 portable Worker/contract tests.
- The full offline archive contains a small CC0 real-cat fixture only for model/geometry testing; it is not an accuracy benchmark. The compact public repository retains its provenance record but omits the image bytes.
- The real-cat Molly boundary case produced a false rejection under the strict edge-contact rule. No Molly image is included in this archive.
- YOLOX provides a bounding box, not segmentation, identity, medical assessment or proof that all body parts are visible.
- Human visibility review is mandatory before approval.
- The public live session lasts about 15 minutes. Reload the page before a fresh jury run.
- The public service is quota-limited. A USD 5 budget is an alert, not a hard cost cap.
- The release scan reported 0 Critical and 7 High findings covered by a documented, time-limited Amazon Linux “Pending Fix” risk acceptance. The system is not represented as vulnerability-free.

## Source-state note

This archive contains the source state corresponding to the deployed jury workflow at the time of packaging. A later local session-renewal change was tested separately but is intentionally not mixed into this archive because it was not deployed. The live demo therefore retains the 15-minute-session limitation described above.

## Rights and licensing

Provenance and license records for the omitted CC0 cat fixture and third-party model/dependencies are included. No Molly image, user photo, production database export, credential, token, account identifier or private GraceWays Animals source is included.

The project source is supplied for competition review; no general open-source license is granted. See [LICENSE-NOTICE.md](LICENSE-NOTICE.md) and [Third-party components](docs/THIRD_PARTY.md).

