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

## Development setup

The project supports Python 3.12 through 3.14 and `ansible-core >=2.19.0`.
Poetry installs the project-scoped export plugin declared in `pyproject.toml`.
Create or update the development environment from the repository root:

```bash
poetry install
```

When dependency constraints change, refresh and validate the lockfile:

```bash
poetry lock
poetry check --lock
```

Runtime dependencies belong in `project.dependencies`. Development-only tools
belong in the `dev` dependency group.

## Required checks

Run all validation commands from the repository root before handing off a
completed change:

```bash
poetry check --lock
poetry run ruff check .
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-tests poetry run pytest -q
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-lint \
  poetry run ansible-lint --profile production src
```

Focused tests can be run during development, for example:

```bash
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-tests \
  poetry run pytest -q tests/unit/plugins/lookup/test_lockbox.py
```

## Generate runtime requirements

Ansible Galaxy does not install a collection's controller-side Python
dependencies. Before building, export the main dependency group into the
collection:

```bash
poetry export \
  -f requirements.txt \
  --output src/requirements.txt
```

`src/requirements.txt` is generated and ignored by Git. Do not edit or commit
it. Development dependencies are not included in the export.

The packaged `src/meta/execution-environment.yml` points `ansible-builder` to
this requirements file.

## Build and inspect the collection

After generating `src/requirements.txt`, build the Galaxy artifact in an
isolated temporary directory:

```bash
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-build \
  poetry run ansible-galaxy collection build src \
  --output-path /tmp/ansible-yandex-build \
  --force
```

Inspect the artifact contents:

```bash
tar -tzf /tmp/ansible-yandex-build/ysignat-yandex-*.tar.gz
```

Confirm that the artifact contains:

- `README.md`
- `CHANGELOG.md`
- `requirements.txt`
- `meta/runtime.yml`
- `meta/execution-environment.yml`

It must not contain Poetry files, virtual environments, caches, tests,
repository-only documentation, or the dependency-carrier `python` directory.

## Isolated installation and documentation check

Install the built artifact into an isolated collection path:

```bash
ANSIBLE_COLLECTIONS_PATH=/tmp/ansible-yandex-collections \
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-install \
ANSIBLE_GALAXY_CACHE_DIR=/tmp/ansible-yandex-galaxy-cache \
  poetry run ansible-galaxy collection install \
  /tmp/ansible-yandex-build/ysignat-yandex-*.tar.gz \
  --collections-path /tmp/ansible-yandex-collections \
  --force
```

Verify plugin discovery and generated documentation:

```bash
ANSIBLE_COLLECTIONS_PATH=/tmp/ansible-yandex-collections \
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-doc \
  poetry run ansible-doc -t lookup ysignat.yandex.lockbox
```

## Release checklist

Before publishing a release:

1. Update the version in both `pyproject.toml` and `src/galaxy.yml`.
2. Update `src/CHANGELOG.md`.
3. Run `poetry lock` and `poetry check --lock`.
4. Run all commands in [Required checks](#required-checks).
5. Generate `src/requirements.txt` as described above.
6. Build and inspect the Galaxy artifact.
7. Confirm that the artifact includes all required files and excludes all
   development-only files.
8. Install the artifact into the isolated path and validate the lookup plugin
   with `ansible-doc`.

Keep the version in `pyproject.toml` synchronized with `src/galaxy.yml` for
every release.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
