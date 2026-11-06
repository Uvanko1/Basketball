import logging
import os
import time as time_module

import edfio
import numpy as np
from PyQt5 import QtCore

from Project.config import SIGNAL, THRESHOLDS
from Project.core.base_tester import BaseTester
from Project.core.threshold_evaluator import evaluate as evaluate_thresholds

logger = logging.getLogger(__name__)


class FileTester(BaseTester):
    progress_signal = QtCore.pyqtSignal(float)
    finished_signal = QtCore.pyqtSignal()
    data_signal = QtCore.pyqtSignal(float, float, float)
    ui_thresholds_signal = QtCore.pyqtSignal(int, int, int)
    ui_emg_signal = QtCore.pyqtSignal(float)
    ui_alpha_band_signal = QtCore.pyqtSignal(float, float)

    def __init__(
        self,
        eeg_filename: str | None = None,
        th1_percent: float = THRESHOLDS.threshold1_percent,
        th2_percent: float = THRESHOLDS.threshold2_percent,
        th3_percent: float = THRESHOLDS.threshold3_percent,
        emg: float = THRESHOLDS.emg_threshold_uv,
        alpha_low: float = THRESHOLDS.alpha_low_hz,
        alpha_high: float = THRESHOLDS.alpha_high_hz,
        Fs: float = SIGNAL.sample_rate_hz,
    ):
        super().__init__(th1_percent, th2_percent, th3_percent, emg, alpha_low, alpha_high, Fs)

        self.eeg_filename = eeg_filename
        self.loaded_annotations: tuple = ()

        self.eeg_data, self.emg_data, self.emg_int_data = self.load_signals_from_files()

    def load_signals_from_files(self):
        eeg_data = emg_data = emg_int_data = None

        if self.eeg_filename and os.path.exists(self.eeg_filename):
            try:
                signals = self.find_eeg_and_emg_in_file(self.eeg_filename)
                eeg_data = signals["eeg"]
                emg_data = signals["emg"]
                emg_int_data = signals["emg_int"]
                if eeg_data is not None:
                    logger.info(
                        "Найден ЭЭГ сигнал в файле: %s", os.path.basename(self.eeg_filename)
                    )
                if emg_data is not None:
                    logger.info(
                        "Найден ЭМГ сигнал в файле: %s", os.path.basename(self.eeg_filename)
                    )
                if emg_int_data is not None:
                    logger.info(
                        "Найден интегральный ЭМГ сигнал в файле: %s",
                        os.path.basename(self.eeg_filename),
                    )
            except Exception as exc:
                logger.warning("Ошибка чтения файла %s: %s", self.eeg_filename, exc)

        return eeg_data, emg_data, emg_int_data

    @staticmethod
    def _extract_real_sample_count(edf: "edfio.Edf") -> int | None:
        marker = "RealSamples:"
        for ann in edf.annotations:
            if ann.text.startswith(marker):
                digits = ann.text[len(marker):]
                if digits.isdigit():
                    return int(digits)
        return None

    def find_eeg_and_emg_in_file(self, filename: str) -> dict:
        result = {"eeg": None, "emg": None, "emg_int": None}
        file_ext = os.path.splitext(filename)[1].lower()

        try:
            if file_ext in (".edf", ".bdf"):
                result = self.load_edf_file(filename)
        except Exception as exc:
            logger.warning("Ошибка при анализе файла %s: %s", filename, exc)

        return result

    def load_edf_file(self, filename: str) -> dict:
        result = {"eeg": None, "emg": None, "emg_int": None}

        try:
            edf = edfio.read_edf(filename)
            self.loaded_annotations = edf.annotations

            ch_names = list(edf.labels)
            channel_data = {label: edf.get_signal(label).data for label in ch_names}

            real_samples = self._extract_real_sample_count(edf)
            if real_samples is not None:
                for label, arr in list(channel_data.items()):
                    if 0 < real_samples < len(arr):
                        logger.info(
                            "Обрезаю EDF-блок (%s): %d -> %d сэмплов",
                            label, len(arr), real_samples,
                        )
                        channel_data[label] = arr[:real_samples]

            if not self.baseline_calculated:
                if self.load_calibration_from_edf(filename):
                    self.baseline_calculated = True
                    self.baseline_calculated_signal.emit(self.alpha_baseline, self.emg_baseline)

            logger.info("EDF: Загружен файл %s", os.path.basename(filename))
            logger.info("Каналов: %d, длительность: %.3f сек", len(ch_names), edf.duration)

            eeg_channels, emg_channels, emg_int_channels = [], [], []

            for ch_name in ch_names:
                ch_lower = ch_name.lower()

                if "eeg" in ch_lower or any(
                    marker in ch_lower
                    for marker in ["fp", "f", "c", "p", "o", "t", "cz", "fz", "pz", "oz"]
                ):
                    eeg_channels.append(ch_name)

                if "emg" in ch_lower or "muscle" in ch_lower or any(
                    marker in ch_lower for marker in ["экг", "eog"]
                ):
                    emg_channels.append(ch_name)

                if ch_lower == "emg_int":
                    emg_int_channels.append(ch_name)

            emg_channels = [ch for ch in emg_channels if ch not in emg_int_channels]

            eeg_name = None
            if eeg_channels:
                exact = [ch for ch in eeg_channels if ch.strip().lower() == "eeg"]
                if exact:
                    eeg_name = exact[0]
                else:
                    occipital = [ch for ch in eeg_channels if any(m in ch.lower() for m in ["o", "p"])]
                    eeg_name = occipital[0] if occipital else eeg_channels[0]
                result["eeg"] = channel_data[eeg_name]
                logger.info("Выбран ЭЭГ канал: %s", eeg_name)

            if emg_channels:
                emg_name = emg_channels[0]
                result["emg"] = channel_data[emg_name]
                logger.info("Выбран ЭМГ канал: %s", emg_name)

            if emg_int_channels:
                emg_int_name = emg_int_channels[0]
                result["emg_int"] = channel_data[emg_int_name]
                logger.info("Выбран ЭМГ интегральный канал: %s", emg_int_name)

            if result["emg"] is None and len(ch_names) > 1 and result["eeg"] is not None:
                for ch_name in ch_names:
                    if ch_name != eeg_name:
                        result["emg"] = channel_data[ch_name]
                        logger.info("Используем как ЭМГ: %s", ch_name)
                        break

        except Exception as exc:
            logger.warning("Ошибка загрузки EDF файла %s: %s", filename, exc)

        return result

    def load_calibration_from_edf(self, filename: str) -> bool:
        try:
            edf = edfio.read_edf(filename)
            ch_names = edf.labels

            if "ALPHA_BASE" in ch_names and "EMG_BASE" in ch_names:
                self.alpha_baseline = float(edf.get_signal("ALPHA_BASE").data[0])
                self.emg_baseline = float(edf.get_signal("EMG_BASE").data[0])
                logger.info(
                    "Калибровка из EDF: alpha=%s, emg=%s", self.alpha_baseline, self.emg_baseline
                )
                return True

            logger.warning("Каналы калибровки не найдены")
            return False

        except Exception as exc:
            logger.warning("Ошибка чтения калибровки: %s", exc)
            return False

    def run(self) -> None:
        if self.eeg_data is None:
            self.error_signal.emit("Не найден ЭЭГ сигнал")
            return
        if self.emg_data is None:
            self.error_signal.emit("Не найден ЭМГ сигнал")
            return
        if self.emg_int_data is None:
            self.error_signal.emit("Не найден интегральный ЭМГ сигнал")
            return

        min_len = min(len(self.eeg_data), len(self.emg_data), len(self.emg_int_data))
        if min_len < self.window_size:
            self.error_signal.emit(f"Недостаточно данных. Нужно минимум {self.window_size}")
            return

        self.eeg_data = self.eeg_data[:min_len]
        self.emg_data = self.emg_data[:min_len]
        self.emg_int_data = self.emg_int_data[:min_len]

        if not self.baseline_calculated:
            if self.load_calibration_from_edf(self.eeg_filename):
                self.baseline_calculated = True
                self.baseline_calculated_signal.emit(self.alpha_baseline, self.emg_baseline)

        logger.info("baseline α=%s, ЭМГ=%s", self.alpha_baseline, self.emg_baseline)

        start_real_time = time_module.perf_counter()
        self.is_running = True

        eeg_buffer, emg_buffer, emg_int_buffer = [], [], []
        annotation_index = 0
        annotations = self.loaded_annotations or ()

        idx = 0
        n_samples = len(self.eeg_data)

        while self.is_running and idx < n_samples:
            eeg_val = float(self.eeg_data[idx])
            emg_val = float(self.emg_data[idx])
            emg_int_val = float(self.emg_int_data[idx])
            self.current_emg_int = emg_int_val

            self.data_signal.emit(eeg_val, emg_val, emg_int_val)

            eeg_buffer.append(eeg_val)
            emg_buffer.append(emg_val)
            emg_int_buffer.append(emg_int_val)
            self.sample_counter += 1

            if len(eeg_buffer) > self.window_size * 3:
                eeg_buffer = eeg_buffer[-self.window_size:]
                emg_buffer = emg_buffer[-self.window_size:]
                emg_int_buffer = emg_int_buffer[-self.window_size:]

            if len(eeg_buffer) >= self.window_size:
                eeg_seg = np.array(eeg_buffer[-self.window_size:], dtype=float)
                current_alpha = self._update_alpha(eeg_seg)
            else:
                current_alpha = 0.0

            if self.sample_counter >= self.step_samples and len(eeg_buffer) >= self.window_size:
                self.sample_counter = 0

                if current_alpha > 0:
                    current_time = idx / self.Fs
                    annotation_index = self._replay_annotations(
                        annotations, annotation_index, current_time
                    )

                    ratio = current_alpha / self.alpha_baseline
                    percent_increase = ratio - 1.0

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
                        reset_edges_on_emg_block=False,
                    )
                    if triggered is not None:
                        logger.info("[ПОРОГ %d] t=%.2f", triggered, current_time)
                        self.sound_signal.emit(triggered)

            current_signal_time = idx / self.Fs
            elapsed_real_time = time_module.perf_counter() - start_real_time
            sleep_time = current_signal_time - elapsed_real_time
            if sleep_time > 0:
                QtCore.QThread.msleep(int(sleep_time * 1000))

            idx += 1

        self.is_running = False
        logger.info("Эмуляция завершена")

        try:
            self.finished_signal.emit()
        except Exception:
            pass

    def _replay_annotations(self, annotations, annotation_index: int, current_time: float) -> int:
        while annotation_index < len(annotations):
            ann = annotations[annotation_index]
            if ann.onset > current_time:
                break

            desc = ann.text
            logger.debug("[REPLAY EVENT] %s", desc)

            if desc.startswith("THRESHOLDS"):
                parts = desc.split("|")
                th1 = int(parts[1].split("=")[1])
                th2 = int(parts[2].split("=")[1])
                th3 = int(parts[3].split("=")[1])
                self.thresholds_changed_signal.emit(th1 / 100, th2 / 100, th3 / 100)
                self.ui_thresholds_signal.emit(th1, th2, th3)

            if desc.startswith("EMG_THRESHOLD"):
                value = float(desc.split("=")[1])
                self.emg_changed_signal.emit(value)
                self.ui_emg_signal.emit(value)

            if desc.startswith("ALPHA_BAND"):
                parts = desc.split("|")
                low = float(parts[1].split("=")[1])
                high = float(parts[2].split("=")[1])
                self.alpha_band_changed_signal.emit(low, high)
                self.ui_alpha_band_signal.emit(low, high)

            if "THRESHOLD_1" in desc:
                self.sound_signal.emit(1)
            elif "THRESHOLD_2" in desc:
                self.sound_signal.emit(2)
            elif "THRESHOLD_3" in desc:
                self.sound_signal.emit(3)

            annotation_index += 1

        return annotation_index