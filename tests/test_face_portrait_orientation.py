import unittest
from PIL import Image, ImageDraw, ImageOps
import app
from tests import test_moments as legacy


class PortraitOrientationTests(unittest.TestCase):
    setUp = legacy.MomentDetectionTests.setUp
    tearDown = legacy.MomentDetectionTests.tearDown

    def test_portrait_crop_uses_detection_orientation_for_all_exif_transforms(self):
        for orientation in range(1, 9):
            with self.subTest(orientation=orientation):
                source = Image.new('RGB', (240, 160), 'red')
                draw = ImageDraw.Draw(source)
                draw.rectangle((120, 0, 239, 79), fill='blue')
                draw.rectangle((0, 80, 119, 159), fill='green')
                draw.rectangle((120, 80, 239, 159), fill='yellow')
                exif = Image.Exif()
                exif[274] = orientation
                path = self.originals / f'portrait-{orientation}.jpg'
                source.save(path, exif=exif, quality=100)
                with Image.open(path) as raw:
                    display = ImageOps.exif_transpose(raw)
                    expected = display.getpixel((30, 30))
                    width, height = display.size
                with app.closing(app.get_conn()) as conn:
                    pid = conn.execute('INSERT INTO photos(rel_path,filename,width,height) VALUES(?,?,?,?)',
                                       (path.name,path.name,width,height)).lastrowid
                    fid = conn.execute("INSERT INTO faces(photo_id,bbox_x,bbox_y,bbox_w,bbox_h,created_at) VALUES(?,20,20,20,20,'2026')", (pid,)).lastrowid
                    conn.commit()
                self.assertTrue(app._build_face_thumb(fid))
                with Image.open(self.thumbs / app._face_thumb_name(fid)) as portrait:
                    actual = portrait.getpixel((portrait.width//2, portrait.height//2))
                self.assertLess(max(abs(a-b) for a,b in zip(expected,actual)), 10)
