from PyQt5 import QtCore, QtWidgets

from Project.config import THRESHOLDS


class Ui_MainWindow:
    def setupUi(self, main_window: QtWidgets.QMainWindow) -> None:
        main_window.setObjectName("MainWindow")
        main_window.resize(900, 650)

        self.centralwidget = QtWidgets.QWidget(main_window)
        self.centralwidget.setObjectName("root")
        main_window.setCentralWidget(self.centralwidget)

        self.main_layout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.main_layout.setContentsMargins(32, 28, 32, 28)
        self.main_layout.setSpacing(32)
        self.left_panel = QtWidgets.QVBoxLayout()
        self.left_panel.setSpacing(16)

        self._build_threshold_panel()
        self.left_panel.addWidget(self.threshold_frame)

        self._build_mode_panel()
        self.left_panel.addWidget(self.mode_frame)

        self.left_panel.addStretch()
        self.main_layout.addLayout(self.left_panel)

        self._build_action_buttons()

        self.retranslateUi(main_window)
        QtCore.QMetaObject.connectSlotsByName(main_window)

    def _spin(self, low: int, high: int, value: int) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        return spin

    def _build_threshold_panel(self) -> None:
        self.threshold_frame = QtWidgets.QFrame()
        self.threshold_frame.setObjectName("card")
        self.threshold_frame.setMinimumWidth(300)
        self.threshold_frame.setMaximumWidth(360)

        self.threshold_layout = QtWidgets.QVBoxLayout(self.threshold_frame)
        self.threshold_layout.setContentsMargins(18, 16, 18, 16)
        self.threshold_layout.setSpacing(6)

        self.threshold_label = QtWidgets.QLabel()
        self.threshold_label.setObjectName("title")
        self.threshold_label.setWordWrap(True)
        self.threshold_label.setStyleSheet("font-size: 15px;")
        self.threshold_layout.addWidget(self.threshold_label)

        self.label_th1 = QtWidgets.QLabel()
        self.spin25 = self._spin(1, 500, THRESHOLDS.threshold1_percent)
        self.label_th2 = QtWidgets.QLabel()
        self.spin50 = self._spin(1, 500, THRESHOLDS.threshold2_percent)
        self.label_th3 = QtWidgets.QLabel()
        self.spin75 = self._spin(1, 500, THRESHOLDS.threshold3_percent)
        self.label_emg = QtWidgets.QLabel()
        self.spin_emg = self._spin(3, 30, int(THRESHOLDS.emg_threshold_uv))

        for widget in (
            self.label_th1, self.spin25,
            self.label_th2, self.spin50,
            self.label_th3, self.spin75,
            self.label_emg, self.spin_emg,
        ):
            self.threshold_layout.addWidget(widget)

    def _build_mode_panel(self) -> None:
        self.mode_frame = QtWidgets.QFrame()
        self.mode_frame.setObjectName("card")
        self.mode_layout = QtWidgets.QVBoxLayout(self.mode_frame)
        self.mode_layout.setContentsMargins(18, 16, 18, 16)
        self.mode_layout.setSpacing(8)

        self.mode_label = QtWidgets.QLabel()
        self.mode_label.setObjectName("title")
        self.mode_label.setStyleSheet("font-size: 15px;")
        self.mode_layout.addWidget(self.mode_label)

        self.radio_file = QtWidgets.QRadioButton()
        self.radio_file.setChecked(True)
        self.mode_layout.addWidget(self.radio_file)

        self.file_frame = QtWidgets.QFrame()
        self.file_layout = QtWidgets.QVBoxLayout(self.file_frame)
        self.file_layout.setContentsMargins(0, 0, 0, 0)

        file_row = QtWidgets.QHBoxLayout()
        self.btn_select_eeg_file = QtWidgets.QPushButton()
        self.eeg_file_label = QtWidgets.QLabel()
        self.eeg_file_label.setObjectName("muted")
        file_row.addWidget(self.btn_select_eeg_file)
        file_row.addWidget(self.eeg_file_label, 1)
        self.file_layout.addLayout(file_row)
        self.mode_layout.addWidget(self.file_frame)

        self.file_label = QtWidgets.QLabel()
        self.file_label.setObjectName("muted")
        self.mode_layout.addWidget(self.file_label)

        self.radio_live = QtWidgets.QRadioButton()
        self.mode_layout.addWidget(self.radio_live)

        # Заряд читается только после подключения датчиков, поэтому здесь — напоминание.
        self.battery_hint = QtWidgets.QLabel()
        self.battery_hint.setObjectName("hint")
        self.battery_hint.setWordWrap(True)
        self.mode_layout.addWidget(self.battery_hint)

    def _build_action_buttons(self) -> None:
        self.center_layout = QtWidgets.QVBoxLayout()
        self.center_layout.setSpacing(14)
        self.center_layout.addStretch()

        self.app_title = QtWidgets.QLabel()
        self.app_title.setObjectName("title")
        self.app_title.setStyleSheet("font-size: 30px;")
        self.app_title.setAlignment(QtCore.Qt.AlignHCenter)
        self.center_layout.addWidget(self.app_title)

        self.app_subtitle = QtWidgets.QLabel()
        self.app_subtitle.setObjectName("muted")
        self.app_subtitle.setAlignment(QtCore.Qt.AlignHCenter)
        self.center_layout.addWidget(self.app_subtitle)
        self.center_layout.addSpacing(18)

        self.pushButton = QtWidgets.QPushButton()
        self.pushButton.setObjectName("primary")
        self.pushButton.setMinimumHeight(60)

        self.pushButton_2 = QtWidgets.QPushButton()
        self.pushButton_2.setMinimumHeight(52)

        self.center_layout.addWidget(self.pushButton)
        self.center_layout.addWidget(self.pushButton_2)
        self.center_layout.addStretch()

        self.main_layout.addLayout(self.center_layout, stretch=1)

    def retranslateUi(self, main_window: QtWidgets.QMainWindow) -> None:
        _translate = QtCore.QCoreApplication.translate

        main_window.setWindowTitle(_translate("MainWindow", "Главное меню"))

        self.app_title.setText(_translate("MainWindow", "Баскетбол и альфа-ритм"))
        self.app_subtitle.setText(_translate("MainWindow", "Тренировка с датчиками ЭЭГ и ЭМГ"))
        self.pushButton.setText(_translate("MainWindow", "Начать"))
        self.pushButton_2.setText(_translate("MainWindow", "Инструкция"))

        self.threshold_label.setText(_translate("MainWindow", "Пороги α в % прироста от базового"))
        self.label_th1.setText(_translate("MainWindow", "Порог 1 — мяч об пол"))
        self.spin25.setSuffix(_translate("MainWindow", " %"))
        self.label_th2.setText(_translate("MainWindow", "Порог 2 — попадание в кольцо"))
        self.spin50.setSuffix(_translate("MainWindow", " %"))
        self.label_th3.setText(_translate("MainWindow", "Порог 3 — кольцо + болельщики"))
        self.spin75.setSuffix(_translate("MainWindow", " %"))
        self.label_emg.setText(_translate("MainWindow", "Порог ЭМГ"))
        self.spin_emg.setSuffix(_translate("MainWindow", " мкВ"))

        self.mode_label.setText(_translate("MainWindow", "Режим работы"))
        self.radio_file.setText(_translate("MainWindow", "Файл"))
        self.btn_select_eeg_file.setText(_translate("MainWindow", "Выбрать файл..."))
        self.eeg_file_label.setText(_translate("MainWindow", "файл не выбран"))
        self.radio_live.setText(_translate("MainWindow", "Реальное время (ЭЭГ + ЭМГ Юниор)"))
        self.battery_hint.setText(_translate(
            "MainWindow", "Перед сессией зарядите оба датчика. Заряд появится в окне измерения."))
