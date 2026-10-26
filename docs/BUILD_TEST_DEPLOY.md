# Build, test and deploy

## Fixed inputs

- AWS Lambda Python 3.12 base image pinned by digest in `infrastructure/Dockerfile`
- `opencv-python-headless==5.0.0.93` (`cv2.__version__ == 5.0.0`)
- NumPy 2.3.5
- Pillow 12.3.0
- OpenCV Zoo YOLOX-S revision `48b10fa505aeb51fbd127fc60a5c660040e823b7`
- Model SHA-256 `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`

All Linux wheels used by the container build are included under `vendor/linux/` and pinned by SHA-256 in `infrastructure/requirements-linux.lock` and `infrastructure/dependencies-linux.json`.

## Build and test the Lambda image

From the archive root:

```bash
docker build --platform linux/amd64 --provenance=false --target tests \
  -f infrastructure/Dockerfile -t gracevision-jury-tests .
docker run --rm --network none --memory 2g --cpus 2 \
  --mount "type=bind,source=$PWD/tests/fixtures/cc0-cat.jpg,target=/fixtures/cc0-cat.jpg,readonly" \
  gracevision-jury-tests
docker build --platform linux/amd64 --provenance=false --target runtime \
  -f infrastructure/Dockerfile -t gracevision-jury-runtime .
```

The tests stage runs the Python unittest suite. It verifies OpenCV 5.0.0, the exact model hash, real OpenCV DNN inference on the CC0 fixture, image-integrity rules, all four policy paths and infrastructure constraints. The container test run is network-disabled.

## Test the jury Worker

The non-browser tests use only Node built-ins and local fakes:

```bash
node --test \
  integration/jury-worker/test/cats.test.mjs \
  integration/jury-worker/test/gateway-permission.test.cjs \
  integration/jury-worker/test/single-photo.test.mjs \
  integration/jury-worker/test/worker-tests.mjs
```

The original Chrome/Playwright regression harness was workstation-specific and is deliberately not presented as a portable command in this jury archive. Its results are disclosed in the technical report. The public endpoint remains directly testable by a judge.

## Infrastructure validation

With `cfn-lint` installed:

```bash
cfn-lint -t \
  infrastructure/repository.json \
  infrastructure/template.json \
  infrastructure/budget.json \
  integration/jury-worker/gateway.json \
  -r eu-central-1
```

The templates are parameterized and contain no account number, private endpoint, secret or image URI.

## Deployment outline

Deployment is intentionally reviewed rather than one-click:

1. Create or verify the ECR repository with `infrastructure/repository.json`.
2. Build and test the immutable runtime image, push it once, and capture its ECR digest.
3. Review the ECR scan. Do not claim that an image is vulnerability-free.
4. Deploy `infrastructure/template.json` with the exact digest as `ImageUri`.
5. Deploy `integration/jury-worker/gateway.json` with the existing Lambda function name. The template creates the fixed Gateway method, request validator, key/usage plan and narrow Lambda permission.
6. Configure the jury Worker using server-side secret names only: `GATEWAY_API_KEY`, `GATEWAY_ENDPOINT`, `TURNSTILE_SECRET_KEY`, and `JOB_TOKEN_SECRET`. `TURNSTILE_SITE_KEY` is public configuration.
7. Upload a Worker version, inspect bindings with no secret values, then activate it separately.
8. Run negative security checks before any positive image job; then run one controlled rights-cleared end-to-end test.

The checked-in Wrangler configuration has no custom route and targets only the separate workers.dev jury Worker. Never point rollback or deployment commands at GraceWays Animals production.

## Deployed-state disclosure

The public demo uses a deployed OpenCV 5 Lambda and the checked-in jury workflow. A later local session-renewal change is not in this archive because it was not deployed. Reload the public page before a new test if the 15-minute session may have expired.

