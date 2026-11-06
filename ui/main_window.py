import logging
import os

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from Project.config import THRESHOLDS
from Project.data.database import DatabaseManager
from Project.testers.file_tester import FileTester
from Project.testers.live_tester import LiveTester
from Project.ui.basket_window import BasketWindow
from Project.ui.main_menu_ui import Ui_MainWindow

logger = logging.getLogger(__name__)

EEG_FILE_FILTER = "EDF/BDF файлы (*.edf *.bdf);;Все файлы (*.*)"

INSTRUCTION_TEXT = (
    "1) ВЫБЕРИТЕ РЕЖИМ РАБОТЫ:\n"
    "   • Файл - для тестирования по заранее записанным данным\n"
    "   • Реальное время - для работы с датчиками ЭЭГ и ЭМГ Юниор\n\n"
    "2) ЕСЛИ ВЫБРАН РЕЖИМ ФАЙЛА:\n"
    "   • Выберите файл ЭЭГ (EDF)\n"
    "   • Выберите файл ЭМГ (EDF)\n"
    "   • Оба файла обязательны\n\n"
    "3) НАСТРОЙТЕ ПОРОГИ в главном меню:\n"
    "   • Порог 1 - мяч об пол (рекомендуется 25%)\n"
    "   • Порог 2 - попадание в кольцо (рекомендуется 50%)\n"
    "   • Порог 3 - кольцо + болельщики (рекомендуется 75%)\n\n"
    "4) НАЖМИТЕ 'НАЧАТЬ' ДЛЯ ЗАПУСКА:\n"
    "   • В режиме реального времени начнется калибровка (5 сек)\n"
    "   • После калибровки система будет отслеживать альфа-ритм\n\n"
    "5) В ОКНЕ ИЗМЕРЕНИЯ:\n"
    "   • Отображаются текущие пороги\n"
    "   • Показывается статус измерения\n"
    "   • Нажмите 'Назад в меню' для возврата\n\n"
    "Требования для режима реального времени:\n"
    "• Два датчика Юниор (ЭЭГ и ЭМГ) с заряженными батареями\n"
    "• Bluetooth адаптер\n"
    "• В окне измерения показывается заряд датчиков; при заряде ниже 30% появится\n"
    "  предупреждение, ниже 15% — просьба зарядить датчик\n"
    "• Оба датчика должны быть подключены и работать"
)


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, db: DatabaseManager, user_id: int, user_fio: str):
        super().__init__()
        self.setupUi(self)

        self.selected_eeg_file_path: str | None = None
        self.basket_window: BasketWindow | None = None
        self.current_tester = None

        self.db = db
        self.current_user_id = user_id
        self.current_user_fio = user_fio

        try:
            self.pushButton.clicked.connect(self.on_start_clicked)
            self.pushButton_2.clicked.connect(self.on_instruction_clicked)
            self.btn_select_eeg_file.clicked.connect(self.on_select_eeg_file_clicked)
        except Exception as exc:
            logger.warning("Ошибка подключения кнопок: %s", exc)

        self.radio_file.toggled.connect(self.on_mode_changed)
        self.on_mode_changed(self.radio_file.isChecked())

        self.setMinimumSize(600, 400)
        self.showMaximized()
        self.load_user_settings()

    def on_mode_changed(self, file_mode_checked: bool) -> None:
        for widget in (self.btn_select_eeg_file, self.eeg_file_label, self.file_label):
            widget.setEnabled(file_mode_checked)

    def on_select_eeg_file_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл данных ЭЭГ", "", EEG_FILE_FILTER
        )
        if not path:
            return

        self.selected_eeg_file_path = path
        filename = os.path.basename(path)
        display_name = filename if len(filename) <= 20 else f"{filename[:17]}..."
        self.eeg_file_label.setText(display_name)
        self.eeg_file_label.setToolTip(path)
        self.update_file_label()

    def update_file_label(self) -> None:
        if self.selected_eeg_file_path:
            eeg_name = os.path.basename(self.selected_eeg_file_path)
            self.file_label.setText(f"ЭЭГ: {eeg_name[:10]}...")
            self.file_label.setToolTip(f"ЭЭГ: {self.selected_eeg_file_path}\n")
        else:
            self.file_label.setText("Файл не выбран")

    def on_instruction_clicked(self) -> None:
        QMessageBox.information(self, "Инструкция", INSTRUCTION_TEXT)

    def on_start_clicked(self) -> None:
        self._close_previous_basket_window()
        self.showMinimized()

        th1 = self.spin25.value()
        th2 = self.spin50.value()
        th3 = self.spin75.value()
        emg = self.spin_emg.value()
        settings = self.db.load_settings(self.current_user_id)
        alpha_low = settings.alpha_freq_left if settings else THRESHOLDS.alpha_low_hz
        alpha_high = settings.alpha_freq_right if settings else THRESHOLDS.alpha_high_hz

        if self.radio_file.isChecked():
            tester = self._build_file_tester(th1, th2, th3, emg, alpha_low, alpha_high)
            if tester is None:
                self.showNormal()
                return
            mode_name = "РЕЖИМ ФАЙЛА (ЭЭГ+ЭМГ)"
        else:
            tester = LiveTester(
                th1_percent=th1, th2_percent=th2, th3_percent=th3, emg=emg,
                alpha_low=alpha_low, alpha_high=alpha_high,
            )
            mode_name = "РЕЖИМ РЕАЛЬНОГО ВРЕМЕНИ (ЭЭГ+ЭМГ)"

        self.basket_window = BasketWindow(
            tester,
            mode_name,
            parent_main=self,
            db=self.db,
            user_id=self.current_user_id,
            user_fio=self.current_user_fio,
        )
        self.basket_window.showFullScreen()

        self.current_tester = tester
        tester.start()
        self.hide()

    def _close_previous_basket_window(self) -> None:
        if self.basket_window is None:
            return
        try:
            if hasattr(self.basket_window, "tester") and self.basket_window.tester:
                self.basket_window.tester.stop()
            self.basket_window.close()
        except Exception as exc:
            logger.warning("Ошибка закрытия окна: %s", exc)
        self.basket_window = None

    def _build_file_tester(
        self, th1: int, th2: int, th3: int, emg: float, alpha_low: float, alpha_high: float
    ) -> FileTester | None:
        if not self.selected_eeg_file_path:
            QMessageBox.warning(
                self, "Ошибка", "Для режима файла необходимо выбрать файл с данными."
            )
            return None

        if not os.path.exists(self.selected_eeg_file_path):
            QMessageBox.critical(
                self, "Ошибка", f"Файл ЭЭГ не найден:\n{self.selected_eeg_file_path}"
            )
            return None

        try:
            if os.path.getsize(self.selected_eeg_file_path) == 0:
                QMessageBox.warning(self, "Ошибка", "Выбранный файл ЭЭГ пуст")
                return None
        except OSError:
            pass

        return FileTester(
            eeg_filename=self.selected_eeg_file_path,
            th1_percent=th1, th2_percent=th2, th3_percent=th3,
            emg=emg, alpha_low=alpha_low, alpha_high=alpha_high,
        )

    def load_user_settings(self) -> None:
        settings = self.db.load_settings(self.current_user_id)

        if settings is None:
            self.db.create_default_settings(self.current_user_id)
            self.spin25.setValue(THRESHOLDS.threshold1_percent)
            self.spin50.setValue(THRESHOLDS.threshold2_percent)
            self.spin75.setValue(THRESHOLDS.threshold3_percent)
            self.spin_emg.setValue(int(THRESHOLDS.emg_threshold_uv))
            return

        self.spin25.setValue(settings.threshold1)
        self.spin50.setValue(settings.threshold2)
        self.spin75.setValue(settings.threshold3)
        self.spin_emg.setValue(int(settings.emg))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.showNormal()
        self.activateWindow()
        self.raise_()
        QtWidgets.QApplication.processEvents()

    def closeEvent(self, event) -> None:
        logger.debug("Закрытие MainWindow")

        if self.basket_window:
            try:
                self.basket_window.close()
            except Exception as exc:
                logger.warning("Ошибка закрытия basket_window: %s", exc)

        if self.current_tester and hasattr(self.current_tester, "stop"):
            try:
                self.current_tester.stop()
            except Exception as exc:
                logger.warning("Ошибка остановки тестера: %s", exc)

        event.accept()
