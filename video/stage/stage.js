// Deterministic motion-graphics stage: renderAt(t) sets every element from the time alone,
// so frames can be captured one by one at any fps.
(() => {
  const TL = window.TL;
  const $ = (s) => document.querySelector(s);
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const seg = (t, a, b) => clamp((t - a) / (b - a));
  const lerp = (a, b, k) => a + (b - a) * k;
  const easeOut = (k) => 1 - Math.pow(1 - k, 3);
  const easeInOut = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
  const easeBack = (k) => { const c1 = 1.5, c3 = c1 + 1; return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2); };
  const sc = Object.fromEntries(TL.scenes.map((s) => [s.id, s]));
  const caps = (id) => TL.captions.filter((c) => c.scene === id);

  // ---- icons (24x24 stroke icons) ----
  const ICON = {
    mic: '<rect x="9" y="2.5" width="6" height="11" rx="3"/><path d="M5.5 10.5a6.5 6.5 0 0 0 13 0"/><path d="M12 17v4.5M8.5 21.5h7"/>',
    camera: '<path d="M4 7.5h3l1.8-3h6.4l1.8 3h3a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2z"/><circle cx="12" cy="13.5" r="3.8"/>',
    chat: '<path d="M3 4.5h10a2 2 0 0 1 2 2V11a2 2 0 0 1-2 2H8l-3.5 3v-3H3a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2z"/><path d="M17.5 8.5H21a2 2 0 0 1 2 2V15a2 2 0 0 1-2 2h-1v3l-3.5-3H12a2 2 0 0 1-2-2v-.5"/>',
    podium: '<path d="M6 11h12l-1.6 10H7.6L6 11z"/><path d="M4.5 11h15"/><circle cx="12" cy="4.3" r="2"/><path d="M12 6.5V11"/><path d="M17 3.5c.9.9.9 2.6 0 3.5M19.4 1.8c1.9 1.9 1.9 5 0 6.9"/>',
    megaphone: '<path d="M3 10v4h3.5L15 19V5l-8.5 5H3z"/><path d="M6.5 14l1.4 5.5h2.6l-1.2-5"/><path d="M18 9.2a3.2 3.2 0 0 1 0 5.6M20.3 6.7a6.5 6.5 0 0 1 0 10.6"/>',
    meeting: '<circle cx="12" cy="5" r="2.3"/><circle cx="5" cy="9" r="2.1"/><circle cx="19" cy="9" r="2.1"/><path d="M2.5 15h19"/><path d="M5 15v5M19 15v5"/><path d="M9 12.3a3 3 0 0 1 6 0"/>',
    computer: '<rect x="2.5" y="3.5" width="19" height="12.5" rx="2"/><path d="M8.5 20.5h7M12 16v4.5"/><path d="M6 12.5h4"/>',
    ai: '<rect x="6" y="6" width="12" height="12" rx="2.5"/><path d="M9 2.5v3.5M15 2.5v3.5M9 18v3.5M15 18v3.5M2.5 9H6M2.5 15H6M18 9h3.5M18 15h3.5"/><path d="M9.3 15l1.4-6h.6l1.4 6M9.8 13h2.4M14.8 9v6"/>',
  };
  const svg = (k) => `<svg viewBox="0 0 24 24">${ICON[k]}</svg>`;
  const ACC = [
    { c: '#0375BA', soft: 'rgba(3,117,186,.07)', cls: 'c-blue' },
    { c: '#69A21E', soft: 'rgba(128,187,46,.10)', cls: 'c-green' },
    { c: '#E47617', soft: 'rgba(228,118,23,.08)', cls: 'c-orange' },
  ];
  const COURSES = [
    { id: 'c1', icon: 'mic' }, { id: 'c2', icon: 'camera' }, { id: 'c3', icon: 'chat', en: 'The Conversation' },
    { id: 'c4', icon: 'podium' }, { id: 'c5', icon: 'megaphone' }, { id: 'c6', icon: 'meeting' },
    { id: 'c7', icon: 'computer', chips: [['W', 'Word', '#2B579A', /ورد/], ['X', 'Excel', '#217346', /كسل/], ['P', 'PowerPoint', '#C43E1C', /باو/]] },
    { id: 'c8', icon: 'ai', en: 'AI' },
  ];

  // ---- build course cards, progress bar and mini grid ----
  const host = $('#courses');
  COURSES.forEach((c, i) => {
    const s = sc[c.id], a = ACC[i % 3];
    const sub = c.en ? `<span class="en">${c.en}</span>` + (s.subtitle && s.subtitle !== c.en ? ` — ${s.subtitle.replace(/^AI\s*—\s*/, '')}` : '') : s.subtitle;
    const el = document.createElement('div');
    el.className = 'course';
    el.id = 'card-' + c.id;
    el.style.setProperty('--accent', a.c);
    el.style.setProperty('--accent-soft', a.soft);
    el.innerHTML = `<div class="course-top"><div><div class="course-lbl">الدورة</div><div class="course-num">0${i + 1}</div></div>
      <div class="course-ico ${a.cls}">${svg(c.icon)}</div></div><h2>${s.title}</h2>` + (c.chips
      ? `<div class="chips">${c.chips.map(([k, name, col]) => `<span class="chip" style="--chip:${col}"><b>${k}</b>${name}</span>`).join('')}</div>`
      : `<p>${sub}</p>`);
    host.appendChild(el);
  });
  $('#progress').innerHTML = COURSES.map(() => '<i><b></b></i>').join('');
  $('#minigrid').innerHTML = COURSES.map((c, i) => `<div class="mini ${ACC[i % 3].cls}">${svg(c.icon)}</div>`).join('');

  // program chips pop in on the word that names them (fallback: spread over the second half of the line)
  const bare = (w) => w.replace(/[\u064B-\u0652]/g, '');
  COURSES.filter((c) => c.chips).forEach((c) => {
    const q = sc[c.id], ws = q.words || [];
    c.chipAt = c.chips.map(([, , , re], i) => {
      const w = ws.find((x) => re.test(bare(x.w)));
      return w ? w.t - 0.1 : lerp(q.start, q.end, 0.5 + 0.15 * i);
    });
  });

  // ---- character framing ----
  const BUST = { x: 150, y: 150, s: 0.92 };
  const FULL = { x: 250, y: 92, s: 0.42 };
  const OFF = { x: -820, y: 150, s: 0.92 };
  const CHAR_W = 756, FACE = { x: 382, y: 169 };
  const keys = [
    [0, OFF], [3.0, OFF], [3.95, BUST, easeBack],
    [sc.s2.start - 0.45, BUST], [sc.s2.start + 0.55, FULL, easeInOut],
    [sc.s5.start - 0.45, FULL], [sc.s5.start + 0.55, BUST, easeInOut],
    [sc.s6.start - 0.45, BUST], [sc.s6.start + 0.55, FULL, easeInOut],
  ];
  function charAt(t) {
    let st = keys[0][1];
    for (let i = 1; i < keys.length; i++) {
      const [t0, a] = keys[i - 1], [t1, b, ease] = keys[i];
      if (t < t0) break;
      const k = (ease || easeInOut)(seg(t, t0, t1));
      st = { x: lerp(a.x, b.x, k), y: lerp(a.y, b.y, k), s: lerp(a.s, b.s, k) };
    }
    return st;
  }
  const envAt = (t) => TL.env[clamp(Math.round(t * TL.fps), 0, TL.env.length - 1)] || 0;

  // ---- helpers for panel in/out ----
  function show(el, t, tin, tout, dir = 1) {
    const kin = easeOut(seg(t, tin, tin + 0.6));
    const kout = easeInOut(seg(t, tout - 0.35, tout + 0.15));
    const o = kin * (1 - kout);
    el.style.opacity = o.toFixed(3);
    el.style.visibility = o > 0.001 ? 'visible' : 'hidden';
    el.style.transform = `translateY(${((1 - kin) * 50 * dir - kout * 40).toFixed(1)}px)`;
    return { kin, kout, o };
  }
  function stagger(children, t, t0, step, dy = 30) {
    [...children].forEach((c, i) => {
      const k = easeBack(seg(t, t0 + i * step, t0 + i * step + 0.55));
      c.style.opacity = clamp(k * 1.4).toFixed(3);
      c.style.transform = `translateY(${((1 - k) * dy).toFixed(1)}px) scale(${(0.9 + 0.1 * k).toFixed(3)})`;
    });
  }

  const els = {
    intro: $('#intro'), ilogo: $('#intro-logo'), ititle: $('#intro-title'), ipill: $('#intro-pill'),
    rings: [...document.querySelectorAll('.rings i')], char: $('#char'), ground: $('#ground'), talk: $('#talk'),
    bars: [...document.querySelectorAll('#talk i')], bug: $('#bug'), caption: $('#caption'), capSpan: $('#caption span'),
    fade: $('#fade'), blobs: [...document.querySelectorAll('.blob')], sweep: $('#sweep'), arcs: [$('#arc1'), $('#arc2')],
    progress: $('#progress'), pbars: [...document.querySelectorAll('#progress i b')], face: $('#face'),
  };
  const RIG = window.FACE || null;
  if (RIG) Object.assign(els.face.style, { left: RIG.box[0] + 'px', top: RIG.box[1] + 'px', width: RIG.box[2] + 'px', height: RIG.box[3] + 'px' });
  els.arcs.forEach((p) => { const L = p.getTotalLength(); p.style.strokeDasharray = L; p.dataset.len = L; });

  window.renderAt = function (t) {
    const end = TL.duration;
    // background drift
    els.blobs.forEach((b, i) => {
      const a = t * (0.12 + i * 0.03) + i * 1.7;
      b.style.transform = `translate(${(Math.sin(a) * 60).toFixed(1)}px, ${(Math.cos(a * 0.8) * 40).toFixed(1)}px)`;
    });
    els.sweep.style.backgroundPosition = `${(100 - ((t * 9) % 300)).toFixed(1)}% 0`;
    els.arcs.forEach((p, i) => {
      const L = +p.dataset.len, k = easeOut(seg(t, 0.4 + i * 0.3, 2.6 + i * 0.3));
      p.style.strokeDashoffset = (L * (1 - k)).toFixed(1);
    });

    // intro
    const ik = easeBack(seg(t, 0.2, 1.1));
    const iout = easeInOut(seg(t, 2.8, 3.5));
    els.intro.style.opacity = (1 - iout).toFixed(3);
    els.intro.style.visibility = iout < 1 ? 'visible' : 'hidden';
    els.ilogo.style.transform = `scale(${(0.4 + 0.6 * ik).toFixed(3)}) translateY(${(-iout * 60).toFixed(1)}px)`;
    els.ilogo.style.opacity = clamp(ik * 1.5).toFixed(3);
    els.rings.forEach((r, i) => {
      const k = seg(t, 0.35 + i * 0.18, 1.6 + i * 0.18);
      r.style.opacity = (k > 0 && k < 1 ? (1 - k) * 0.8 : 0).toFixed(3);
      r.style.transform = `scale(${(0.6 + k * 1.4).toFixed(3)})`;
    });
    const tk = easeOut(seg(t, 1.2, 1.9)), pk = easeBack(seg(t, 1.7, 2.3));
    els.ititle.style.opacity = tk.toFixed(3);
    els.ititle.style.transform = `translateY(${((1 - tk) * 30).toFixed(1)}px)`;
    els.ipill.style.opacity = clamp(pk * 1.3).toFixed(3);
    els.ipill.style.transform = `scale(${(0.7 + 0.3 * pk).toFixed(3)})`;

    // corner logo bug (hidden on the end card, which shows the big logo)
    const bugO = easeOut(seg(t, 3.2, 3.8)) * (1 - easeInOut(seg(t, sc.s6.start - 0.5, sc.s6.start)));
    els.bug.style.opacity = bugO.toFixed(3);

    // character: framing + idle breathing + voice-driven bob
    const st = charAt(t), env = envAt(t);
    const breathe = Math.sin(t * 2 * Math.PI * 0.32);
    const tilt = Math.sin(t * 1.15) * 0.5 + env * 0.7 * Math.sin(t * 7.3);
    const s = st.s * (1 + 0.004 * breathe + 0.008 * env);
    const y = st.y + breathe * 3 - env * 7 * (st.s / 0.92);
    els.char.style.transform = `translate(${st.x.toFixed(1)}px, ${y.toFixed(1)}px) rotate(${tilt.toFixed(3)}deg) scale(${s.toFixed(4)})`;
    // ground shadow only when the feet are on screen
    const full = clamp((0.92 - st.s) / 0.5);
    const footX = st.x + CHAR_W * st.s / 2, footY = st.y + 2200 * st.s - 22;
    els.ground.style.opacity = (full * 0.95).toFixed(3);
    els.ground.style.transform = `translate(${(footX - 210).toFixed(1)}px, ${footY.toFixed(1)}px) scale(${(st.s / 0.42).toFixed(3)}, 1)`;

    // speaking bubble next to the head while the voice plays
    const speaking = TL.scenes.some((q) => t >= q.start - 0.05 && t <= q.end + 0.1) ? 1 : 0;
    const vis = clamp((st.x + 600) / 400) * speaking;
    const hx = st.x + (FACE.x + 230) * st.s, hy = y + (FACE.y - 60) * st.s;
    els.talk.style.opacity = (RIG ? 0 : vis * 0.98).toFixed(3);
    els.talk.style.transform = `translate(${hx.toFixed(1)}px, ${hy.toFixed(1)}px) scale(${(0.75 + 0.25 * (st.s / 0.92)).toFixed(3)})`;
    els.bars.forEach((b, i) => {
      const h = 10 + 40 * clamp(env * (0.65 + 0.35 * Math.abs(Math.sin(t * (9 + i * 2.3) + i))));
      b.style.height = h.toFixed(1) + 'px';
    });

    // scene panels
    const nextStart = (id) => {
      const i = TL.scenes.findIndex((q) => q.id === id);
      return i + 1 < TL.scenes.length ? TL.scenes[i + 1].start : end;
    };
    for (const id of ['s1', 's2', 's3', 's4', 's5', 's6']) {
      const el = document.getElementById(id);
      const tin = id === 's1' ? 3.6 : sc[id].start - 0.35;
      const tout = id === 's6' ? end + 1 : nextStart(id) - 0.3;
      show(el, t, tin, tout);
    }
    // s2: the "2" leap badge pops
    const lk = easeBack(seg(t, sc.s2.start + 1.6, sc.s2.start + 2.3));
    const leap = document.querySelector('.leap');
    leap.style.opacity = clamp(lk * 1.4).toFixed(3);
    leap.style.transform = `scale(${(0.6 + 0.4 * lk).toFixed(3)})`;
    // s3: feature cards appear on the words that name them
    const c3 = caps('s3');
    [...document.querySelectorAll('#s3 .feat')].forEach((f, i) => {
      const at = (c3[i + 2] || c3[c3.length - 1]).t - 0.15;
      const k = easeBack(seg(t, at, at + 0.55));
      f.style.opacity = clamp(k * 1.4).toFixed(3);
      f.style.transform = `translateY(${((1 - k) * 40).toFixed(1)}px) scale(${(0.85 + 0.15 * k).toFixed(3)})`;
    });
    // s4: count to 8 + mini grid
    const ck = easeOut(seg(t, sc.s4.start + 0.3, sc.s4.start + 1.8));
    $('#count-num').textContent = Math.round(8 * ck);
    stagger(document.querySelectorAll('#minigrid .mini'), t, sc.s4.start + 0.6, 0.18);
    // s5: CTA pulse
    const pulse = 1 + 0.035 * Math.max(0, Math.sin((t - sc.s5.start) * 5));
    const cta = document.querySelector('.cta');
    const ck5 = easeBack(seg(t, sc.s5.start + 1.0, sc.s5.start + 1.6));
    cta.style.opacity = clamp(ck5 * 1.4).toFixed(3);
    cta.style.transform = `scale(${((0.7 + 0.3 * ck5) * pulse).toFixed(3)})`;
    const fut = document.querySelector('.future');
    const fk = easeOut(seg(t, caps('s5').slice(-1)[0].t - 0.2, caps('s5').slice(-1)[0].t + 0.4));
    fut.style.opacity = fk.toFixed(3);
    fut.style.transform = `translateY(${((1 - fk) * 30).toFixed(1)}px)`;
    // s6: logo pop
    const ek = easeBack(seg(t, sc.s6.start - 0.1, sc.s6.start + 0.6));
    $('#end-logo').style.transform = `scale(${(0.5 + 0.5 * ek).toFixed(3)})`;

    // course cards + progress
    let anyCourse = 0;
    COURSES.forEach((c, i) => {
      const el = document.getElementById('card-' + c.id);
      const tin = sc[c.id].start - 0.3;
      const tout = i + 1 < COURSES.length ? sc[COURSES[i + 1].id].start - 0.3 : sc.s5.start - 0.3;
      const kin = easeOut(seg(t, tin, tin + 0.55));
      const kout = easeInOut(seg(t, tout - 0.25, tout + 0.2));
      const o = kin * (1 - kout);
      el.style.opacity = o.toFixed(3);
      el.style.visibility = o > 0.001 ? 'visible' : 'hidden';
      el.style.transform = `translateX(${((1 - kin) * -140 + kout * 160).toFixed(1)}px) rotate(${((1 - kin) * -2).toFixed(2)}deg)`;
      const ico = el.querySelector('.course-ico');
      const ik2 = easeBack(seg(t, tin + 0.2, tin + 0.75));
      ico.style.transform = `scale(${(0.5 + 0.5 * ik2).toFixed(3)}) rotate(${((1 - ik2) * -20).toFixed(1)}deg)`;
      if (c.chipAt) [...el.querySelectorAll('.chip')].forEach((ch, j) => {
        const k = easeBack(seg(t, c.chipAt[j], c.chipAt[j] + 0.45));
        ch.style.opacity = clamp(k * 1.5).toFixed(3);
        ch.style.transform = `translateY(${((1 - k) * 26).toFixed(1)}px) scale(${(0.6 + 0.4 * k).toFixed(3)})`;
      });
      anyCourse = Math.max(anyCourse, o);
      const fill = seg(t, sc[c.id].start, sc[c.id].end);
      els.pbars[i].style.transform = `scaleX(${fill.toFixed(3)})`;
    });
    const pIn = easeOut(seg(t, sc.c1.start - 0.3, sc.c1.start + 0.3)) * (1 - easeInOut(seg(t, sc.s5.start - 0.5, sc.s5.start)));
    els.progress.style.opacity = pIn.toFixed(3);

    // captions
    const cap = TL.captions.find((c) => t >= c.t - 0.05 && t < c.end);
    if (cap) {
      if (els.capSpan.textContent !== cap.text) els.capSpan.textContent = cap.text;
      const k = easeOut(seg(t, cap.t - 0.05, cap.t + 0.2));
      els.caption.style.opacity = k.toFixed(3);
      els.caption.style.transform = `translateX(-50%) translateY(${((1 - k) * 12).toFixed(1)}px)`;
    } else {
      els.caption.style.opacity = '0';
    }

    // animated face (lip sync, blinks, brows): per-frame patch over the still character
    let pending = null;
    if (RIG) {
      const f = clamp(Math.round(t * TL.fps), 0, RIG.frames.length - 1), id = RIG.frames[f];
      const on = id >= 0 && st.x > -700;
      els.face.style.display = on ? 'block' : 'none';
      if (on) {
        const src = `../build/face/${id}.png`;
        if (els.face.dataset.src !== src) { els.face.dataset.src = src; els.face.src = src; pending = els.face.decode().catch(() => {}); }
      }
    }

    // final fade to white
    els.fade.style.opacity = easeInOut(seg(t, end - 0.8, end)).toFixed(3);
    return pending;
  };

  window.stageReady = Promise.all([
    document.fonts.ready,
    ...[...document.images].map((im) => (im.complete ? Promise.resolve() : new Promise((r) => { im.onload = im.onerror = r; }))),
  ]).then(() => { window.renderAt(0); return true; });
})();
