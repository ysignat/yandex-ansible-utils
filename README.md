# Ansible collection `ysignat.yandex`

This repository contains the `ysignat.yandex` Ansible collection of Yandex
Cloud utilities. The collection root is `src`, not the repository root.

User-facing installation, authentication, configuration, and lookup examples
are in the [collection README](src/README.md).

## Repository layout

```text
src/galaxy.yml             Galaxy collection metadata
src/plugins/               Collection plugins
src/meta/                  Ansible runtime and execution-environment metadata
src/python/                Poetry dependency-carrier package
src/README.md              Packaged user documentation
src/CHANGELOG.md           Collection release notes
tests/unit/                Pytest unit tests
pyproject.toml             Runtime and development dependencies
poetry.lock                Locked development environment
```

The package under `src/python` allows consumers to install the controller-side
Python dependencies through Poetry. It is not collection runtime code and is
excluded from the Galaxy artifact by `src/galaxy.yml`.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
