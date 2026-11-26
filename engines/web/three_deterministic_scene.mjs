#!/usr/bin/env node
/**
 * Deterministic Three.js (v0.187.0) Procedural Scene & Simulation Evaluator.
 * Strictly prohibits wall-clock time; evaluates every transform/particle at exact (frame / fps)
 * using a seeded Mulberry32 PRNG and modern ES module Three.js classes.
 */
import * as THREE from 'three';
import { createTimeline } from 'animejs';
import { scaleLinear } from 'd3-scale';

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    let t = (a += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function evaluateDeterministicThreeShot({
  shotId = 'S001',
  fps = 30,
  frame = 0,
  durationFrames = 90,
  seed = 1337,
  width = 1080,
  height = 1920,
  focalLengthMm = 35,
  sensorWidthMm = 36,
}) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x111318);

  const fovDeg = THREE.MathUtils.radToDeg(
    2 * Math.atan(sensorWidthMm / (2 * focalLengthMm))
  );
  const camera = new THREE.PerspectiveCamera(fovDeg, width / height, 0.1, 200);

  const progressScale = scaleLinear().domain([0, Math.max(1, durationFrames - 1)]).range([0, 1]).clamp(true);
  const u = progressScale(frame);

  // Anime.js v4 deterministic timeline seeked strictly by frame time (ms)
  const animState = { camZ: 4.5, pedestalScaleY: 0.2 };
  const tl = createTimeline({ autoplay: false });
  tl.add(animState, {
    camZ: 3.6,
    pedestalScaleY: 1.0,
    duration: (durationFrames / fps) * 1000,
    ease: 'inOutCubic',
  });
  tl.seek((frame / fps) * 1000);

  camera.position.set(0, 1.4, animState.camZ);
  camera.lookAt(0, 0.8, 0);
  camera.updateMatrixWorld(true);

  const geom = new THREE.BoxGeometry(0.8, 1.0, 0.8);
  const mat = new THREE.MeshStandardMaterial({
    color: 0x4f8cff,
    roughness: 0.68,
    metalness: 0.08,
  });
  const pedestal = new THREE.Mesh(geom, mat);
  pedestal.scale.set(1, animState.pedestalScaleY, 1);
  pedestal.updateMatrixWorld(true);
  scene.add(pedestal);

  const rng = mulberry32(seed);
  const firstParticle = [
    Number(((rng() - 0.5) * 2.0).toFixed(6)),
    Number((rng() * 2.0 + u * 0.25).toFixed(6)),
    Number(((rng() - 0.5) * 2.0).toFixed(6)),
  ];

  geom.dispose();
  mat.dispose();

  return {
    shotId,
    threeVersion: THREE.REVISION,
    frame,
    fps,
    timeSeconds: Number((frame / fps).toFixed(6)),
    cameraPosition: camera.position.toArray().map((v) => Number(v.toFixed(6))),
    pedestalScaleY: Number(pedestal.scale.y.toFixed(6)),
    seededParticleSample: firstParticle,
    colorSpace: THREE.SRGBColorSpace,
    deterministic: true,
  };
}

if (process.argv.includes('--self-test')) {
  const runA = evaluateDeterministicThreeShot({ shotId: 'S002', frame: 45, durationFrames: 90, seed: 2026 });
  const runB = evaluateDeterministicThreeShot({ shotId: 'S002', frame: 45, durationFrames: 90, seed: 2026 });
  const identical = JSON.stringify(runA) === JSON.stringify(runB);
  if (!identical) {
    console.error('Determinism check FAILED');
    process.exit(2);
  }
  console.log(JSON.stringify({ status: 'ok', identical, sample: runA }));
}
