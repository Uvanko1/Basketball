import ctypes
import logging
import threading
import time
from collections import deque
from typing import Optional, Tuple

from Project.config import EEGLIB_DIR, UNIOR_DLL_PATH

logger = logging.getLogger(__name__)

EEG_CHANNEL = 1
EMG_CHANNEL = 2
EMGINT_CHANNEL = 11

# Номера модулей для battery(): float battery(int moduleno)
EEG_MODULE = 1
EMG_MODULE = 2


class UniorChannelData(ctypes.Structure):
    _fields_ = [("value", ctypes.c_float), ("time", ctypes.c_float)]


class UniorDevice:
    def __init__(self, fs: float = 250.0, device_type: str = "EEG"):
        self.Fs = fs
        self.device_type = device_type
        self.is_connected = False
        self.is_running = False
        self.data_buffer = deque(maxlen=int(fs * 10))
        self.time_buffer = deque(maxlen=int(fs * 10))
        self.unior = None
        self.last_error = ""
        self.connection_lock = threading.Lock()
        # DLL опрашивается из потока теста и (для заряда) из GUI — сериализуем вызовы
        self.io_lock = threading.Lock()
        self.unior_battery = None

    def load_library(self) -> Tuple[bool, str]:
        try:
            if not os_path_exists(UNIOR_DLL_PATH):
                return False, f"Файл {UNIOR_DLL_PATH} не найден"

            add_dll_directory_if_available(EEGLIB_DIR)

            self.unior = ctypes.CDLL(UNIOR_DLL_PATH)

            self.unior_open = self.unior.open
            self.unior_open.argtypes = [ctypes.c_char_p]
            self.unior_open.restype = ctypes.c_bool

            self.unior_close = self.unior.close
            self.unior_close.restype = ctypes.c_bool

            self.unior_start = self.unior.start
            self.unior_start.restype = ctypes.c_bool

            self.unior_stop = self.unior.stop
            self.unior_stop.restype = ctypes.c_bool

            self.unior_read = self.unior.read
            self.unior_read.argtypes = [ctypes.c_int]
            self.unior_read.restype = ctypes.POINTER(UniorChannelData)

            self.unior_version = self.unior.version
            self.unior_version.restype = ctypes.c_char_p

            try:
                self.unior_battery = self.unior.battery
                self.unior_battery.argtypes = [ctypes.c_int]   # номер модуля: 1 — ЭЭГ, 2 — ЭМГ
                self.unior_battery.restype = ctypes.c_float    # процент 0..100
            except Exception:
                self.unior_battery = None

            try:
                self.unior_get_module_count = self.unior.getModuleCount
                self.unior_get_module_count.restype = ctypes.c_int
            except Exception:
                self.unior_get_module_count = None

            return True, "Библиотека загружена"

        except Exception as exc:
            return False, f"Ошибка загрузки DLL: {exc}"

    def connect(self) -> Tuple[bool, str]:
        with self.connection_lock:
            try:
                success, message = self.load_library()
                if not success:
                    return False, message

                version_str = "Неизвестно"
                try:
                    if self.unior_get_module_count:
                        logger.info("Доступно модулей: %s", self.unior_get_module_count())
                except Exception:
                    pass

                try:
                    version = self.unior_version()
                    if version:
                        version_str = version.decode("utf-8", errors="ignore")
                except Exception:
                    pass

                logger.info("ЮНИор %s - версия: %s", self.device_type, version_str)

                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        if self.unior_open(b"Auto"):
                            self.is_connected = True
                            self.last_error = ""
                            return True, f"{self.device_type} устройство подключено. Версия: {version_str}"
                        time.sleep(0.5)
                    except Exception as exc:
                        if attempt == max_attempts - 1:
                            return False, (
                                f"Ошибка подключения {self.device_type} "
                                f"(попытка {attempt + 1}/{max_attempts}): {exc}"
                            )

                return False, f"Не удалось подключиться к {self.device_type} устройству."

            except Exception as exc:
                return False, f"Критическая ошибка подключения {self.device_type}: {exc}"

    def disconnect(self) -> bool:
        with self.connection_lock:
            try:
                if self.is_connected and hasattr(self, "unior_close"):
                    self.stop()
                    self.unior_close()
                self.is_connected = False
                self.is_running = False
                self.data_buffer.clear()
                self.time_buffer.clear()
                return True
            except Exception as exc:
                logger.warning("Ошибка при отключении %s: %s", self.device_type, exc)
                return False

    def start(self) -> bool:
        if not self.is_connected:
            return False
        with self.connection_lock:
            try:
                if self.unior_start():
                    self.is_running = True
                    self.data_buffer.clear()
                    self.time_buffer.clear()
                    return True
                return False
            except Exception as exc:
                self.last_error = f"Ошибка запуска {self.device_type}: {exc}"
                return False

    def stop(self) -> bool:
        with self.connection_lock:
            try:
                if self.is_running and hasattr(self, "unior_stop"):
                    self.unior_stop()
                self.is_running = False
                return True
            except Exception as exc:
                logger.warning("Ошибка при остановке %s: %s", self.device_type, exc)
                return False

    def read_sample(self) -> Tuple[Optional[float], Optional[float]]:
        if not self.is_running:
            return None, None

        try:
            channel = EEG_CHANNEL if self.device_type == "EEG" else EMG_CHANNEL
            with self.io_lock:
                p = self.unior_read(channel)
                if not bool(p):
                    return None, None
                val = p.contents.value
                t = p.contents.time / 1000.0

            self.data_buffer.append(val)
            self.time_buffer.append(t)
            return val, t

        except Exception as exc:
            if "access violation" in str(exc).lower() or "указатель" in str(exc).lower():
                self.is_running = False
                self.is_connected = False
                self.last_error = f"{self.device_type} устройство отключилось"
            return None, None

    def read_emg_integral(self) -> Tuple[Optional[float], Optional[float]]:
        if self.device_type != "EMG" or not self.is_running:
            return None, None
        try:
            with self.io_lock:
                p = self.unior_read(EMGINT_CHANNEL)
                if not bool(p):
                    return None, None
                return p.contents.value, p.contents.time / 1000.0
        except Exception:
            return None, None

    def read_battery(self) -> Optional[int]:
        """Заряд в % (0-100) или None, если датчик не подключён / DLL не отдаёт заряд."""
        if not self.is_connected or self.unior_battery is None:
            return None
        try:
            module = EEG_MODULE if self.device_type == "EEG" else EMG_MODULE
            with self.io_lock:
                value = float(self.unior_battery(module))
            if value != value or not 0.0 <= value <= 100.0:  # NaN или вне диапазона
                return None
            return int(round(value))
        except Exception as exc:
            logger.debug("Заряд %s не прочитан: %s", self.device_type, exc)
            return None

    def check_connection(self) -> Tuple[bool, str]:
        if not self.is_connected:
            return False, f"{self.device_type} устройство не подключено"

        try:
            val, _t = self.read_sample()
            if val is None:
                for _ in range(3):
                    time.sleep(0.1)
                    val, _t = self.read_sample()
                    if val is not None:
                        return True, f"{self.device_type} устройство работает"

                self.is_running = False
                self.is_connected = False
                return False, f"{self.device_type} устройство перестало отвечать"

            return True, f"{self.device_type} устройство работает"
        except Exception as exc:
            self.is_running = False
            self.is_connected = False
            return False, f"Ошибка проверки соединения {self.device_type}: {exc}"


