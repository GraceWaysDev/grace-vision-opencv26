from unittest.mock import patch as cat_patch
from cat_fixture import mock_detections
import hashlib,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app.core import ROOT,sha,write_new,record,approve,process
from app.policy import decide
import cv2
if cv2.__version__.split(".")[0] != "5":
    raise RuntimeError("Tests require actual OpenCV 5")
class Safety(unittest.TestCase):
    def setUp(self):
        detector = cat_patch("app.cats.detections", side_effect=mock_detections)
        detector.start(); self.addCleanup(detector.stop)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/"evaluation");self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_hash_known_vector(self):
        self.assertEqual(sha(b"abc"),"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    def test_original_write_once(self):
        f=self.root/"originals/a";write_new(f,b"original")
        with self.assertRaises(FileExistsError): write_new(f,b"changed")
        self.assertEqual(f.read_bytes(),b"original")
    def test_policy_rejects_blur(self):
        m=dict(width=800,height=600,sharpness=2,brightness=125,contrast=45,dark_fraction=0,overexposed_fraction=0)
        self.assertEqual(decide(m)[0],"TRY_NEXT_IMAGE")
    def test_decisions_deterministic(self):
        m=dict(width=800,height=600,sharpness=200,brightness=125,contrast=45,dark_fraction=0,overexposed_fraction=0)
        self.assertEqual(decide(m)[0],"ACCEPT_ORIGINAL");m["brightness"]=65
        self.assertEqual(decide(m)[0],"ENHANCE");self.assertEqual(decide(m),decide(m))
    def test_major4_refused(self):
        from app.imaging import runtime
        class Wrong: __version__="4.99.0"
        with patch.dict(sys.modules,{"cv2":Wrong()}):
            with self.assertRaises(RuntimeError): runtime()
    def setup_trace(self):
        batch="a"*32;original="originals/a.png";write_new(self.root/original,b"fixture")
        from app.cats import MODEL, POLICY, inspect
        import numpy as np
        cat=inspect(np.zeros((640,800,3),np.uint8))
        trace=dict(cat_policy=POLICY,cat_model=MODEL,id=batch,selected=0,items=[dict(cat=cat,eligible=True,original=original,proposal=original,original_sha256=sha(b"fixture"),proposal_sha256=sha(b"fixture"))],status="AWAITING_HUMAN",published=False)
        record(self.root/f"traces/{batch}.json",trace);return batch
    def test_no_implicit_publication(self):
        batch=self.setup_trace();self.assertFalse((self.root/f"approvals/{batch}.json").exists())
        result=approve(batch,"APPROVE",self.root);self.assertEqual(result["status"],"APPROVED_LOCAL");self.assertFalse(result["published"])
        with self.assertRaises(FileExistsError): approve(batch,"APPROVE",self.root)
    def test_tamper_blocks_approval(self):
        batch=self.setup_trace();(self.root/"originals/a.png").write_bytes(b"tampered")
        with self.assertRaises(ValueError): approve(batch,"APPROVE",self.root)
        self.assertFalse((self.root/f"approvals/{batch}.json").exists())
    def test_path_rejected(self):
        with self.assertRaises(ValueError): approve("../outside","APPROVE",self.root)
class ActualImaging(unittest.TestCase):
    def setUp(self):
        detector = cat_patch("app.cats.detections", side_effect=mock_detections)
        detector.start(); self.addCleanup(detector.stop)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/"evaluation");self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def photo(self,brightness=130):
        import numpy as np
        from app.imaging import png_bytes
        return png_bytes(np.clip(np.random.default_rng(42).normal(brightness,40,(640,800,3)),0,255).astype(np.uint8))
    def test_real_version(self): self.assertEqual(cv2.__version__.split(".")[0],"5")
    def test_actual_measurements(self):
        import numpy as np
        from app.imaging import measure
        m=measure(np.full((600,800,3),100,dtype=np.uint8))
        self.assertEqual(m["brightness"],100);self.assertEqual(m["contrast"],0);self.assertEqual(m["sharpness"],0);self.assertEqual(m["pixels"],480000)
    def test_pipeline_original_and_hash(self):
        data=self.photo();trace=process([data,data],True,self.root)
        self.assertEqual((self.root/trace["items"][0]["original"]).read_bytes(),data)
        self.assertEqual(trace["items"][0]["original_sha256"],hashlib.sha256(data).hexdigest())
        self.assertFalse(trace["published"]);self.assertEqual(trace["status"],"AWAITING_HUMAN")
    def test_enhanced_remeasured(self):
        from app.imaging import measure,decode,enhance,png_bytes
        data=self.photo(65);trace=process([data,data],True,self.root);item=trace["items"][0]
        candidate, operations=enhance(decode(data), item["metrics"])
        self.assertTrue(operations);self.assertEqual(item["operations"],operations)
        self.assertEqual(item["after"],measure(decode(png_bytes(candidate))))
        self.assertEqual(trace["decision"],"REQUEST_NEW_PHOTO")
        self.assertFalse(item["eligible"]);self.assertEqual(item["proposal"],item["original"])
        self.assertEqual(list(self.root.glob("derivatives/**/*")),[])
    def test_strong_blur_requests_new(self):
        import numpy as np
        from app.imaging import png_bytes
        data=png_bytes(np.full((600,800,3),120,dtype=np.uint8));trace=process([data,data],True,self.root)
        self.assertEqual(trace["decision"],"REQUEST_NEW_PHOTO");self.assertTrue(all(not i["operations"] for i in trace["items"]))
        with self.assertRaises(ValueError): approve(trace["id"],"APPROVE",self.root)
    def test_gaussian_blur_is_not_rescued(self):
        from app.imaging import decode,png_bytes
        image=cv2.GaussianBlur(decode(self.photo()),(0,0),8)
        data=png_bytes(image)
        trace=process([data,data],True,self.root)
        self.assertEqual(trace["decision"],"REQUEST_NEW_PHOTO")
        self.assertTrue(all(i["metrics"]["sharpness"]<35 and not i["operations"] for i in trace["items"]))
    def test_exposure_fractions_from_pixels(self):
        import numpy as np
        from app.imaging import measure
        image=np.zeros((600,800,3),dtype=np.uint8)
        image[:,400:]=255
        metrics=measure(image)
        self.assertEqual(metrics["dark_fraction"],.5)
        self.assertEqual(metrics["overexposed_fraction"],.5)
        self.assertEqual(metrics["brightness"],127.5)
    def test_batch_and_rights(self):
        data=self.photo()
        with self.assertRaises(ValueError): process([],True,self.root)
        with self.assertRaises(ValueError): process([data,data],False,self.root)
if __name__=="__main__": unittest.main()
