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

## Release checklist

Before publishing a release:

1. Update the version in both `pyproject.toml` and `src/galaxy.yml`.
2. Update `src/CHANGELOG.md`.
3. Generate `src/requirements.txt` as described above.
4. Build and inspect the Galaxy artifact.
5. Confirm that the artifact includes all required files and excludes all
   development-only files.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
