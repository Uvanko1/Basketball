"""Индикаторы заряда датчиков и баннер предупреждения."""
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from Project.core.battery_monitor import BatteryLevel, BatteryMonitor
from Project.ui.theme import FONT_DISPLAY, P

LEVEL_COLOR = {
    BatteryLevel.OK: P["ok"],
    BatteryLevel.LOW: P["low"],
    BatteryLevel.CRITICAL: P["critical"],
    BatteryLevel.UNKNOWN: P["muted"],
}
LEVEL_TEXT = {
    BatteryLevel.OK: "Заряд в норме",
    BatteryLevel.LOW: "Скоро зарядить",
    BatteryLevel.CRITICAL: "Зарядите датчик",
    BatteryLevel.UNKNOWN: "Нет данных",
}


class BatteryIcon(QtWidgets.QWidget):
    """Аккумулятор, нарисованный вручную: заливка по проценту, цвет по уровню."""

    def __init__(self, compact: bool = False, parent=None):
        super().__init__(parent)
        self._percent: Optional[int] = None
        self._level = BatteryLevel.UNKNOWN
        self._pulse = 0.0
        self._compact = compact
        self.setFixedSize(34, 17) if compact else self.setFixedSize(64, 30)
        self._anim = QtCore.QVariantAnimation(self, duration=900, startValue=0.55, endValue=1.0,
                                              loopCount=-1)
        self._anim.setEasingCurve(QtCore.QEasingCurve.InOutSine)
        self._anim.valueChanged.connect(self._on_pulse)

    def set_state(self, percent: Optional[int], level: BatteryLevel) -> None:
        self._percent, self._level = percent, level
        # мигание только при критическом уровне — единственное «живое» движение интерфейса
        if level == BatteryLevel.CRITICAL:
            self._anim.start()
        else:
            self._anim.stop()
            self._pulse = 1.0
        self.update()

    def _on_pulse(self, v):
        self._pulse = float(v)
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        body = QtCore.QRectF(1.5, 1.5, self.width() - (6 if self._compact else 8), self.height() - 3)
        color = QtGui.QColor(LEVEL_COLOR[self._level])

        p.setPen(QtGui.QPen(QtGui.QColor(P["muted"]), 1.5 if self._compact else 2))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawRoundedRect(body, *( (4, 4) if self._compact else (6, 6) ))
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(P["muted"]))
        nub = 3 if self._compact else 4
        p.drawRoundedRect(QtCore.QRectF(body.right() + 1.5, self.height() / 2 - nub, nub, nub * 2), 1.5, 1.5)

        if self._percent is None:
            p.setPen(QtGui.QColor(P["muted"]))
            p.setFont(QtGui.QFont("Segoe UI", 12, QtGui.QFont.Bold))
            p.drawText(body, QtCore.Qt.AlignCenter, "?")
            return
        pad = 3 if self._compact else 4
        inner = body.adjusted(pad, pad, -pad, -pad)
        fill = QtCore.QRectF(inner.left(), inner.top(),
                             max(3.0, inner.width() * self._percent / 100), inner.height())
        color.setAlphaF(self._pulse)
        p.setBrush(color)
        p.drawRoundedRect(fill, 2, 2)


class SensorBatteryCard(QtWidgets.QFrame):
    def __init__(self, name: str, compact: bool = False, parent=None):
        super().__init__(parent)
        self.name = name
        self._compact = compact
        self._vsize = 16 if compact else 26
        self.setObjectName("card")
        self.setMinimumHeight(44 if compact else 64)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.icon = BatteryIcon(compact)
        self.title = QtWidgets.QLabel(name)
        self.title.setStyleSheet(
            f"font-family: {FONT_DISPLAY}; font-size: {13 if compact else 15}px; font-weight: 600;")
        self.value = QtWidgets.QLabel("—")
        self.status = QtWidgets.QLabel(LEVEL_TEXT[BatteryLevel.UNKNOWN])
        self.status.setStyleSheet(f"font-size: {11 if compact else 13}px; color: {P['muted']};")
        self._style_value(P["line"])

        text = QtWidgets.QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(self.title)
        text.addWidget(self.status)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4) if compact else lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(8 if compact else 12)
        lay.addWidget(self.icon)
        lay.addLayout(text, 1)
        lay.addWidget(self.value)

    def _style_value(self, color: str) -> None:
        self.value.setStyleSheet(
            f"font-family: {FONT_DISPLAY}; font-size: {self._vsize}px; font-weight: 700; color: {color};")

    def set_state(self, percent: Optional[int], level: BatteryLevel) -> None:
        self.icon.set_state(percent, level)
        self.value.setText("—" if percent is None else f"{percent}%")
        self._style_value(LEVEL_COLOR[level] if level != BatteryLevel.OK else P["line"])
        self.status.setText(LEVEL_TEXT[level])
        self.status.setStyleSheet(
            f"font-size: {11 if self._compact else 13}px; color: {LEVEL_COLOR[level]};")


