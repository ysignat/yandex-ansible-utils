# Repository guidance

## Project overview

This repository is published as `github.com/ysignat/yandex-ansible-utils` and
contains the `ysignat.yandex` Ansible collection. Preserve that collection FQCN
regardless of repository layout or project-package naming changes. The
collection root is `src`, not the repository root.

While the collection version is below `1.0.0`, treat its public interfaces as
pre-stable. Whenever either version changes, update both `pyproject.toml` and
`src/galaxy.yml` so they remain synchronized. Update `src/CHANGELOG.md` when
preparing a release.

## Automated version tagging

- `.github/workflows/tag-version.yml` runs after every push to `main` and has
  `contents: write` permission so its `GITHUB_TOKEN` can push a Git tag.
- The workflow reads `version` from `src/galaxy.yml` and `project.version` from
  `pyproject.toml`. A mismatch fails with a GitHub Actions error annotation that
  reports both values and asks the contributor to synchronize the files.
- A matching version is used verbatim as the tag name; do not add a `v` prefix.
  The workflow creates an annotated tag on the pushed commit.
- Rerunning the workflow is safe when the tag already points to that commit. If
  the tag points to another commit, the workflow fails and requires a version
  bump; it must never move or overwrite an existing version tag.
- Keep full Git history and tags available in the checkout step because the
  duplicate-tag safety check depends on them. Keep tagging jobs serialized with
  the workflow's concurrency group to reduce races between rapid pushes.

## Layout

- `src/galaxy.yml`: Galaxy collection metadata.
- `src/plugins/`: collection plugins.
- `src/meta/`: Ansible runtime and execution-environment metadata.
- `src/python/`: Poetry dependency-carrier package; this is not collection
  runtime code and must remain excluded from the Galaxy artifact.
- `src/README.md`: packaged, user-facing collection documentation.
- `tests/unit/`: pytest unit tests.
- `README.md`: repository development and release documentation.
- `pyproject.toml` and `poetry.lock`: canonical dependencies and development
  environment.

## Dependencies and generated files

- Use Poetry from the repository root.
- Runtime dependencies belong in `project.dependencies`.
- Development-only dependencies belong in the `dev` dependency group.
- `src/requirements.txt` is generated and ignored by Git. Do not edit or
  commit it, and do not stage it. Recreate it when required for packaging.
- Generate runtime requirements before building the collection:

  ```bash
  poetry export -f requirements.txt --output src/requirements.txt
  ```

- Ansible Galaxy does not install controller-side Python dependencies for a
  collection. Keep `src/meta/execution-environment.yml` pointing to the
  generated requirements file.

## Required checks

Run relevant focused tests while developing. Before handing off a completed
change, run all of the following from the repository root:

```bash
poetry check --lock
poetry run ruff check .
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-tests poetry run pytest -q
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-lint \
  poetry run ansible-lint --profile production src
```

When a change affects packaged collection code, metadata, dependencies, or
documentation, generate requirements and validate a Galaxy build:

```bash
poetry export -f requirements.txt --output src/requirements.txt
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-build \
  poetry run ansible-galaxy collection build src \
  --output-path /tmp/ansible-yandex-build \
  --force
```

Before a release, and after discovery or packaging changes, inspect and install
the artifact in an isolated directory and validate its generated documentation:

```bash
tar -tzf /tmp/ansible-yandex-build/ysignat-yandex-*.tar.gz
ANSIBLE_COLLECTIONS_PATH=/tmp/ansible-yandex-collections \
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-install \
ANSIBLE_GALAXY_CACHE_DIR=/tmp/ansible-yandex-galaxy-cache \
  poetry run ansible-galaxy collection install \
  /tmp/ansible-yandex-build/ysignat-yandex-*.tar.gz \
  --collections-path /tmp/ansible-yandex-collections \
  --force
ANSIBLE_COLLECTIONS_PATH=/tmp/ansible-yandex-collections \
ANSIBLE_LOCAL_TEMP=/tmp/ansible-yandex-doc \
  poetry run ansible-doc -t lookup ysignat.yandex.lockbox
```

Confirm that the artifact contains the files required below and none of the
excluded development files. Use isolated paths under `/tmp` for installation
and documentation checks. Redirect `ANSIBLE_LOCAL_TEMP` and
`ANSIBLE_GALAXY_CACHE_DIR` when default home directories are not writable.
`src/requirements.txt` must exist before artifact inspection, installation, or
documentation validation.

