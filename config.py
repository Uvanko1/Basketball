import os
import sys
from dataclasses import dataclass


def _bundle_root() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _app_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


PROJECT_ROOT: str = _bundle_root()
APP_DIR: str = _app_root()
RESOURCES_DIR: str = os.path.join(PROJECT_ROOT, "Resources")
EEGLIB_DIR: str = os.path.join(PROJECT_ROOT, "EEGLib")
SESSION_DATA_DIR: str = os.path.join(APP_DIR, "session_data")
DB_PATH: str = os.path.join(APP_DIR, "app_data.db")

SOUND_BALL_PATH: str = os.path.join(RESOURCES_DIR, "ball_cut.wav")
SOUND_RING_PATH: str = os.path.join(RESOURCES_DIR, "ring.wav")
SOUND_CLAPS_PATH: str = os.path.join(RESOURCES_DIR, "claps.wav")

UNIOR_DLL_NAME: str = "unior_v4.dll"
UNIOR_DLL_PATH: str = os.path.join(EEGLIB_DIR, UNIOR_DLL_NAME)


@dataclass(frozen=True)
class SignalConfig:
    sample_rate_hz: float = 250.0
    window_sec: float = 1.0
    step_sec: float = 0.1
    alpha_update_step_sec: float = 0.0
    calibration_sec: float = 5.0
    min_trigger_interval_sec: float = 1.0
    buffer_seconds: float = 5.0


@dataclass(frozen=True)
class ThresholdDefaults:
    threshold1_percent: int = 25
    threshold2_percent: int = 50
    threshold3_percent: int = 75
    emg_threshold_uv: float = 5.0
    alpha_low_hz: float = 9.0
    alpha_high_hz: float = 11.0


SIGNAL = SignalConfig()
THRESHOLDS = ThresholdDefaults()

EVENT_THRESHOLDS = "THRESHOLDS"
EVENT_EMG_THRESHOLD = "EMG_THRESHOLD"
EVENT_ALPHA_BAND = "ALPHA_BAND"
EVENT_THRESHOLD_HIT_PREFIX = "THRESHOLD_"
THRESHOLD_SCORES = {1: 1, 2: 2, 3: 3}