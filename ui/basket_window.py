import logging
import os

import numpy as np
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtMultimedia import QSound
from PyQt5.QtWidgets import QMessageBox

from Project.core.battery_monitor import BatteryLevel, BatteryMonitor
from Project.config import SOUND_BALL_PATH, SOUND_CLAPS_PATH, SOUND_RING_PATH, SESSION_DATA_DIR
from Project.core.edf_export import build_session_filename, save_session_to_edf
from Project.core.session_recorder import SessionRecorder
from Project.data.database import DatabaseManager
from Project.testers.file_tester import FileTester
from Project.testers.live_tester import LiveTester
from Project.ui.basket_ui import Ui_Basket
from Project.ui.battery_widget import BatteryPanel
from Project.ui.theme import P, status_style

logger = logging.getLogger(__name__)

MODE_LIVE = "РЕЖИМ РЕАЛЬНОГО ВРЕМЕНИ (ЭЭГ+ЭМГ)"

STATUS_STYLE_DEFAULT = status_style(P["line"])
STATUS_STYLE_OK = status_style(P["ok"])
STATUS_STYLE_WARN = status_style(P["low"])
STATUS_STYLE_ERROR = status_style(P["critical"])

THRESHOLD_HIT_MESSAGES = {
    1: ("Мяч об пол! (превышен порог 1)", status_style(P["emg"])),
    2: ("Попадание в кольцо! (превышен порог 2)", status_style(P["eeg"])),
    3: ("Кольцо + болельщики! (превышен порог 3)", status_style(P["ball"])),
}


def find_device_manager(tester):
    """Ищет у теста объект с battery_readers() (DualUniorManager) без привязки к имени атрибута."""
    for value in vars(tester).values():
        if hasattr(value, "battery_readers"):
            return value
    return None


