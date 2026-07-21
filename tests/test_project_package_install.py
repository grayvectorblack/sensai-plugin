"""Regression coverage for public E2E drivers outside the repository tree."""

import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_uv_run_makes_project_package_importable_to_external_driver(tmp_path: Path) -> None:
    driver = tmp_path / "external_driver.py"
    driver.write_text("import sensai_plugin\nprint(sensai_plugin.__name__)\n", encoding="utf-8")

    result = subprocess.run(
        ["uv", "run", "python", str(driver)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "sensai_plugin"
