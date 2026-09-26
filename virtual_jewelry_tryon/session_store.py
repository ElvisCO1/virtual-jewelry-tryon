"""Save independent JSON revisions without overwriting previous evidence."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import uuid4


DEFAULT_DIRECTORY = Path(__file__).resolve().parent.parent / 'data' / 'sessions'
SCHEMA_VERSION = 1


def save_session(buffer, name, directory=DEFAULT_DIRECTORY):
    """Mark saved only after a complete write; failed saves retain in-memory data."""
    name = name.strip()
    if not name or len(name) > 80:
        raise ValueError('Escribe un nombre de prueba entre 1 y 80 caracteres.')
    if not buffer.samples:
        raise ValueError('Captura al menos una muestra antes de guardar.')
    payload = {
        'schema_version': SCHEMA_VERSION,
        'session_id': buffer.session_id,
        'name': name,
        'created_at_utc': buffer.created_at_utc,
        'saved_at_utc': datetime.now(timezone.utc).isoformat(),
        'revision': buffer.revision,
        'valid_count': buffer.valid_count,
        'samples': buffer.samples,
    }
    # Serialize before creating a file; reject non-finite measurements.
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r'[^a-zA-Z0-9_-]+', '_', name).strip('_') or 'prueba'
    path = directory / f'{slug}_{buffer.session_id}_r{buffer.revision}_{uuid4().hex[:8]}.json'
    # Exclusive creation also prevents collisions from replacing another session.
    with path.open('x', encoding='utf-8') as stream:
        try:
            stream.write(encoded + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            path.unlink(missing_ok=True)
            raise
    buffer.saved_revision = buffer.revision
    buffer.saved_name = name
    return path
