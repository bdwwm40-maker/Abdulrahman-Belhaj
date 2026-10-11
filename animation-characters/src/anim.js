// Poses and looping animations for the character SVGs built by generate.py.
// window.setPose(name, t) poses the character at time t (seconds, 0..DURATION).
(function () {
  const DURATION = 4; // every clip is a seamless 4-second loop
  const TAU = Math.PI * 2;
  const sin = (t, period, phase = 0) => Math.sin((TAU * t) / period + phase);
  const breath = (t) => (1 - Math.cos((TAU * t) / 2)) / 2;

  function blink(t, times) {
    let s = 1;
    for (const b of times) {
      const d = Math.abs(t - b);
      if (d < 0.09) s = Math.min(s, 0.08 + 0.92 * (d / 0.09));
    }
    return s;
  }

  // 40 mouth shapes = one every 0.1 s over the 4 s loop
  const TALK = ['mid', 'big', 'o', 'big', 'smile', 'mid', 'big', 'mid', 'o', 'smile',
    'big', 'mid', 'big', 'o', 'mid', 'smile', 'smile', 'mid', 'big', 'o',
    'big', 'mid', 'smile', 'mid', 'big', 'big', 'o', 'mid', 'smile', 'mid',
    'big', 'o', 'mid', 'big', 'mid', 'smile', 'smile', 'smile', 'mid', 'smile'];
  const talkMouth = (t) => TALK[Math.floor(t * 10) % TALK.length];

  const rest = (side, t) => {
    const s = side === 'L' ? 1 : -1;
    return { u: s * (12 + 1.5 * breath(t)), f: -s * 6, h: 0, front: false, hand: 'open', thumb: s };
  };

  const POSES = {
    idle(t) {
      return {
        upperY: -4 * breath(t), headRot: 1.5 * sin(t, 4), eyesX: 0, browsY: 0,
        blink: blink(t, [1.2, 3.4]), mouth: 'smile', L: rest('L', t), R: rest('R', t),
      };
    },
    wave(t) {
      const w = sin(t, 4 / 6);
      return {
        upperY: -3 * breath(t), headRot: 3 + 1.2 * sin(t, 2), eyesX: 2, browsY: -3,
        blink: blink(t, [2.1]), mouth: 'grin', L: rest('L', t),
        R: { u: -128 + 3 * sin(t, 4 / 6, 0.8), f: -48 + 24 * w, h: -6 * w, front: false, hand: 'open', thumb: 1 },
      };
    },
    talk(t) {
      return {
        upperY: -3 * breath(t), headRot: 2.5 * sin(t, 2, 1), eyesX: 0,
        browsY: -2 - 2 * Math.max(0, sin(t, 1)),
        blink: blink(t, [1.6, 3.5]), mouth: talkMouth(t),
        L: { u: 32 + 4 * sin(t, 2), f: 118 + 10 * sin(t, 1, 0.5), h: 12, front: false, hand: 'open', thumb: 1 },
        R: rest('R', t),
      };
    },
    'point-right'(t) {
      const speaking = (t % 2) < 1.6;
      return {
        upperY: -3 * breath(t), headRot: 4 + sin(t, 2), eyesX: 7, browsY: -2,
        blink: blink(t, [2.6]), mouth: speaking ? talkMouth(t) : 'smile', L: rest('L', t),
        R: { u: -100 + 2 * sin(t, 1), f: -14 + 5 * sin(t, 1, 0.4), h: 0, front: false, hand: 'point', thumb: 1 },
      };
    },
    'point-left'(t) {
      const speaking = (t % 2) < 1.6;
      return {
        upperY: -3 * breath(t), headRot: -4 - sin(t, 2), eyesX: -7, browsY: -2,
        blink: blink(t, [2.6]), mouth: speaking ? talkMouth(t) : 'smile', R: rest('R', t),
        L: { u: 100 - 2 * sin(t, 1), f: 14 - 5 * sin(t, 1, 0.4), h: 0, front: false, hand: 'point', thumb: -1 },
      };
    },
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  function apply(p) {
    $('#upper').setAttribute('transform', `translate(0,${p.upperY.toFixed(2)})`);
    $('#head').setAttribute('transform', `rotate(${p.headRot.toFixed(2)} 300 400)`);
    $('#eyes').setAttribute('transform', `translate(${p.eyesX},0)`);
    $$('.eye').forEach((e) => {
      const cx = +e.dataset.cx;
      const cy = +e.dataset.cy;
      e.setAttribute('transform', `translate(${cx},${cy}) scale(1,${p.blink.toFixed(3)}) translate(${-cx},${-cy})`);
    });
    $('#brows').setAttribute('transform', `translate(0,${p.browsY.toFixed(2)})`);
    $$('.mouth').forEach((m) => { m.style.display = m.dataset.shape === p.mouth ? 'inline' : 'none'; });
    for (const side of ['L', 'R']) {
      const a = p[side];
      const arm = $(`#arm${side}`);
      const upper = arm.dataset.upper;
      const hand = arm.dataset.hand;
      $$(`.u${side}`).forEach((e) => e.setAttribute('transform', `rotate(${a.u.toFixed(2)})`));
      $$(`.f${side}`).forEach((e) => e.setAttribute('transform', `translate(0,${upper}) rotate(${a.f.toFixed(2)})`));
      $$(`.h${side}`).forEach((e) => e.setAttribute('transform', `translate(0,${hand}) rotate(${a.h.toFixed(2)})`));
      $$(`.th${side}`).forEach((e) => e.setAttribute('transform', `scale(${a.thumb},1)`));
      $$(`.fi${side}`).forEach((e) => { e.style.display = a.hand === 'point' ? 'inline' : 'none'; });
      $$(`.ol${side}`).forEach((e) => { e.style.display = a.hand === 'point' ? 'none' : 'inline'; });
      const slot = $(a.front ? '#slotFront' : '#slotBack');
      if (arm.parentNode !== slot) slot.appendChild(arm);
    }
  }

  window.DURATION = DURATION;
  window.POSES = Object.keys(POSES);
  window.setPose = (name, t) => apply(POSES[name](t % DURATION));
})();
