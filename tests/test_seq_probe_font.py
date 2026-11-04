import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from seq_refine import probe_font


class TestProbeFont(unittest.TestCase):
    def test_missing_system_font_still_renders_comparison_labels(self):
        original = ImageFont.truetype

        def without_dejavu(font, *args, **kwargs):
            if isinstance(font, str):
                raise OSError('글꼴 없는 Kaggle 환경')
            return original(font, *args, **kwargs)

        with patch.object(ImageFont, 'truetype', side_effect=without_dejavu):
            font = probe_font()
            image = Image.new('RGB', (320, 32), 'white')
            ImageDraw.Draw(image).text((4, 3), 'Input balanced-v1 Target', font=font, fill='black')
        self.assertNotEqual(image.getextrema(), ((255, 255),) * 3)
