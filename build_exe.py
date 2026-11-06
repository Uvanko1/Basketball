import glob
import os
import shutil
import subprocess
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(SRC_DIR, "_build_tmp")
VENV_DIR = os.path.join(SRC_DIR, "_venv_build")

IS_WINDOWS = os.name == "nt"
BASE_PYTHON = os.environ.get("BASE_PYTHON", r"C:\Program Files\Python312\python.exe")

APP_NAME = "BioBasket"
CONSOLE = "--console" in sys.argv

PACKAGES = ["core", "data", "device", "testers", "ui"]
ASSET_DIRS = ["EEGLib", "Resources"]

REQUIRED_FILES = [
    "main.py",
    "config.py",
    os.path.join("EEGLib", "unior_v4.dll"),
    os.path.join("Resources", "ball_cut.wav"),
    os.path.join("Resources", "ring.wav"),
    os.path.join("Resources", "claps.wav"),
    os.path.join("Resources", "basket_rc.py"),
]

DEPS = [
    "pyinstaller",
    "PyQt5==5.15.11",
    "numpy>=2.0,<2.3",
    "scipy==1.14.1",
    "edfio~=0.4",
    "pyqtgraph~=0.14.0",
]


def get_venv_python():
    sub = "Scripts" if IS_WINDOWS else "bin"
    exe = "python.exe" if IS_WINDOWS else "python"
    return os.path.join(VENV_DIR, sub, exe)


def get_base_python():
    if os.path.exists(BASE_PYTHON):
        return BASE_PYTHON
    print(f"Не найден {BASE_PYTHON}, беру текущий интерпретатор: {sys.executable}")
    return sys.executable


def ensure_venv():
    venv_python = get_venv_python()
    if os.path.exists(venv_python):
        print(f"Сборочный venv уже есть: {VENV_DIR}")
        return venv_python

    print("Создание чистого сборочного venv...")
    subprocess.run([get_base_python(), "-m", "venv", VENV_DIR], check=True)

    print("Установка зависимостей (только нужные)...")
    subprocess.run(
        [venv_python, "-m", "pip", "install", "--no-cache-dir", "--default-timeout=300"] + DEPS,
        check=True,
    )
    print("Venv готов.")
    return venv_python


def _patch_scipy():
    pattern = os.path.join(
        VENV_DIR, "**", "site-packages", "scipy", "stats", "_distn_infrastructure.py"
    )
    found = glob.glob(pattern, recursive=True)
    if not found:
        return
    target = found[0]
    with open(target, "r", encoding="utf-8") as f:
        src = f.read()
    old = "del obj\n"
    new = "try:\n    del obj\nexcept NameError:\n    pass\n"
    if old in src and new not in src:
        src = src.replace(old, new, 1)
        with open(target, "w", encoding="utf-8") as f:
            f.write(src)
        print("Патч scipy _distn_infrastructure.py применён.")


def check_sources():
    missing = [p for p in REQUIRED_FILES if not os.path.exists(os.path.join(SRC_DIR, p))]
    missing += [d for d in PACKAGES + ASSET_DIRS if not os.path.isdir(os.path.join(SRC_DIR, d))]
    if missing:
        print("ОШИБКА: не найдены нужные файлы/папки (запускайте скрипт из папки Project/):")
        for p in missing:
            print(f"  - {p}")
        sys.exit(1)

    with open(os.path.join(SRC_DIR, "config.py"), "r", encoding="utf-8") as f:
        cfg = f.read()
    if "sys.executable" not in cfg:
        print()
        print("!" * 60)
        print("ВНИМАНИЕ: config.py кладёт app_data.db и session_data в sys._MEIPASS.")
        print("В режиме --onefile это временная папка: пользователи, настройки и")
        print("записанные сессии будут пропадать при каждом закрытии программы.")
        print("Исправьте config.py (см. описание: отдельный APP_DIR для данных).")
        print("!" * 60)
        print()


def collect_hidden_imports(project_dir):
    modules = ["Project"]
    for root, _dirs, files in os.walk(project_dir):
        for name in files:
            if not name.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(root, name), project_dir)
            parts = rel[:-3].split(os.sep)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if parts:
                modules.append(".".join(["Project"] + parts))
    return sorted(set(modules))


SPEC_TEMPLATE = r'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

EXCLUDES = [
    'pytest', 'doctest', 'test',
    'matplotlib',
    'tkinter', '_tkinter',
    'IPython', 'jupyter', 'notebook', 'ipykernel', 'ipywidgets',
    'tornado', 'flask', 'django', 'http.server',
    'h5py', 'tables', 'numba', 'llvmlite',
    'sphinx', 'babel', 'setuptools', 'pip', 'wheel',
    'pandas', 'sympy', 'OpenGL',
    'torch', 'torchvision', 'torchaudio', 'transformers',
    'cv2', 'sklearn', 'scikit-learn',
    'pyarrow', 'pymupdf', 'nltk', 'networkx', 'mne',
]

