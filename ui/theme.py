"""Тема «вечерний зал»: графитовая площадка, оранжевый мяч, разметка кремового цвета."""
from PyQt5 import QtGui, QtWidgets

P = {
    "floor":   "#171B22",   # фон окна
    "panel":   "#202631",   # карточки
    "panel_hi": "#2A3240",  # наведение / рамки
    "line":    "#EFE8D8",   # «разметка площадки» — основной текст
    "muted":   "#8E98A8",
    "ball":    "#F2701D",   # главный акцент
    "ball_dk": "#C95A12",
    "eeg":     "#5BC0EB",   # цвета графиков
    "emg":     "#E9B44C",
    "alpha":   "#4ED1A1",
    "ok":      "#4ED1A1",
    "low":     "#F2A33A",
    "critical": "#E5484D",
}
FONT_DISPLAY = "Bahnschrift, 'Segoe UI Semibold', 'Segoe UI', sans-serif"
FONT_BODY = "'Segoe UI', 'Noto Sans', sans-serif"

QSS = f"""
* {{ font-family: {FONT_BODY}; font-size: 13px; color: {P['line']}; }}
QMainWindow, QDialog, QWidget#root {{ background: {P['floor']}; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-family: {FONT_DISPLAY}; font-size: 22px; font-weight: 600; }}
QLabel#score {{ font-family: {FONT_DISPLAY}; font-size: 64px; font-weight: 700; color: {P['ball']}; }}
QLabel#muted, QLabel#hint {{ color: {P['muted']}; }}

QFrame#card, QGroupBox {{
    background: {P['panel']}; border: 1px solid {P['panel_hi']}; border-radius: 12px; }}
QGroupBox {{ margin-top: 14px; padding: 14px 12px 10px 12px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px;
    font-family: {FONT_DISPLAY}; font-size: 13px; color: {P['muted']}; }}

QPushButton {{ background: {P['panel_hi']}; border: 1px solid #38425A; border-radius: 8px;
    padding: 8px 18px; }}
QPushButton:hover {{ background: #344058; }}
QPushButton:pressed {{ background: {P['panel']}; }}
QPushButton:disabled {{ color: #5A6475; background: {P['panel']}; border-color: {P['panel_hi']}; }}
QPushButton#primary {{ background: {P['ball']}; border: none; color: #1A1206;
    font-family: {FONT_DISPLAY}; font-weight: 700; font-size: 15px; padding: 10px 26px; }}
QPushButton#primary:hover {{ background: #FF8434; }}
QPushButton#primary:pressed {{ background: {P['ball_dk']}; }}
QPushButton#primary:disabled {{ background: #4A3A2C; color: #8A7A68; }}
QPushButton:focus {{ border: 1px solid {P['line']}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {P['floor']};
    border: 1px solid {P['panel_hi']}; border-radius: 8px; padding: 6px 10px;
    selection-background-color: {P['ball']}; selection-color: #1A1206; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {P['ball']}; }}
QComboBox QAbstractItemView {{ background: {P['panel']}; selection-background-color: {P['ball']};
    selection-color: #1A1206; border: 1px solid {P['panel_hi']}; }}

QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right;
    width: 22px; border: none; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right;
    width: 22px; border: none; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ width: 0; height: 0; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-bottom: 5px solid {P['muted']}; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ width: 0; height: 0; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-top: 5px solid {P['muted']}; }}
QSpinBox::up-arrow:hover, QSpinBox::down-arrow:hover,
QDoubleSpinBox::up-arrow:hover, QDoubleSpinBox::down-arrow:hover {{ border-bottom-color: {P['ball']}; }}

QRadioButton {{ spacing: 8px; }}
QRadioButton::indicator {{ width: 12px; height: 12px; border-radius: 8px; border: 2px solid {P['muted']};
    background: {P['floor']}; }}
QRadioButton::indicator:checked {{ background: {P['ball']}; border-color: {P['ball']}; }}
QRadioButton:disabled {{ color: #5A6475; }}

QSlider::groove:horizontal {{ height: 6px; background: {P['panel_hi']}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {P['ball']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {P['line']}; width: 18px; height: 18px;
    margin: -7px 0; border-radius: 9px; border: 2px solid {P['ball']}; }}
QSlider::handle:horizontal:disabled {{ background: #5A6475; border-color: #3A4354; }}
QSlider::sub-page:horizontal:disabled {{ background: #3A4354; }}

QTabWidget::pane {{ border: 1px solid {P['panel_hi']}; border-radius: 10px; top: -1px; }}
QTabBar::tab {{ background: transparent; padding: 8px 18px; color: {P['muted']};
    border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {P['line']}; border-bottom: 2px solid {P['ball']}; }}

QProgressBar {{ background: {P['panel_hi']}; border: none; border-radius: 5px; height: 10px;
    text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {P['ball']}; border-radius: 5px; }}

QStatusBar {{ background: {P['panel']}; color: {P['muted']}; }}
QToolTip {{ background: {P['panel']}; color: {P['line']}; border: 1px solid {P['ball']}; padding: 4px 8px; }}
QMessageBox {{ background: {P['panel']}; }}
"""


def apply_theme(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.Window, QtGui.QColor(P["floor"]))
    pal.setColor(QtGui.QPalette.Base, QtGui.QColor(P["floor"]))
    pal.setColor(QtGui.QPalette.Text, QtGui.QColor(P["line"]))
    pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor(P["line"]))
    pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(P["ball"]))
    app.setPalette(pal)
    app.setStyleSheet(QSS)


def style_plot(plot, color: str, title: str = "", y_label: str = "") -> None:
    """Оформить pyqtgraph.PlotWidget: plot — PlotWidget, color — P['eeg'] / P['emg'] / P['alpha']."""
    bg = QtGui.QColor(P["panel"])
    bg.setAlpha(215)  # чуть прозрачный — сцена с корзиной просвечивает
    plot.setBackground(bg)
    item = plot.getPlotItem()
    item.showGrid(x=True, y=True, alpha=0.12)
    for axis in ("left", "bottom"):
        ax = item.getAxis(axis)
        ax.setPen(P["muted"])
        ax.setTextPen(P["muted"])
    if title:
        item.setTitle(title, color=P["line"], size="11pt")
    if y_label:
        item.setLabel("left", y_label, color=P["muted"])
    for curve in item.curves:
        curve.setPen(color, width=2)


def overlay_panel_style(object_name: str) -> str:
    """Полупрозрачная панель поверх фоновой картинки (для виджетов с objectName)."""
    return (f"QWidget#{object_name} {{ background: rgba(23,27,34,215); "
            f"border: 1px solid {P['panel_hi']}; border-radius: 14px; }}")


def status_style(color: str) -> str:
    """Плашка статуса с цветной полосой слева."""
    return (f"color: {color}; font-size: 13px; padding: 12px; "
            f"background-color: rgba(23,27,34,170); border-radius: 8px; "
            f"border-left: 4px solid {color};")
