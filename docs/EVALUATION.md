# Evaluation

## Method

Evaluation separates deterministic synthetic controls from rights-cleared real-photo evidence. It does not combine them into an invented accuracy score.

The measured qualities are resolution, Laplacian sharpness, mean brightness, dark/clipped shares and luminance contrast. Cat-framing evidence includes detector confidence, bounding-box area, center offset and edge contact. A bounding box is not a segmentation mask and does not certify identity, anatomy or unobstructed visibility.

## AWS control-path evidence

| Evidence | System action | Result |
| --- | --- | --- |
| Synthetic suitable control | `ACCEPT_ORIGINAL` | No derivative; original hash preserved |
| Synthetic correctable control | `ENHANCE` | Separate derivative; exact saved bytes remeasured |
| Synthetic unusable control | `REQUEST_NEW_PHOTO` | No reconstruction or fabricated detail |

Recorded correctable-control measurements:

| Metric | Original | Derivative |
| --- | ---: | ---: |
| Resolution | 800 × 640 | 800 × 640 |
| Brightness | 82.132 | 94.306 |
| Sharpness | 7610.638 | 8299.301 |
| Contrast | 43.468 | 45.392 |

These measurements came from the real AWS OpenCV 5.0.0 workflow. They demonstrate plumbing and policy branches, not real-photo accuracy.

## Rights-cleared real-cat fixture

`tests/fixtures/cc0-cat.jpg` is a CC0 Wikimedia Commons image recorded in `tests/fixtures/provenance.json`. It is used for real OpenCV DNN inference and crop geometry tests. In the controlled framing test, the detected box occupied 8.234% of the synthetic canvas before cropping and 50.932% after the conservative crop; confidence was 0.908 before and 0.937 after. This one image is not a benchmark.

## Molly boundary case

A rights-cleared user test with Molly produced `REQUEST_NEW_PHOTO` even though darkness and slight blur were technically correctable. Detector confidence was 86.8% and the bounding box covered 77.9% of the frame, but the strict edge-contact rule rejected the image. No derivative was approved and nothing was published.

This is a known **false rejection** and calibration target, not a successful enhancement. The Molly image is deliberately absent from the archive.

## Verification record

- Phase 4H: 358 tests and 437 browser assertions passed for the cat-framing release.
- The final container confirmed OpenCV 5.0.0, the exact model hash and CPU DNN inference.
- AWS traces demonstrated immutable originals, separate derivatives, remeasurement and `published=false` decisions.
- A later local session-renewal change passed 107 targeted checks but is not claimed as deployed and is not mixed into this source archive.

## Error analysis and limits

- The sample is too small for sensitivity, specificity or user-impact claims.
- YOLOX-S is trained for general object detection, not shelter-photo composition, identity or welfare assessment.
- Edge contact is intentionally conservative and can reject usable close-ups.
- Occlusion, missing body parts, coat preservation and medical relevance require human inspection.
- Global gamma/contrast/sharpening can change perception even without synthesizing pixels; reviewers must reject misleading results.
- Inputs are limited to JPEG/PNG, at most 2 MiB and 1600 × 1600 pixels in the public demo.

Next evaluation work should use a larger rights-cleared set spanning lighting, blur, backgrounds, cat sizes, coats, poses, partial occlusion and multiple cats, with errors reviewed by animal-welfare users.

