import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from app import cats, core
from app.imaging import decode, measure, png_bytes

class CatGeometry(unittest.TestCase):
    def frame(self, boxes, shape=(1200,1600)):
        image=np.random.default_rng(7).integers(50,200,(*shape,3),dtype=np.uint8)
        with patch('app.cats.detections',return_value=boxes):
            return image,cats.inspect(image)

    def test_small_resolved_cat_crop(self):
        image,c=self.frame([{'bbox':[600,400,1000,800],'confidence':.9}])
        self.assertEqual(c['action'],'ENHANCE');self.assertAlmostEqual(c['area_fraction'],1/12)
        result=cats.crop(image,c);x,y,r,b=c['crop']
        np.testing.assert_array_equal(result,image[y:b,x:r])
        self.assertLessEqual(result.shape[0],image.shape[0]);self.assertLessEqual(result.shape[1],image.shape[1])
        self.assertEqual(c['crop_resolution'],[r-x,b-y])

    def test_well_framed_cat(self):
        _,c=self.frame([{'bbox':[400,200,1200,1000],'confidence':.9}])
        self.assertEqual(c['action'],'ACCEPT_ORIGINAL');self.assertIsNone(c['crop'])

    def test_edge_clipped_cat(self):
        _,c=self.frame([{'bbox':[0,200,800,1000],'confidence':.9}])
        self.assertTrue(c['edge_contact']);self.assertEqual(c['action'],'TRY_NEXT_IMAGE')

    def test_none_low_confidence_multiple(self):
        for boxes,reason in [([], 'CAT_NOT_RELIABLE'),([{'bbox':[300,300,800,900],'confidence':.5}],'CAT_NOT_RELIABLE'),([{'bbox':[300,300,800,900],'confidence':.9},{'bbox':[900,300,1400,900],'confidence':.8}],'MULTIPLE_CATS')]:
            with self.subTest(reason=reason):
                _,c=self.frame(boxes);self.assertEqual(c['reason'],reason);self.assertEqual(c['action'],'TRY_NEXT_IMAGE')

    def test_too_small_cannot_be_upscaled(self):
        _,c=self.frame([{'bbox':[600,400,700,550],'confidence':.9}])
        self.assertEqual(c['reason'],'CAT_CROP_RESOLUTION');self.assertEqual(c['action'],'TRY_NEXT_IMAGE')

    def test_old_trace_cannot_be_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);batch='a'*32
            core.record(root/f'traces/{batch}.json',{'selected':0,'items':[{'eligible':True}]})
            with self.assertRaisesRegex(ValueError,'Neue Katzenprüfung'):
                core.approve(batch,'APPROVE',root)

    def test_missing_visibility_is_never_certified(self):
        _,c=self.frame([{'bbox':[400,200,1200,1000],'confidence':.99}])
        self.assertEqual(c['visibility'],'HUMAN_REVIEW_REQUIRED')

class RealYoloX(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=Path('/fixtures/cc0-cat.jpg').read_bytes()
        if hashlib.sha256(source).hexdigest()!='4eaed17556ab8963816f50d99c2e11acc3c1abf13ce6803bdbdd335e3f56bb43':
            raise ValueError('Fixture changed')
        cls.photo=cv2.resize(decode(source),(800,600),interpolation=cv2.INTER_AREA)
        cls.small=np.full((1200,1600,3),125,np.uint8)
        cls.small[300:900,400:1200]=cls.photo

    def test_real_model_small_cat_crop_and_remeasure(self):
        data=png_bytes(self.small)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);trace=core.process([data],True,root);item=trace['items'][0]
            self.assertEqual(trace['opencv_version'],'5.0.0');self.assertEqual(trace['cat_model'],cats.MODEL)
            self.assertEqual(trace['decision'],'ENHANCE',json.dumps(item))
            self.assertEqual(item['cat']['reason'],'CAT_CROP_RECOMMENDED')
            self.assertEqual(item['after_cat']['action'],'ACCEPT_ORIGINAL')
            self.assertEqual((root/item['original']).read_bytes(),data)
            self.assertEqual(item['original_sha256'],core.sha(data))
            saved=(root/item['proposal']).read_bytes();self.assertEqual(core.sha(saved),item['proposal_sha256'])
            self.assertEqual(item['after'],measure(decode(saved)));self.assertEqual(item['after_cat'],cats.inspect(decode(saved)))
            self.assertNotEqual(item['original'],item['proposal']);self.assertTrue(item['eligible'])
            self.assertEqual([list(o)[0] for o in item['operations']],['crop'])
            x,y,r,b=item['cat']['crop'];np.testing.assert_array_equal(decode(saved),self.small[y:b,x:r])
            self.assertFalse((root/f"approvals/{trace['id']}.json").exists());self.assertFalse(trace['published'])
            approved=core.approve(trace['id'],'APPROVE',root);self.assertFalse(approved['published'])
            # The resulting framing remains acceptable; no synthetic second derivative.
            again=core.process([saved],True,root)
            self.assertEqual(again['decision'],'ACCEPT_ORIGINAL');self.assertEqual(again['items'][0]['proposal'],again['items'][0]['original'])

    def test_real_no_cat(self):
        c=cats.inspect(np.full((800,800,3),125,np.uint8))
        self.assertFalse(c['detected']);self.assertEqual(c['action'],'TRY_NEXT_IMAGE')

    def test_real_two_cats_no_identity_choice(self):
        image=np.full((900,1600,3),125,np.uint8);image[150:750,:800]=self.photo;image[150:750,800:]=self.photo
        c=cats.inspect(image)
        self.assertEqual(c['reason'],'MULTIPLE_CATS',json.dumps(c));self.assertIsNone(c['bbox'])

    def test_dark_and_blurry_real_cat_not_rescued(self):
        for image in [(self.small.astype(float)*.04).astype(np.uint8),cv2.GaussianBlur(self.small,(0,0),20)]:
            with self.subTest(),tempfile.TemporaryDirectory() as tmp:
                t=core.process([png_bytes(image)],True,Path(tmp))
                self.assertEqual(t['decision'],'REQUEST_NEW_PHOTO');self.assertFalse(t['items'][0]['eligible'])
                self.assertFalse(list(Path(tmp).glob('derivatives/**/*.png')))

    def test_runtime_exact_model_hash(self):
        self.assertEqual(cv2.__version__,'5.0.0')
        self.assertEqual(hashlib.sha256(Path('/var/task/models/yolox-s/model.onnx').read_bytes()).hexdigest(),cats.MODEL_SHA256)

if __name__=='__main__':unittest.main()
