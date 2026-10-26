# Security and operational limits

## Controls

- Public UI and processing are separated from GraceWays Animals production.
- Cloudflare Worker checks Turnstile, origin/CSRF state, rights confirmation, request size and short-lived capabilities.
- AWS keys, API Gateway key values, signed storage URLs and account identifiers are not shipped in the browser or this archive.
- S3 public access is blocked, ACLs are disabled, transport is required and objects are AES-256 encrypted.
- The Lambda role has prefix-scoped get/put/list access and no delete permission.
- Originals, derivatives, traces and approvals expire after seven days through prefix-specific lifecycle rules.
- Lambda reserved concurrency is 2. Gateway rate and burst are 2; the usage plan allows 40 operations per day.
- A fully decided job uses four Gateway/Lambda operations. Partial jobs also consume quota.
- A USD 5 monthly budget sends warnings only; it is not a hard spending cap.
- Approval records remain `published=false`; no production publishing route exists.

## Container scan disclosure

The released image scan reported 0 Critical, 7 High, 9 Medium, 5 Low and 1 Undefined findings. The seven High findings were limited to Amazon Linux base-image packages for which the manufacturer evidence said “Pending Fix” at review time. A time-limited competition exception documented reachability and accepted the residual risk. This does not prove that the image is vulnerability-free.

The affected system libraries were not loaded by the tested OpenCV/DNN application process, and the application exposes no user-controlled shell, model path or regular-expression program. Those facts narrow reachability; they do not erase the findings. Rebuild and rescan when manufacturer fixes become available.

## Privacy and rights

Only images with appropriate processing and demonstration rights may be uploaded. The rights checkbox records a user assertion; it does not independently prove ownership. Avoid personal data and remove unnecessary EXIF before public demonstrations.

This archive contains no user photos, Molly image, production export, browser profile, log, credential, token, account number, account-specific ARN or private endpoint. Infrastructure templates retain parameterized ARN expressions required for deployment.

## Model and policy limits

- A detector box is not a segmentation mask.
- Detection does not prove cat identity, coat preservation, injury state, anatomy or full visibility.
- The conservative crop never upscales or fills missing pixels.
- Severe blur, missing reliable information, multiple cats, uncertain edges or unsafe crop geometry lead to another image or a new-photo request.
- Human review of the original and proposal remains mandatory.

