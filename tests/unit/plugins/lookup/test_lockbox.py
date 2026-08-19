from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, Self, cast

import grpc
import pytest
import yaml
from ansible import constants as ansible_constants
from ansible.errors import AnsibleError

from plugins.lookup import lockbox

if TYPE_CHECKING:
    from types import TracebackType


class FakeRpcError(grpc.RpcError):
    def code(self) -> grpc.StatusCode:
        return grpc.StatusCode.UNAVAILABLE

    def details(self) -> str:
        return "sensitive upstream details"


class FakeEntry:
    def __init__(
        self,
        key: str,
        *,
        text_value: str = "",
        has_text_value: bool = True,
    ) -> None:
        self.key = key
        self.text_value = text_value
        self.has_text_value = has_text_value

    def HasField(self, field: str) -> bool:  # noqa: N802
        return field == "text_value" and self.has_text_value


class FakeResponse:
    def __init__(self, entries: list[FakeEntry]) -> None:
        self.entries = entries


class FakeStub:
    def __init__(
        self,
        response: FakeResponse | None = None,
        error: grpc.RpcError | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.request: lockbox.payload_service_pb2.GetPayloadRequest | None = None
        self.call_kwargs: dict[str, object] | None = None

    def Get(  # noqa: N802
        self,
        request: lockbox.payload_service_pb2.GetPayloadRequest,
        **kwargs: object,
    ) -> FakeResponse | None:
        self.request = request
        self.call_kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


class FakeClosableClient:
    def close(self) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class FakeChannel:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class ClientFactory(Protocol):
    def __call__(
        self,
        *,
        timeout: float = 10.0,
        stub: FakeStub | None = None,
    ) -> lockbox.LockboxClient: ...


@pytest.fixture
def client_factory(monkeypatch: pytest.MonkeyPatch) -> ClientFactory:
    credentials = object()

    def ssl_channel_credentials() -> object:
        return credentials

    def secure_channel(endpoint: str, supplied_credentials: object) -> FakeChannel:
        _ = endpoint, supplied_credentials
        return FakeChannel()

    monkeypatch.setattr(grpc, "ssl_channel_credentials", ssl_channel_credentials)
    monkeypatch.setattr(grpc, "secure_channel", secure_channel)

    def create(
        *,
        timeout: float = 10.0,
        stub: FakeStub | None = None,
    ) -> lockbox.LockboxClient:
        resolved_stub = stub or FakeStub()

        def payload_service_stub(channel: object) -> FakeStub:
            _ = channel
            return resolved_stub

        monkeypatch.setattr(
            lockbox.payload_service_pb2_grpc,
            "PayloadServiceStub",
            payload_service_stub,
        )
        return lockbox.LockboxClient("test.endpoint:443", "fake-iam-token", timeout)

    return create


@pytest.fixture
def lookup_module() -> lockbox.LookupModule:
    load_name = "ysignat.yandex.lockbox"
    options = yaml.safe_load(lockbox.DOCUMENTATION)["options"]
    ansible_constants.config.initialize_plugin_configuration_definitions(
        "lookup",
        load_name,
        options,
    )
    plugin = lockbox.LookupModule()
    plugin._load_name = load_name  # noqa: SLF001
    return plugin


def test_client_initializes_secure_grpc_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials = object()
    channel = FakeChannel()
    stub = object()
    timeout = 4.0

    def ssl_channel_credentials() -> object:
        return credentials

    def secure_channel(endpoint: str, supplied_credentials: object) -> object:
        assert endpoint == "custom.endpoint:443"
        assert supplied_credentials is credentials
        return channel

    def payload_service_stub(supplied_channel: object) -> object:
        assert supplied_channel is channel
        return stub

    monkeypatch.setattr(grpc, "ssl_channel_credentials", ssl_channel_credentials)
    monkeypatch.setattr(grpc, "secure_channel", secure_channel)
    monkeypatch.setattr(
        lockbox.payload_service_pb2_grpc,
        "PayloadServiceStub",
        payload_service_stub,
    )

    with lockbox.LockboxClient(
        "custom.endpoint:443",
        "token",
        timeout,
    ) as client:
        assert client.iam_token == "token"
        assert client.timeout == timeout
        assert client.channel is channel
        assert client.stub is stub

    assert channel.closed is True


@pytest.mark.parametrize("iam_token", [None, "", "   ", 123])
def test_client_requires_iam_token(iam_token: object) -> None:
    with pytest.raises(AnsibleError, match="Yandex IAM token is required"):
        lockbox.LockboxClient("endpoint", cast("Any", iam_token), 10.0)


def test_client_requires_nonempty_endpoint() -> None:
    with pytest.raises(AnsibleError, match="Lockbox endpoint must be a non-empty string"):
        lockbox.LockboxClient("", "token", 10.0)


def test_timeout_is_passed_to_rpc(client_factory: ClientFactory) -> None:
    timeout = 2.5
    entry = FakeEntry(
        key="password",
        text_value="secret-value",
    )
    stub = FakeStub(response=FakeResponse([entry]))
    client = client_factory(timeout=timeout, stub=stub)

    value = client.get_value("secret-id", "version-id", "password")

    assert value == "secret-value"
    assert stub.request is not None
    assert stub.call_kwargs is not None
    assert stub.request.secret_id == "secret-id"
    assert stub.request.version_id == "version-id"
    assert stub.call_kwargs["timeout"] == timeout


def test_omitted_version_uses_latest_secret_version(
    client_factory: ClientFactory,
) -> None:
    entry = FakeEntry(
        key="password",
        text_value="secret-value",
    )
    stub = FakeStub(response=FakeResponse([entry]))
    client = client_factory(stub=stub)

    value = client.get_value("secret-id", None, "password")

    assert value == "secret-value"
    assert stub.request is not None
    assert stub.request.secret_id == "secret-id"
    assert stub.request.version_id == ""


def test_missing_key_is_reported(client_factory: ClientFactory) -> None:
    stub = FakeStub(response=FakeResponse([]))
    client = client_factory(stub=stub)

    with pytest.raises(
        AnsibleError,
        match=r"Secret key 'password' not found in 'secret-id'",
    ):
        client.get_value("secret-id", None, "password")


def test_unsupported_value_type_is_reported(client_factory: ClientFactory) -> None:
    entry = FakeEntry(
        key="password",
        has_text_value=False,
    )
    stub = FakeStub(response=FakeResponse([entry]))
    client = client_factory(stub=stub)

    with pytest.raises(
        AnsibleError,
        match=r"only text values are supported",
    ):
        client.get_value("secret-id", None, "password")


def test_rpc_error_is_converted_without_sensitive_details(
    client_factory: ClientFactory,
) -> None:
    client = client_factory(stub=FakeStub(error=FakeRpcError()))

    with pytest.raises(
        AnsibleError,
        match=(
            r"Failed to retrieve Lockbox secret 'secret-id' "
            r"\(gRPC status: UNAVAILABLE\)"
        ),
    ) as raised:
        client.get_value("secret-id", "version-id", "password")

    message = str(raised.value)
    assert "sensitive-token" not in message
    assert "sensitive upstream details" not in message


@pytest.mark.parametrize(
    "timeout",
    [0, -1, "invalid", None, float("inf"), float("nan"), True],
)
def test_timeout_must_be_positive_and_finite(timeout: object) -> None:
    with pytest.raises(
        AnsibleError,
        match="Lockbox timeout must be a positive number",
    ):
        lockbox.LockboxClient("endpoint", "token", cast("Any", timeout))


def test_parse_secret_reference() -> None:
    assert lockbox.parse_secret_reference(
        "secret-id:version-id:database/password",
    ) == ("secret-id", "version-id", "database/password")


def test_parse_secret_reference_without_version() -> None:
    assert lockbox.parse_secret_reference("secret-id:directory\\password") == (
        "secret-id",
        None,
        "directory\\password",
    )


def test_parse_secret_reference_leaves_component_validation_to_api() -> None:
    assert lockbox.parse_secret_reference("secret id:version?:key#fragment") == (
        "secret id",
        "version?",
        "key#fragment",
    )


@pytest.mark.parametrize(
    "term",
    [
        None,
        123,
        "",
        "secret-id",
        "secret-id:",
        ":key",
        "secret-id::key",
        "secret-id:version-id:",
        "secret-id:version-id:key:extra",
        "secret-id/key",
    ],
)
def test_invalid_secret_reference_is_rejected(term: object) -> None:
    with pytest.raises(
        AnsibleError,
        match=r"Expected secret-id:key or secret-id:version-id:key",
    ):
        lockbox.parse_secret_reference(term)


def test_no_terms_are_rejected(lookup_module: lockbox.LookupModule) -> None:
    with pytest.raises(
        AnsibleError,
        match=r"lockbox lookup requires secret-id:key or secret-id:version-id:key",
    ):
        lookup_module.run([], variables={"yc_iam_token": "token"})


def test_lookup_closes_client(
    monkeypatch: pytest.MonkeyPatch,
    lookup_module: lockbox.LookupModule,
) -> None:
    closed = False

    class FakeClient(FakeClosableClient):
        def __init__(self, **_kwargs: object) -> None:
            pass

        def get_value(
            self,
            secret_id: str,
            version_id: str | None,
            key: str,
        ) -> str:
            _ = secret_id, version_id, key
            return "value"

        def close(self) -> None:
            nonlocal closed
            closed = True

    monkeypatch.setattr(lockbox, "LockboxClient", FakeClient)

    result = lookup_module.run(
        ["secret-id:password"],
        variables={"yc_iam_token": "token"},
    )

    assert result == ["value"]
    assert closed is True


def test_custom_timeout_is_passed_to_client(
    monkeypatch: pytest.MonkeyPatch,
    lookup_module: lockbox.LookupModule,
) -> None:
    client_options: dict[str, object] = {}
    lookup_arguments: dict[str, str | None] = {}

    class FakeClient(FakeClosableClient):
        def __init__(self, **kwargs: object) -> None:
            client_options.update(kwargs)

        def get_value(
            self,
            secret_id: str,
            version_id: str | None,
            key: str,
        ) -> str:
            lookup_arguments.update(
                secret_id=secret_id,
                version_id=version_id,
                key=key,
            )
            return "value"

    monkeypatch.setattr(lockbox, "LockboxClient", FakeClient)
    monkeypatch.setenv("YC_LOCKBOX_TIMEOUT", "99")

    result = lookup_module.run(
        ["secret-id:version-id:password"],
        variables={
            "yc_iam_token": "token",
            "yc_lockbox_timeout": 88,
        },
        timeout="3.5",
    )

    assert result == ["value"]
    assert client_options == {
        "endpoint": "payload.lockbox.api.cloud.yandex.net:443",
        "iam_token": "token",
        "timeout": 3.5,
    }
    assert lookup_arguments == {
        "secret_id": "secret-id",
        "version_id": "version-id",
        "key": "password",
    }


def test_multiple_lookups_and_custom_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    lookup_module: lockbox.LookupModule,
) -> None:
    client_options: dict[str, object] = {}
    lookup_arguments: list[tuple[str, str | None, str]] = []

    class FakeClient(FakeClosableClient):
        def __init__(self, **kwargs: object) -> None:
            client_options.update(kwargs)

        def get_value(
            self,
            secret_id: str,
            version_id: str | None,
            key: str,
        ) -> str:
            lookup_arguments.append((secret_id, version_id, key))
            return f"value-{key}"

    monkeypatch.setattr(lockbox, "LockboxClient", FakeClient)
    monkeypatch.setenv("YC_LOCKBOX_ENDPOINT", "environment.endpoint:443")

    result = lookup_module.run(
        ["first:version-1:username", "second:password"],
        variables={
            "yc_iam_token": "token",
            "yc_lockbox_endpoint": "variable.endpoint:443",
        },
        endpoint="custom.endpoint:443",
    )

    assert result == ["value-username", "value-password"]
    assert client_options["endpoint"] == "custom.endpoint:443"
    assert lookup_arguments == [
        ("first", "version-1", "username"),
        ("second", None, "password"),
    ]


