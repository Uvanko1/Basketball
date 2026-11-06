import logging
import os
from datetime import date, datetime
from typing import Optional

import numpy as np
from edfio import Edf, EdfAnnotation, EdfSignal, Patient, Recording

from Project.core.session_recorder import SessionRecorder

logger = logging.getLogger(__name__)

CH_LABELS = ["EEG", "EMG", "EMG_INT", "ALPHA", "ALPHA_BASE", "EMG_BASE"]

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _translit_ascii(text: str) -> str:
    result = []
    for ch in text:
        lower = ch.lower()
        if lower in _TRANSLIT:
            piece = _TRANSLIT[lower]
            result.append(piece.upper() if ch.isupper() and piece else piece)
        elif ch == " ":
            result.append("_")
        else:
            result.append(ch)
    ascii_text = "".join(result).encode("ascii", errors="ignore").decode("ascii")
    return ascii_text or "X"


def _safe_filename(user_fio: str) -> str:
    return "".join(c for c in user_fio if c.isalnum() or c == "_").replace(" ", "_")


def build_session_filename(session_dir: str, user_fio: str, timestamp: Optional[str] = None) -> str:
    os.makedirs(session_dir, exist_ok=True)
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(session_dir, f"{_safe_filename(user_fio)}_{timestamp}.edf")


def _event_description(event) -> str:
    kind = event.event
    payload = event.payload

    if kind.startswith("THRESHOLD_"):
        return f'{kind}|score={payload["score"]}'
    if kind == "THRESHOLDS":
        return f'THRESHOLDS|th1={payload["th1"]}|th2={payload["th2"]}|th3={payload["th3"]}'
    if kind == "EMG_THRESHOLD":
        return f'EMG_THRESHOLD|value={payload["value"]}'
    if kind == "ALPHA_BAND":
        return f'ALPHA_BAND|low={payload["low"]}|high={payload["high"]}'
    return kind


def save_session_to_edf(
    filename: str,
    recorder: SessionRecorder,
    fs: float,
    alpha_baseline: float,
    emg_baseline: float,
    user_id: int,
    user_fio: str,
) -> bool:
    eeg_data = np.array(recorder.eeg_full, dtype=np.float64)
    emg_data = np.array(recorder.emg_full, dtype=np.float64)
    emg_int_data = np.array(recorder.emg_int_full, dtype=np.float64)
    alpha_data = np.array(recorder.alpha_full, dtype=np.float64)

    min_len = min(len(eeg_data), len(emg_data), len(alpha_data))
    if min_len == 0:
        return False

    eeg_data = eeg_data[-min_len:]
    emg_data = emg_data[-min_len:]
    emg_int_data = emg_int_data[-min_len:]
    alpha_data = alpha_data[-min_len:]

    alpha_base_val = alpha_baseline if alpha_baseline > 0 else 1e-6
    emg_base_val = emg_baseline if emg_baseline > 0 else 1e-6

    alpha_base = np.full(min_len, alpha_base_val)
    emg_base = np.full(min_len, emg_base_val)

    try:
        signals = [
            EdfSignal(eeg_data, sampling_frequency=fs, label="EEG"),
            EdfSignal(emg_data, sampling_frequency=fs, label="EMG"),
            EdfSignal(emg_int_data, sampling_frequency=fs, label="EMG_INT"),
            EdfSignal(alpha_data, sampling_frequency=fs, label="ALPHA"),
            EdfSignal(alpha_base, sampling_frequency=fs, label="ALPHA_BASE"),
            EdfSignal(emg_base, sampling_frequency=fs, label="EMG_BASE"),
        ]

        annotations = [
            EdfAnnotation(float(ev.time), None, _event_description(ev))
            for ev in recorder.game_events
            if ev.time <= min_len / fs
        ]

        patient = Patient(code=str(user_id), name=_translit_ascii(user_fio))
        recording = Recording(startdate=date.today(), additional=(f"Score_{recorder.score}",))

        edf = Edf(
            signals,
            patient=patient,
            recording=recording,
            starttime=datetime.now().time(),
            data_record_duration=min_len / fs,
            annotations=annotations,
        )
        edf.write(filename)
        logger.info("Сессия сохранена: %s (счёт=%s)", filename, recorder.score)
        return True

    except Exception:
        logger.exception("Ошибка сохранения EDF")
        return False
