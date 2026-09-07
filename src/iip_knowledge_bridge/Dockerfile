# ---- Build stage: install the package + deps in an isolated prefix ----
FROM python:3.13-slim AS builder

WORKDIR /app

# pyproject.toml is the single source of truth for dependencies
# (requirements.txt was removed - it had drifted out of sync and
# mixed test-only deps into the production install).
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

# ---- Runtime stage: slim image, no build tools or pip cache ----
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY README.md .

ENV PYTHONUNBUFFERED=1 \
    IIP_ENVIRONMENT=production

RUN useradd -m -u 1000 iipuser && chown -R iipuser:iipuser /app
USER iipuser

# The 'iip' console script is installed by pip via [project.scripts]
# in pyproject.toml - no need to invoke the module path directly.
ENTRYPOINT ["iip"]
CMD ["health"]