def test_endpoint_and_timeout_are_read_from_environment(
    monkeypatch: pytest.MonkeyPatch,
    lookup_module: lockbox.LookupModule,
) -> None:
    client_options: dict[str, object] = {}
    environment_timeout = 7.5

    class FakeClient(FakeClosableClient):
        def __init__(self, **kwargs: object) -> None:
            client_options.update(kwargs)

        def get_value(
            self,
            secret_id: str,
            version_id: str | None,
            key: str,
        ) -> str:
            _ = secret_id, version_id, key
            return "value"

    monkeypatch.setenv("YC_IAM_TOKEN", "token")
    monkeypatch.setenv("YC_LOCKBOX_ENDPOINT", "environment.endpoint:443")
    monkeypatch.setenv("YC_LOCKBOX_TIMEOUT", str(environment_timeout))
    monkeypatch.setattr(lockbox, "LockboxClient", FakeClient)

    result = lookup_module.run(["secret-id:password"])

    assert result == ["value"]
    assert client_options["endpoint"] == "environment.endpoint:443"
    assert client_options["timeout"] == environment_timeout


def test_endpoint_and_timeout_variables_override_environment(
    monkeypatch: pytest.MonkeyPatch,
    lookup_module: lockbox.LookupModule,
) -> None:
    client_options: dict[str, object] = {}
    variable_timeout = 6

    class FakeClient(FakeClosableClient):
        def __init__(self, **kwargs: object) -> None:
            client_options.update(kwargs)

        def get_value(
            self,
            secret_id: str,
            version_id: str | None,
            key: str,
        ) -> str:
            _ = secret_id, version_id, key
            return "value"

    monkeypatch.setenv("YC_LOCKBOX_ENDPOINT", "environment.endpoint:443")
    monkeypatch.setenv("YC_LOCKBOX_TIMEOUT", "7.5")
    monkeypatch.setattr(lockbox, "LockboxClient", FakeClient)

    result = lookup_module.run(
        ["secret-id:password"],
        variables={
            "yc_iam_token": "token",
            "yc_lockbox_endpoint": "variable.endpoint:443",
            "yc_lockbox_timeout": variable_timeout,
        },
    )

    assert result == ["value"]
    assert client_options["endpoint"] == "variable.endpoint:443"
    assert client_options["timeout"] == float(variable_timeout)


