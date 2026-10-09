from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CrawlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    targets: list[str] = Field(default_factory=list)
    scope_hosts: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    include_subdomains: bool = False
    max_depth: int = Field(default=5, ge=0, le=100)
    max_pages: int = Field(default=1000, ge=1, le=1000000)
    rate_limit: float = Field(default=0.5, gt=0, le=100)
    concurrency: int = Field(default=8, ge=1, le=128)
    timeout: float = Field(default=30, gt=0, le=600)
    max_body_bytes: int = Field(default=2097152, ge=1024, le=16777216)
    max_discoveries: int = Field(default=20000, ge=1, le=1000000)
    max_links_per_page: int = Field(default=1000, ge=1, le=10000)
    respect_robots: bool = True
    allow_local: bool = False
    browser: bool = False
    source_maps: bool = False
    validate_passive: bool = False
    passive: list[str] = Field(default_factory=list)
    passive_limit: int = Field(default=1000, ge=1, le=10000)
    commoncrawl_index: str = "CC-MAIN-2026-38"
    output: str | None = None
    sqlite: str | None = None
    jobdir: str | None = None

    @field_validator("passive")
    @classmethod
    def validate_sources(cls, value):
        if set(value) - {"wayback", "commoncrawl", "urlscan"}:
            raise ValueError("Unknown passive source")
        return value


def load_yaml(path):
    data = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a YAML mapping")
    return data
