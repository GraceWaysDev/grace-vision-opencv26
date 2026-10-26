# Cat framing: competition policy cat-frame-1

The previous technical ACCEPT_ORIGINAL evaluation of Molly is **professionally incomplete**, as reported by the user: technical image quality does not prove useful cat coverage. That result must not be approved. Molly has not been copied into the public artifact, model fixtures or container. After deployment, approval of any legacy trace without this cat policy/model is rejected; the user must start a new job.

## Model provenance

- Official OpenCV Zoo YOLOX-S, COCO, `object_detection_yolox_2022nov.onnx`, float32.
- Repository revision: `48b10fa505aeb51fbd127fc60a5c660040e823b7`.
- Binary SHA-256: `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`; 35,858,002 bytes.
- Model, source wrappers and LICENSE obtained only from the official `opencv/opencv_zoo` repository. Its model README explicitly licenses all files in that directory under Apache-2.0. LICENSE and provenance accompany the runtime model.
- Runtime: OpenCV **5.0.0**, `cv2.dnn`, OpenCV backend, CPU target, COCO index 15 (`cat`). RGB letterbox 640 × 640, value 114, anchor strides 8/16/32, objectness × class probability, class-aware NMS IoU 0.5; matches the pinned official wrapper. Resizing is only detector preprocessing, never image-output upscaling.
- The OpenCV 5 graph engine warns that selectable targets are not supported. This image has no GPU backend/device and inference runs on CPU; the warning is retained in local test evidence.
- Model loading verifies SHA-256 before inference. The path is fixed; no user-provided model, executable, expression or model download is accepted.

## Provisional general thresholds

These are explicit competition thresholds, not thresholds trained on Molly or a claim of calibrated probabilities.

| Measurement | Rule |
|---|---|
| Cat candidate | score ≥ 0.35 after class-aware NMS |
| Reliable single detection | exactly one candidate, score ≥ 0.60 |
| Cat area | **bounding-rectangle area / image area**, not segmented cat pixels |
| Good framing | rectangle share ≥ 25%, centre offset ≤ 20% of half image diagonal |
| Edge uncertainty | box within 2% of any image edge → request new photo |
| Multiple cats | request human review and a new unambiguous photo; never choose an identity |
| Small/off-centre cat | crop proposal only if other quality checks pass and safe margins/resolution are available |
| Crop margin | each side enlarged by max(48 px, 20% of that box dimension); require at least max(24 px, 15%) margin after fitting within the image |
| Resolution | crop short side ≥ 480 px, detected box short side ≥ 160 px, final planned box coverage ≥ 25% |
| Technical quality | existing sharpness/exposure/contrast thresholds remain unchanged |
| Post-processing | re-decode exact PNG bytes; remeasure technical quality and rerun YOLOX; eligible only when both pass |

The detector cannot reliably certify occlusion, anatomy, identity, complete paws/ears/tail or absence of strong occlusion. No fabricated visibility score is output: `HUMAN_REVIEW_REQUIRED` remains explicit. A separate translated review checkbox blocks original/proposal approval until the person confirms visibility and safe framing. The user explicitly accepted this limitation for Phase 4H with mandatory human visibility review before every approval.

## Pixel and workflow safety

Crop is an integer array slice plus lossless PNG encoding; no resizing, reconstruction, inpainting, feature synthesis or background replacement. Technical corrections run only when measured technical thresholds call for them. No derivative is stored when remeasurement fails. Originals and their SHA-256 remain immutable and separate from derivatives. No cat → no automatic technical-only acceptance. Legacy trace approval is blocked.

The browser shows before/after cat measurements, safe reason vocabulary and model name/version in the Decision Trace. Measurements are bounded and whitelisted in the private bridge and Worker. Job tokens carry the cat-policy version, so older tokens cannot authorize a new-policy approval. URLs and resource names are not forwarded. Blob previews still reuse verified bytes; `fetch(blob:...)` is forbidden. CSP is unchanged.

Four Gateway/Lambda calls per completely decided job remain create/analyze/result/decide. Gateway schema, API key, permissions, quota 40/day, secrets and storage configuration are unchanged. Human approval changes only the demonstration's main image, never publication.

## Evidence separation

1. Existing synthetic technical tests use an **explicit detector stub**. Their technical pixel measurements remain real OpenCV measurements; they are not detection evidence.
2. New geometry tests use controlled boxes to cover borders, low confidence, multiple cats and crop limits.
3. Real offline DNN tests use a separate CC0 photograph by Asabae2752, “A photograph of a cat lying down 0002”, obtained from Wikimedia Commons. Original SHA-256: `9d4355751377e74e70cf77b1bc13c8f5dcff52b1f2d1049a03b885b01b365279`. Deterministic local test transformations are downscaling, placing that image on a plain test canvas, duplication, blur and exposure reduction. They are test fixtures only, not production enhancement operations.
4. An offline browser test replays the exact measured trace and derivative from actual local OpenCV processing through a fake network transport. No cloud inference is claimed for that replay.
5. Molly is reserved for the subsequent user-driven real evaluation in normal Chrome after all release gates.

Official model/license: https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/object_detection_yolox

Local fixture license: https://commons.wikimedia.org/wiki/File:A_photograph_of_a_cat_lying_down_0002.jpg (CC0-1.0).
