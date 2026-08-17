from __future__ import annotations

import math
from typing import TYPE_CHECKING, Self

import grpc
from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from yandex.cloud.lockbox.v1 import payload_service_pb2, payload_service_pb2_grpc

if TYPE_CHECKING:
    from types import TracebackType

DOCUMENTATION = r"""
name: lockbox
author:
  - ysignat <ignatovegors@gmail.com>
short_description: Retrieve secrets from Yandex Cloud Lockbox
description:
  - Retrieves secret values from Yandex Cloud Lockbox using the gRPC API.
options:
  _terms:
    description:
      - Secret reference in the form C(secret-id:key) or C(secret-id:version-id:key).
      - When the version ID is omitted, the latest secret version is used.
    required: true
  iam_token:
    description:
      - Yandex Cloud IAM token used to authenticate Lockbox requests.
      - The Ansible variable takes precedence over the environment variable.
    required: true
    type: str
    vars:
      - name: yc_iam_token
    env:
      - name: YC_IAM_TOKEN
  endpoint:
    description:
      - Lockbox gRPC endpoint.
      - The Ansible variable takes precedence over the environment variable.
    default: payload.lockbox.api.cloud.yandex.net:443
    type: str
    vars:
      - name: yc_lockbox_endpoint
    env:
      - name: YC_LOCKBOX_ENDPOINT
  timeout:
    description:
      - Maximum time in seconds to wait for a Lockbox RPC.
      - The Ansible variable takes precedence over the environment variable.
    type: float
    default: 10.0
    vars:
      - name: yc_lockbox_timeout
    env:
      - name: YC_LOCKBOX_TIMEOUT
"""

EXAMPLES = r"""
- name: Read database password
  no_log: true
  ansible.builtin.set_fact:
    database_password: >-
      {{ lookup('ysignat.yandex.lockbox',
                'e6qetpqfe8vv00000000:e6qdnt9t2qsd00000000:password') }}
  vars:
    yc_iam_token: "{{ lookup('ansible.builtin.env', 'YC_IAM_TOKEN') }}"
"""


class LockboxClient:
    """Retrieve secret values from the Yandex Cloud Lockbox API."""

    def __init__(
        self,
        endpoint: str,
        iam_token: str,
        timeout: float,
    ) -> None:
        """Initialize a Lockbox client with resolved lookup options."""
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise AnsibleError("Lockbox endpoint must be a non-empty string")

        if not isinstance(iam_token, str) or not iam_token.strip():
            raise AnsibleError("Yandex IAM token is required")

        if (
            isinstance(timeout, bool)  # Bool is a subclass of int
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise AnsibleError("Lockbox timeout must be a positive number")

        self.iam_token = iam_token
        self.timeout = float(timeout)
        self.endpoint = endpoint

        credentials = grpc.ssl_channel_credentials()

        self.channel = grpc.secure_channel(
            endpoint,
            credentials,
        )

        self.stub = payload_service_pb2_grpc.PayloadServiceStub(self.channel)

    def close(self) -> None:
        """Close the underlying gRPC channel."""
        self.channel.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def get_value(
        self,
        secret_id: str,
        version_id: str | None,
        key: str,
    ) -> str:
        """Retrieve a text value from a Lockbox secret version."""
        request = payload_service_pb2.GetPayloadRequest(secret_id=secret_id)
        if version_id is not None:
            request.version_id = version_id

        metadata = (
            (
                "authorization",
                f"Bearer {self.iam_token}",
            ),
        )

        try:
            response = self.stub.Get(
                request,
                metadata=metadata,
                timeout=self.timeout,
            )
        except grpc.RpcError as error:
            status_name = error.code().name
            raise AnsibleError(
                f"Failed to retrieve Lockbox secret '{secret_id}' (gRPC status: {status_name})",
            ) from None

        for entry in response.entries:
            if entry.key == key:
                if entry.HasField("text_value"):
                    return entry.text_value

                raise AnsibleError(
                    f"Secret key '{key}' in '{secret_id}' contains a value that is not a text entry; "
                    "only text values are supported",
                )

        raise AnsibleError(f"Secret key '{key}' not found in '{secret_id}'")


def parse_secret_reference(term: object) -> tuple[str, str | None, str]:
    """Parse a colon-delimited Lockbox secret reference."""
    expected = "secret-id:key or secret-id:version-id:key"

    if not isinstance(term, str):
        raise AnsibleError(f"Invalid Lockbox reference: {term!r}. Expected {expected}")

    parts = term.split(":")
    if len(parts) == 2:  # noqa: PLR2004
        secret_id, key = parts
        version_id = None
    elif len(parts) == 3:  # noqa: PLR2004
        secret_id, version_id, key = parts
    else:
        raise AnsibleError(f"Invalid Lockbox reference: {term!r}. Expected {expected}")

    if any(not part for part in parts):
        raise AnsibleError(f"Invalid Lockbox reference: {term!r}. Expected {expected}")

    return secret_id, version_id, key


class LookupModule(LookupBase):
    """Look up text values stored in Yandex Cloud Lockbox."""

    def run(self, terms, variables=None, **kwargs):  # noqa: ANN001, ANN003, ANN201
        """Resolve lookup options and retrieve all requested secret values."""
        if not terms:
            raise AnsibleError(
                "lockbox lookup requires secret-id:key or secret-id:version-id:key",
            )

        variables = variables or {}
        self.set_options(var_options=variables, direct=kwargs)

        with LockboxClient(
            endpoint=self.get_option("endpoint"),
            iam_token=self.get_option("iam_token"),
            timeout=self.get_option("timeout"),
        ) as client:
            results = []

            for term in terms:
                secret_id, version_id, key = parse_secret_reference(term)

                results.append(
                    client.get_value(
                        secret_id=secret_id,
                        version_id=version_id,
                        key=key,
                    ),
                )
            return results
