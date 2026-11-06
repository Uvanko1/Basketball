"""Мониторинг заряда датчиков ЭЭГ/ЭМГ и выбор уровня предупреждения."""
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Optional

from PyQt5 import QtCore

logger = logging.getLogger(__name__)


class BatteryLevel(Enum):
    UNKNOWN = "unknown"
    OK = "ok"
    LOW = "low"
    CRITICAL = "critical"


@dataclass(frozen=True)
class BatteryConfig:
    low_percent: int = 30          # ниже — мягкое предупреждение
    critical_percent: int = 15     # ниже — «зарядите сейчас»
    hysteresis: int = 3            # чтобы уровень не мигал на границе
    poll_interval_ms: int = 15_000
    fast_poll_ms: int = 2_000      # пока датчик ещё подключается и заряд неизвестен
    critical_reminder_sec: int = 300


BATTERY = BatteryConfig()  # при желании перенесите в Project/config.py


def classify(percent: Optional[int], previous: BatteryLevel = BatteryLevel.UNKNOWN,
             cfg: BatteryConfig = BATTERY) -> BatteryLevel:
    if percent is None:
        return BatteryLevel.UNKNOWN
    h = cfg.hysteresis
    # возврат на более «хороший» уровень требует запаса в h процентов
    crit = cfg.critical_percent + (h if previous == BatteryLevel.CRITICAL else 0)
    low = cfg.low_percent + (h if previous in (BatteryLevel.LOW, BatteryLevel.CRITICAL) else 0)
    if percent < crit:
        return BatteryLevel.CRITICAL
    if percent < low:
        return BatteryLevel.LOW
    return BatteryLevel.OK


class BatteryMonitor(QtCore.QObject):
    """Раз в poll_interval_ms опрашивает датчики и шлёт сигналы в UI.

    readers: {"ЭЭГ": callable -> Optional[int], "ЭМГ": callable -> Optional[int]}
    """

    battery_updated = QtCore.pyqtSignal(str, object, object)  # имя, % | None, BatteryLevel
    warning = QtCore.pyqtSignal(str, int, object)             # имя, %, BatteryLevel

    def __init__(self, readers: Dict[str, Callable[[], Optional[int]]],
                 cfg: BatteryConfig = BATTERY, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.readers = readers
        self.percent: Dict[str, Optional[int]] = {n: None for n in readers}
        self.level: Dict[str, BatteryLevel] = {n: BatteryLevel.UNKNOWN for n in readers}
        self._last_warn: Dict[str, float] = {}
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.poll)

    def start(self) -> None:
        self.poll()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def poll(self) -> None:
        for name, reader in self.readers.items():
            try:
                value = reader()
            except Exception:
                logger.exception("Не удалось прочитать заряд: %s", name)
                value = None
            self.update_value(name, value)
        unknown = any(v is None for v in self.percent.values())
        self._timer.setInterval(self.cfg.fast_poll_ms if unknown else self.cfg.poll_interval_ms)

    def update_value(self, name: str, value: Optional[int]) -> None:
        """Публичный метод — удобно для тестов и симулятора."""
        if value is not None:
            value = max(0, min(100, int(value)))
        prev = self.level.get(name, BatteryLevel.UNKNOWN)
        level = classify(value, prev, self.cfg)
        self.percent[name], self.level[name] = value, level
        self.battery_updated.emit(name, value, level)

        if level in (BatteryLevel.LOW, BatteryLevel.CRITICAL):
            now = time.monotonic()
            worse = level != prev and (prev in (BatteryLevel.UNKNOWN, BatteryLevel.OK)
                                       or level == BatteryLevel.CRITICAL)
            remind = (level == BatteryLevel.CRITICAL and
                      now - self._last_warn.get(name, 0) > self.cfg.critical_reminder_sec)
            if worse or remind:
                self._last_warn[name] = now
                self.warning.emit(name, value, level)

    def worst_level(self) -> BatteryLevel:
        order = [BatteryLevel.CRITICAL, BatteryLevel.LOW, BatteryLevel.OK, BatteryLevel.UNKNOWN]
        for lvl in order:
            if lvl in self.level.values():
                return lvl
        return BatteryLevel.UNKNOWN
