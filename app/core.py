import hashlib
import json
import re
import uuid
from pathlib import Path
from datetime import datetime, timezone
from .policy import decide, POLICY_VERSION

ROOT = Path(__file__).resolve().parents[1]
def sha(data):
    return hashlib.sha256(data).hexdigest()
def now():
    return datetime.now(timezone.utc).isoformat()
def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(data)
def record(path, value):
    write_new(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))
def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        raise ValueError("Ungültige Kennung.")
    return value

def process(images, rights, root=ROOT, *, batch=None):
    from .imaging import runtime, decode, measure, enhance, png_bytes
    from .cats import inspect, crop, MODEL, POLICY
    if rights is not True:
        raise ValueError("Nutzungsrechte und Katzenmotiv müssen bestätigt werden.")
    if not 1 <= len(images) <= 5:
        raise ValueError("Bitte 1 bis 5 Fotos auswählen.")
    cv = runtime()
    # Validate the complete batch before accepting any original.
    decoded = [decode(data) for data in images]
    batch = identifier(batch) if batch is not None else uuid.uuid4().hex
    items = []
    for index, (data, image) in enumerate(zip(images, decoded)):
        item_id = str(index)
        suffix = ".png" if data.startswith(b"\x89PNG") else ".jpg"
        original = f"originals/{batch}/{item_id}{suffix}"
        write_new(root/original, data)
        m = measure(image)
        action, reasons = decide(m)
        cat = inspect(image)
        if cat["action"] == "TRY_NEXT_IMAGE":
            action = "TRY_NEXT_IMAGE"
        elif action != "TRY_NEXT_IMAGE" and cat["action"] == "ENHANCE":
            action = "ENHANCE"
        item = {"index": index, "original": original, "original_sha256": sha(data), "metrics": m,
                "action": action, "reasons": reasons, "proposal": original, "proposal_sha256": sha(data),
                "cat": cat, "operations": [], "eligible": action == "ACCEPT_ORIGINAL"}
        if action == "ENHANCE":
            result, operations = image.copy(), []
            if cat["action"] == "ENHANCE":
                result = crop(image, cat)
                operations.append({"crop": cat["crop"], "upscaled": False})
            current = measure(result)
            if decide(current)[0] == "ENHANCE":
                result, technical = enhance(result, current)
                operations.extend(technical)
            encoded = png_bytes(result)
            saved_candidate = decode(encoded)
            after = measure(saved_candidate)  # Re-measure exact saved candidate bytes.
            after_cat = inspect(saved_candidate)
            post_action, post_reasons = decide(after)
            item.update(after=after, after_cat=after_cat, operations=operations,
                        eligible=post_action == "ACCEPT_ORIGINAL" and after_cat["action"] == "ACCEPT_ORIGINAL",
                        post_action=post_action, post_reasons=post_reasons)
            if item["eligible"]:
                path = f"derivatives/{batch}/{item_id}.png"
                write_new(root/path, encoded)
                item.update(proposal=path, proposal_sha256=sha(encoded))
            else:
                item["action"] = "TRY_NEXT_IMAGE"
                item["reasons"].append("Vorschlag erfüllt die Schwellen nicht; nächstes Foto prüfen.")
        items.append(item)
    candidates = [i for i in items if i["eligible"]]
    # Input order breaks equal scores deterministically; never selects a rejected image.
    selected = max(candidates, key=lambda i: ((i.get("after") or i["metrics"])["sharpness"], -i["index"])) if candidates else None
    trace = {"id": batch, "created_at": now(), "opencv_version": cv.__version__, "policy": POLICY_VERSION,
             "cat_policy": POLICY, "cat_model": MODEL,
             "rights_confirmed": True, "rights_scope": "user confirms permission for local processing and cat subject",
             "items": items, "selected": selected["index"] if selected else None,
             "decision": selected["action"] if selected else "REQUEST_NEW_PHOTO",
             "status": "AWAITING_HUMAN", "published": False}
    record(root/f"traces/{batch}.json", trace)
    return trace

def load(batch, root=ROOT):
    identifier(batch)
    return json.loads((root/f"traces/{batch}.json").read_text(encoding="utf-8"))

def approve(batch, decision, root=ROOT):
    trace = load(batch, root)
    if decision not in ("APPROVE", "REQUEST_NEW_PHOTO"):
        raise ValueError("Ungültige Entscheidung.")
    selected = trace["selected"]
    if decision == "APPROVE":
        from .cats import POLICY, MODEL
        if trace.get("cat_policy") != POLICY or trace.get("cat_model") != MODEL:
            raise ValueError("Neue Katzenprüfung erforderlich; altes Ergebnis nicht freigeben.")
        if selected is None or not trace["items"][selected]["eligible"]:
            raise ValueError("Kein freigabefähiger Vorschlag.")
        item = trace["items"][selected]
        cat = item.get("after_cat") or item.get("cat")
        if not cat or cat["action"] != "ACCEPT_ORIGINAL" or cat["count"] != 1 or cat["edge_contact"]:
            raise ValueError("Keine bestätigte Katzenrahmenprüfung.")
        for path, expected in [(item["original"], item["original_sha256"]), (item["proposal"], item["proposal_sha256"])]:
            if sha((root/path).read_bytes()) != expected:
                raise ValueError("Integritätsprüfung fehlgeschlagen; keine Freigabe.")
    result = {"batch": batch, "decision": decision, "at": now(), "selected": selected,
              "status": "APPROVED_LOCAL" if decision == "APPROVE" else "REQUEST_NEW_PHOTO",
              "published": False, "proposal_sha256": trace["items"][selected]["proposal_sha256"] if selected is not None else None}
    record(root/f"approvals/{batch}.json", result)  # Immutable first human decision.
    return result