a = Analysis(
    [@@MAIN_PY@@],
    pathex=[@@BUILD_DIR@@],
    binaries=[],
    datas=[
        (@@DLL_SRC@@, 'EEGLib'),
        (@@WAV_BALL@@, 'Resources'),
        (@@WAV_RING@@, 'Resources'),
        (@@WAV_CLAPS@@, 'Resources'),
    ],
    hiddenimports=@@HIDDEN@@ + ['PyQt5.QtMultimedia'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

QT_REMOVE = [
    'Qt5WebEngine', 'Qt5Quick', 'Qt5Qml', 'Qt5Designer',
    'Qt5Location', 'Qt5Bluetooth', 'Qt5Nfc', 'Qt5Sensors',
    'Qt5SerialPort', 'Qt5Test', 'Qt5WebSockets', 'Qt5WebChannel',
    'Qt5Positioning', 'Qt5DBus', 'Qt5Help', 'Qt5Script',
    'Qt5XmlPatterns', 'opengl32sw',
]
a.binaries = [b for b in a.binaries if not any(q in b[0] for q in QT_REMOVE)]

QT_PLUGIN_KEEP = ['platforms', 'imageformats', 'styles', 'audio', 'mediaservice']
a.datas = [d for d in a.datas
           if 'plugins' not in d[0]
           or any(k in d[0] for k in QT_PLUGIN_KEEP)]

a.datas = [d for d in a.datas if 'translations' not in d[0]]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name=@@APP_NAME@@,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['unior_v4.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'python312.dll'],
    runtime_tmpdir=None,
    console=@@CONSOLE@@,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''


def build(python_exe):
    check_sources()

    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR)

    project_dir = os.path.join(BUILD_DIR, "Project")
    os.makedirs(project_dir)

    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for folder in PACKAGES + ASSET_DIRS:
        shutil.copytree(
            os.path.join(SRC_DIR, folder), os.path.join(project_dir, folder), ignore=ignore
        )
    shutil.copy2(os.path.join(SRC_DIR, "config.py"), os.path.join(project_dir, "config.py"))

    for root, _dirs, _files in os.walk(project_dir):
        init_path = os.path.join(root, "__init__.py")
        if not os.path.exists(init_path):
            open(init_path, "w").close()

    shutil.copy2(os.path.join(SRC_DIR, "main.py"), os.path.join(BUILD_DIR, "main.py"))

    _patch_scipy()

    res_dir = os.path.join(project_dir, "Resources")
    replacements = {
        "@@MAIN_PY@@": repr(os.path.join(BUILD_DIR, "main.py")),
        "@@BUILD_DIR@@": repr(BUILD_DIR),
        "@@DLL_SRC@@": repr(os.path.join(project_dir, "EEGLib", "unior_v4.dll")),
        "@@WAV_BALL@@": repr(os.path.join(res_dir, "ball_cut.wav")),
        "@@WAV_RING@@": repr(os.path.join(res_dir, "ring.wav")),
        "@@WAV_CLAPS@@": repr(os.path.join(res_dir, "claps.wav")),
        "@@HIDDEN@@": repr(collect_hidden_imports(project_dir)),
        "@@APP_NAME@@": repr(APP_NAME),
        "@@CONSOLE@@": repr(CONSOLE),
    }
    spec_content = SPEC_TEMPLATE
    for key, value in replacements.items():
        spec_content = spec_content.replace(key, value)

    spec_path = os.path.join(BUILD_DIR, f"{APP_NAME}.spec")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_content)

    print()
    print("=" * 60)
    print("Запуск PyInstaller..." + (" (режим с консолью)" if CONSOLE else ""))
    print("=" * 60)

    result = subprocess.run(
        [python_exe, "-m", "PyInstaller", "--clean", spec_path],
        cwd=BUILD_DIR,
    )

    if result.returncode != 0:
        print("\nОШИБКА: Сборка завершилась с ошибкой.")
        sys.exit(1)

    exe_name = APP_NAME + (".exe" if IS_WINDOWS else "")
    exe_src = os.path.join(BUILD_DIR, "dist", exe_name)
    exe_dst = os.path.join(SRC_DIR, exe_name)

    if os.path.exists(exe_src):
        shutil.copy2(exe_src, exe_dst)
        size_mb = os.path.getsize(exe_dst) / (1024 * 1024)
        print()
        print("=" * 60)
        print(f"ГОТОВО! {exe_dst}")
        print(f"Размер: {size_mb:.0f} МБ")
        print("=" * 60)
        print()
        print("app_data.db и папка session_data создаются рядом с exe при первом запуске.")
        print("Чтобы перенести пользователей, положите старый app_data.db рядом с exe.")
    else:
        print("\nОШИБКА: exe не найден после сборки.")
        sys.exit(1)

    print("\nОчистка временных файлов сборки...")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    print("Готово. (venv оставлен в _venv_build для повторных сборок)")


if __name__ == "__main__":
    python_exe = ensure_venv()
    build(python_exe)