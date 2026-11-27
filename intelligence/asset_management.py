"""Hardened Intelligent Asset Management System (v3.4).

Integrates:
1. AssetDiscoveryEngine (shot-requirement driven + live Poly Haven / ambientCG query adapters)
2. AutomaticAssetDownloader (HTTPS + host allowlist + SSRF guard + byte cap + format magic check)
3. AssetRegistryManager (atomic persistence)
4. RepositoryRegistryManager
5. AssetCacheManager (separated Cloud vs Android Vivo X200 Pro cache tiers, atomic writes, safe paths,
   corruption quarantine, SHA-256 verification, LRU quota eviction, safe zip extraction)
6. LicenseValidator + AttributionLedger (preserves CC-BY / OFL-1.1 / MIT credits)
7. ProceduralAssetGenerator (12 semantic multi-component glTF 2.0 categories; separates PLACEHOLDER)
8. AssetStyleHarmonizer (real glTF PBR & HSV palette buffer harmonization)
9. CrossEngineAssetConverter (real vertex scaling, +Y/+Z axis rotation, normal correction, GLB<->glTF)
10. CharacterRetargetingEngine (honest UNIT_TESTED bone map vs SPECIFICATION_ONLY curve retargeting)
11. AssetQualityControl (blocks PLACEHOLDER boxes, corrupt buffers, missing dependencies, & mobile_guard violations)
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from intelligence.asset_style_converter import (
    DATA_URI_PREFIX,
    HonestRiggingAndRetargetingAdapter,
    RealAssetStyleHarmonizer,
    RealGeometryAndTextureConverter,
    decode_gltf_buffer_zero,
    glb_to_gltf,
    gltf_to_glb,
)
from intelligence.procedural_geometry import (
    SemanticProceduralAssetGenerator,
    infer_semantic_category,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_DIR = ROOT_DIR / "registry"
DEFAULT_CACHE_DIR = ROOT_DIR / ".xdx_cache"

GLOBAL_STYLE_BIBLE_V3_4: dict[str, Any] = {
    "id": "xdx_stylized_diorama_v3_4",
    "unit_scale_m": 1.0,
    "roughness_clamp": [0.30, 0.88],
    "metallic_max": 0.45,
    "bevel_radius_m": 0.006,
    "tone_mapping": "ACESFilmic",
    "color_space": "sRGB",
    "vivo_x200_pro_max_tris_per_asset": 35000,
    "vivo_x200_pro_max_texture_px": 1024,
    "default_palette": ["#F4D8B8", "#4F8CFF", "#8B5E3C", "#FFD166", "#1E293B"],
}
# Keep alias for Phase 01 backward compatibility
GLOBAL_STYLE_BIBLE_V3_3 = GLOBAL_STYLE_BIBLE_V3_4

ALLOWED_ASSET_HOSTS: frozenset[str] = frozenset(
    {
        "api.polyhaven.com",
        "dl.polyhaven.org",
        "polyhaven.com",
        "ambientcg.com",
        "cdn.ambientcg.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "kenney.nl",
        "quaternius.com",
    }
)

SAFE_ASSET_ID_REGEX = re.compile(r"^[A-Za-z0-9_\-]+$")
ALLOWED_EXTRACT_EXTENSIONS: frozenset[str] = frozenset(
    {".gltf", ".glb", ".bin", ".png", ".jpg", ".jpeg", ".hdr", ".exr", ".ttf", ".woff2", ".json", ".txt", ".md"}
)


class LicenseValidationError(PermissionError):
    """Raised when an asset or dependency violates XDX license policy."""


class AssetBlockedError(RuntimeError):
    """Raised when an asset cannot be procured without violating placeholder, format, or QC rules."""


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def sanitize_safe_identifier(raw_id: str) -> str:
    """Reject path traversal (`..`, `/`, `\\`, null bytes) in asset IDs and cache keys."""
    if not isinstance(raw_id, str) or not raw_id or "/" in raw_id or "\\" in raw_id or ".." in raw_id or "\x00" in raw_id:
        raise ValueError(f"Unsafe path/asset identifier rejected: {raw_id!r}")
    if not SAFE_ASSET_ID_REGEX.match(raw_id):
        raise ValueError(f"Identifier contains disallowed characters: {raw_id!r}")
    return raw_id


def validate_external_asset_url(url: str, *, allowed_hosts: frozenset[str] = ALLOWED_ASSET_HOSTS) -> str:
    """Validate external HTTPS URL, block credentials/IPs/localhost/SSRF, and check host allowlist."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"External asset downloads must use https:// (got {parsed.scheme!r})")
    if parsed.username or parsed.password:
        raise ValueError("Credentials inside asset URLs are forbidden")
    host = (parsed.hostname or "").lower().strip(".")
    if not host or host in {"localhost"}:
        raise ValueError("Missing or localhost asset URL host rejected")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError(f"Private/internal IP address blocked: {host}")
    except ValueError as exc:
        if "Private/internal" in str(exc):
            raise
    if host not in allowed_hosts:
        raise ValueError(f"Host '{host}' is not in verified ALLOWED_ASSET_HOSTS")
    return url


