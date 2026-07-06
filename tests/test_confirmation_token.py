"""
Unit tests for the execute() confirmation-token handshake.

Bug: a destructive op (e.g. DELETE /synthetic/datasets/{id}) executed when the
caller sent confirmed=true on the first call, bypassing the gate without the user
ever being asked. The gate now requires a server-issued confirmation_token (echoed
from the confirmation_required response) instead of trusting a bare confirmed flag.

These tests cover the token primitive that makes the bypass impossible: a token
cannot be produced without having received it from the server.

All tests in this module were AI-generated. Each test carries an
``# AI-generated`` comment on the first line of its body.
"""

from dct_mcp_server.tools.core.confirmation_token import (
    make_confirmation_token,
    verify_confirmation_token,
)


def test_token_is_stable_within_process():
    # AI-generated
    t1 = make_confirmation_token("DELETE", "/synthetic/datasets/ds-1")
    t2 = make_confirmation_token("DELETE", "/synthetic/datasets/ds-1")
    assert t1 == t2  # echoed token must verify within a session


def test_valid_token_verifies():
    # AI-generated
    token = make_confirmation_token("DELETE", "/synthetic/datasets/ds-1")
    assert (
        verify_confirmation_token(token, "DELETE", "/synthetic/datasets/ds-1") is True
    )


def test_missing_token_does_not_verify():
    # AI-generated
    # This is the bug case: confirmed=true with no token must NOT pass the gate.
    assert (
        verify_confirmation_token(None, "DELETE", "/synthetic/datasets/ds-1") is False
    )
    assert verify_confirmation_token("", "DELETE", "/synthetic/datasets/ds-1") is False


def test_token_is_operation_specific():
    # AI-generated
    token = make_confirmation_token("DELETE", "/synthetic/datasets/ds-1")
    # A token for one operation must not authorise a different path or method.
    assert (
        verify_confirmation_token(token, "DELETE", "/synthetic/datasets/ds-2") is False
    )
    assert verify_confirmation_token(token, "POST", "/synthetic/datasets/ds-1") is False


def test_wrong_token_does_not_verify():
    # AI-generated
    assert (
        verify_confirmation_token("deadbeef", "DELETE", "/synthetic/datasets/ds-1")
        is False
    )


def test_method_is_case_insensitive():
    # AI-generated
    token = make_confirmation_token("delete", "/synthetic/datasets/ds-1")
    assert (
        verify_confirmation_token(token, "DELETE", "/synthetic/datasets/ds-1") is True
    )
