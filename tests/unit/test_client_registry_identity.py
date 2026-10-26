from dct_mcp_server.core.auth import AuthContext
from dct_mcp_server.core.client_registry import ClientRegistry


def test_identity_key_returns_string():
    reg = ClientRegistry(max_size=4)
    auth = AuthContext(account_id="user-1", api_key=None, auth_mode="embedded")
    key = reg.identity_key(auth)
    assert isinstance(key, str)
    assert len(key) > 0


def test_identity_key_consistent():
    reg = ClientRegistry(max_size=4)
    auth = AuthContext(account_id="user-1", api_key=None, auth_mode="embedded")
    assert reg.identity_key(auth) == reg.identity_key(auth)


def test_identity_key_differs_by_account():
    reg = ClientRegistry(max_size=4)
    a1 = reg.identity_key(
        AuthContext(account_id="u1", api_key=None, auth_mode="embedded")
    )
    a2 = reg.identity_key(
        AuthContext(account_id="u2", api_key=None, auth_mode="embedded")
    )
    assert a1 != a2
