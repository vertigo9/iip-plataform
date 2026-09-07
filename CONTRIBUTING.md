# Contributing to IIP Platform

## Development Workflow

1. **Install development dependencies:**
   `ash
   pip install -e ".[dev]"
   `

2. **Make your changes:**
   - Create a feature branch
   - Follow the existing code style (Black formatter)
   - Add type hints where possible

3. **Run tests before committing:**
   `ash
   python -m pytest -v
   python -m ruff check src/
   `

4. **Ensure coverage doesn't drop:**
   `ash
   python -m pytest --cov=iip --cov-fail-under=68
   `

5. **Update documentation if needed:**
   - README.md for user-facing changes
   - ADRs for architectural decisions
   - Inline comments for complex logic

## Code Style

- **Formatter:** Black (line length 100)
- **Linter:** Ruff (E, F, I, N, W, UP rules)
- **Type checker:** MyPy (strict mode)
- **Tests:** pytest with coverage

## Submitting Changes

1. Open a pull request
2. Describe the changes clearly
3. Reference related issues if applicable
4. Ensure all CI checks pass
