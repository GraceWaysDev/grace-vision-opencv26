"""Download pinned Windows CPython 3.12 wheels from PyPI, checking published SHA-256."""
import hashlib,json,pathlib,urllib.request,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parents[1]
PINS={"opencv-python-headless":"5.0.0.93","numpy":"2.3.5","pillow":"12.3.0"}
class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urllib.parse.urlsplit(newurl).hostname not in {"pypi.org","files.pythonhosted.org"}:
            raise RuntimeError("Non-PyPI redirect blocked")
        return super().redirect_request(req,fp,code,msg,headers,newurl)
def main():
    opener=urllib.request.build_opener(OfficialRedirect)
    target=ROOT/"vendor";target.mkdir(exist_ok=True)
    entries=[]
    for name,version in PINS.items():
        url=f"https://pypi.org/pypi/{name}/{version}/json"
        with opener.open(url,timeout=60) as r: data=json.load(r)
        (target/f"{name}-{version}.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
        candidates=[f for f in data["urls"] if f["filename"].endswith("win_amd64.whl") and (("cp37-abi3" in f["filename"]) if name.startswith("opencv") else ("cp312-cp312" in f["filename"]))]
        if len(candidates)!=1: raise RuntimeError(f"Ambiguous wheel: {name}")
        f=candidates[0]
        if f["yanked"] or urllib.parse.urlsplit(f["url"]).hostname!="files.pythonhosted.org": raise RuntimeError("Unacceptable artifact")
        dest=target/f["filename"]
        with opener.open(f["url"],timeout=180) as response: blob=response.read()
        actual=hashlib.sha256(blob).hexdigest()
        if actual!=f["digests"]["sha256"]: raise RuntimeError("Checksum mismatch")
        dest.write_bytes(blob)
        entries.append({"name":name,"version":version,"metadata_url":url,"download_url":f["url"],"filename":f["filename"],"sha256":actual,"bytes":len(blob),"license":data["info"].get("license_expression") or data["info"].get("license"),"requires_dist":data["info"].get("requires_dist"),"upload_time":f["upload_time_iso_8601"]})
        print(name,version,actual)
    (ROOT/"dependency-lock.json").write_text(json.dumps(entries,indent=2),encoding="utf-8")
    (ROOT/"requirements.lock").write_text("\n".join(e["name"]+"=="+e["version"]+" --hash=sha256:"+e["sha256"] for e in entries)+"\n",encoding="utf-8")
if __name__=="__main__": main()
