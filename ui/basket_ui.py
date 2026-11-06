from PyQt5 import QtCore, QtWidgets
import pyqtgraph as pg

from Project.config import THRESHOLDS
from Project.ui.theme import P, overlay_panel_style, status_style, style_plot

CTRL_FRAME_STYLE = (
    "QFrame#ctrlFrame { background: rgba(23,27,34,225); border: 1px solid " + P["panel_hi"] + ";"
    " border-radius: 14px; }"
)

CENTRAL_WIDGET_STYLE = """
    QWidget#centralwidget {
        background-image: url(:/newPrefix/basket.jpg);
        background-position: center;
        background-repeat: no-repeat;
    }
"""


class Ui_Basket:
    def setupUi(self, basket_window: QtWidgets.QMainWindow) -> None:
        basket_window.setObjectName("Basket")
        basket_window.resize(800, 600)

        self.centralwidget = QtWidgets.QWidget(basket_window)
        self.centralwidget.setObjectName("centralwidget")
        self.centralwidget.setStyleSheet(CENTRAL_WIDGET_STYLE)
        basket_window.setCentralWidget(self.centralwidget)

        self.main_layout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(20)

        self._build_control_panel()
        self.main_layout.addWidget(
            self.ctrl_frame, 0, alignment=QtCore.Qt.AlignLeft
        )

        self._build_plot_area()
        self.main_layout.addWidget(self.right_container)

        self._build_score_label()
        self._build_threshold_sliders()
        self._build_alpha_and_emg_controls()

        self.retranslateUi(basket_window)
        QtCore.QMetaObject.connectSlotsByName(basket_window)

    def _build_control_panel(self) -> None:
        self.ctrl_frame = QtWidgets.QFrame()
        self.ctrl_frame.setObjectName("ctrlFrame")
        self.ctrl_frame.setStyleSheet(CTRL_FRAME_STYLE)
        self.ctrl_frame.setMinimumWidth(300)
        self.ctrl_frame.setMaximumWidth(380)
        self.ctrl_frame.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)

        self.ctrl_layout = QtWidgets.QVBoxLayout(self.ctrl_frame)
        self.ctrl_layout.setContentsMargins(16, 16, 16, 16)
        self.ctrl_layout.setSpacing(10)

        self.ctrl_label = QtWidgets.QLabel()
        self.ctrl_label.setObjectName("title")
        self.ctrl_layout.addWidget(self.ctrl_label)

        # Счёт — главная цифра экрана, поэтому он первый в панели
        self.score_label = QtWidgets.QLabel("Счёт: 0")
        self.score_label.setObjectName("score")
        self.score_label.setStyleSheet("font-size: 44px;")
        self.ctrl_layout.addWidget(self.score_label)

        # Сюда окно вставляет BatteryPanel (только в режиме реального времени)
        self.battery_container = QtWidgets.QVBoxLayout()
        self.battery_container.setContentsMargins(0, 0, 0, 0)
        self.ctrl_layout.addLayout(self.battery_container)

        self.thresholds_label = QtWidgets.QLabel()
        self.thresholds_label.setWordWrap(True)
        self.thresholds_label.setObjectName("muted")
        self.ctrl_layout.addWidget(self.thresholds_label)

        self.mode_label = QtWidgets.QLabel()
        self.mode_label.setWordWrap(True)
        self.mode_label.setStyleSheet(status_style(P["eeg"]).replace("padding: 12px", "padding: 8px"))
        self.ctrl_layout.addWidget(self.mode_label)

        self.eeg_status_label = QtWidgets.QLabel()
        self.eeg_status_label.setStyleSheet(f"color: {P['eeg']}; font-size: 12px;")
        self.ctrl_layout.addWidget(self.eeg_status_label)

        self.emg_status_label = QtWidgets.QLabel()
        self.emg_status_label.setStyleSheet(f"color: {P['emg']}; font-size: 12px;")
        self.ctrl_layout.addWidget(self.emg_status_label)

        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(80)
        self.status_label.setStyleSheet(status_style(P["line"]))
        self.ctrl_layout.addWidget(self.status_label)

        self.ctrl_layout.addStretch()

        self.btn_back = QtWidgets.QPushButton()
        self.btn_back.setMinimumHeight(40)
        self.ctrl_layout.addWidget(self.btn_back)

    def _build_plot_area(self) -> None:
        self.right_container = QtWidgets.QWidget()
        self.right_layout = QtWidgets.QVBoxLayout(self.right_container)
        self.right_layout.addStretch()

        self.bottom_row = QtWidgets.QHBoxLayout()
        self.bottom_row.addStretch()

        self.plot_container = QtWidgets.QWidget()
        self.plot_container.setFixedSize(600, 550)
        self.plot_container.setObjectName("plotCard")
        self.plot_container.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.plot_container.setStyleSheet(overlay_panel_style("plotCard"))
        self.plot_layout = QtWidgets.QVBoxLayout(self.plot_container)
        self.plot_layout.setContentsMargins(10, 10, 10, 10)

        self.bottom_row.addWidget(self.plot_container)
        self.right_layout.addLayout(self.bottom_row)

        self.eeg_plot = pg.PlotWidget(title="Сырой ЭЭГ")
        self.eeg_curve = self.eeg_plot.plot(pen=pg.mkPen("c", width=1))
        self.plot_layout.addWidget(self.eeg_plot)

        self.emg_plot = pg.PlotWidget(title="Сырой ЭМГ")
        self.emg_curve = self.emg_plot.plot(pen=pg.mkPen("m", width=1))
        self.plot_layout.addWidget(self.emg_plot)

        self.emg_int_plot = pg.PlotWidget(title="Интегральная ЭМГ")
        self.emg_int_curve = self.emg_int_plot.plot(pen=pg.mkPen("m", width=1))
        self.plot_layout.addWidget(self.emg_int_plot)

        self.alpha_plot = pg.PlotWidget(title="Альфа-ритм (9–11 Гц)")
        self.alpha_curve = self.alpha_plot.plot(pen=pg.mkPen("g", width=2))
        self.plot_layout.addWidget(self.alpha_plot)

        for plot, curve, color in (
            (self.eeg_plot, self.eeg_curve, P["eeg"]),
            (self.emg_plot, self.emg_curve, P["emg"]),
            (self.emg_int_plot, self.emg_int_curve, P["emg"]),
            (self.alpha_plot, self.alpha_curve, P["alpha"]),
        ):
            style_plot(plot, color)
            curve.setPen(pg.mkPen(color, width=2 if plot is self.alpha_plot else 1))

    def _build_score_label(self) -> None:
        pass  # score_label создаётся в _build_control_panel

    def _build_threshold_sliders(self) -> None:
        self.slider_th1 = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_th2 = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_th3 = QtWidgets.QSlider(QtCore.Qt.Horizontal)

        self.slider_th1.setValue(THRESHOLDS.threshold1_percent)
        self.slider_th2.setValue(THRESHOLDS.threshold2_percent)
        self.slider_th3.setValue(THRESHOLDS.threshold3_percent)

        self.slider_layout = QtWidgets.QVBoxLayout()

        for label_text, slider in (
            ("Порог 1 (%)", self.slider_th1),
            ("Порог 2 (%)", self.slider_th2),
            ("Порог 3 (%)", self.slider_th3),
        ):
            label = QtWidgets.QLabel(label_text)
            label.setObjectName("muted")
            self.slider_layout.addWidget(label)
            self.slider_layout.addWidget(slider)

        for slider in (self.slider_th1, self.slider_th2, self.slider_th3):
            slider.setMinimum(0)
            slider.setMaximum(100)

        self.plot_layout.addLayout(self.slider_layout)

    def _build_alpha_and_emg_controls(self) -> None:
        self.alpha_low_spin = QtWidgets.QDoubleSpinBox()
        self.alpha_high_spin = QtWidgets.QDoubleSpinBox()
        self.emg_spin = QtWidgets.QDoubleSpinBox()

        self.alpha_low_spin.setRange(1.0, 30.0)
        self.alpha_high_spin.setRange(1.0, 30.0)
        self.emg_spin.setRange(3.0, 100000.0)

        self.alpha_low_spin.setValue(THRESHOLDS.alpha_low_hz)
        self.alpha_high_spin.setValue(THRESHOLDS.alpha_high_hz)
        self.emg_spin.setValue(THRESHOLDS.emg_threshold_uv)

        self.alpha_low_spin.setSuffix(" Гц")
        self.alpha_high_spin.setSuffix(" Гц")
        self.emg_spin.setSuffix(" мкВ")

        self.alpha_low_spin.setSingleStep(0.5)
        self.alpha_high_spin.setSingleStep(0.5)
        self.emg_spin.setSingleStep(1)

        alpha_layout = QtWidgets.QHBoxLayout()
        alpha_layout.addWidget(QtWidgets.QLabel("Альфа от:"))
        alpha_layout.addWidget(self.alpha_low_spin)
        alpha_layout.addWidget(QtWidgets.QLabel("до:"))
        alpha_layout.addWidget(self.alpha_high_spin)
        alpha_layout.addWidget(QtWidgets.QLabel("Порог ЭМГ"))
        alpha_layout.addWidget(self.emg_spin)

        self.plot_layout.addLayout(alpha_layout)

    def retranslateUi(self, basket_window: QtWidgets.QMainWindow) -> None:
        _translate = QtCore.QCoreApplication.translate
        basket_window.setWindowTitle(_translate("Basket", "Баскетбол - Измерение"))
        self.ctrl_label.setText(_translate("Basket", "Измерение"))
        self.thresholds_label.setText(_translate("Basket", "Пороги: не установлены"))
        self.mode_label.setText(_translate("Basket", "Режим: не выбран"))
        self.eeg_status_label.setText(_translate("Basket", "ЭЭГ: не подключен"))
        self.emg_status_label.setText(_translate("Basket", "ЭМГ: не подключен"))
        self.status_label.setText(_translate("Basket", "Статус: подготовка..."))
        self.btn_back.setText(_translate("Basket", "Назад в меню"))


import Project.Resources.basket_rc
