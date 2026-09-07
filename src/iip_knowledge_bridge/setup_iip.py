"""
IIP Platform v0.1.0-alpha — Project Setup Script
Gera toda a estrutura de diretórios e arquivos iniciais.
Compatível com Windows, Linux e macOS.

Uso: python setup_iip.py
"""

from pathlib import Path

# ============================================================
# CONFIGURAÇÃO
# ============================================================

PROJECT_NAME = "iip-platform"
BASE_DIR = Path.cwd()

# ============================================================
# ESTRUTURA DE DIRETÓRIOS
# ============================================================

DIRECTORIES = [
    "",
    "docs",
    "docs/architecture",
    "docs/adr",
    "docs/api",
    "docs/modules",
    "docs/releases",
    "scripts",
    "tests",
    "examples",
    "src",
    "src/iip",
    "src/iip/core",
    "src/iip/common",
    "src/iip/config",
    "src/iip/events",
    "src/iip/registry",
    "src/iip/logging",
    "src/iip/metrics",
    "src/iip/health",
    "src/iip/synchronization",
    "src/iip/replication",
    "src/iip/plugins",
    "src/iip/versioning",
    "src/iip/exceptions",
    "src/iip/cli",
]

# ============================================================
# CONTEÚDO DOS ARQUIVOS
# ============================================================

FILES: dict[str, str] = {}

# --- Root files ---

FILES["pyproject.toml"] = """\
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "iip-platform"
version = "0.1.0-alpha"
description = "Institutional Investment Platform — IIP"
readme = "README.md"
license = {text = "Proprietary"}
requires-python = ">=3.13"
authors = [{name = "IIP Team"}]

dependencies = [
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "structlog>=24.1",
    "click>=8.1",
    "rich>=13.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "black>=24.4",
    "mypy>=1.10",
]
db = [
    "sqlalchemy>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
]
cache = [
    "redis>=5.0",
]

[project.scripts]
iip = "iip.cli.main:cli"

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.black]
line-length = 100
target-version = ["py313"]

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = "-v --cov=iip --cov-report=term-missing --cov-fail-under=80"
asyncio_mode = "auto"

[tool.setuptools.packages.find]
where = ["src"]
"""

FILES["README.md"] = """\
# IIP — Institutional Inves
"""
