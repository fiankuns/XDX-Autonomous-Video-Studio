// XDX canonical timeline (integer frames). One timeline per project; chapters are logical groupings of its shots.
// The signed package (storyboard + caption plan) is the only source: scenes never hard-code frame numbers.
export function buildTimeline(PKG, { syncLeadSeconds = 0.3 } = {}) {
  if (!PKG || !Number.isInteger(PKG.fps) || !Number.isInteger(PKG.total_frames)) throw new Error("timeline: fps/total_frames must be integers");
  let expect = 0;
  for (const [id, a, b] of PKG.shots) {
    if (!Number.isInteger(a) || !Number.isInteger(b) || a !== expect || b <= a) throw new Error(`timeline: shot ${id} is not contiguous integer frames`);
    expect = b;
  }
  if (expect !== PKG.total_frames) throw new Error("timeline: shots do not cover total_frames exactly");
  const CUEF = {};
  for (const [sid, a, b] of PKG.cues) (CUEF[sid] = CUEF[sid] || []).push({ a: Math.round(a * PKG.fps), b: Math.round(b * PKG.fps) });
  const SYNC_LEAD = Math.round(syncLeadSeconds * PKG.fps); // visuals may lead the words by at most this many frames
  const cue = (sid, i) => CUEF[sid][i];
  const chapters = (PKG.chapters || []).map((c) => ({ ...c })); // optional logical chapters (derived view, never a second timeline)
  return { CUEF, SYNC_LEAD, cue, shots: PKG.shots, fps: PKG.fps, total_frames: PKG.total_frames, chapters };
}
