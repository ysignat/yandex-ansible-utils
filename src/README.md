# Ansible collection `ysignat.yandex`

The `ysignat.yandex` collection provides utilities for integrating Ansible
with Yandex Cloud. It includes the `lockbox` lookup plugin, which retrieves
text values from Yandex Cloud Lockbox on the Ansible controller.

## Requirements

- Python 3.12 through 3.14 on the Ansible controller
- `ansible-core >=2.19.0`
- A Yandex Cloud identity with the `lockbox.payloadViewer` role for each secret
  it needs to read

## Installation

The collection and its controller-side Python dependencies are installed
separately because Ansible Galaxy does not install Python dependencies declared
by a collection.

In the versioned examples below, replace `<version>` with the release to
install.

Install the latest release from Ansible Galaxy:

```bash
ansible-galaxy collection install ysignat.yandex
```

To install a specific version, add a version constraint such as
`ysignat.yandex:==<version>`.

Alternatively, install a release tarball directly from GitHub:

```bash
VERSION="<version>"
ansible-galaxy collection install \
  "https://github.com/ysignat/yandex-ansible-utils/releases/download/${VERSION}/ysignat-yandex-${VERSION}.tar.gz"
```

Or install the collection source from a Git tag:

```bash
VERSION="<version>"
ansible-galaxy collection install \
  "git+ssh://git@github.com/ysignat/yandex-ansible-utils.git,${VERSION}"
```

Use Poetry to add the controller-side Python dependencies from a Git tag:

```bash
VERSION="<version>"
poetry add \
  "git+ssh://git@github.com/ysignat/yandex-ansible-utils.git@${VERSION}"
```

Alternatively, add them from the release source-code tarball:

```bash
VERSION="<version>"
poetry add \
  "https://github.com/ysignat/yandex-ansible-utils/archive/refs/tags/${VERSION}.tar.gz"
```

When Poetry does not manage the Ansible environment, install the same package
with pip instead:

```bash
VERSION="<version>"
python -m pip install \
  "git+ssh://git@github.com/ysignat/yandex-ansible-utils.git@${VERSION}"
```

Replace the Git URL with the release source-code tarball URL from the preceding
example to install that archive with pip.

For Ansible execution environments, the packaged
`meta/execution-environment.yml` directs `ansible-builder` to
`requirements.txt` automatically.

## Authentication

The lookup requires a Yandex Cloud IAM token. Set it in the environment on the
Ansible controller:

```bash
export YC_IAM_TOKEN="..."
```

The plugin reads `YC_IAM_TOKEN` implicitly. You can also read the environment
variable explicitly with the built-in `env` lookup and assign it to the
`yc_iam_token` Ansible variable:

```yaml
vars:
  yc_iam_token: "{{ lookup('ansible.builtin.env', 'YC_IAM_TOKEN') }}"
```

When both are present, `yc_iam_token` takes precedence over `YC_IAM_TOKEN`.

## Usage

References use one of these colon-delimited forms:

```text
secret-id:key
secret-id:version-id:key
```

The two-part form reads the current (latest) secret version.

Read `password` from the latest version:

```yaml
- name: Read the latest database password
  no_log: true
  ansible.builtin.set_fact:
    database_password: >-
      {{ lookup('ysignat.yandex.lockbox',
                'e6qetpqfe8vv00000000:password') }}
```

Read it from a specific version:

```yaml
- name: Read a versioned database password
  no_log: true
  ansible.builtin.set_fact:
    database_password: >-
      {{ lookup('ysignat.yandex.lockbox',
                'e6qetpqfe8vv00000000:e6qdnt9t2qsd00000000:password') }}
```

Use `query` to retrieve multiple values while preserving a list result:

```yaml
- name: Read multiple Lockbox values
  no_log: true
  ansible.builtin.set_fact:
    database_credentials: >-
      {{ query('ysignat.yandex.lockbox',
               'e6qetpqfe8vv00000000:username',
               'e6qetpqfe8vv00000000:password') }}
```

## Plugin options

| Option      | Direct argument | Ansible variable      | Environment variable  | Default                                    |
| ----------- | --------------- | --------------------- | --------------------- | ------------------------------------------ |
| IAM token   | `iam_token`     | `yc_iam_token`        | `YC_IAM_TOKEN`        | Required                                   |
| Endpoint    | `endpoint`      | `yc_lockbox_endpoint` | `YC_LOCKBOX_ENDPOINT` | `payload.lockbox.api.cloud.yandex.net:443` |
| RPC timeout | `timeout`       | `yc_lockbox_timeout`  | `YC_LOCKBOX_TIMEOUT`  | `10.0` seconds                             |

Precedence, from highest to lowest, is:

1. Direct lookup argument
2. Ansible variable
3. Controller environment variable
4. Documented default

For example, to use a private Lockbox-compatible endpoint and a five-second
timeout:

```yaml
{{ lookup('ysignat.yandex.lockbox',
          'e6qetpqfe8vv00000000:password',
          endpoint='lockbox-proxy.example.com:443',
          timeout=5) }}
```

The endpoint must be a non-empty string. The timeout must be a positive, finite
number and is applied to every Lockbox RPC.

## Errors and limitations

- Only text entries are supported. Looking up a binary entry raises an Ansible
  error.
- Empty components, extra delimiters, and malformed references raise an
  Ansible error.
- Missing keys and unsupported value types raise an Ansible error instead of
  returning an empty value.
- Lockbox RPC failures become Ansible errors containing the gRPC status and
  secret ID. They do not contain the IAM token or raw upstream error details.
- The gRPC channel is closed after each lookup invocation.

## Secret handling

- Do not commit IAM tokens or retrieved secret values to source control.
- Source tokens from environment variables, Ansible Vault, or another secret
  manager.
- Add `no_log: true` to every task that could expose retrieved values.
- Avoid displaying real secrets with `debug`.
- Keep controller and execution-environment logs access-controlled.

## Development

The collection source lives at `src` in the repository. See the
repository-root README for dependency setup, tests, lint, requirements export,
build, installation, and release commands.

## License

MIT