class DualUniorManager:
    def __init__(self, fs: float = 250.0):
        self.Fs = fs
        self.eeg_device = UniorDevice(fs, "EEG")
        self.emg_device = UniorDevice(fs, "EMG")
        self.is_running = False

    def connect_both(self):
        results = []
        eeg_success, eeg_msg = self.eeg_device.connect()
        results.append(("ЭЭГ", eeg_success, eeg_msg))

        emg_success, emg_msg = self.emg_device.connect()
        results.append(("ЭМГ", emg_success, emg_msg))

        return eeg_success and emg_success, results

    def disconnect_both(self):
        results = [
            ("ЭЭГ", self.eeg_device.disconnect()),
            ("ЭМГ", self.emg_device.disconnect()),
        ]
        self.is_running = False
        return results

    def start_both(self) -> Tuple[bool, str]:
        if not self.eeg_device.is_connected or not self.emg_device.is_connected:
            return False, "Оба устройства должны быть подключены"

        eeg_started = self.eeg_device.start()
        emg_started = self.emg_device.start()
        self.is_running = eeg_started and emg_started
        return self.is_running, (
            f"ЭЭГ: {'запущен' if eeg_started else 'ошибка'}, "
            f"ЭМГ: {'запущен' if emg_started else 'ошибка'}"
        )

    def stop_both(self) -> bool:
        eeg_stopped = self.eeg_device.stop()
        emg_stopped = self.emg_device.stop()
        self.is_running = False
        return eeg_stopped and emg_stopped

    def read_samples(self):
        if not self.is_running:
            return None, None, None, None, None, None

        eeg_val, eeg_t = self.eeg_device.read_sample()
        emg_val, emg_t = self.emg_device.read_sample()
        emg_int, emg_int_t = self.emg_device.read_emg_integral()
        return eeg_val, eeg_t, emg_val, emg_t, emg_int, emg_int_t

    def battery_readers(self):
        return {"ЭЭГ": self.eeg_device.read_battery, "ЭМГ": self.emg_device.read_battery}

    def check_connections(self):
        eeg_ok, eeg_msg = self.eeg_device.check_connection()
        emg_ok, emg_msg = self.emg_device.check_connection()
        return eeg_ok and emg_ok, [f"ЭЭГ: {eeg_msg}", f"ЭМГ: {emg_msg}"]


def os_path_exists(path: str) -> bool:
    import os

    return os.path.exists(path)


def add_dll_directory_if_available(directory: str) -> None:
    import os

    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is not None:
        try:
            add_dll_directory(directory)
        except OSError:
            pass
