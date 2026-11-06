import logging
from collections import deque

import numpy as np
from PyQt5 import QtCore

from Project.config import SIGNAL, THRESHOLDS
from Project.core.base_tester import BaseTester
from Project.core.threshold_evaluator import evaluate as evaluate_thresholds
from Project.device.eeg_unior_ext import DualUniorManager

logger = logging.getLogger(__name__)


class LiveTester(BaseTester):
    data_signal = QtCore.pyqtSignal(float, float, float, float, float)
    connection_status_signal = QtCore.pyqtSignal(str)
    device_status_signal = QtCore.pyqtSignal(str, str)

    def __init__(
        self,
        th1_percent: float = THRESHOLDS.threshold1_percent,
        th2_percent: float = THRESHOLDS.threshold2_percent,
        th3_percent: float = THRESHOLDS.threshold3_percent,
        emg: float = THRESHOLDS.emg_threshold_uv,
        alpha_low: float = THRESHOLDS.alpha_low_hz,
        alpha_high: float = THRESHOLDS.alpha_high_hz,
        Fs: float = SIGNAL.sample_rate_hz,
    ):
        super().__init__(th1_percent, th2_percent, th3_percent, emg, alpha_low, alpha_high, Fs)

        self.device_manager = DualUniorManager(Fs)

        self.eeg_calibration_data = []
        self.emg_calibration_data = []
        self.calibration_time = SIGNAL.calibration_sec
        self.calibration_collected = False
        self._calibration_samples_collected = 0
        self._calibration_samples_needed = int(Fs * SIGNAL.calibration_sec)

        buffer_len = int(Fs * SIGNAL.buffer_seconds)
        self.eeg_buffer = deque(maxlen=buffer_len)
        self.emg_buffer = deque(maxlen=buffer_len)
        self.emg_int_buffer = deque(maxlen=buffer_len)
        self.time_buffer = deque(maxlen=buffer_len)

    def check_device_connection(self):
        try:
            self.connection_status_signal.emit("Подключение к ЭЭГ и ЭМГ датчикам...")
            all_connected, results = self.device_manager.connect_both()

            if not all_connected:
                error_messages = []
                for device_name, success, message in results:
                    mark = "✓" if success else "✗"
                    self.device_status_signal.emit(device_name, f"{mark} {message}")
                    if not success:
                        error_messages.append(f"{device_name}: {message}")
                self.device_manager.disconnect_both()
                return False, "\n".join(error_messages)

            self.connection_status_signal.emit("Запуск сбора данных...")
            started, start_msg = self.device_manager.start_both()
            if not started:
                self.device_manager.disconnect_both()
                return False, f"Не удалось запустить сбор данных: {start_msg}"

            eeg_val = emg_val = emg_int = None
            for _ in range(20):
                eeg_val, _eeg_t, emg_val, _emg_t, emg_int, _emg_int_t = self.device_manager.read_samples()
                if eeg_val is not None and emg_val is not None and emg_int is not None:
                    self.device_manager.stop_both()
                    self.device_status_signal.emit("ЭЭГ", "Устройство подключено")
                    self.device_status_signal.emit("ЭМГ", "Устройство подключено")
                    return True, "Оба устройства подключены и готовы к работе"
                QtCore.QThread.msleep(100)

            self.device_manager.stop_both()
            self.device_manager.disconnect_both()

            if eeg_val is None:
                return False, "ЭЭГ датчик подключен, но данные не поступают."
            if emg_val is None:
                return False, "ЭМГ датчик подключен, но данные не поступают."
            return False, "Оба датчика подключены, но данные не поступают."

        except Exception as exc:
            self.device_manager.disconnect_both()
            return False, f"Ошибка при проверке подключения: {exc}"

    def run(self) -> None:
        self.reset_calibration()
        self.eeg_calibration_data = []
        self.emg_calibration_data = []
        self.calibration_collected = False
        self.eeg_buffer.clear()
        self.emg_buffer.clear()
        self.emg_int_buffer.clear()
        self.time_buffer.clear()

        self.connection_status_signal.emit("Подключение к ЭЭГ и ЭМГ датчикам...")
        connected, message = self.check_device_connection()
        if not connected:
            self.error_signal.emit(message)
            return

        self.is_running = True
        self.connection_status_signal.emit("Сбор данных с обоих датчиков...")
        logger.info("Начат сбор данных с ЭЭГ и ЭМГ датчиков Юниор")
        logger.info(
            "Пороги: %.0f%%, %.0f%%, %.0f%%", self.th1 * 100, self.th2 * 100, self.th3 * 100
        )
        logger.info(
            "Окно: 1 секунда (%d сэмплов), Шаг: 0.1 секунды (%d сэмплов)",
            self.window_size, self.step_samples,
        )

        self._calibration_samples_collected = 0
        self._calibration_samples_needed = int(self.Fs * self.calibration_time)

        try:
            self.device_manager.start_both()
            while self.is_running:
                eeg_val, eeg_t, emg_val, _emg_t, emg_int, _emg_int_t = self.device_manager.read_samples()
                self.current_emg_int = emg_int

                if not self.is_running:
                    break

                if eeg_val is None or emg_val is None or emg_int is None or eeg_t is None:
                    all_ok, _messages = self.device_manager.check_connections()
                    if not all_ok:
                        self.error_signal.emit("Один из датчиков отключился")
                        break
                    QtCore.QThread.msleep(10)
                    continue

                self.data_signal.emit(eeg_val, eeg_t, emg_val, _emg_t, emg_int)

                self.eeg_buffer.append(eeg_val)
                self.emg_buffer.append(emg_val)
                self.emg_int_buffer.append(emg_int)
                self.time_buffer.append(eeg_t)
                self.sample_counter += 1

                if not self.calibration_collected:
                    self._collect_calibration_sample(eeg_val, emg_val)
                    if not self.is_running:
                        break
                elif self.baseline_calculated and len(self.eeg_buffer) >= self.window_size:
                    self._process_live_window()

        except Exception as exc:
            self.error_signal.emit(f"Ошибка в потоке сбора данных: {exc}")

        finally:
            self.cleanup_devices()

    def _collect_calibration_sample(self, eeg_val, emg_val) -> None:
        self.eeg_calibration_data.append(eeg_val)
        self.emg_calibration_data.append(emg_val)
        self._calibration_samples_collected += 1
        collected = self._calibration_samples_collected
        needed = self._calibration_samples_needed

        if collected >= needed:
            if len(self.eeg_calibration_data) >= self.window_size:
                eeg_segment = np.array(self.eeg_calibration_data)
                self.alpha_baseline = self.calculate_alpha_amplitude(eeg_segment)

                emg_segment = np.array(self.emg_calibration_data)
                self.emg_baseline = self.calculate_emg_amplitude(emg_segment)

                if self.alpha_baseline > 0 and self.emg_baseline > 0:
                    self.baseline_calculated = True
                    self.calibration_collected = True
                    self.baseline_calculated_signal.emit(self.alpha_baseline, self.emg_baseline)
                    self.connection_status_signal.emit(
                        f"Калибровка завершена. ЭЭГ baseline: {self.alpha_baseline}, "
                        f"ЭМГ baseline: {self.emg_baseline}"
                    )
                    logger.info(
                        "Калибровка завершена. ЭЭГ: %s, ЭМГ: %s", self.alpha_baseline, self.emg_baseline
                    )
                else:
                    self.error_signal.emit("Не удалось вычислить базовые уровни сигналов")
                    self.is_running = False
            else:
                self.error_signal.emit("Недостаточно данных для калибровки")
                self.is_running = False
        else:
            progress = int((collected / needed) * 100)
            self.connection_status_signal.emit(f"Калибровка... {progress}%")

    def _process_live_window(self) -> None:
        eeg_seg = np.array(list(self.eeg_buffer)[-self.window_size:], dtype=float)
        current_alpha = self._update_alpha(eeg_seg)

        if self.sample_counter < self.step_samples:
            return
        self.sample_counter = 0

        if current_alpha <= 0 or self.alpha_baseline <= 0:
            return

        ratio = current_alpha / self.alpha_baseline
        percent_increase = ratio - 1.0
        current_time = self.time_buffer[-1] if self.time_buffer else 0

        triggered = evaluate_thresholds(
            self.threshold_state,
            percent_increase,
            self.current_emg_int,
            self.emg_int_threshold,
            self.th1,
            self.th2,
            self.th3,
            current_time,
            self.min_trigger_interval,
            reset_edges_on_emg_block=True,
        )

        logger.debug(
            "Alpha=%.4f | Baseline=%.4f | Increase=%.1f%% | EMG_INT=%.2f",
            current_alpha, self.alpha_baseline, percent_increase * 100, self.current_emg_int,
        )

        if triggered is not None:
            logger.info(
                "[ПОРОГ %d] t=%.1fсек: α=%.4f, +%.1f%%",
                triggered, current_time, current_alpha, percent_increase * 100,
            )
            try:
                self.sound_signal.emit(triggered)
            except Exception:
                pass

    def cleanup_devices(self) -> None:
        try:
            if hasattr(self, "device_manager"):
                self.device_manager.stop_both()
                self.device_manager.disconnect_both()
        except Exception as exc:
            logger.warning("Ошибка при очистке устройств: %s", exc)