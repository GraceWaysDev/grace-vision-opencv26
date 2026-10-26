# Third-party components

| Component | Fixed version / revision | License evidence |
| --- | --- | --- |
| OpenCV Python headless | 5.0.0.93 (`cv2` 5.0.0) | `docs/licenses/opencv-python-headless-*` |
| NumPy | 2.3.5 | `docs/licenses/numpy-*` |
| Pillow | 12.3.0 | `docs/licenses/pillow-*` |
| OpenCV Zoo YOLOX-S COCO | Revision `48b10fa505aeb51fbd127fc60a5c660040e823b7`, SHA-256 `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063` | `vendor/models/yolox-s/LICENSE` and `provenance.json` |
| CC0 cat test fixture | Packaged SHA-256 `4eaed17556ab8963816f50d99c2e11acc3c1abf13ce6803bdbdd335e3f56bb43`; source hash retained in provenance | `tests/fixtures/provenance.json` |

Linux wheel filenames, byte counts, source URLs and SHA-256 values are recorded in `infrastructure/dependencies-linux.json` and enforced by `infrastructure/requirements-linux.lock` during the offline Docker build.