def safe_extract_zip(
    zip_path: Path,
    dest_dir: Path,
    *,
    max_total_uncompressed_bytes: int = 50 * 1024 * 1024,
    max_compression_ratio: float = 25.0,
) -> list[Path]:
    """Extract a ZIP archive safely with Zip-Slip, symlink, extension, and Zip-Bomb protection."""
    dest_resolved = dest_dir.resolve()
    dest_resolved.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    total_uncompressed = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            member_name = info.filename
            if member_name.startswith(("/", "\\")) or ".." in Path(member_name).parts or "\x00" in member_name:
                raise ValueError(f"Zip-Slip path traversal blocked: {member_name!r}")

            # Reject Unix symlinks stored in zip external_attr (0o120000)
            unix_mode = (info.external_attr >> 16) & 0o170000
            if unix_mode == 0o120000:
                raise ValueError(f"Symlink inside archive blocked: {member_name!r}")

            target_path = (dest_resolved / member_name).resolve()
            if dest_resolved not in target_path.parents and target_path != dest_resolved:
                raise ValueError(f"Archive path escaped destination root: {member_name!r}")

            ext = target_path.suffix.lower()
            if ext not in ALLOWED_EXTRACT_EXTENSIONS:
                raise ValueError(f"Disallowed file extension '{ext}' in archive entry '{member_name}'")

            total_uncompressed += info.file_size
            if total_uncompressed > max_total_uncompressed_bytes:
                raise ValueError("Archive exceeded max_total_uncompressed_bytes (Zip-Bomb protection)")
            comp_size = max(1, info.compress_size)
            if info.file_size > 65536 and (info.file_size / comp_size) > max_compression_ratio:
                raise ValueError("Suspicious compression ratio blocked (Zip-Bomb protection)")

            with zf.open(info, "r") as src_fh:
                payload = src_fh.read(max_total_uncompressed_bytes + 1)
            if len(payload) > info.file_size:
                raise ValueError("Archive stream exceeded declared file_size")
            atomic_write_bytes(target_path, payload)
            extracted.append(target_path)

    return extracted


def verify_file_format_and_dependencies(data: bytes, extension: str, *, base_dir: Path | None = None) -> dict[str, Any]:
    """Verify binary/JSON magic signatures and external dependency integrity (never trust HTTP 200 HTML)."""
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    if not data:
        raise ValueError("Empty asset payload (0 bytes)")

    head_strip = data[:128].lstrip()
    if head_strip.startswith((b"<!DOCTYPE html", b"<html", b"<HTML")):
        raise ValueError("HTML document received instead of binary/3D asset payload")

    if ext == ".glb":
        doc, raw_bin = glb_to_gltf(data)
        return {"format": "glb", "gltf_version": doc.get("asset", {}).get("version"), "bin_bytes": len(raw_bin)}

    if ext == ".gltf":
        doc = json.loads(data.decode("utf-8"))
        if doc.get("asset", {}).get("version") != "2.0":
            raise ValueError("Invalid glTF asset.version (expected '2.0')")
        for buf in doc.get("buffers", []):
            uri = buf.get("uri", "")
            declared = int(buf.get("byteLength", 0))
            if isinstance(uri, str) and uri.startswith(DATA_URI_PREFIX):
                decoded = decode_gltf_buffer_zero({"buffers": [buf]})
                if len(decoded) < declared:
                    raise ValueError(f"glTF embedded buffer shorter ({len(decoded)}) than byteLength ({declared})")
            elif isinstance(uri, str) and uri:
                if ".." in uri or uri.startswith(("/", "http://", "https://")):
                    raise ValueError(f"Unsafe or unbundled external glTF buffer URI: {uri}")
                if base_dir is None or not (base_dir / uri).is_file():
                    raise ValueError(f"Missing external glTF buffer dependency: {uri}")
                if (base_dir / uri).stat().st_size < declared:
                    raise ValueError(f"External glTF buffer '{uri}' truncated")
        for img in doc.get("images", []):
            iuri = img.get("uri", "")
            if isinstance(iuri, str) and iuri and not iuri.startswith("data:image/"):
                if ".." in iuri or iuri.startswith("/"):
                    raise ValueError(f"Unsafe glTF image URI: {iuri}")
                if base_dir is None or not (base_dir / iuri).is_file():
                    raise ValueError(f"Missing external glTF texture dependency: {iuri}")
        return {"format": "gltf", "gltf_version": "2.0", "mesh_count": len(doc.get("meshes", []))}

    if ext == ".png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid PNG magic signature")
        return {"format": "png"}

    if ext in {".jpg", ".jpeg"}:
        if not data.startswith(b"\xff\xd8\xff"):
            raise ValueError("Invalid JPEG magic signature")
        return {"format": "jpeg"}

    if ext == ".hdr":
        if not data.startswith((b"#?RADIANCE", b"#?RGBE")):
            raise ValueError("Invalid Radiance HDR signature")
        return {"format": "hdr"}

    return {"format": ext.lstrip(".")}


