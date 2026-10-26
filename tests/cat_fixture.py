"""Explicit detector test double for existing technical-imaging regression tests."""
def mock_detections(image):
    h,w=image.shape[:2]
    return [{"bbox":[int(.2*w),int(.2*h),int(.8*w),int(.8*h)],"confidence":.9}]
