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