class LicenseValidator:
    """Validates SPDX identifiers and commercial/bundling rules against license_registry.json."""

    def __init__(self, license_registry_path: Path | None = None) -> None:
        path = license_registry_path or (DEFAULT_REGISTRY_DIR / "license_registry.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self._policies = {entry["id"]: entry for entry in data["entries"]}

    def validate(
        self,
        license_id: str,
        *,
        require_commercial: bool = True,
        require_direct_bundle: bool = True,
    ) -> dict[str, Any]:
        policy = self._policies.get(license_id)
        if policy is None:
            raise LicenseValidationError(f"Unknown or unverified license '{license_id}' — blocked by fail-closed policy.")
        if policy["status"] == "blocked":
            raise LicenseValidationError(f"License '{license_id}' is explicitly BLOCKED ({policy.get('conditions', '')}).")
        if require_commercial and not policy.get("commercial_allowed", False):
            raise LicenseValidationError(f"License '{license_id}' disallows commercial production.")
        if require_direct_bundle and not policy.get("allow_direct_bundle", False):
            raise LicenseValidationError(
                f"License '{license_id}' requires copyleft/custom isolation and cannot be directly bundled."
            )
        return {
            "valid": True,
            "license_id": license_id,
            "status": policy["status"],
            "attribution_required": bool(policy.get("attribution_required", False)),
            "conditions": policy.get("conditions"),
        }


class AttributionLedger:
    """Persists provenance & required license attributions (`CC-BY`, `OFL-1.1`, `MIT`) atomically."""

    def __init__(self, ledger_path: Path) -> None:
        self.ledger_path = ledger_path
        if not self.ledger_path.is_file():
            atomic_write_bytes(self.ledger_path, b"[]\n")

    def record(self, asset_meta: dict[str, Any]) -> None:
        entries: list[dict[str, Any]] = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        rec = {
            "asset_id": asset_meta["asset_id"],
            "name": asset_meta["name"],
            "source_provider": asset_meta["source_provider"],
            "source_url": asset_meta["source_url"],
            "license_spdx": asset_meta["license_spdx"],
            "attribution_required": bool(asset_meta.get("attribution_required", False)),
            "attribution_text": asset_meta.get("attribution_text")
            or f"{asset_meta['name']} ({asset_meta['source_provider']}, {asset_meta['license_spdx']})",
            "sha256": asset_meta.get("sha256"),
        }
        entries = [e for e in entries if e.get("asset_id") != rec["asset_id"]]
        entries.append(rec)
        atomic_write_bytes(self.ledger_path, (json.dumps(entries, indent=2) + "\n").encode("utf-8"))

    def list_entries(self) -> list[dict[str, Any]]:
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))


class AssetRegistryManager:
    """Reads, queries, and atomically updates asset_registry.json."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = registry_path or (DEFAULT_REGISTRY_DIR / "asset_registry.json")
        self._data = json.loads(self.registry_path.read_text(encoding="utf-8"))

    def list_assets(self) -> list[dict[str, Any]]:
        return list(self._data.get("assets", []))

    def get_by_id(self, asset_id: str) -> dict[str, Any] | None:
        for item in self._data.get("assets", []):
            if item["asset_id"] == asset_id:
                return dict(item)
        return None

    def find_matching(self, query: str, *, category: str | None = None, engine: str | None = None) -> list[dict[str, Any]]:
        tokens = [t.lower() for t in query.replace("_", " ").split() if t.strip()]
        matches: list[dict[str, Any]] = []
        for item in self._data.get("assets", []):
            if category and item.get("category") != category:
                continue
            if engine and engine not in item.get("compatible_engines", []):
                continue
            blob = " ".join(
                [item["asset_id"].lower(), item["name"].lower(), " ".join(t.lower() for t in item.get("tags", []))]
            )
            if not tokens or any(tok in blob for tok in tokens):
                matches.append(dict(item))
        return matches

    def upsert_asset(self, entry: dict[str, Any], *, persist: bool = True) -> None:
        assets = self._data.setdefault("assets", [])
        for idx, existing in enumerate(assets):
            if existing["asset_id"] == entry["asset_id"]:
                assets[idx] = entry
                break
        else:
            assets.append(entry)
        if persist:
            atomic_write_bytes(self.registry_path, (json.dumps(self._data, indent=2) + "\n").encode("utf-8"))


class RepositoryRegistryManager:
    """Queries audited external GitHub repositories and asset provider catalogs."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = registry_path or (DEFAULT_REGISTRY_DIR / "repository_registry.json")
        self._data = json.loads(self.registry_path.read_text(encoding="utf-8"))

    def get_entry(self, name_or_id: str) -> dict[str, Any] | None:
        needle = name_or_id.lower()
        for entry in self._data.get("entries", []):
            if entry["id"].lower() == needle or entry["name"].lower() == needle:
                return dict(entry)
        return None

    def list_approved_asset_providers(self) -> list[dict[str, Any]]:
        return [
            dict(e)
            for e in self._data.get("entries", [])
            if e.get("category") == "Asset Providers" and "selected" in str(e.get("status", ""))
        ]


