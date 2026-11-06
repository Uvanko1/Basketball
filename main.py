import faulthandler
import logging
import os
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler


def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


LOG_PATH = os.path.join(_app_dir(), "biobasket.log")
_fault_file = None


def _show_fatal(text: str) -> None:
    try:
        from PyQt5 import QtWidgets

        if QtWidgets.QApplication.instance() is not None:
            QtWidgets.QMessageBox.critical(
                None, "BioBasket: ошибка", f"{text}\n\nПодробности в файле:\n{LOG_PATH}"
            )
            return
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0, f"{text}\n\nПодробности в файле:\n{LOG_PATH}", "BioBasket: ошибка", 0x10
            )
        except Exception:
            pass


def _setup_diagnostics() -> None:
    global _fault_file

    handlers = [RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    log = logging.getLogger("main")

    try:
        _fault_file = open(LOG_PATH, "a", encoding="utf-8")
        faulthandler.enable(file=_fault_file, all_threads=True)
    except Exception:
        pass

    def excepthook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        log.error("Необработанное исключение:\n%s", text)
        _show_fatal(f"{exc_type.__name__}: {exc}")

    def thread_excepthook(args):
        text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        log.error("Исключение в потоке %s:\n%s", getattr(args.thread, "name", "?"), text)

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook

    log.info("=== Запуск BioBasket === frozen=%s, python=%s", getattr(sys, "frozen", False), sys.version.split()[0])
    log.info("exe/dir: %s | лог: %s", _app_dir(), LOG_PATH)


_setup_diagnostics()
_log = logging.getLogger("main")

try:
    from PyQt5 import QtWidgets

    from Project import config
    from Project.data.database import DatabaseManager
    from Project.ui.login_dialog import UserLoginDialog
    from Project.ui.main_window import MainWindow
    from Project.ui.theme import apply_theme
except Exception as _exc:
    _log.exception("Ошибка импорта модулей")
    _show_fatal(f"Ошибка запуска: {_exc}")
    raise SystemExit(1)

_log.info("DLL датчика: %s (%s)", config.UNIOR_DLL_PATH, "найдена" if os.path.exists(config.UNIOR_DLL_PATH) else "НЕ НАЙДЕНА")
_log.info("Звуки: %s", [os.path.exists(p) for p in (config.SOUND_BALL_PATH, config.SOUND_RING_PATH, config.SOUND_CLAPS_PATH)])
_log.info("БД: %s | сессии: %s", config.DB_PATH, config.SESSION_DATA_DIR)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    apply_theme(app)

    db = DatabaseManager()
    login = UserLoginDialog(db)

    if login.exec_() == QtWidgets.QDialog.Accepted:
        main_window = MainWindow(db, login.user_id, login.user_fio)
        main_window.show()
        sys.exit(app.exec_())

    _log.info("Окно логина закрыто без входа — выход")
    sys.exit(0)


if __name__ == "__main__":
    main()