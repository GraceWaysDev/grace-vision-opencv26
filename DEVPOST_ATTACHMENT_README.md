# Grace Vision — Devpost jury attachment

This compact attachment accompanies the OpenCV AI Competition 2026 submission.
It contains the project source, tests, CloudFormation templates, jury Worker,
technical report, architecture image, dependency locks, third-party licenses,
and provenance records.

## Deliberately omitted from this 35 MB-limited upload

The complete reproducibility archive also contains:

- three hash-pinned Linux wheels for OpenCV 5.0.0, NumPy, and Pillow;
- the pinned OpenCV Zoo YOLOX-S ONNX model; and
- the metadata-stripped CC0 cat test fixture.

Those large binary artifacts exceed Devpost's attachment limit. Their exact
filenames, versions, byte lengths, SHA-256 values, licenses, and provenance
remain recorded in the included lock and metadata files. The full verified
archive is intended for the repository release referenced by the submission.

The compact attachment is therefore suitable for code and documentation review,
but the full archive is the self-contained offline build artifact.

## Quick review

- Start with `README.md`.
- See `docs/submission/Technical_Report.pdf` and
  `docs/submission/Architecture.png`.
- Run the portable Worker contract tests using the command in `README.md`.
- Review AWS/Lambda source under `app/` and `infrastructure/`.
- Review the public security boundary under `integration/jury-worker/`.

No user-supplied animal photo, GraceWays production export, credential, token,
account identifier, private endpoint, log, browser profile, or runtime object is
included.
