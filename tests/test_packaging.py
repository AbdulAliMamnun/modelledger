from __future__ import annotations

import subprocess
import sys
import shutil
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_built_wheel_contains_and_loads_default_registry(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(
        PROJECT_ROOT,
        source,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", "venv", "build", "dist", "*.egg-info", "__pycache__"
        ),
    )
    wheel_directory = tmp_path / "wheel"
    wheel_directory.mkdir()
    subprocess.run(
        [
            sys.executable, "-m", "pip", "wheel", str(source), "--no-deps",
            "--no-build-isolation", "--wheel-dir", str(wheel_directory),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_directory.glob("modelledger-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        assert "modelledger/data/models.yaml" in archive.namelist()

    installed = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", str(wheel), "--no-deps",
            "--target", str(installed),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(installed)!r}); "
        "from modelledger.registry import load_registry; "
        "models = load_registry(); "
        "assert len(models) == 3; "
        "print(models[0]['model_id'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "demo-active-v1"