class BasketWindow(QtWidgets.QMainWindow, Ui_Basket):
    def __init__(
        self,
        tester,
        mode_name: str,
        parent_main=None,
        db: DatabaseManager | None = None,
        user_id: int | None = None,
        user_fio: str | None = None,
    ):
        super().__init__()
        self.setupUi(self)

        self.tester = tester
        self.mode_name = mode_name
        self.parent_main = parent_main
        self.db = db
        self.user_id = user_id
        self.user_fio = user_fio

        self.recorder = SessionRecorder(fs=tester.Fs, graph_window_sec=1.0)
        self.session_saved = False

        self._apply_initial_settings()
        self._connect_ui_signals()
        self._connect_tester_signals()
        self._lock_controls_in_file_mode()
        self._setup_sounds()
        self._apply_mode_labels(mode_name)
        self._setup_battery_monitor()

        self.gui_timer = QtCore.QTimer()
        self.gui_timer.timeout.connect(self.update_plots)
        self.gui_timer.start(33)

        if "РЕЖИМ РЕАЛЬНОГО ВРЕМЕНИ" in self.mode_name:
            self.status_label.setText("Подготовка к подключению датчиков...")
        else:
            self.status_label.setText("Загрузка данных из файлов...")

        self.btn_back.clicked.connect(self.on_back_clicked)
        self.setMinimumSize(800, 600)
        self.showMaximized()

    def _apply_initial_settings(self) -> None:
        self.slider_th1.setValue(round(self.tester.th1 * 100))
        self.slider_th2.setValue(round(self.tester.th2 * 100))
        self.slider_th3.setValue(round(self.tester.th3 * 100))
        self.emg_spin.setValue(self.tester.emg_int_threshold)
        self.alpha_low_spin.setValue(self.tester.alpha_low)
        self.alpha_high_spin.setValue(self.tester.alpha_high)

        self.th1 = self.slider_th1.value()
        self.th2 = self.slider_th2.value()
        self.th3 = self.slider_th3.value()
        self.emg = self.emg_spin.value()

        thresholds_text = f"Пороги: {self.th1}%, {self.th2}%, {self.th3}%, ЭМГ: {self.emg} мкВ"
        self.thresholds_label.setText(thresholds_text)

    def _lock_controls_in_file_mode(self) -> None:
        if not isinstance(self.tester, FileTester):
            return

        for widget in (
            self.slider_th1, self.slider_th2, self.slider_th3,
            self.emg_spin, self.alpha_low_spin, self.alpha_high_spin,
        ):
            widget.setEnabled(False)

    def _apply_mode_labels(self, mode_name: str) -> None:
        self.mode_label.setText(f"Режим: {mode_name}")
        color = P["ball"] if mode_name == MODE_LIVE else P["eeg"]
        self.mode_label.setStyleSheet(status_style(color).replace("padding: 12px", "padding: 8px"))

    def _connect_ui_signals(self) -> None:
        self.slider_th1.valueChanged.connect(self.on_thresholds_changed)
        self.slider_th2.valueChanged.connect(self.on_thresholds_changed)
        self.slider_th3.valueChanged.connect(self.on_thresholds_changed)
        self.emg_spin.valueChanged.connect(self.on_emg_changed)
        self.alpha_low_spin.valueChanged.connect(self.on_alpha_band_changed)
        self.alpha_high_spin.valueChanged.connect(self.on_alpha_band_changed)

    def _connect_tester_signals(self) -> None:
        tester = self.tester

        if hasattr(tester, "data_signal"):
            tester.data_signal.connect(self.on_new_data)
        if hasattr(tester, "alpha_value_signal"):
            tester.alpha_value_signal.connect(self.on_alpha_value)
        if hasattr(tester, "finished_signal"):
            tester.finished_signal.connect(self.on_session_finished_auto)
        if hasattr(tester, "ui_thresholds_signal"):
            tester.ui_thresholds_signal.connect(self.update_thresholds_ui)
        if hasattr(tester, "ui_emg_signal"):
            tester.ui_emg_signal.connect(self.update_emg_ui)
        if hasattr(tester, "ui_alpha_band_signal"):
            tester.ui_alpha_band_signal.connect(self.update_alpha_band_ui)

        try:
            tester.sound_signal.connect(self.on_sound_signal)
            tester.error_signal.connect(self.on_error)
            if hasattr(tester, "baseline_calculated_signal"):
                tester.baseline_calculated_signal.connect(self.on_baseline_calculated)
            if hasattr(tester, "connection_status_signal"):
                tester.connection_status_signal.connect(self.on_connection_status)
            if hasattr(tester, "device_status_signal"):
                tester.device_status_signal.connect(self.on_device_status)
        except Exception as exc:
            logger.warning("Ошибка подключения сигналов: %s", exc)

    def _setup_battery_monitor(self) -> None:
        """Заряд датчиков — только в режиме реального времени."""
        self.battery_monitor: BatteryMonitor | None = None
        if not isinstance(self.tester, LiveTester):
            return

        manager = find_device_manager(self.tester)
        if manager is None:
            logger.warning("Не найден менеджер датчиков у %s — заряд не показывается",
                           type(self.tester).__name__)
            return

        self.battery_monitor = BatteryMonitor(manager.battery_readers(), parent=self)
        self.battery_panel = BatteryPanel(self.battery_monitor, vertical=True)
        self.battery_container.addWidget(self.battery_panel)
        self.battery_monitor.warning.connect(self.on_battery_warning)
        self.battery_monitor.start()

    def on_battery_warning(self, name: str, percent: int, level) -> None:
        logger.warning("Низкий заряд датчика %s: %s%% (%s)", name, percent, level.value)
        # Баннер в панели заряда уже показывает предупреждение, статус игры не трогаем

    def _setup_sounds(self) -> None:
        for path, label in (
            (SOUND_BALL_PATH, "ball_cut.wav"),
            (SOUND_RING_PATH, "ring.wav"),
            (SOUND_CLAPS_PATH, "claps.wav"),
        ):
            if not os.path.exists(path):
                logger.warning("Файл звука не найден: %s", label)

        self.sound1 = self._load_sound(SOUND_BALL_PATH)
        self.sound2 = self._load_sound(SOUND_RING_PATH)
        self.sound3 = self._load_sound(SOUND_CLAPS_PATH)

    @staticmethod
    def _load_sound(path: str):
        return QSound(path) if os.path.exists(path) else None

    def on_emg_changed(self) -> None:
        emg = self.emg_spin.value()
        if hasattr(self.tester, "emg_changed_signal"):
            self.tester.emg_changed_signal.emit(emg)

        self._refresh_thresholds_label()
        self.recorder.register_emg_threshold_changed(emg)

    def on_thresholds_changed(self) -> None:
        th1, th2, th3 = self.slider_th1.value(), self.slider_th2.value(), self.slider_th3.value()

        if hasattr(self.tester, "thresholds_changed_signal"):
            self.tester.thresholds_changed_signal.emit(th1 / 100.0, th2 / 100.0, th3 / 100.0)

        self._refresh_thresholds_label()
        self.recorder.register_thresholds_changed(th1, th2, th3)

    def on_alpha_band_changed(self) -> None:
        low, high = self.alpha_low_spin.value(), self.alpha_high_spin.value()
        if low >= high:
            return

        if hasattr(self.tester, "alpha_band_changed_signal"):
            self.tester.alpha_band_changed_signal.emit(low, high)

        self.alpha_plot.setTitle(f"Альфа-ритм ({low:.1f}–{high:.1f} Гц)")
        self.recorder.register_alpha_band_changed(low, high)

    def _refresh_thresholds_label(self) -> None:
        self.thresholds_label.setText(
            f"Пороги: {self.slider_th1.value()}%, "
            f"{self.slider_th2.value()}%, "
            f"{self.slider_th3.value()}%, "
            f"ЭМГ: {self.emg_spin.value()} мкВ"
        )

    def update_thresholds_ui(self, th1: int, th2: int, th3: int) -> None:
        for slider, value in (
            (self.slider_th1, th1), (self.slider_th2, th2), (self.slider_th3, th3)
        ):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self._refresh_thresholds_label()

    def update_emg_ui(self, value: float) -> None:
        self.emg_spin.blockSignals(True)
        self.emg_spin.setValue(value)
        self.emg_spin.blockSignals(False)
        self._refresh_thresholds_label()

    def update_alpha_band_ui(self, low: float, high: float) -> None:
        for spin, value in ((self.alpha_low_spin, low), (self.alpha_high_spin, high)):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        self.alpha_plot.setTitle(f"Альфа-ритм ({low:.1f}–{high:.1f} Гц)")

    def on_new_data(self, *args) -> None:
        if len(args) == 5:
            eeg_val, _eeg_t, emg_val, _emg_t, emg_int = args
        elif len(args) == 3:
            eeg_val, emg_val, emg_int = args
        elif len(args) == 2:
            eeg_val, emg_val = args
            emg_int = 0.0
        else:
            return

        self.recorder.add_sample(eeg_val, emg_val, emg_int)

    def on_alpha_value(self, value: float) -> None:
        self.recorder.set_current_alpha(value)

    def update_plots(self) -> None:
        r = self.recorder
        if len(r.eeg_plot_buffer) < r.max_plot_samples:
            return

        t0 = r.t_global - r.graph_window_sec
        time_axis = np.linspace(t0, r.t_global, r.max_plot_samples)

        self.eeg_curve.setData(time_axis, np.array(r.eeg_plot_buffer))
        self.emg_curve.setData(time_axis, np.array(r.emg_plot_buffer))
        self.emg_int_curve.setData(time_axis, np.array(r.emg_int_plot_buffer))
        self.alpha_curve.setData(time_axis, np.array(r.alpha_plot_buffer))

    def on_baseline_calculated(self, eeg_baseline, *_rest) -> None:
        self.status_label.setText(
            f"Калибровка завершена. ЭЭГ: {eeg_baseline}\nОтслеживание сигналов..."
        )
        self.status_label.setStyleSheet(STATUS_STYLE_OK)

    def on_connection_status(self, status: str) -> None:
        self.status_label.setText(status)
        if "Калибровка завершена" in status:
            self.status_label.setStyleSheet(STATUS_STYLE_OK)
        elif "Калибровка" in status:
            self.status_label.setStyleSheet(STATUS_STYLE_WARN)
        else:
            self.status_label.setStyleSheet(STATUS_STYLE_DEFAULT)

    def on_device_status(self, device_type: str, status: str) -> None:
        if device_type == "ЭЭГ":
            self.eeg_status_label.setText(f"ЭЭГ: {status}")
        elif device_type == "ЭМГ":
            self.emg_status_label.setText(f"ЭМГ: {status}")

    def on_error(self, msg: str) -> None:
        self.status_label.setText(f"Ошибка: {msg}")
        self.status_label.setStyleSheet(STATUS_STYLE_ERROR)
        QMessageBox.critical(self, "Ошибка", msg)

    def on_sound_signal(self, threshold_index: int) -> None:
        message, style = THRESHOLD_HIT_MESSAGES[threshold_index]

        if threshold_index == 1:
            self._play(self.sound1, "1 (ball)")
        elif threshold_index == 2:
            self._play(self.sound2, "2 (ring)")
        elif threshold_index == 3:
            self._play(self.sound2, "2 (ring, часть порога 3)")
            if self.sound3:
                QtCore.QTimer.singleShot(300, self.sound3.play)
            else:
                logger.info("[SOUND] 3 (claps) requested but file missing.")

        self.status_label.setText(message)
        self.status_label.setStyleSheet(style)

        score = self.recorder.register_threshold_hit(threshold_index)
        self.score_label.setText(f"Счёт: {score}")

    def _play(self, sound, label: str) -> None:
        if sound:
            sound.play()
        else:
            logger.info("[SOUND] %s requested but file missing.", label)

    def on_session_finished_auto(self) -> None:
        logger.info("Получен сигнал о завершении сессии из-за окончания файла.")
        try:
            if self.tester and getattr(self.tester, "is_running", False):
                self.tester.stop()
                QtCore.QThread.msleep(200)
        except Exception as exc:
            logger.warning("Ошибка остановки тестера: %s", exc)

        if not self.session_saved and isinstance(self.tester, LiveTester):
            self.save_session_data()

        self.close()
        self.close_window()

    def on_back_clicked(self) -> None:
        logger.debug("Нажата кнопка 'Назад в меню'")
        self.tester.backed = True
        self.btn_back.setEnabled(False)

        if self.tester and hasattr(self.tester, "stop"):
            try:
                self.tester.stop()
                if isinstance(self.tester, LiveTester):
                    self.save_session_data()
                QtCore.QTimer.singleShot(150, self.close_window)
            except Exception as exc:
                logger.warning("Ошибка при остановке тестера: %s", exc)

    def show_final_message(self) -> None:
        QMessageBox.information(
            self, "Результат сессии", f"Сессия завершена!\nВаш финальный счёт: {self.recorder.score}"
        )

    def close_window(self) -> None:
        logger.debug("Закрываю BasketWindow...")
        if not self.parent_main:
            return
        try:
            self.parent_main.showNormal()
            self.parent_main.raise_()
            self.parent_main.activateWindow()
            self.parent_main.load_user_settings()
            self.close()
            QtCore.QTimer.singleShot(100, self.show_final_message)
        except Exception as exc:
            logger.warning("Ошибка при восстановлении главного окна: %s", exc)

    def save_session_data(self) -> None:
        if isinstance(self.tester, FileTester):
            return
        if self.session_saved or not self.user_id:
            return

        filename = build_session_filename(SESSION_DATA_DIR, self.user_fio)

        saved = save_session_to_edf(
            filename=filename,
            recorder=self.recorder,
            fs=self.tester.Fs,
            alpha_baseline=getattr(self.tester, "alpha_baseline", 0.0) or 0.0,
            emg_baseline=getattr(self.tester, "emg_baseline", 0.0) or 0.0,
            user_id=self.user_id,
            user_fio=self.user_fio,
        )

        if not saved:
            return

        self.db.update_settings(
            self.user_id,
            self.slider_th1.value(),
            self.slider_th2.value(),
            self.slider_th3.value(),
            self.alpha_low_spin.value(),
            self.alpha_high_spin.value(),
            self.emg_spin.value(),
        )
        self.db.save_session(self.user_id, self.recorder.score, filename)
        self.session_saved = True

    def closeEvent(self, event) -> None:
        logger.debug("Закрытие BasketWindow через событие")
        self.cleanup()

        if self.tester and getattr(self.tester, "is_running", False):
            try:
                self.tester.stop()
            except Exception as exc:
                logger.warning("Ошибка при остановке тестера: %s", exc)

        if self.parent_main:
            try:
                self.parent_main.showNormal()
                self.parent_main.raise_()
                self.parent_main.activateWindow()
                QtWidgets.QApplication.processEvents()
            except Exception as exc:
                logger.warning("Ошибка при восстановлении главного окна: %s", exc)

        event.accept()

    def cleanup(self) -> None:
        try:
            if getattr(self, "battery_monitor", None):
                self.battery_monitor.stop()

            for sound in (self.sound1, self.sound2, self.sound3):
                if sound:
                    sound.stop()

            for plot in (self.eeg_plot, self.emg_plot, self.emg_int_plot, self.alpha_plot):
                plot.clear()

            r = self.recorder
            for buf in (
                r.eeg_plot_buffer, r.emg_plot_buffer, r.emg_int_plot_buffer,
                r.alpha_plot_buffer, r.time_plot_buffer,
            ):
                buf.clear()

        except Exception as exc:
            logger.warning("Ошибка при очистке ресурсов: %s", exc)
