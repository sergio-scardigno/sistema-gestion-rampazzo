"""
Build cross-platform para Sistema Rampazzo.

Uso:
    python build.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SPEC_FILE = PROJECT_ROOT / "SistemaRampazzo.spec"
MAIN_FILE = PROJECT_ROOT / "main.py"
BUILD_DIR = PROJECT_ROOT / "build_out"
DIST_DIR = PROJECT_ROOT / "dist_out"
APP_DIR = DIST_DIR / "SistemaRampazzo"
BUILD_NUMBER_FILE = PROJECT_ROOT / "build_number.txt"
BUILD_INFO_FILE = PROJECT_ROOT / "build_info.py"
ZIP_FILE = PROJECT_ROOT / "SistemaRampazzo.zip"
CONFIG_FILE = PROJECT_ROOT / "config.ini"
CONFIG_EXAMPLE_FILE = PROJECT_ROOT / "config.ini.example"


def _print(msg: str) -> None:
    print(msg, flush=True)


def _fail(msg: str, exit_code: int = 1) -> None:
    _print(f"[ERROR] {msg}")
    raise SystemExit(exit_code)


def _check_project_files() -> None:
    if not MAIN_FILE.exists():
        _fail("No se encontro main.py. Ejecutar build.py desde la raiz del proyecto.")
    if not SPEC_FILE.exists():
        _fail("No se encontro SistemaRampazzo.spec. Es necesario para el build.")


def _ensure_pyinstaller() -> None:
    _print("[1/6] Verificando PyInstaller...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--version"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        version = result.stdout.strip() or result.stderr.strip() or "desconocida"
        _print(f"      OK (version {version})")
        return

    _print("      No encontrado. Instalando...")
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        cwd=PROJECT_ROOT,
    )
    if install.returncode != 0:
        _fail("No se pudo instalar PyInstaller.")
    _print("      Instalado correctamente.")


def _clean_previous_builds() -> None:
    _print("[2/6] Limpiando build anterior...")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    _print("      OK")


def _read_build_number() -> int:
    if not BUILD_NUMBER_FILE.exists():
        return 0
    raw = BUILD_NUMBER_FILE.read_text(encoding="utf-8").strip()
    try:
        return int(raw)
    except ValueError:
        return 0


def _write_build_info() -> int:
    _print("[3/6] Incrementando numero de build...")
    build_number = _read_build_number() + 1
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    BUILD_NUMBER_FILE.write_text(f"{build_number}\n", encoding="utf-8")
    BUILD_INFO_FILE.write_text(
        f"BUILD_NUMBER = {build_number}\n"
        f'BUILD_TIMESTAMP = "{timestamp}"\n',
        encoding="utf-8",
    )
    _print(f"      Build #{build_number} - {timestamp}")
    return build_number


def _run_pyinstaller() -> None:
    _print("[4/6] Compilando ejecutable con PyInstaller...")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC_FILE),
        "--noconfirm",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
    ]
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        _fail("PyInstaller fallo. Revisar los mensajes de error.")

    app_binary_name = "SistemaRampazzo.exe" if sys.platform.startswith("win") else "SistemaRampazzo"
    app_binary = APP_DIR / app_binary_name
    if not app_binary.exists():
        _fail(f"No se genero el binario esperado: {app_binary}")

    _print(f"      Binario generado: {app_binary}")


def _copy_config_files() -> None:
    _print("[5/6] Copiando archivos de configuracion...")
    APP_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        shutil.copy2(CONFIG_FILE, APP_DIR / "config.ini")
        _print("      config.ini copiado (con credenciales de MongoDB).")
    else:
        _print("      [WARN] No se encontro config.ini. La app iniciara en modo offline.")

    if CONFIG_EXAMPLE_FILE.exists():
        shutil.copy2(CONFIG_EXAMPLE_FILE, APP_DIR / "config.ini.example")

    _print("      OK")


def _create_zip() -> Path:
    _print("[6/6] Generando ZIP distribuible...")
    if ZIP_FILE.exists():
        ZIP_FILE.unlink()

    archive_base = PROJECT_ROOT / "SistemaRampazzo"
    zip_path = Path(
        shutil.make_archive(
            base_name=str(archive_base),
            format="zip",
            root_dir=str(APP_DIR),
        )
    )
    size_mb = round(zip_path.stat().st_size / (1024 * 1024), 1)
    _print(f"      ZIP generado: {zip_path} ({size_mb} MB)")
    return zip_path


def main() -> None:
    _print("============================================")
    _print("  Sistema Rampazzo - Build + ZIP")
    _print("============================================")
    _print(f"Python: {sys.executable}")

    _check_project_files()
    _ensure_pyinstaller()
    _clean_previous_builds()
    build_number = _write_build_info()
    _run_pyinstaller()
    _copy_config_files()
    zip_path = _create_zip()

    _print("")
    _print("============================================")
    _print("  BUILD EXITOSO")
    _print("============================================")
    _print(f"Build: #{build_number}")
    _print(f"Salida app: {APP_DIR}")
    _print(f"ZIP: {zip_path}")


if __name__ == "__main__":
    main()
