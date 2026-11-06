import logging

from PyQt5 import QtCore

from Project.config import SIGNAL, THRESHOLDS
from Project.core import signal_processing
from Project.core.threshold_evaluator import ThresholdState

logger = logging.getLogger(__name__)


class BaseTester(QtCore.QThread):
    sound_signal = QtCore.pyqtSignal(int)
    error_signal = QtCore.pyqtSignal(str)
    alpha_band_changed_signal = QtCore.pyqtSignal(float, float)
    thresholds_changed_signal = QtCore.pyqtSignal(float, float, float)
    emg_changed_signal = QtCore.pyqtSignal(float)
    baseline_calculated_signal = QtCore.pyqtSignal(float, float)
    alpha_value_signal = QtCore.pyqtSignal(float)

    def __init__(
        self,
        th1_percent: float = THRESHOLDS.threshold1_percent,
        th2_percent: float = THRESHOLDS.threshold2_percent,
        th3_percent: float = THRESHOLDS.threshold3_percent,
        emg: float = THRESHOLDS.emg_threshold_uv,
        alpha_low: float = THRESHOLDS.alpha_low_hz,
        alpha_high: float = THRESHOLDS.alpha_high_hz,
        fs: float = SIGNAL.sample_rate_hz,
    ):
        super().__init__()

        self.Fs = fs
        self.window_size = int(fs * SIGNAL.window_sec)
        self.step_samples = int(fs * SIGNAL.step_sec)
        self.alpha_update_samples = max(1, int(fs * SIGNAL.alpha_update_step_sec))
        self.min_trigger_interval = SIGNAL.min_trigger_interval_sec

        self.alpha_low = alpha_low
        self.alpha_high = alpha_high

        self.th1 = th1_percent / 100.0
        self.th2 = th2_percent / 100.0
        self.th3 = th3_percent / 100.0

        self.emg_int_threshold = emg
        self.current_emg_int = 0.0

        self.alpha_baseline = None
        self.emg_baseline = None
        self.baseline_calculated = False

        self.threshold_state = ThresholdState()
        self.sample_counter = 0
        self._alpha_counter = 0
        self._last_alpha = 0.0
        self.is_running = False
        self.backed = False

        self.alpha_band_changed_signal.connect(self.update_alpha_band)
        self.thresholds_changed_signal.connect(self.update_thresholds)
        self.emg_changed_signal.connect(self.update_emg)

    @QtCore.pyqtSlot(float, float, float)
    def update_thresholds(self, th1: float, th2: float, th3: float) -> None:
        logger.info("Новые пороги: %.0f%%, %.0f%%, %.0f%%", th1 * 100, th2 * 100, th3 * 100)
        self.th1, self.th2, self.th3 = th1, th2, th3

    @QtCore.pyqtSlot(float)
    def update_emg(self, emg: float) -> None:
        logger.info("Новый порог ЭМГ: %s", emg)
        self.emg_int_threshold = emg

    @QtCore.pyqtSlot(float, float)
    def update_alpha_band(self, low: float, high: float) -> None:
        if low < high:
            self.alpha_low, self.alpha_high = low, high
            logger.info("Новый диапазон альфа-ритма: %.1f-%.1f Гц", low, high)

    def calculate_alpha_amplitude(self, data_segment) -> float:
        try:
            return signal_processing.calculate_alpha_amplitude(
                data_segment, self.Fs, self.alpha_low, self.alpha_high, self.window_size
            )
        except Exception as exc:
            self._emit_error(f"Ошибка расчёта альфа-ритма (FFT): {exc}")
            return 0.0

    def calculate_emg_amplitude(self, data_segment) -> float:
        return signal_processing.calculate_emg_amplitude(data_segment)

    def _emit_error(self, message: str) -> None:
        try:
            self.error_signal.emit(message)
        except Exception:
            pass

    def _update_alpha(self, eeg_seg) -> float:
        self._alpha_counter += 1
        if self._alpha_counter >= self.alpha_update_samples:
            self._alpha_counter = 0
            self._last_alpha = self.calculate_alpha_amplitude(eeg_seg)
            try:
                self.alpha_value_signal.emit(self._last_alpha)
            except Exception:
                pass
        return self._last_alpha

    def reset_calibration(self) -> None:
        self.alpha_baseline = None
        self.emg_baseline = None
        self.baseline_calculated = False
        self.threshold_state.reset()
        self.sample_counter = 0

    def stop(self) -> None:
        logger.debug("%s.stop()", type(self).__name__)
        self.is_running = False