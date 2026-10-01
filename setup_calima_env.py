#!/usr/bin/env python3
"""Create an environment for calima_mqtt.py and optionally run it."""

import argparse
import os
import shutil
import subprocess
import sys
import venv

try:
    from pathlib import Path
except ImportError:
    Path = None


ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, ".venv")
REQUIREMENTS = os.path.join(ROOT, "calima-requirements.txt")
APP = os.path.join(ROOT, "calima_mqtt.py")
CONDA_ENV_NAME = "calima-mqtt"
DEFAULT_CONDA_PYTHON = "3.9"


def run(command):
    print("+", " ".join(command))
    subprocess.check_call(command, cwd=ROOT)


def is_windows():
    return os.name == "nt"


def venv_python():
    if is_windows():
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def find_conda():
    candidates = []
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe:
        candidates.append(conda_exe)

    which_conda = shutil.which("conda")
    if which_conda:
        candidates.append(which_conda)

    home = os.path.expanduser("~")
    if is_windows():
        candidates.extend([
            os.path.join(home, "miniforge3", "Scripts", "conda.exe"),
            os.path.join(home, "miniconda3", "Scripts", "conda.exe"),
            os.path.join(home, "anaconda3", "Scripts", "conda.exe"),
        ])
    else:
        candidates.extend([
            os.path.join(home, "miniforge3", "bin", "conda"),
            os.path.join(home, "miniconda3", "bin", "conda"),
            os.path.join(home, "anaconda3", "bin", "conda"),
        ])

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def install_with_python(python):
    run([python, "-m", "pip", "install", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "-r", REQUIREMENTS])


def create_venv():
    if not os.path.exists(VENV_DIR):
        print("Creating virtual environment at {}".format(VENV_DIR))
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)

    python = venv_python()
    install_with_python(python)
    return [python]


def conda_run_prefix(conda, env_name):
    return [conda, "run", "-n", env_name]


def conda_env_exists(conda, env_name):
    try:
        subprocess.check_call(
            [conda, "run", "-n", env_name, "python", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=ROOT,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def create_conda(env_name, python_version, install_on_windows):
    conda = find_conda()
    if not conda:
        raise SystemExit("Could not find conda. Activate Miniforge or pass --manager venv.")

    if not conda_env_exists(conda, env_name):
        run([conda, "create", "-y", "-n", env_name, "python={}".format(python_version), "pip"])

    prefix = conda_run_prefix(conda, env_name)
    run(prefix + ["python", "-m", "pip", "install", "--upgrade", "pip"])

    if is_windows() and not install_on_windows:
        print()
        print("Skipping Calima Bluetooth dependencies on Windows.")
        print("bluepy builds a Linux Bluetooth helper with make, so install/run this on the Raspberry Pi or Linux host.")
        print("Use --install-on-windows if you only want to see the expected build failure.")
    else:
        run(prefix + ["python", "-m", "pip", "install", "-r", REQUIREMENTS])

    return prefix + ["python"]


def validate_runtime_env():
    missing = [name for name in ("CALIMA_MACADDR", "CALIMA_PINCODE") if not os.environ.get(name)]
    if missing:
        raise SystemExit("Missing required environment variable(s): {}".format(", ".join(missing)))


def create_environment(args):
    if args.manager == "conda":
        return create_conda(args.env_name, args.python_version, args.install_on_windows)
    if args.manager == "venv":
        return create_venv()

    if find_conda():
        return create_conda(args.env_name, args.python_version, args.install_on_windows)
    return create_venv()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manager",
        choices=("auto", "conda", "venv"),
        default="auto",
        help="Environment manager to use. Default: auto, preferring conda when available.",
    )
    parser.add_argument(
        "--env-name",
        default=CONDA_ENV_NAME,
        help="Conda environment name. Default: {}.".format(CONDA_ENV_NAME),
    )
    parser.add_argument(
        "--python-version",
        default=DEFAULT_CONDA_PYTHON,
        help="Python version for conda env creation. Default: {}.".format(DEFAULT_CONDA_PYTHON),
    )
    parser.add_argument(
        "--install-on-windows",
        action="store_true",
        help="Try installing bluepy on Windows even though it is expected to fail.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run calima_mqtt.py after creating/updating the environment.",
    )
    args = parser.parse_args()

    python_command = create_environment(args)

    if args.run:
        validate_runtime_env()
        run(python_command + [APP])
    else:
        print()
        print("Environment is ready.")
        print("Set CALIMA_MACADDR and CALIMA_PINCODE, then run:")
        print("  {}".format(" ".join(python_command + [APP])))
        print("Or rerun this setup script with --run.")


if __name__ == "__main__":
    main()
