# Contributing to GrooveXlabs

Thank you for your interest in contributing! We welcome pull requests, bug reports, and feature requests.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/REPO_NAME.git`
3. Install dev dependencies: `pip install -e ".[dev]"`
4. Run tests: `pytest`
5. Make your changes
6. Run linting: `ruff check .`
7. Submit a pull request

## Code Style

- We use **Ruff** for linting and formatting
- Line length: 100 characters
- Target Python version: 3.10+
- Type hints required for public APIs

## Testing

- All new features must include tests
- All bug fixes must include a regression test
- Run the full suite: `pytest -v`
- Aim for >80% coverage

## Commit Messages

Use conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test changes
- `chore:` Maintenance tasks
- `security:` Security fixes

## Pull Request Process

1. Update README.md if needed
2. Add tests for new functionality
3. Ensure CI passes (tests + lint)
4. Request review from a maintainer
5. Squash commits if requested

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers
- Focus on the code, not the person
- No harassment or discrimination

## Questions?

Open a [GitHub Discussion](https://github.com/GrooveXlabs/REPO_NAME/discussions) or email hello@groovexlabs.com