class WarningBanner(QtWidgets.QFrame):
    """Полоса над карточками. Низкий заряд можно скрыть, критический — нет."""

    def __init__(self, compact: bool = False, parent=None):
        super().__init__(parent)
        self._compact = compact
        self.text = QtWidgets.QLabel()  # без переноса: строки короткие, а высота остаётся точной
        self.text.setStyleSheet(f"font-size: {12 if compact else 13}px;")
        self.close_btn = QtWidgets.QPushButton("Ок" if compact else "Понятно")
        if compact:
            self.close_btn.setStyleSheet("padding: 2px 10px;")
        self.close_btn.setMaximumHeight(26 if compact else 32)
        self.close_btn.clicked.connect(self._on_close)
        self.on_dismiss = None
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 8, 6)
        lay.setSpacing(8)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.close_btn, 0, QtCore.Qt.AlignVCenter)
        self.hide()

    def _on_close(self) -> None:
        self.hide()
        if self.on_dismiss:
            self.on_dismiss()

    def show_warning(self, lines: list, level: BatteryLevel) -> None:
        color = LEVEL_COLOR[level]
        self.setStyleSheet(
            f"WarningBanner {{ background: {P['panel']}; border: 1px solid {color};"
            f" border-left: 5px solid {color}; border-radius: 8px; }}")
        self.text.setText("\n".join(lines))
        self.close_btn.setVisible(level != BatteryLevel.CRITICAL)
        self.show()


class BatteryPanel(QtWidgets.QWidget):
    """Карточки ЭЭГ/ЭМГ + баннер. Баннер всегда строится из ТЕКУЩИХ значений."""

    def __init__(self, monitor: BatteryMonitor, vertical: bool = False, parent=None):
        super().__init__(parent)
        self.monitor = monitor
        self._dismissed = None  # снимок уровней, при которых баннер скрыли
        self.cards = {n: SensorBatteryCard(n, compact=vertical) for n in monitor.readers}
        self.banner = WarningBanner(compact=vertical)
        self.banner.on_dismiss = lambda: setattr(self, "_dismissed", dict(self.monitor.level))

        row = QtWidgets.QVBoxLayout() if vertical else QtWidgets.QHBoxLayout()
        row.setSpacing(6 if vertical else 12)
        for c in self.cards.values():
            row.addWidget(c)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6 if vertical else 10)
        lay.addWidget(self.banner)
        lay.addLayout(row)

        monitor.battery_updated.connect(self._on_updated)

    def _on_updated(self, name, percent, level) -> None:
        self.cards[name].set_state(percent, level)
        self._refresh_banner()

    def _refresh_banner(self) -> None:
        levels = self.monitor.level
        lines, worst = [], None
        for n, lvl in levels.items():
            pct = self.monitor.percent[n]
            if lvl == BatteryLevel.CRITICAL:
                lines.append(f"{n} {pct}%: зарядите датчик")
                worst = BatteryLevel.CRITICAL
            elif lvl == BatteryLevel.LOW:
                lines.append(f"{n} {pct}%: скоро зарядить")
                worst = worst or BatteryLevel.LOW
        if worst is None:
            self.banner.hide()
            self._dismissed = None
            return
        if worst == BatteryLevel.LOW and self._dismissed == levels:
            return  # мягкое предупреждение уже скрыто, ничего не изменилось
        if worst == BatteryLevel.CRITICAL:
            lines.append("Иначе сессия может прерваться")
        self.banner.show_warning(lines, worst)


def confirm_start_session(parent, monitor: BatteryMonitor) -> bool:
    """Вызовите перед стартом калибровки/игры. True — можно начинать."""
    low = [n for n, l in monitor.level.items() if l == BatteryLevel.CRITICAL]
    if not low:
        return True
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Warning)
    box.setWindowTitle("Низкий заряд датчиков")
    box.setText(f"Низкий заряд: {', '.join(low)}.")
    box.setInformativeText("Датчик может отключиться посреди сессии, и запись будет неполной. "
                           "Рекомендуем зарядить его перед началом.")
    start = box.addButton("Всё равно начать", QtWidgets.QMessageBox.AcceptRole)
    box.addButton("Отмена", QtWidgets.QMessageBox.RejectRole)
    box.exec_()
    return box.clickedButton() is start
