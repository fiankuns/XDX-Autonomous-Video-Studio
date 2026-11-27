"""Phase 01.5 Regression Tests — Hierarchical Storyboard (15s–180s) & Anti-Placeholder Creative Intelligence (Categories 5–10)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from intelligence.authored_showcase_150s import build_authored_time_perception_payload
from intelligence.creative_pipeline import (
    PLACEHOLDER_PATTERNS,
    CreativePayloadValidator,
    PlaceholderScriptError,
    PreProductionPackageBuilder,
    TopicResearchEngine,
    UnverifiedResearchError,
)


@pytest.mark.parametrize(
    ("duration_s", "genres"),
    [
        (15, ["explainer"]),
        (30, ["edukasi", "komedi_absurd"]),
        (60, ["sejarah", "biografi", "dokumenter"]),
        (150, ["explainer", "edukasi", "sejarah", "biografi", "komedi_absurd"]),
        (180, ["horor", "storytelling", "sejarah"]),
    ],
)
def test_hierarchical_storyboard_across_durations_and_genres(
    tmp_path: Path,
    duration_s: int,
    genres: list[str],
) -> None:
    pkg_dir = tmp_path / f"pkg_{duration_s}s"
    builder = PreProductionPackageBuilder()
    res = builder.build_waiting_approval_package(
        package_dir=pkg_dir,
        project_id=f"test_{duration_s}s",
        genres=genres,
        target_duration_s=duration_s,
        authored_payload=build_authored_time_perception_payload(
            project_id=f"test_{duration_s}s",
            target_duration_s=duration_s,
            genres=genres,
        ),
    )
    assert res["status"] == "WAITING_APPROVAL"

    sb = json.loads((pkg_dir / "storyboard.json").read_text(encoding="utf-8"))
    expected_frames = duration_s * 30
    assert sb["total_frames"] == expected_frames
    assert sb["duration_s"] == float(duration_s)

    # Hierarchical structure populated
    assert len(sb["sequences"]) >= 1
    assert len(sb["scenes"]) >= 1
    assert len(sb["narrative_beats"]) >= 3
    assert len(sb["shots"]) > len(sb["narrative_beats"])

    # Exact integer frame contiguity & strict <= 10s (<= 300 frames) per shot
    cursor = 0
    for idx, shot in enumerate(sb["shots"]):
        assert shot["start_frame"] == cursor, f"Gap/overlap at {shot['shot_id']}"
        assert shot["end_frame"] > shot["start_frame"]
        assert shot["duration_frames"] == shot["end_frame"] - shot["start_frame"]
        assert 45 <= shot["duration_frames"] <= 300, f"Shot {shot['shot_id']} violated 1.5s..10s bound: {shot['duration_s']}s"
        assert 1.5 <= shot["duration_s"] <= 10.0
        assert len(shot["action_events"]) >= 1
        assert len(shot["audio_events"]) >= 2
        assert len(shot["vfx_events"]) >= 1
        assert PLACEHOLDER_PATTERNS.search(shot["narration_segment"]) is None
        assert PLACEHOLDER_PATTERNS.search(shot["action_mid"]) is None
        # Check explicit transition overlap handle accounting
        ts = shot["transition_spec"]
        assert ts["render_handle_frames_head"] == ts["overlap_frames_in"]
        assert ts["render_handle_frames_tail"] == ts["overlap_frames_out"]
        if idx > 0 and ts["overlap_frames_in"] > 0:
            prev_ts = sb["shots"][idx - 1]["transition_spec"]
            assert prev_ts["overlap_frames_out"] == ts["overlap_frames_in"]
        cursor = shot["end_frame"]

    assert cursor == expected_frames


def test_placeholder_narration_and_offtopic_script_rejected() -> None:
    validator = CreativePayloadValidator()
    good = build_authored_time_perception_payload(target_duration_s=150)
    metrics = validator.validate(good)
    assert metrics["spoken_word_count"] >= 200
    assert metrics["domain_keyword_overlap_script"] >= 3

    # 1. Inject bracketed beat label placeholder -> rejected
    bad_vo = copy.deepcopy(good)
    bad_vo["narrative_beats"][0]["narration_vo"] = "[HOOK_ANOMALY] Mengapa waktu melambat: Hook visual langsung 0-3 detik."
    with pytest.raises(PlaceholderScriptError):
        validator.validate(bad_vo)

    # 2. Inject generic visual action placeholder ("staging awal") -> rejected
    bad_act = copy.deepcopy(good)
    bad_act["narrative_beats"][0]["shot_blueprints"][0]["concrete_action"] = "Pembukaan beat B01: staging awal karakter."
    with pytest.raises(PlaceholderScriptError):
        validator.validate(bad_act)

    # 3. Off-topic unrelated script -> rejected by lexical topic-relevance check
    off_topic = copy.deepcopy(good)
    for b in off_topic["narrative_beats"]:
        b["narration_vo"] = "Resep menggoreng kerupuk udang renyah memakai minyak kelapa sawit hangat di wajan baja."
        b["dialogue_lines"] = []
    with pytest.raises(PlaceholderScriptError):
        validator.validate(off_topic)


def test_unverified_factual_research_rejected() -> None:
    research_engine = TopicResearchEngine()
    good = build_authored_time_perception_payload(target_duration_s=60)
    compiled_topic, _ = research_engine.validate_and_compile_research(good)
    assert compiled_topic["metrics_measured"]["citation_coverage_ratio"] == 1.0

    # 1. pending_external_verification URL -> rejected
    bad_pending = copy.deepcopy(good)
    bad_pending["topic_research"]["claims"][0]["source_url"] = "pending_external_verification"
    with pytest.raises(UnverifiedResearchError):
        research_engine.validate_and_compile_research(bad_pending)

    # 2. Non-HTTPS or example.com URL -> rejected
    bad_example = copy.deepcopy(good)
    bad_example["topic_research"]["claims"][0]["source_url"] = "https://example.com/fake-study"
    with pytest.raises(UnverifiedResearchError):
        research_engine.validate_and_compile_research(bad_example)

    # 3. unverified_claim status on factual genre -> rejected
    bad_status = copy.deepcopy(good)
    bad_status["topic_research"]["claims"][1]["epistemic_status"] = "unverified_claim"
    with pytest.raises(UnverifiedResearchError):
        research_engine.validate_and_compile_research(bad_status)

    # 4. INCOMPLETE_BLOCKED research dossier -> rejected
    bad_incomplete = copy.deepcopy(good)
    bad_incomplete["topic_research"]["research_status"] = "INCOMPLETE_BLOCKED"
    with pytest.raises(UnverifiedResearchError):
        research_engine.validate_and_compile_research(bad_incomplete)
