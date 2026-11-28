from pathlib import Path
from PIL import Image, ImageDraw
from intelligence.design_fidelity_gate import silhouette_report


def _disc(path, cx, mode="RGBA"):
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((cx - 40, 60, cx + 40, 140), fill=(200, 100, 100, 255))
    im.save(path)


def test_shifted_silhouette_not_scored_as_identical_when_framing_matters(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _disc(a, 100); _disc(b, 125)
    r = silhouette_report(a, b, align="none")
    assert r["iou"] < 0.7 and r["verdict"] == "FAIL"   # naive RGB flatten would give ~1.0


def test_bbox_alignment_accepts_same_shape_different_framing(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _disc(a, 100); _disc(b, 125)
    assert silhouette_report(a, b, align="bbox")["verdict"] == "PASS_GEOMETRY_ONLY"


def test_wrong_proportions_fail(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _disc(a, 100)
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0)); ImageDraw.Draw(im).rectangle((90, 20, 110, 180), fill=(1, 1, 1, 255)); im.save(b)
    assert silhouette_report(a, b)["verdict"] == "FAIL"


def test_multicriteria_fails_when_iou_ok_but_palette_and_framing_wrong(tmp_path):
    from intelligence.design_fidelity_gate import evaluate_design
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _disc(a, 100)
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((60, 60, 140, 140), fill=(10, 200, 10, 255)); im.save(b)  # same shape, wrong colour
    r = evaluate_design(a, b, palette=["#C86464"])
    assert r["silhouette"]["verdict"] == "PASS_GEOMETRY_ONLY"
    assert r["criteria"]["palette"] is False and r["verdict"] == "FAIL"


def test_multicriteria_passes_matching_render(tmp_path):
    from intelligence.design_fidelity_gate import evaluate_design
    a = tmp_path / "a.png"; _disc(a, 100)
    r = evaluate_design(a, a, palette=["#C86464"], landmarks={"eye": (0.3, 0.4)}, ref_landmarks={"eye": (0.31, 0.41)})
    # landmarks alone are NOT enough evidence: proportions + geometry missing -> never PASS
    assert r["verdict"] == "INSUFFICIENT_EVIDENCE", r
    assert r["criteria"]["landmarks"] is True


def test_landmark_error_detects_misplaced_features():
    from intelligence.design_fidelity_gate import landmark_error
    assert landmark_error({"eye": (0.9, 0.9)}, {"eye": (0.3, 0.4)})["mean_error"] > 0.5


def test_missing_evidence_is_insufficient_not_pass(tmp_path):
    from intelligence.design_fidelity_gate import evaluate_design
    a = tmp_path / "a.png"; _disc(a, 100)
    r = evaluate_design(a, a, palette=["#C86464"])
    assert r["verdict"] != "PASS_AUTOMATED_CHECKS"
    assert {"proportions", "landmarks", "geometry"} <= set(r["missing_evidence"])


def test_empty_geometry_data_is_not_skipped(tmp_path):
    from intelligence.design_fidelity_gate import evaluate_design
    a = tmp_path / "a.png"; _disc(a, 100)
    r = evaluate_design(a, a, palette=["#C86464"], geometry={})
    assert "geometry" in r["missing_evidence"] and r["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_other_view_without_reference_is_insufficient_and_framing_is_not_similarity(tmp_path):
    from intelligence.design_fidelity_gate import evaluate_design
    a = tmp_path / "a.png"; _disc(a, 100)
    r = evaluate_design(a, a, palette=["#C86464"], other_views={"side": str(a)},
                        part_ratios={"leg": .4}, ref_part_ratios={"leg": .4},
                        landmarks={"eye": (.3, .4)}, ref_landmarks={"eye": (.3, .4)},
                        geometry={"within_budget": True, "needs_attention": []})
    assert r["missing_evidence"] == ["view_side_reference"] and r["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_full_evidence_can_pass_and_hair_has_own_criterion(tmp_path):
    from intelligence.design_fidelity_gate import evaluate_design
    a = tmp_path / "a.png"; _disc(a, 100)
    r = evaluate_design(a, a, palette=["#C86464"], other_views={"side": str(a)}, ref_views={"side": str(a)},
                        part_ratios={"leg": .4}, ref_part_ratios={"leg": .4},
                        landmarks={"eye": (.3, .4)}, ref_landmarks={"eye": (.3, .4)},
                        geometry={"within_budget": True, "needs_attention": []})
    assert "hair" in r["criteria"] and r["verdict"] == "PASS_AUTOMATED_CHECKS"