def test_iam_token_is_read_from_environment(
    monkeypatch: pytest.MonkeyPatch,
    lookup_module: lockbox.LookupModule,
) -> None:
    client_options: dict[str, object] = {}

    class FakeClient(FakeClosableClient):
        def __init__(self, **kwargs: object) -> None:
            client_options.update(kwargs)

        def get_value(
            self,
            secret_id: str,
            version_id: str | None,
            key: str,
        ) -> str:
            _ = secret_id, version_id, key
            return "value"

    monkeypatch.setenv("YC_IAM_TOKEN", "environment-token")
    monkeypatch.setattr(lockbox, "LockboxClient", FakeClient)

    result = lookup_module.run(["secret-id:version-id:password"])

    assert result == ["value"]
    assert client_options["iam_token"] == "environment-token"


def test_ansible_variable_takes_priority_over_environment(
    monkeypatch: pytest.MonkeyPatch,
    lookup_module: lockbox.LookupModule,
) -> None:
    client_options: dict[str, object] = {}

    class FakeClient(FakeClosableClient):
        def __init__(self, **kwargs: object) -> None:
            client_options.update(kwargs)

        def get_value(
            self,
            secret_id: str,
            version_id: str | None,
            key: str,
        ) -> str:
            _ = secret_id, version_id, key
            return "value"

    monkeypatch.setenv("YC_IAM_TOKEN", "environment-token")
    monkeypatch.setattr(lockbox, "LockboxClient", FakeClient)

    result = lookup_module.run(
        ["secret-id:version-id:password"],
        variables={"yc_iam_token": "variable-token"},
    )

    assert result == ["value"]
    assert client_options["iam_token"] == "variable-token"
