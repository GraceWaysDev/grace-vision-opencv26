# Official AWS Lambda Python 3.12, linux/amd64; tag rechecked 2026-10-23 (unchanged).
FROM public.ecr.aws/lambda/python@sha256:c73d459e2dcaefa83c47c095560ad164d732251312b3371c7a49c46f1c4d4ff5 AS dependencies
COPY vendor/linux/ /wheels/
COPY infrastructure/requirements-linux.lock /requirements-linux.lock
RUN python -m pip install --no-index --no-cache-dir --find-links=/wheels --require-hashes --target=/opt/python -r /requirements-linux.lock

FROM public.ecr.aws/lambda/python@sha256:c73d459e2dcaefa83c47c095560ad164d732251312b3371c7a49c46f1c4d4ff5 AS runtime
# Confirmed RPM/curl/PCRE2 ALAS fixes; retain their exact versions.
RUN dnf --releasever=2023.12.20260928 upgrade -y \
    rpm-4.16.1.3-29.amzn2023.0.8 \
    rpm-libs-4.16.1.3-29.amzn2023.0.8 \
    curl-minimal-8.21.0-5.amzn2023.0.2 \
    libcurl-minimal-8.21.0-5.amzn2023.0.2 \
    pcre2-10.40-1.amzn2023.0.4 \
    pcre2-syntax-10.40-1.amzn2023.0.4 \
    && dnf clean all
# ALAS2023-2026-3204: update the OpenSSL variants installed by Lambda.
RUN dnf --releasever=2023.12.20261012 upgrade -y \
    openssl-snapsafe-libs-3.5.8-1.amzn2023.0.3 \
    openssl-fips-provider-latest-3.5.8-1.amzn2023.0.3 \
    && dnf clean all
COPY --from=dependencies /opt/python/ /opt/python/
ENV PYTHONPATH=/opt/python PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY vendor/models/yolox-s/model.onnx ${LAMBDA_TASK_ROOT}/models/yolox-s/model.onnx
COPY vendor/models/yolox-s/LICENSE ${LAMBDA_TASK_ROOT}/models/yolox-s/LICENSE
COPY vendor/models/yolox-s/provenance.json ${LAMBDA_TASK_ROOT}/models/yolox-s/provenance.json
RUN python -c "from app.cats import MODEL_SHA256; import hashlib; assert hashlib.sha256(open('/var/task/models/yolox-s/model.onnx','rb').read()).hexdigest() == MODEL_SHA256"
RUN python -c "import cv2; print(cv2.__version__); assert cv2.__version__ == '5.0.0'" && python -m pip check
CMD ["app.lambda_handler.handler"]

FROM runtime AS tests
COPY tests/ ${LAMBDA_TASK_ROOT}/tests/
COPY infrastructure/ ${LAMBDA_TASK_ROOT}/infrastructure/
RUN mkdir -p ${LAMBDA_TASK_ROOT}/evaluation
ENTRYPOINT ["python"]
CMD ["-m", "unittest", "discover", "-s", "tests", "-v"]
