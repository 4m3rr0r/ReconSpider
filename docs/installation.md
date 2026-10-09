# Installation

Use Ubuntu with Python 3.11 or newer:

```bash
sudo apt-get install python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
reconspider --help
scrapy list
```

The dev extra installs pytest, Ruff, build, and shub. For runtime only use `pip install .`.
Scrapy supplies lxml/Twisted; dependency wheels normally avoid compiler requirements. If your architecture lacks wheels, install `build-essential python3-dev libxml2-dev libxslt1-dev libssl-dev libffi-dev` as needed. Python 3.11+ is required even if Ubuntu's default Python is older.

Cloud uses `requirements.txt` as additions to a stack containing Scrapy; local installation uses the complete dependency declaration in `pyproject.toml`. Never put API keys in either file. Browser packages and Chromium are not required for the supported static crawler.

See the README's local demonstration before pointing the tool at a permitted public host. To develop, run `pytest -q`, `ruff check .`, `ruff format --check .`, and `python -m build` from this directory.
