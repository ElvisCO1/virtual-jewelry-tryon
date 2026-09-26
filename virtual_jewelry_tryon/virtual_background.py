"""Optional display-only person segmentation and background compositing."""
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .config import PROJECT_ROOT

BACKGROUND_DIRECTORY = PROJECT_ROOT / 'assets' / 'backgrounds'
MODEL = PROJECT_ROOT / 'models' / 'selfie_segmenter.tflite'


class VirtualBackground:
    def __init__(self):
        self.enabled = False
        self.path = None
        self.image = None
        self._segmenter = None
        self._fitted = None
        self.error = None

    def load(self, path):
        # imdecode supports Windows paths containing non-ASCII characters.
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('No se pudo leer la imagen de fondo.')
        self.image, self.path = image, Path(path)
        self._fitted = None

    def prepare(self):
        if self.image is None:
            raise ValueError('Selecciona una imagen de fondo primero.')
        if self._segmenter is None:
            if not MODEL.is_file():
                raise FileNotFoundError('Falta models/selfie_segmenter.tflite. Consulta README.md.')
            self._segmenter = vision.ImageSegmenter.create_from_options(
                vision.ImageSegmenterOptions(base_options=python.BaseOptions(model_asset_path=str(MODEL)),
                    running_mode=vision.RunningMode.IMAGE, output_confidence_masks=True,
                    output_category_mask=False))

    def apply(self, frame):
        if not self.enabled:
            return frame
        try:
            self.prepare()
            height, width = frame.shape[:2]
            # The model sees a reduced copy; hand detection already used the original.
            small = cv2.resize(frame, (256, 256))
            result = self._segmenter.segment(mp.Image(image_format=mp.ImageFormat.SRGB,
                data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB)))
            mask = result.confidence_masks[0].numpy_view()
            alpha = cv2.resize(mask, (width, height), interpolation=cv2.INTER_LINEAR)
            alpha = np.clip((alpha - .1) / .8, 0, 1)[:, :, None]
            if self._fitted is None or self._fitted.shape != frame.shape:
                ih, iw = self.image.shape[:2]
                scale = max(width / iw, height / ih)
                fitted = cv2.resize(self.image, (max(width, round(iw*scale)), max(height, round(ih*scale))))
                y, x = (fitted.shape[0]-height)//2, (fitted.shape[1]-width)//2
                self._fitted = fitted[y:y+height, x:x+width]
            return np.rint(frame * alpha + self._fitted * (1-alpha)).astype(np.uint8)
        except (OSError, ValueError, RuntimeError, cv2.error) as error:
            self.error = str(error)
            self.enabled = False
            self.close()
            return frame

    def close(self):
        if self._segmenter is not None:
            self._segmenter.close()
            self._segmenter = None