## Python and test conventions

- Support Python 3.12 through 3.14.
- Keep tests in pytest style; do not introduce `unittest.TestCase` classes.
- Add type annotations to test helpers, fixtures, fakes, and captured values.
- The pytest Python path and collection source root is `src`.
- Import the lookup plugin in tests as:

  ```python
  from plugins.lookup import lockbox
  ```

- Mock gRPC channels and generated stubs in unit tests. Real Yandex Cloud
  integration tests must be opt-in and must not require credentials during the
  normal test run.
- When changing the lookup plugin, cover:
  - Direct argument, Ansible variable, environment variable, and default
    resolution, including their precedence.
  - Missing and whitespace-only IAM tokens and endpoints.
  - Boolean, zero, negative, infinite, and NaN timeouts.
  - Reference parsing, RPC request construction, successful text values,
    unsupported values, and missing keys.
  - Multiple lookup terms and result ordering.
  - Channel cleanup after successful calls and exceptions.
  - gRPC error conversion and verification that errors never contain IAM
    tokens, retrieved values, or raw upstream error details.

## Lockbox plugin behavior

- Lookup references use `secret-id:key` or `secret-id:version-id:key`.
- Omitting the version ID requests the latest secret version.
- Pass component values to the Lockbox API unchanged and let the API validate
  its supported character set.
- Reject malformed references, extra delimiters, and empty values with
  `AnsibleError`.
- Require the IAM token to be a non-empty string.
- Require a non-empty endpoint string before creating the gRPC connection.
- Pass the endpoint unchanged to `grpc.secure_channel` and keep TLS enabled by
  using a secure gRPC channel.
- Only text entries are supported; unsupported value types must raise a clear
  `AnsibleError` rather than failing silently.
- Close the gRPC channel after both successful and failing lookup runs.
- Configuration precedence is:

  1. Direct lookup argument
  2. Ansible variable
  3. Controller environment variable
  4. Documented default

- Supported option sources and defaults are:

  | Option    | Direct argument | Ansible variable      | Environment variable  | Default                                    |
  | --------- | --------------- | --------------------- | --------------------- | ------------------------------------------ |
  | IAM token | `iam_token`     | `yc_iam_token`        | `YC_IAM_TOKEN`        | Required                                   |
  | Endpoint  | `endpoint`      | `yc_lockbox_endpoint` | `YC_LOCKBOX_ENDPOINT` | `payload.lockbox.api.cloud.yandex.net:443` |
  | Timeout   | `timeout`       | `yc_lockbox_timeout`  | `YC_LOCKBOX_TIMEOUT`  | `10.0` seconds                             |

- Keep the RPC timeout positive, finite, configurable, and passed to every
  Lockbox RPC. Reject boolean timeout values even though `bool` is a subclass
  of `int` in Python.
- Translate `grpc.RpcError` into stable `AnsibleError` messages containing
  useful status and secret context.

## Security

- Never log, display, commit, or include IAM tokens or retrieved secret values
  in errors.
- Do not include raw upstream gRPC error details when they might expose
  sensitive information.
- Every task example that retrieves a secret must include `no_log: true`
  immediately after the task name.
- Tests must use obviously fake credentials and secret values.

## Documentation and packaging

- Update `src/README.md` and embedded plugin `DOCUMENTATION`/`EXAMPLES` when
  user-facing behavior or options change.
- Keep user-facing defaults, option sources, authentication guidance, and
  examples synchronized across `src/README.md`, embedded `DOCUMENTATION` and
  `EXAMPLES`, tests, and implementation.
- Embedded plugin examples must use the same environment-based authentication
  approach documented in `src/README.md`.
- Update the root `README.md` when development, validation, build, or release
  workflows change.
- Ensure the built artifact contains `README.md`, `CHANGELOG.md`,
  `requirements.txt`, `meta/runtime.yml`, and
  `meta/execution-environment.yml`.
- Ensure the artifact does not contain Poetry files, virtual environments,
  caches, tests, repository-only documentation, or the dependency-carrier
  `python` directory.

## Working tree safety

- Preserve existing user changes and staging state unless explicitly asked to
  modify them.
- Do not commit, stage, publish, or tag changes unless explicitly requested.
- Treat ignored virtual environments, caches, and generated requirements as
  local state. Remove them only when necessary for the requested work.
