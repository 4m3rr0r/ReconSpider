"""Check the artifact metadata consumed by Scrapy Cloud's dependency checker."""

import subprocess
import sys
from importlib.metadata import distributions
from pathlib import Path


def test_deployment_egg_exposes_loadable_scrapy_settings(tmp_path):
    project = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "setup.py",
            "egg_info",
            "--egg-base",
            str(tmp_path),
            "build",
            "--build-base",
            str(tmp_path / "build"),
            "bdist_egg",
            "--bdist-dir",
            str(tmp_path / "egg"),
            "--dist-dir",
            str(tmp_path / "dist"),
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    egg = next((tmp_path / "dist").glob("*.egg"))
    distribution = next(distributions(path=[str(egg)]))
    settings = next(
        entry
        for entry in distribution.entry_points
        if entry.group == "scrapy" and entry.name == "settings"
    )
    assert settings.value == "reconspider.settings"
    assert settings.load().SPIDER_MODULES == ["reconspider.spiders"]
    assert any(entry.name == "reconspider" for entry in distribution.entry_points)
