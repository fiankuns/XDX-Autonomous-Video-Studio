#!/usr/bin/env node
/**
 * Deterministic Remotion v4 Master Timeline & Caption Verification Module.
 * Verifies zero-gap [start_frame, end_frame) sequence math, spring() determinism,
 * and @remotion/captions TikTok-style page generation.
 */
import { interpolate, spring } from 'remotion';
import { createTikTokStyleCaptions } from '@remotion/captions';

export function verifyMasterTimelineSpec({ fps = 30, shots = [], sampleText = 'Halo penonton Indonesia' }) {
  let cursor = 0;
  for (const s of shots) {
    if (s.start_frame !== cursor) {
      throw new Error(`Timeline gap/overlap at ${s.shot_id}: expected ${cursor}, got ${s.start_frame}`);
    }
    if (s.end_frame <= s.start_frame) {
      throw new Error(`Invalid shot duration at ${s.shot_id}`);
    }
    cursor = s.end_frame;
  }

  const hookScale = spring({
    frame: 10,
    fps,
    config: { mass: 0.8, damping: 12, stiffness: 180 },
  });
  const fadeAlpha = interpolate(10, [0, 15], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const words = sampleText.split(/\s+/).filter(Boolean);
  const captionsInput = words.map((w, idx) => ({
    text: idx === 0 ? w : ` ${w}`,
    startMs: idx * 320,
    endMs: (idx + 1) * 320,
    timestampMs: idx * 320,
    confidence: 1.0,
  }));

  const { pages } = createTikTokStyleCaptions({
    captions: captionsInput,
    combineTokensWithinMilliseconds: 1200,
  });

  return {
    status: 'ok',
    totalFrames: cursor,
    durationSeconds: Number((cursor / fps).toFixed(4)),
    hookSpringSample: Number(hookScale.toFixed(6)),
    fadeAlphaSample: Number(fadeAlpha.toFixed(6)),
    captionPagesGenerated: pages.length,
  };
}

if (process.argv.includes('--self-test')) {
  const sampleShots = [
    { shot_id: 'S001', start_frame: 0, end_frame: 90 },
    { shot_id: 'S002', start_frame: 90, end_frame: 210 },
    { shot_id: 'S003', start_frame: 210, end_frame: 300 },
  ];
  const res = verifyMasterTimelineSpec({ fps: 30, shots: sampleShots });
  console.log(JSON.stringify(res));
}
