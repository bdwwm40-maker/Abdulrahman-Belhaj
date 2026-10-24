// Stylized 3D character wearing the beige polo (two chest logos) and navy trousers
// from the reference photo. Built from primitives with a named joint hierarchy so
// it can be animated in three.js, Blender, Cinema 4D, or After Effects (glTF).
import * as THREE from 'three';

export const COLORS = {
  shirt: 0xe3c9a6,
  shirtShade: 0xd6ba94,
  button: 0xf4efe6,
  pants: 0x1e2c4c,
  skin: 0xc68e63,
  hair: 0x24170f,
  shoe: 0xf2f2f2,
  sole: 0x2b2b2b,
  eye: 0x1b120c,
};

const mat = (color, roughness = 0.75) =>
  new THREE.MeshStandardMaterial({ color, roughness, metalness: 0 });

function mesh(geo, material, name, pos = [0, 0, 0], scale = [1, 1, 1], rot = [0, 0, 0]) {
  const m = new THREE.Mesh(geo, material);
  m.name = name;
  m.position.set(...pos);
  m.scale.set(...scale);
  m.rotation.set(...rot);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

function joint(name, pos, parent) {
  const g = new THREE.Group();
  g.name = name;
  g.position.set(...pos);
  parent.add(g);
  return g;
}

export function buildCharacter({ logoLeft, logoRight } = {}) {
  const M = {
    shirt: mat(COLORS.shirt, 0.85),
    shirtShade: mat(COLORS.shirtShade, 0.85),
    button: mat(COLORS.button, 0.4),
    pants: mat(COLORS.pants, 0.8),
    skin: mat(COLORS.skin, 0.6),
    hair: mat(COLORS.hair, 0.9),
    shoe: mat(COLORS.shoe, 0.5),
    sole: mat(COLORS.sole, 0.7),
    eyeWhite: mat(0xffffff, 0.3),
    eye: mat(COLORS.eye, 0.2),
    mouth: mat(0x7a3b2e, 0.6),
  };

  const root = new THREE.Group();
  root.name = 'Character';

  // ---------- Hips & legs (navy trousers) ----------
  const hips = joint('Hips', [0, 0.98, 0], root);
  hips.add(mesh(new THREE.CapsuleGeometry(0.17, 0.08, 8, 24), M.pants, 'Pelvis',
    [0, 0.0, 0], [0.92, 0.95, 0.66], [0, 0, Math.PI / 2]));
  // belt line
  hips.add(mesh(new THREE.TorusGeometry(0.175, 0.012, 8, 40), M.pants, 'Waistband',
    [0, 0.1, 0], [1.03, 0.72, 1], [Math.PI / 2, 0, 0]));

  for (const side of ['L', 'R']) {
    const s = side === 'L' ? 1 : -1;
    const thigh = joint(`UpperLeg_${side}`, [0.1 * s, 0, 0], hips);
    thigh.add(mesh(new THREE.CapsuleGeometry(0.085, 0.34, 8, 20), M.pants, `Thigh_${side}`,
      [0, -0.22, 0]));
    const knee = joint(`LowerLeg_${side}`, [0, -0.45, 0], thigh);
    knee.add(mesh(new THREE.CapsuleGeometry(0.075, 0.34, 8, 20), M.pants, `Shin_${side}`,
      [0, -0.2, 0]));
    // trouser cuff
    knee.add(mesh(new THREE.CylinderGeometry(0.08, 0.085, 0.05, 20), M.pants, `Cuff_${side}`,
      [0, -0.4, 0]));
    const foot = joint(`Foot_${side}`, [0, -0.44, 0], knee);
    foot.add(mesh(new THREE.CapsuleGeometry(0.06, 0.13, 8, 16), M.shoe, `Shoe_${side}`,
      [0, -0.035, 0.05], [1.05, 0.75, 1], [Math.PI / 2, 0, 0]));
    foot.add(mesh(new THREE.CapsuleGeometry(0.062, 0.14, 8, 16), M.sole, `Sole_${side}`,
      [0, -0.075, 0.05], [1.08, 0.28, 1], [Math.PI / 2, 0, 0]));
  }

  // ---------- Torso (beige polo) ----------
  const spine = joint('Spine', [0, 0.06, 0], hips);
  const chest = joint('Chest', [0, 0, 0], spine);
  // polo silhouette as a lathe profile: [radius, height]
  const DEPTH = 0.68;
  const profile = [[0.001, 0.02], [0.2, 0.0], [0.198, 0.08], [0.19, 0.22], [0.198, 0.36],
    [0.205, 0.46], [0.203, 0.53], [0.185, 0.585], [0.14, 0.625], [0.085, 0.655], [0.07, 0.665]];
  const rAt = (y) => {
    for (let i = 2; i < profile.length; i++) {
      const [r0, y0] = profile[i - 1], [r1, y1] = profile[i];
      if (y <= y1) return r0 + (r1 - r0) * (y - y0) / (y1 - y0);
    }
    return profile.at(-1)[0];
  };
  const frontZ = (y) => rAt(y) * DEPTH;
  const torsoGeo = new THREE.LatheGeometry(profile.map(([r, y]) => new THREE.Vector2(r, y)), 64);
  chest.add(mesh(torsoGeo, M.shirt, 'Shirt_Body', [0, 0, 0], [1, 1, DEPTH]));
  // untucked hem
  chest.add(mesh(new THREE.TorusGeometry(0.2, 0.01, 8, 48), M.shirtShade, 'Shirt_Hem',
    [0, 0.008, 0], [1, DEPTH, 1], [Math.PI / 2, 0, 0]));

  // polo collar: band + two flaps
  chest.add(mesh(new THREE.CylinderGeometry(0.068, 0.078, 0.05, 32, 1, true), M.shirt,
    'Collar_Band', [0, 0.68, 0], [1, 1, 0.92]));
  for (const side of [1, -1]) {
    chest.add(mesh(new THREE.BoxGeometry(0.085, 0.01, 0.07), M.shirtShade,
      `Collar_Flap_${side > 0 ? 'L' : 'R'}`, [0.05 * side, 0.665, 0.065],
      [1, 1, 1], [0.55, 0.5 * side, -0.3 * side]));
  }
  // placket with three buttons, following the chest curve
  [0.6, 0.565, 0.53].forEach((y, i) => {
    chest.add(mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.005, 16), M.button,
      `Button_${i + 1}`, [0, y, frontZ(y) + 0.002], [1, 1, 1], [Math.PI / 2 - 0.35 * (y - 0.5) * 6, 0, 0]));
  });
  chest.add(mesh(new THREE.BoxGeometry(0.04, 0.003, 0.003), M.shirtShade, 'Placket_Bottom',
    [0, 0.51, frontZ(0.51) + 0.001]));

  // chest logos (decals), positioned as in the photo
  const addLogo = (tex, name, x, w, h) => {
    if (!tex) return;
    tex.colorSpace = THREE.SRGBColorSpace;
    const m = new THREE.MeshStandardMaterial({
      map: tex, transparent: true, alphaTest: 0.08, roughness: 0.8, depthWrite: false,
    });
    const plane = mesh(new THREE.PlaneGeometry(w, h), m, name, [x, 0.48, frontZ(0.48) * Math.cos(x / rAt(0.48) * 1.1) + 0.006]);
    plane.rotation.y = x * 2.2; // follow the torso curve
    plane.castShadow = false;
    chest.add(plane);
  };
  // wearer's right chest (viewer's left): colourful emblem; wearer's left: white ribbon
  addLogo(logoLeft, 'Logo_Emblem', -0.105, 0.085, 0.114);
  addLogo(logoRight, 'Logo_Ribbon', 0.105, 0.085, 0.113);

  // ---------- Arms (short sleeves) ----------
  for (const side of ['L', 'R']) {
    const s = side === 'L' ? 1 : -1;
    const shoulder = joint(`UpperArm_${side}`, [0.215 * s, 0.53, 0], chest);
    shoulder.rotation.z = 0.12 * s;
    shoulder.add(mesh(new THREE.SphereGeometry(0.072, 24, 16), M.shirt, `Sleeve_Cap_${side}`,
      [0, -0.01, 0]));
    shoulder.add(mesh(new THREE.CylinderGeometry(0.072, 0.076, 0.19, 24), M.shirt, `Sleeve_${side}`,
      [0, -0.095, 0]));
    shoulder.add(mesh(new THREE.TorusGeometry(0.076, 0.007, 8, 24), M.shirtShade, `Sleeve_Hem_${side}`,
      [0, -0.19, 0], [1, 1, 1], [Math.PI / 2, 0, 0]));
    shoulder.add(mesh(new THREE.CapsuleGeometry(0.05, 0.16, 8, 16), M.skin, `Arm_${side}`,
      [0, -0.2, 0]));
    const elbow = joint(`LowerArm_${side}`, [0, -0.3, 0], shoulder);
    elbow.add(mesh(new THREE.CapsuleGeometry(0.045, 0.2, 8, 16), M.skin, `Forearm_${side}`,
      [0, -0.12, 0]));
    const hand = joint(`Hand_${side}`, [0, -0.26, 0], elbow);
    hand.add(mesh(new THREE.SphereGeometry(0.055, 20, 16), M.skin, `Palm_${side}`,
      [0, -0.04, 0], [0.85, 1.15, 0.6]));
    hand.add(mesh(new THREE.CapsuleGeometry(0.018, 0.04, 6, 10), M.skin, `Thumb_${side}`,
      [-0.035 * s, -0.03, 0.025], [1, 1, 1], [0.4, 0, 0.5 * s]));
  }

  // ---------- Neck & head ----------
  const neck = joint('Neck', [0, 0.67, 0], chest);
  neck.add(mesh(new THREE.CylinderGeometry(0.055, 0.06, 0.1, 20), M.skin, 'Neck_Mesh', [0, 0.03, 0]));
  const head = joint('Head', [0, 0.08, 0], neck);
  head.add(mesh(new THREE.SphereGeometry(0.135, 40, 32), M.skin, 'Head_Mesh',
    [0, 0.13, 0.005], [0.95, 1.12, 1]));
  // hair: short cap
  head.add(mesh(new THREE.SphereGeometry(0.142, 40, 24, 0, Math.PI * 2, 0, Math.PI * 0.52),
    M.hair, 'Hair', [0, 0.155, -0.008], [0.97, 1.08, 1.03], [-0.25, 0, 0]));
  for (const side of [1, -1]) {
    const tag = side > 0 ? 'L' : 'R';
    head.add(mesh(new THREE.SphereGeometry(0.03, 16, 12), M.skin, `Ear_${tag}`,
      [0.128 * side, 0.13, 0], [0.5, 1, 0.8]));
    head.add(mesh(new THREE.SphereGeometry(0.022, 20, 16), M.eyeWhite, `EyeWhite_${tag}`,
      [0.045 * side, 0.15, 0.118], [1, 1, 0.5]));
    head.add(mesh(new THREE.SphereGeometry(0.013, 16, 12), M.eye, `Pupil_${tag}`,
      [0.045 * side, 0.149, 0.128], [1, 1, 0.5]));
    head.add(mesh(new THREE.BoxGeometry(0.05, 0.01, 0.012), M.hair, `Brow_${tag}`,
      [0.047 * side, 0.188, 0.118], [1, 1, 1], [0, 0, -0.12 * side]));
  }
  head.add(mesh(new THREE.SphereGeometry(0.02, 16, 12), M.skin, 'Nose', [0, 0.115, 0.135], [0.9, 1.1, 1]));
  head.add(mesh(new THREE.TorusGeometry(0.028, 0.006, 8, 20, Math.PI), M.mouth, 'Smile',
    [0, 0.075, 0.122], [1, 0.8, 1], [0, 0, Math.PI]));

  root.traverse((o) => { if (o.isMesh) o.frustumCulled = false; });
  return root;
}

