"""IAM-authorized direct Lambda Invoke API. No public HTTP/function URL."""
import json
import os
from .imaging import runtime
from .jobs import Jobs
from .storage import S3Store, LocalStore

CV_VERSION = runtime().__version__
if CV_VERSION != "5.0.0":
    raise RuntimeError("Pinned OpenCV 5.0.0 required")
print("Grace Vision cv2.__version__ =", CV_VERSION)

def default_jobs():
    if os.environ.get("GRACEVISION_STORAGE") == "local":
        # Only explicitly selected for offline container tests; not in deployment template.
        return Jobs(LocalStore(os.environ["GRACEVISION_LOCAL_ROOT"]))
    import boto3
    from botocore.config import Config
    client = boto3.client("s3", region_name="eu-central-1", config=Config(
        signature_version="s3v4", retries={"max_attempts": 2, "mode": "standard"},
        connect_timeout=5, read_timeout=30))
    return Jobs(S3Store(client, os.environ["DATA_BUCKET"]))

def handle(event, jobs):
    try:
        if not isinstance(event, dict) or len(json.dumps(event)) > 8192:
            raise ValueError("Invalid or oversized event")
        operation = event.get("operation")
        schemas = {"create": {"operation", "uploads", "rights_confirmed"},
                   "analyze": {"operation", "job_id"}, "result": {"operation", "job_id"},
                   "decide": {"operation", "job_id", "decision"}}
        if operation not in schemas or set(event) != schemas[operation]:
            raise ValueError("Invalid operation or fields")
        if operation == "create":
            result = jobs.create(event["uploads"], event["rights_confirmed"])
        elif operation == "analyze":
            result = jobs.analyze(event["job_id"])
        elif operation == "result":
            result = jobs.result(event["job_id"])
        else:
            result = jobs.decide(event["job_id"], event["decision"])
        return {"statusCode": 200, "result": result, "opencv_version": CV_VERSION}
    except FileNotFoundError:
        return {"statusCode": 404, "error": "NOT_FOUND"}
    except FileExistsError:
        return {"statusCode": 409, "error": "ALREADY_EXISTS"}
    except (ValueError, TypeError, KeyError):
        return {"statusCode": 400, "error": "INVALID_REQUEST_OR_IMAGE"}
    except Exception:
        # Never log event bodies, signed URLs, image bytes or credentials.
        return {"statusCode": 500, "error": "PROCESSING_FAILED"}

def handler(event, context):
    return handle(event, default_jobs())
