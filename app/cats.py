"""Pinned OpenCV Zoo YOLOX-S, COCO cat (15), CPU; no identity/occlusion inference.

Pre/postprocessing adapted from OpenCV Zoo yolox.py/demo.py (Apache-2.0).
Bounding rectangle area is NOT segmented animal area. Human visibility review is
always required: this model cannot certify individual ears, paws or tail.
"""
import hashlib
import math
import threading
from pathlib import Path
import numpy as np
from .imaging import runtime

MODEL_SHA256 = "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"
MODEL_REVISION = "48b10fa505aeb51fbd127fc60a5c660040e823b7"
MODEL = {"name": "OpenCV Zoo YOLOX-S COCO", "version": "2022nov", "sha256": MODEL_SHA256,
         "revision": MODEL_REVISION, "backend": "OpenCV DNN CPU", "class": "cat"}
POLICY = "cat-frame-1"
_net = None
_lock = threading.Lock()

def detections(image):
    global _net
    cv = runtime()
    with _lock:
        if _net is None:
            model = Path(__file__).resolve().parents[1] / "models/yolox-s/model.onnx"
            if hashlib.sha256(model.read_bytes()).hexdigest() != MODEL_SHA256:
                raise RuntimeError("Cat model integrity check failed")
            _net = cv.dnn.readNet(str(model))
            _net.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
            _net.setPreferableTarget(cv.dnn.DNN_TARGET_CPU)
        h, w = image.shape[:2]
        scale = min(640 / h, 640 / w)
        # Only the detector input is resized. No output image is upscaled.
        rgb = cv.cvtColor(image, cv.COLOR_BGR2RGB)
        padded = np.full((640, 640, 3), 114, np.float32)
        rw, rh = max(1, int(w * scale)), max(1, int(h * scale))
        padded[:rh, :rw] = cv.resize(rgb, (rw, rh), interpolation=cv.INTER_LINEAR)
        _net.setInput(padded.transpose(2, 0, 1)[None])
        out = _net.forward().copy()[0]
    if out.shape != (8400, 85) or not np.isfinite(out).all():
        raise RuntimeError("Unexpected cat model output")
    grids, strides = [], []
    for stride in (8, 16, 32):
        x, y = np.meshgrid(np.arange(640 // stride), np.arange(640 // stride))
        grids.append(np.stack((x, y), 2).reshape(-1, 2))
        strides.append(np.full((x.size, 1), stride))
    st = np.concatenate(strides)
    centers = (out[:, :2] + np.concatenate(grids)) * st
    sizes = np.exp(np.clip(out[:, 2:4], -20, 20)) * st
    boxes = np.concatenate((centers - sizes / 2, sizes), axis=1) / scale
    scores = out[:, 4:5] * out[:, 5:]
    labels, confidence = scores.argmax(axis=1), scores.max(axis=1)
    keep = cv.dnn.NMSBoxesBatched(boxes.tolist(), confidence.tolist(), labels.tolist(), .35, .5)
    found = []
    for index in np.asarray(keep).reshape(-1):
        if labels[index] != 15:
            continue
        x, y, bw, bh = boxes[index]
        box = [max(0, min(w, math.floor(x))), max(0, min(h, math.floor(y))),
               max(0, min(w, math.ceil(x + bw))), max(0, min(h, math.ceil(y + bh)))]
        if box[2] > box[0] and box[3] > box[1]:
            found.append({"bbox": box, "confidence": float(confidence[index])})
    return sorted(found, key=lambda d: (-d["confidence"], d["bbox"]))[:20]

def inspect(image):
    h, w = image.shape[:2]
    found = detections(image)
    cats = []
    for d in found:
        x0, y0, x1, y1 = d["bbox"]
        cats.append({**d, "area_fraction": (x1-x0)*(y1-y0)/(w*h),
                     "center_offset": math.hypot((x0+x1)/2-w/2, (y0+y1)/2-h/2)/math.hypot(w/2,h/2),
                     "edge_contact": x0 <= .02*w or y0 <= .02*h or x1 >= .98*w or y1 >= .98*h})
    info = {"detected": bool(cats), "count": len(cats), "detections": cats,
            "confidence": cats[0]["confidence"] if cats else 0.,
            "bbox": cats[0]["bbox"] if len(cats)==1 else None,
            "area_fraction": cats[0]["area_fraction"] if len(cats)==1 else None,
            "center_offset": cats[0]["center_offset"] if len(cats)==1 else None,
            "edge_contact": any(c["edge_contact"] for c in cats),
            "visibility": "HUMAN_REVIEW_REQUIRED", "crop": None, "crop_resolution": None,
            "reason": "CAT_NOT_RELIABLE", "action": "TRY_NEXT_IMAGE"}
    if len(cats)>1:
        info["reason"] = "MULTIPLE_CATS"
        return info
    if not cats or cats[0]["confidence"] < .60:
        return info
    if info["edge_contact"]:
        info["reason"] = "CAT_EDGE_UNCERTAIN"
        return info
    if info["area_fraction"] >= .25 and info["center_offset"] <= .20:
        info.update(reason="CAT_FRAME_OK", action="ACCEPT_ORIGINAL")
        return info
    x0, y0, x1, y1 = info["bbox"]
    bw, bh = x1-x0, y1-y0
    cw, ch = min(w, max(480, math.ceil(bw + 2*max(48, .20*bw)))), min(h, max(480, math.ceil(bh + 2*max(48, .20*bh))))
    left = min(w-cw, max(0, math.floor((x0+x1-cw)/2)))
    top = min(h-ch, max(0, math.floor((y0+y1-ch)/2)))
    info.update(crop=[left, top, left+cw, top+ch], crop_resolution=[cw, ch])
    if min(cw,ch)<480 or min(bw,bh)<160 or bw*bh/(cw*ch)<.25:
        info["reason"] = "CAT_CROP_RESOLUTION"
        return info
    # Require the entire conservative safety margin, never silently clip it.
    if x0-left < max(24,.15*bw) or y0-top < max(24,.15*bh) or left+cw-x1 < max(24,.15*bw) or top+ch-y1 < max(24,.15*bh):
        info["reason"] = "CAT_MARGIN_UNCERTAIN"
        return info
    info.update(reason="CAT_CROP_RECOMMENDED", action="ENHANCE")
    return info

def crop(image, info):
    if info["action"] != "ENHANCE" or info["reason"] != "CAT_CROP_RECOMMENDED":
        raise ValueError("No safe crop available")
    left, top, right, bottom = info["crop"]
    return image[top:bottom, left:right].copy()