// ---------- Animation clips ----------
const q = (x, y, z) => new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z)).toArray();

function rotTrack(node, times, eulers) {
  return new THREE.QuaternionKeyframeTrack(`${node}.quaternion`, times,
    eulers.flatMap((e) => q(...e)));
}

export function buildClips() {
  const idle = new THREE.AnimationClip('Idle', 3, [
    new THREE.VectorKeyframeTrack('Chest.scale', [0, 1.5, 3], [1, 1, 1, 1.015, 1.01, 1.02, 1, 1, 1]),
    rotTrack('Head', [0, 1.5, 3], [[0, 0, 0], [0.04, 0.08, 0.02], [0, 0, 0]]),
    rotTrack('UpperArm_L', [0, 1.5, 3], [[0, 0, 0.12], [0, 0, 0.15], [0, 0, 0.12]]),
    rotTrack('UpperArm_R', [0, 1.5, 3], [[0, 0, -0.12], [0, 0, -0.15], [0, 0, -0.12]]),
  ]);

  const waveT = [0, 0.4, 0.7, 1.0, 1.3, 1.6, 2.0];
  const wave = new THREE.AnimationClip('Wave', 2, [
    rotTrack('UpperArm_R', waveT, [[0, 0, -0.12], [0, 0, -2.2], [0, 0, -2.3], [0, 0, -2.2],
      [0, 0, -2.3], [0, 0, -2.2], [0, 0, -0.12]]),
    rotTrack('LowerArm_R', waveT, [[0, 0, 0], [0, 0, -0.6], [0, 0, -1.0], [0, 0, -0.35],
      [0, 0, -1.0], [0, 0, -0.35], [0, 0, 0]]),
    rotTrack('Head', waveT, [[0, 0, 0], [0, -0.15, 0.05], [0, -0.15, 0.05], [0, -0.15, 0.05],
      [0, -0.15, 0.05], [0, -0.15, 0.05], [0, 0, 0]]),
    rotTrack('UpperArm_L', [0, 2], [[0, 0, 0.12], [0, 0, 0.12]]),
  ]);

  const walkT = [0, 0.25, 0.5, 0.75, 1.0];
  const legSwing = (a) => walkT.map((_, i) => [[a, 0, -a, 0, a][i], 0, 0]);
  const armSwing = (a, z) => walkT.map((_, i) => [[a, 0, -a, 0, a][i], 0, z]);
  const walk = new THREE.AnimationClip('Walk', 1, [
    rotTrack('UpperLeg_L', walkT, legSwing(-0.45)),
    rotTrack('UpperLeg_R', walkT, legSwing(0.45)),
    rotTrack('LowerLeg_L', walkT, [[0.1, 0, 0], [0.6, 0, 0], [0.15, 0, 0], [0.05, 0, 0], [0.1, 0, 0]]),
    rotTrack('LowerLeg_R', walkT, [[0.15, 0, 0], [0.05, 0, 0], [0.1, 0, 0], [0.6, 0, 0], [0.15, 0, 0]]),
    rotTrack('UpperArm_L', walkT, armSwing(0.4, 0.12)),
    rotTrack('UpperArm_R', walkT, armSwing(-0.4, -0.12)),
    rotTrack('LowerArm_L', walkT, [[-0.3, 0, 0], [-0.2, 0, 0], [-0.1, 0, 0], [-0.2, 0, 0], [-0.3, 0, 0]]),
    rotTrack('LowerArm_R', walkT, [[-0.1, 0, 0], [-0.2, 0, 0], [-0.3, 0, 0], [-0.2, 0, 0], [-0.1, 0, 0]]),
    new THREE.VectorKeyframeTrack('Hips.position', walkT,
      [0, 0.98, 0, 0, 1.0, 0, 0, 0.98, 0, 0, 1.0, 0, 0, 0.98, 0]),
    rotTrack('Spine', walkT, [[0.05, 0.08, 0], [0.05, 0, 0], [0.05, -0.08, 0], [0.05, 0, 0], [0.05, 0.08, 0]]),
  ]);

  return [idle, wave, walk];
}
