// XDX rig kit: topic-agnostic animation primitives that make acting correct BY CONSTRUCTION instead of by guessed angles.
//   solveArm      two-bone IK: put the wrist on a world target (shoulder + elbow rotations from a pole hint)
//   aimAxis       rotate an object so one of its local axes points at a world target (fan facing a face, remote tip at the AC)
//   lookHead      turn a head toward a world target with natural yaw/pitch limits
//   anchors       named world-space probes (positions/directions) so a test can verify an action geometrically
// Conventions of the XDX character rig: arm groups hang along local -Y; rotating about local X by a negative angle swings the
// limb forward (+Z); the head looks along local +Z.
import * as THREE from "three";

const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _c = new THREE.Vector3(), _d = new THREE.Vector3();
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion();

function setWorldQuaternion(obj, worldQ) {
  obj.parent.getWorldQuaternion(_q2).invert();
  obj.quaternion.copy(_q2.multiply(worldQ));
}

// arm = { sh, el, wr } with upper arm length L1 (sh->el) and forearm length L2 (el->wr).
export function solveArm(arm, targetWorld, poleWorld, L1 = 0.29, L2 = 0.255) {
  arm.sh.updateWorldMatrix(true, false);
  const S = arm.sh.getWorldPosition(new THREE.Vector3());
  const toT = targetWorld.clone().sub(S);
  const dRaw = toT.length();
  const d = Math.min(Math.max(dRaw, Math.abs(L1 - L2) + 1e-3), L1 + L2 - 1e-3);
  const u = toT.normalize();
  // elbow side: component of the pole hint perpendicular to the shoulder->target axis
  const p = poleWorld.clone().sub(S); p.addScaledVector(u, -p.dot(u));
  if (p.lengthSq() < 1e-8) p.set(0, -1, 0).addScaledVector(u, u.y);
  p.normalize();
  const cosA = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d);
  const alpha = Math.acos(Math.min(1, Math.max(-1, cosA)));
  const upper = u.clone().multiplyScalar(Math.cos(alpha)).addScaledVector(p, Math.sin(alpha)).normalize();
  const E = S.clone().addScaledVector(upper, L1);
  const T = S.clone().addScaledVector(u, d);
  const fore = T.sub(E).normalize();
  // local basis of the upper arm: Y = -upper, Z = direction the forearm bends toward, X = Y x Z
  const Y = upper.clone().negate();
  const Z = fore.clone().addScaledVector(upper, -fore.dot(upper));
  if (Z.lengthSq() < 1e-8) Z.copy(p).negate();
  Z.normalize();
  const X = _a.copy(Y).cross(Z).normalize().clone();
  _m.makeBasis(X, Y, Z);
  setWorldQuaternion(arm.sh, _q.setFromRotationMatrix(_m));
  const cosB = (L1 * L1 + L2 * L2 - d * d) / (2 * L1 * L2);
  const beta = Math.acos(Math.min(1, Math.max(-1, cosB)));
  arm.el.rotation.set(-(Math.PI - beta), 0, 0);
  return { reachable: dRaw <= L1 + L2, distance: dRaw };
}

// Rotate `obj` (about its own origin) so its local `axisLocal` points at `targetWorld`; `roll` spins it about that axis.
export function aimAxis(obj, axisLocal, targetWorld, roll = 0) {
  obj.updateWorldMatrix(true, false);
  const pos = obj.getWorldPosition(_b);
  const want = _c.copy(targetWorld).sub(pos).normalize();
  const curQ = obj.getWorldQuaternion(new THREE.Quaternion());
  const cur = _d.copy(axisLocal).normalize().applyQuaternion(curQ);
  const dq = new THREE.Quaternion().setFromUnitVectors(cur, want);
  let q = dq.multiply(curQ);
  if (roll) q = new THREE.Quaternion().setFromAxisAngle(want, roll).multiply(q);
  setWorldQuaternion(obj, q);
}

// Turn a head (looks along +Z) toward a target; amount 0..1 blends from the current rotation; limits in radians.
export function lookHead(head, targetWorld, amount = 1, maxYaw = 1.15, maxPitch = 0.5) {
  head.parent.updateWorldMatrix(true, false);
  const local = head.parent.worldToLocal(targetWorld.clone()).sub(head.position);
  const yaw = Math.atan2(local.x, local.z);
  const pitch = -Math.atan2(local.y, Math.hypot(local.x, local.z));
  const cl = (v, m) => Math.max(-m, Math.min(m, v));
  head.rotation.set(head.rotation.x + (cl(pitch, maxPitch) - head.rotation.x) * amount, head.rotation.y + (cl(yaw, maxYaw) - head.rotation.y) * amount, head.rotation.z);
}

// World-space probe of a named point plus an optional local direction.
export function anchor(obj, localPos = null, localDir = null) {
  obj.updateWorldMatrix(true, false);
  const p = localPos ? obj.localToWorld(localPos.clone()) : obj.getWorldPosition(new THREE.Vector3());
  const out = { p: [p.x, p.y, p.z] };
  if (localDir) {
    const d = localDir.clone().normalize().applyQuaternion(obj.getWorldQuaternion(new THREE.Quaternion()));
    out.d = [d.x, d.y, d.z];
  }
  return out;
}

// Two-axis aim: local axisA -> worldDirA exactly, and local axisB as close as possible to worldDirB (roll about A).
export function aimTwo(obj, axisA, worldDirA, axisB, worldDirB) {
  obj.updateWorldMatrix(true, false);
  const A = worldDirA.clone().normalize();
  const B = worldDirB.clone().addScaledVector(A, -worldDirB.dot(A));
  if (B.lengthSq() < 1e-8) B.set(0, 1, 0).addScaledVector(A, -A.y);
  B.normalize();
  const C = new THREE.Vector3().crossVectors(A, B);
  const a = axisA.clone().normalize();
  const b = axisB.clone().addScaledVector(a, -axisB.dot(a)).normalize();
  const c = new THREE.Vector3().crossVectors(a, b);
  const W = new THREE.Matrix4().makeBasis(A, B, C);
  const L = new THREE.Matrix4().makeBasis(a, b, c);
  const R = W.multiply(L.transpose());
  setWorldQuaternion(obj, new THREE.Quaternion().setFromRotationMatrix(R));
}
