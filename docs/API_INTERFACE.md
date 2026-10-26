# Jury API interface

The browser never invokes AWS directly. It calls the same-origin Cloudflare Worker, which maps a fixed public protocol to four API Gateway/Lambda operations.

| Operation | Purpose | State change |
| --- | --- | --- |
| `create` | Validate rights and a 1–5 image manifest; issue short-lived upload slots | Creates private job state |
| `analyze` | Verify uploaded originals and run OpenCV analysis/policy | Writes trace and optional derivative |
| `result` | Return measurements, reasons, hashes and short-lived previews | Read-only |
| `decide` | Record one explicit approve or request-new-photo decision | Writes immutable review record |

Inputs are constrained by both Worker and Gateway schema. The public demo accepts JPEG/PNG, no more than 2 MiB per image and no dimension above 1600 pixels. The Lambda independently validates the batch, decodes each image and rejects unsupported or malformed content.

The `analyze` response includes the exact OpenCV version, per-image technical metrics, cat-framing evidence, reasons, optional operations, original/proposal hashes, selected index, overall decision and `published=false`.

The `decide` operation accepts only the selected eligible proposal. Before recording approval, the Lambda verifies the current cat-policy/model version, proposal eligibility, framing result, single-cat requirement, no edge uncertainty and both original/proposal hashes. Replays fail because the approval record is created once.

Internal resource addresses, API key values, signed URLs and job identifiers are intentionally omitted from this document.

