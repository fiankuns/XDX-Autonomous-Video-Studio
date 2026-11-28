// XDX style binding: scene colours come from the signed character bible / style bible, never from literals in the scene.
// Convention: a character's locked palette is ordered [primary garment, secondary garment, hair, accent].
export const PALETTE_ROLES = ["shirt", "pants", "hair", "accent"];
export function bindCharacterPalette(PKG) {
  const p = PKG && PKG.character_palette;
  if (!Array.isArray(p) || p.length !== PALETTE_ROLES.length || !p.every((c) => /^#[0-9A-Fa-f]{6}$/.test(c))) {
    throw new Error("style binding: package is missing a valid locked character palette (character_bible.json)");
  }
  const out = {};
  PALETTE_ROLES.forEach((r, i) => { out[r] = p[i]; });
  return { SHIRT: out.shirt, PANTS: out.pants, HAIR: out.hair, ACCENT: out.accent, style_bible_id: PKG.style_bible_id };
}
