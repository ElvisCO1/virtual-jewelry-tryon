"""Manual validation samples and session identity, independent of the GUI."""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4


class SampleBuffer:
    def __init__(self):
        self.samples = []
        self.session_id = str(uuid4())
        self.created_at_utc = datetime.now(timezone.utc).isoformat()
        self.revision = 0
        self.saved_revision = 0
        self.saved_name = None

    @property
    def dirty(self):
        return self.revision != self.saved_revision

    @property
    def valid_count(self):
        return sum(not s['discarded'] for s in self.samples)

    def capture(self, snapshot, handedness):
        if snapshot is None:
            raise ValueError('Espera un fotograma del modo manual.')
        matches = [h for h in snapshot['hands'] if h['handedness'] == handedness]
        if len(matches) != 1 or not matches[0]['eligible']:
            raise ValueError('Selecciona una mano detectada sin ambigüedad.')
        if any(s['frame_id'] == snapshot['frame_id'] and s['hand']['handedness'] == handedness
               and not s['discarded'] for s in self.samples):
            raise ValueError('Ese fotograma ya está capturado para esta mano.')
        sample = deepcopy({k: v for k, v in snapshot.items() if k != 'hands'})
        sample.update(sample_id=str(uuid4()), captured_at_utc=datetime.now(timezone.utc).isoformat(),
                      hand=deepcopy(matches[0]), assessment='adequate', discarded=False)
        self.samples.append(sample)
        self.revision += 1
        return sample

    def discard_last(self):
        for sample in reversed(self.samples):
            if not sample['discarded']:
                sample['discarded'] = True
                self.revision += 1
                return sample
        raise ValueError('No hay muestras válidas para descartar.')