class AssetCacheManager:
    """Content-addressed SHA-256 LRU Cache with separated Cloud vs Android Mobile tiers and atomic writes."""

    TIER_QUOTAS = {
        "cloud": 512 * 1024 * 1024,          # 512 MB for Cloud Remotion/Three.js renders
        "android_mobile": 64 * 1024 * 1024,  # 64 MB mobile_guard friendly tier for Vivo X200 Pro
    }

    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        tier: str = "cloud",
        max_cache_bytes: int | None = None,
    ) -> None:
        if tier not in self.TIER_QUOTAS:
            raise ValueError(f"Invalid cache tier '{tier}'. Expected one of {sorted(self.TIER_QUOTAS)}")
        self.tier = tier
        base = cache_dir or DEFAULT_CACHE_DIR
        # Keep backward-compatible flat path if caller passed an explicit temp test directory,
        # while separating sub-tiers when tier="android_mobile" or default cache_dir is used.
        self.cache_dir = (base / tier) if (cache_dir is None or tier == "android_mobile") else base
        self.max_cache_bytes = max_cache_bytes if max_cache_bytes is not None else self.TIER_QUOTAS[tier]
        self.blobs_dir = self.cache_dir / "blobs"
        self.quarantine_dir = self.cache_dir / "quarantine"
        self.index_path = self.cache_dir / "cache_index.json"
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.is_file():
            self._write_index({})

    def _read_index(self) -> dict[str, dict[str, Any]]:
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_index(self, index: dict[str, dict[str, Any]]) -> None:
        atomic_write_bytes(self.index_path, (json.dumps(index, indent=2) + "\n").encode("utf-8"))

    def get(self, asset_id: str) -> Path | None:
        safe_id = sanitize_safe_identifier(asset_id)
        idx = self._read_index()
        rec = idx.get(safe_id)
        if not rec:
            return None
        blob = (self.blobs_dir / rec["filename"]).resolve()
        if self.blobs_dir.resolve() not in blob.parents or not blob.is_file():
            return None
        raw = blob.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        if actual_sha != rec["sha256"]:
            # Quarantine corrupted blob and purge index entry
            q_target = self.quarantine_dir / f"corrupt_{rec['filename']}"
            os.replace(blob, q_target)
            del idx[safe_id]
            self._write_index(idx)
            return None
        rec["last_accessed"] = time.time()
        rec["hits"] = int(rec.get("hits", 0)) + 1
        self._write_index(idx)
        return blob

    def put(
        self,
        asset_id: str,
        data: bytes,
        *,
        extension: str = ".gltf",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        safe_id = sanitize_safe_identifier(asset_id)
        if len(data) > self.max_cache_bytes:
            raise ValueError(f"Asset '{safe_id}' size ({len(data)} B) exceeds {self.tier} quota ({self.max_cache_bytes} B)")
        ext = extension if extension.startswith(".") else f".{extension}"
        if ext.lower() not in ALLOWED_EXTRACT_EXTENSIONS:
            raise ValueError(f"Unsupported cache extension: {ext}")
        verify_file_format_and_dependencies(data, ext)

        sha = hashlib.sha256(data).hexdigest()
        filename = f"{safe_id}_{sha[:12]}{ext}"
        target = self.blobs_dir / filename
        atomic_write_bytes(target, data)

        idx = self._read_index()
        now = time.time()
        idx[safe_id] = {
            "asset_id": safe_id,
            "tier": self.tier,
            "filename": filename,
            "sha256": sha,
            "size_bytes": len(data),
            "stored_at": now,
            "last_accessed": now,
            "hits": 0,
            "metadata": metadata or {},
        }
        self._enforce_quota(idx, protected_key=safe_id)
        self._write_index(idx)
        return idx[safe_id]

    def _enforce_quota(self, idx: dict[str, dict[str, Any]], *, protected_key: str | None = None) -> None:
        total = sum(int(v.get("size_bytes", 0)) for v in idx.values())
        if total <= self.max_cache_bytes:
            return
        by_lru = sorted(idx.items(), key=lambda kv: float(kv[1].get("last_accessed", 0)))
        for k, rec in by_lru:
            if total <= self.max_cache_bytes:
                break
            if k == protected_key:
                continue
            blob = self.blobs_dir / rec["filename"]
            if blob.is_file():
                blob.unlink()
            total -= int(rec.get("size_bytes", 0))
            del idx[k]


class AutomaticAssetDownloader:
    """Downloads a single validated HTTPS asset from allowlisted hosts with byte caps & format validation."""

    def __init__(
        self,
        *,
        max_download_bytes: int = 25 * 1024 * 1024,
        timeout_s: float = 15.0,
        allowed_hosts: frozenset[str] = ALLOWED_ASSET_HOSTS,
    ) -> None:
        self.max_download_bytes = max_download_bytes
        self.timeout_s = timeout_s
        self.allowed_hosts = allowed_hosts

    def download_bytes(self, url: str, *, expected_extension: str = ".glb") -> bytes:
        validate_external_asset_url(url, allowed_hosts=self.allowed_hosts)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "XDX-Autonomous-Video-Studio/3.4 (Targeted-Verified-Asset-Fetch)"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            if resp.status != 200:
                raise ValueError(f"Asset download failed with HTTP {resp.status}")
            chunks: list[bytes] = []
            read_total = 0
            while True:
                buf = resp.read(65536)
                if not buf:
                    break
                read_total += len(buf)
                if read_total > self.max_download_bytes:
                    raise ValueError(f"Download exceeded max_download_bytes ({self.max_download_bytes})")
                chunks.append(buf)
        payload = b"".join(chunks)
        verify_file_format_and_dependencies(payload, expected_extension)
        return payload


class ProceduralAssetGenerator(SemanticProceduralAssetGenerator):
    """Production-ready multi-component semantic asset generator (12 categories + explicit greybox mode)."""


class AssetStyleHarmonizer(RealAssetStyleHarmonizer):
    """Buffer- and metadata-level Style Bible harmonizer."""

    def __init__(self, style_bible: dict[str, Any] | None = None) -> None:
        super().__init__(style_bible or GLOBAL_STYLE_BIBLE_V3_4)

    def harmonize(self, asset_meta: dict[str, Any]) -> dict[str, Any]:
        return self.harmonize_metadata(asset_meta)


class CrossEngineAssetConverter(RealGeometryAndTextureConverter):
    """Real vertex/normal/axis converter + cross-engine import/export contract builder."""

    def build_conversion_contract(self, asset_meta: dict[str, Any]) -> dict[str, Any]:
        up_axis = asset_meta.get("up_axis", "+Y")
        unit_scale = float(asset_meta.get("unit_scale_m", 1.0))
        scale_multiplier = round(1.0 / unit_scale, 6) if unit_scale > 0 else 1.0
        return {
            "asset_id": asset_meta["asset_id"],
            "canonical_interchange_format": "gltf_2_0_and_glb",
            "blender_import_transform": {
                "target_up_axis": "+Z",
                "target_forward_axis": "-Y",
                "axis_rotation_applied_by_converter": "Y_UP_TO_Z_UP" if up_axis == "+Y" else None,
                "scale_factor": scale_multiplier,
            },
            "threejs_import_transform": {
                "target_up_axis": "+Y",
                "target_forward_axis": "-Z",
                "axis_rotation_applied_by_converter": "Z_UP_TO_Y_UP" if up_axis == "+Z" else None,
                "scale_factor": scale_multiplier,
                "albedo_color_space": "SRGBColorSpace",
                "orm_color_space": "LinearSRGBColorSpace",
            },
            "remotion_compositing_contract": {
                "alpha_channel": "png_rgba_when_overlay_else_opaque",
                "frame_sync": "zero_based_integer",
            },
        }


class CharacterRetargetingEngine(HonestRiggingAndRetargetingAdapter):
    """Bone-mapping validator with honest SPECIFICATION_ONLY disclosure on animation curve transfer."""

    def create_retarget_map(self, source_convention: str, *, gltf_doc: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.create_retarget_specification(source_convention, gltf_doc=gltf_doc)


class AssetQualityControl:
    """Validates byte integrity, glTF/GLB structure, mobile_guard budgets, and blocks PLACEHOLDER proxies."""

    def inspect(
        self,
        asset_meta: dict[str, Any],
        blob_path: Path | None = None,
        *,
        allow_placeholder_for_final: bool = False,
    ) -> dict[str, Any]:
        issues: list[str] = []
        is_placeholder = bool(
            asset_meta.get("is_placeholder")
            or asset_meta.get("origin_type") == "primitive_placeholder"
            or asset_meta.get("qc_status") == "PLACEHOLDER"
        )
        if is_placeholder and not allow_placeholder_for_final:
            issues.append("PLACEHOLDER primitive box is strictly rejected for final production Asset QC.")

        if not asset_meta.get("style_harmonized") and not is_placeholder:
            issues.append("Asset has not been harmonized with Global Style Bible")

        poly = asset_meta.get("polycount_budget")
        max_tris = GLOBAL_STYLE_BIBLE_V3_4["vivo_x200_pro_max_tris_per_asset"]
        if isinstance(poly, int) and poly > max_tris:
            issues.append(f"Polycount {poly} exceeds Vivo X200 Pro mobile_guard budget ({max_tris})")

        triangle_count_measured = None
        component_count = 0
        if blob_path is not None:
            if not blob_path.is_file() or blob_path.stat().st_size == 0:
                issues.append("Cached blob file is missing or 0 bytes")
            else:
                try:
                    raw = blob_path.read_bytes()
                    verify_file_format_and_dependencies(raw, blob_path.suffix, base_dir=blob_path.parent)
                    if blob_path.suffix.lower() in {".gltf", ".glb"}:
                        doc = json.loads(raw.decode("utf-8")) if blob_path.suffix.lower() == ".gltf" else glb_to_gltf(raw)[0]
                        extras = doc.get("asset", {}).get("extras") or {}
                        if extras.get("is_placeholder") is True and not allow_placeholder_for_final:
                            issues.append("glTF extras marks asset as is_placeholder=True; blocked for final production.")
                        accs = doc.get("accessors", [])
                        meshes = doc.get("meshes", [])
                        component_count = len(meshes)
                        tris = 0
                        for m in meshes:
                            for prim in m.get("primitives", []):
                                if "indices" in prim:
                                    tris += int(accs[int(prim["indices"])]["count"]) // 3
                        triangle_count_measured = tris
                        if not is_placeholder and asset_meta.get("category") == "prop_3d" and tris <= 12 and component_count <= 1:
                            issues.append(
                                f"Generic single-box geometry ({tris} triangles, {component_count} mesh) rejected as production prop."
                            )
                except Exception as exc:
                    issues.append(f"Asset format/dependency integrity error: {exc}")

        passed = len(issues) == 0
        return {
            "passed": passed,
            "asset_id": asset_meta["asset_id"],
            "is_placeholder": is_placeholder,
            "triangle_count_measured": triangle_count_measured,
            "component_count": component_count,
            "issues": issues,
        }


class AssetDiscoveryEngine:
    """Determines required semantic assets from storyboard shots and searches verified CC0 providers."""

    def infer_requirements_from_storyboard(self, storyboard: dict[str, Any]) -> list[dict[str, Any]]:
        needed: dict[str, dict[str, Any]] = {}
        for shot in storyboard.get("shots", []):
            env_id = shot.get("environment_id")
            if env_id and env_id not in needed:
                needed[env_id] = {
                    "requested_id": env_id,
                    "category": "environment_modular",
                    "semantic_type": infer_semantic_category(env_id) or "modular_building",
                    "target_engine": shot["primary_engine"],
                    "used_in_shots": [shot["shot_id"]],
                }
            elif env_id:
                needed[env_id]["used_in_shots"].append(shot["shot_id"])

            for aid in shot.get("asset_ids", []):
                if aid not in needed:
                    cat = (
                        "character_rig"
                        if aid.startswith("char_")
                        else ("font_typography" if aid.startswith("font_") else "prop_3d")
                    )
                    needed[aid] = {
                        "requested_id": aid,
                        "category": cat,
                        "semantic_type": infer_semantic_category(aid),
                        "target_engine": shot["primary_engine"],
                        "used_in_shots": [shot["shot_id"]],
                    }
                else:
                    needed[aid]["used_in_shots"].append(shot["shot_id"])
        return list(needed.values())


@dataclass
class AssetProcurementResult:
    asset_id: str
    resolution_source: str
    steps_executed: list[str]
    asset_metadata: dict[str, Any]
    semantic_spec: dict[str, Any] | None
    cached_path: str | None
    android_cached_path: str | None
    conversion_contract: dict[str, Any]
    qc_report: dict[str, Any]


class IntelligentAssetPipeline:
    """Executes the hardened 9-step Intelligent Asset Procurement workflow."""

    def __init__(
        self,
        *,
        registry: AssetRegistryManager | None = None,
        repo_registry: RepositoryRegistryManager | None = None,
        cache: AssetCacheManager | None = None,
        android_cache: AssetCacheManager | None = None,
        license_validator: LicenseValidator | None = None,
        attribution_ledger: AttributionLedger | None = None,
        downloader: AutomaticAssetDownloader | None = None,
        procedural: ProceduralAssetGenerator | None = None,
        harmonizer: AssetStyleHarmonizer | None = None,
        converter: CrossEngineAssetConverter | None = None,
        qc: AssetQualityControl | None = None,
        external_lookup_fn: Callable[[str, str], dict[str, Any] | None] | None = None,
    ) -> None:
        self.registry = registry or AssetRegistryManager()
        self.repo_registry = repo_registry or RepositoryRegistryManager()
        self.cache = cache or AssetCacheManager(tier="cloud")
        self.android_cache = android_cache or AssetCacheManager(
            cache_dir=self.cache.cache_dir.parent, tier="android_mobile"
        )
        self.license_validator = license_validator or LicenseValidator()
        self.attribution_ledger = attribution_ledger or AttributionLedger(
            self.cache.cache_dir / "attribution_ledger.json"
        )
        self.downloader = downloader or AutomaticAssetDownloader()
        self.procedural = procedural or ProceduralAssetGenerator()
        self.harmonizer = harmonizer or AssetStyleHarmonizer()
        self.converter = converter or CrossEngineAssetConverter()
        self.qc = qc or AssetQualityControl()
        self.external_lookup_fn = external_lookup_fn

    def procure_asset(
        self,
        asset_id: str,
        *,
        category: str = "prop_3d",
        semantic_category: str | None = None,
        target_engine: str = "threejs",
        persist_registry: bool = False,
        mirror_to_android_cache: bool = False,
        allow_placeholder_greybox: bool = False,
    ) -> AssetProcurementResult:
        safe_id = sanitize_safe_identifier(asset_id)
        steps: list[str] = []
        semantic_spec: dict[str, Any] | None = None

        # Step 1: Check registry
        steps.append("1_check_registry")
        reg_entry = self.registry.get_by_id(safe_id)

        # Step 2: Check cache
        steps.append("2_check_cache")
        cached_blob = self.cache.get(safe_id)

        resolution_source = "registry_and_cache"
        raw_bytes: bytes | None = None
        ext = ".gltf"

        if reg_entry is not None and cached_blob is not None:
            steps.append("4_validate_license_and_compatibility")
            self.license_validator.validate(reg_entry["license_spdx"])
        elif reg_entry is not None and cached_blob is None:
            steps.append("4_validate_license_and_compatibility")
            self.license_validator.validate(reg_entry["license_spdx"])
            sem_hint = semantic_category or reg_entry.get("semantic_type") or infer_semantic_category(safe_id) or "modular_building"
            if reg_entry.get("category") in {"prop_3d", "environment_modular"} and self.procedural.supports_category(sem_hint):
                steps.append("6_generate_semantic_procedural_for_registry_entry")
                raw_bytes, semantic_spec, _ = self.procedural.generate_semantic_asset(safe_id, semantic_category=sem_hint)
                resolution_source = "registry_hydrated_procedurally"
        else:
            # Step 3: Discover external asset
            steps.append("3_discover_external_asset")
            ext_candidate = self.external_lookup_fn(safe_id, category) if self.external_lookup_fn else None

            if ext_candidate is not None:
                # Step 4: Validate source, license, and compatibility
                steps.append("4_validate_license_and_compatibility")
                self.license_validator.validate(str(ext_candidate.get("license_spdx", "UNKNOWN")))
                if target_engine not in ext_candidate.get("compatible_engines", [target_engine]):
                    raise ValueError(f"External asset '{safe_id}' incompatible with engine '{target_engine}'")

                # Step 5: Targeted download + format verification
                steps.append("5_download_required_asset")
                ext = str(ext_candidate.get("extension", ".gltf"))
                if "inline_bytes" in ext_candidate:
                    raw_bytes = bytes(ext_candidate["inline_bytes"])
                    verify_file_format_and_dependencies(raw_bytes, ext)
                else:
                    raw_bytes = self.downloader.download_bytes(
                        str(ext_candidate["download_url"]), expected_extension=ext
                    )
                reg_entry = {
                    "asset_id": safe_id,
                    "name": ext_candidate.get("name", safe_id),
                    "category": category,
                    "semantic_type": semantic_category or infer_semantic_category(safe_id),
                    "is_placeholder": False,
                    "origin_type": "external_downloaded",
                    "source_provider": ext_candidate.get("provider", "External Verified CC0"),
                    "source_url": ext_candidate.get("source_url", ext_candidate.get("download_url", "https://polyhaven.com")),
                    "license_spdx": ext_candidate["license_spdx"],
                    "attribution_required": bool(ext_candidate.get("attribution_required", False)),
                    "attribution_text": ext_candidate.get("attribution_text"),
                    "commercial_allowed": True,
                    "formats": [ext.lstrip(".")],
                    "unit_scale_m": 1.0,
                    "up_axis": "+Y",
                    "polycount_budget": int(ext_candidate.get("polycount_budget", 4000)),
                    "compatible_engines": ext_candidate.get("compatible_engines", ["blender", "threejs"]),
                    "style_harmonized": False,
                    "style_profile": {},
                    "qc_status": "not_tested",
                }
                resolution_source = "external_downloaded"
            else:
                # Step 6: Semantic Procedural Generation (or BLOCKED if unsupported & placeholder disallowed)
                sem_cat = semantic_category or infer_semantic_category(safe_id)
                if sem_cat and self.procedural.supports_category(sem_cat):
                    steps.append("4_validate_license_and_compatibility")
                    self.license_validator.validate("MIT")
                    steps.append("6_generate_semantic_procedural_asset")
                    raw_bytes, semantic_spec, tri_count = self.procedural.generate_semantic_asset(
                        safe_id, semantic_category=sem_cat
                    )
                    reg_entry = {
                        "asset_id": safe_id,
                        "name": f"Procedural {sem_cat.replace('_', ' ').title()} ({safe_id})",
                        "category": category,
                        "semantic_type": sem_cat,
                        "is_placeholder": False,
                        "origin_type": "procedural_generated",
                        "source_provider": "XDX Semantic Procedural Generator v3.4",
                        "source_url": f"local://semantic-procedural/{sem_cat}/{safe_id}",
                        "license_spdx": "MIT",
                        "attribution_required": False,
                        "attribution_text": None,
                        "commercial_allowed": True,
                        "formats": ["gltf", "glb"],
                        "unit_scale_m": 1.0,
                        "up_axis": "+Y",
                        "polycount_budget": tri_count,
                        "measured_triangles": tri_count,
                        "component_count": len(semantic_spec["components"]),
                        "compatible_engines": ["blender", "threejs"],
                        "style_harmonized": False,
                        "style_profile": {"roughness": 0.65, "metallic": 0.10},
                        "qc_status": "not_tested",
                    }
                    resolution_source = "procedural_generated"
                elif allow_placeholder_greybox:
                    steps.append("6_generate_diagnostic_placeholder_greybox")
                    raw_bytes, semantic_spec, tri_count = self.procedural.generate_primitive_placeholder_box(safe_id)
                    reg_entry = {
                        "asset_id": safe_id,
                        "name": f"PLACEHOLDER PROXY ({safe_id})",
                        "category": category,
                        "semantic_type": "primitive_placeholder",
                        "is_placeholder": True,
                        "origin_type": "primitive_placeholder",
                        "source_provider": "XDX Diagnostic Greybox",
                        "source_url": f"local://placeholder/{safe_id}",
                        "license_spdx": "MIT",
                        "attribution_required": False,
                        "attribution_text": None,
                        "commercial_allowed": True,
                        "formats": ["gltf"],
                        "unit_scale_m": 1.0,
                        "up_axis": "+Y",
                        "polycount_budget": tri_count,
                        "compatible_engines": ["blender", "threejs"],
                        "style_harmonized": False,
                        "style_profile": {},
                        "qc_status": "PLACEHOLDER",
                    }
                    resolution_source = "primitive_placeholder"
                else:
                    raise AssetBlockedError(
                        f"BLOCKED: Asset '{safe_id}' (category='{category}') is not in registry, not found on "
                        "verified external providers, and has no semantic procedural generator. "
                        "Refusing to substitute a generic 12-triangle box."
                    )

        assert reg_entry is not None

        # Step 7: Real buffer-level & metadata Style Harmonization + Ground/Normal Conversion
        steps.append("7_harmonize_global_style_bible")
        if raw_bytes is not None and ext == ".gltf" and not reg_entry.get("is_placeholder"):
            gltf_doc = json.loads(raw_bytes.decode("utf-8"))
            gltf_doc, _ = self.harmonizer.harmonize_gltf_document(gltf_doc)
            gltf_doc, _ = self.converter.transform_gltf_geometry(
                gltf_doc,
                scale_factor=1.0,
                normalize_normals=True,
                snap_bottom_to_ground=True,
            )
            raw_bytes = json.dumps(gltf_doc, indent=2).encode("utf-8")

        harmonized = self.harmonizer.harmonize(reg_entry)
        conv = self.converter.build_conversion_contract(harmonized)

        android_cached_blob: Path | None = None
        if raw_bytes is not None:
            put_rec = self.cache.put(safe_id, raw_bytes, extension=ext, metadata={"source": resolution_source})
            cached_blob = self.cache.get(safe_id)
            harmonized["sha256"] = put_rec["sha256"]
            harmonized["cache_key"] = put_rec["filename"]
            harmonized["cache_tier"] = self.cache.tier
            if mirror_to_android_cache and ext == ".gltf":
                glb_bytes = gltf_to_glb(json.loads(raw_bytes.decode("utf-8")))
                self.android_cache.put(safe_id, glb_bytes, extension=".glb", metadata={"target": "vivo_x200_pro"})
                android_cached_blob = self.android_cache.get(safe_id)

        # Step 8: Validate asset quality (blocks PLACEHOLDER unless allow_placeholder_greybox=True)
        steps.append("8_validate_asset_quality")
        qc_res = self.qc.inspect(
            harmonized,
            cached_blob,
            allow_placeholder_for_final=allow_placeholder_greybox,
        )
        if not qc_res["passed"]:
            harmonized["qc_status"] = "BLOCKED"
            raise AssetBlockedError(f"Asset QC blocked '{safe_id}': {qc_res['issues']}")
        harmonized["qc_status"] = "PLACEHOLDER" if harmonized.get("is_placeholder") else "tested"
        if qc_res["triangle_count_measured"] is not None:
            harmonized["measured_triangles"] = qc_res["triangle_count_measured"]
        if qc_res["component_count"]:
            harmonized["component_count"] = qc_res["component_count"]

        # Step 9: Persist attribution & registry for reuse
        steps.append("9_persist_for_reuse")
        self.attribution_ledger.record(harmonized)
        self.registry.upsert_asset(harmonized, persist=persist_registry)

        return AssetProcurementResult(
            asset_id=safe_id,
            resolution_source=resolution_source,
            steps_executed=steps,
            asset_metadata=harmonized,
            semantic_spec=semantic_spec,
            cached_path=str(cached_blob) if cached_blob else None,
            android_cached_path=str(android_cached_blob) if android_cached_blob else None,
            conversion_contract=conv,
            qc_report=qc_res,
        )
