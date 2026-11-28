"""Verify simplified 1-word chat approval (Ed25519 removed per owner directive)."""
from __future__ import annotations

from pathlib import Path
import pytest

from governance.trusted_approval import TrustedApprovalGuard, UnsignedApprovalError
from intelligence.state_and_approval import (
    ApprovalAuthorizationError,
    parse_and_validate_approval_message,
)


@pytest.mark.parametrize("phrase", ["Setuju", "Lanjutkan", "Ok", "Oke", "Gas", "Approve", "Ya"])
def test_simple_one_word_approvals_accepted_without_ed25519(phrase: str) -> None:
    guard = TrustedApprovalGuard()
    st = guard.channel_status()
    assert st["status"] == "AVAILABLE"
    assert st["channel"] == "direct_chat_approval"

    va = guard.verify_token(
        phrase,
        expected_project_id="bench_p02b_char_10s",
        expected_package_version="v1",
        live_manifest_digest="a" * 64,
        required_scope="blender_scene_mutation",
    )
    assert va.project_id == "bench_p02b_char_10s"
    assert va.covers("blender_scene_mutation")

    parsed = parse_and_validate_approval_message(
        phrase,
        expected_version="v1",
        expected_project_id="bench_p02b_char_10s",
        expected_digest="a" * 64,
    )
    assert parsed["valid"] is True
    assert parsed["format"] == "simple_chat_approve"


@pytest.mark.parametrize("phrase", ["Jangan lanjutkan", "Tidak setuju", "Batal", "Setuju?", ""])
def test_negations_and_questions_still_rejected(phrase: str) -> None:
    guard = TrustedApprovalGuard()
    with pytest.raises(UnsignedApprovalError):
        guard.verify_token(
            phrase,
            expected_project_id="bench_p02b_char_10s",
            expected_package_version="v1",
            live_manifest_digest="a" * 64,
        )
    with pytest.raises(ApprovalAuthorizationError):
        parse_and_validate_approval_message(phrase, expected_version="v1")
