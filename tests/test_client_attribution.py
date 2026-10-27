"""DCT API source attribution headers (PPM-1727).

Embedded mode is the DCT AI Assistant driving the server, so its DCT API calls
are tagged for source attribution (``X-Dct-Client-Name`` + a
``Delphix-AI-Assistant`` User-Agent). Standalone/local clients are deliberately
left unattributed so DCT can tell AI-Assistant traffic apart from everything
else.

All functions in this module were AI-generated.
"""

from dct_mcp_server.dct_client.client import DCTAPIClient


def test_embedded_identity_client_is_attributed():  # AI-generated
    c = DCTAPIClient.for_identity("acct-4711")
    assert c.headers["X-Dct-Client-Name"] == "Delphix AI Assistant"
    assert c.headers["User-Agent"].startswith("Delphix-AI-Assistant/")
    # identity travels as the internal trust header, never as an API key
    assert c.headers["X-CLIENT-ID"] == "acct-4711"
    assert "Authorization" not in c.headers


def test_standalone_client_is_not_attributed():  # AI-generated
    # conftest sets DCT_API_KEY / DCT_BASE_URL; default auth mode is standalone.
    c = DCTAPIClient()
    assert "X-Dct-Client-Name" not in c.headers
    assert c.headers["User-Agent"].startswith("dct-mcp-server/")
    assert c.headers["Authorization"].startswith("apk ")


def test_embedded_client_sends_the_callers_ip(monkeypatch):  # AI-generated
    monkeypatch.setenv("DCT_CLIENT_IP", " 203.0.113.9 ")
    c = DCTAPIClient.for_identity("acct-4711")
    assert c.headers["X-Dct-Client-IP"] == "203.0.113.9"


def test_embedded_client_without_an_ip_sends_no_ip_header(monkeypatch):  # AI-generated
    monkeypatch.delenv("DCT_CLIENT_IP", raising=False)
    c = DCTAPIClient.for_identity("acct-4711")
    assert "X-Dct-Client-IP" not in c.headers


def test_standalone_client_never_sends_an_ip(monkeypatch):  # AI-generated
    # Only the DCT AI Assistant host vouches for the caller's address.
    monkeypatch.setenv("DCT_CLIENT_IP", "203.0.113.9")
    c = DCTAPIClient()
    assert "X-Dct-Client-IP" not in c.headers
