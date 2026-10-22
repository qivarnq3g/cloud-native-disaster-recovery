// Liquid glass for the control layer only (nav, buttons, status chips, chapter bar), after Apple's
// Liquid Glass: content stays clear, controls float above it as glass.
// Everywhere: frosted blur, a top sheen and a rim light that turns toward the pointer (CSS in the page).
// Chromium only: the backdrop is also bent near the rim through an SVG displacement map in
// backdrop-filter, the lensing that makes it read as glass rather than tinted film. Glass
// materialises by ramping that bend with the element's own opacity instead of only fading.
(() => {
  const brands = navigator.userAgentData?.brands?.map(b => b.brand).join(' ') || '';
  const refract = /Chromium|Google Chrome|Microsoft Edge/.test(brands);
  const NS = 'http://www.w3.org/2000/svg';
  const defs = document.createElementNS(NS, 'svg');
  defs.setAttribute('width', '0'); defs.setAttribute('height', '0'); defs.setAttribute('aria-hidden', 'true');
  defs.style.position = 'absolute';
  document.body.prepend(defs);

  // Displacement map for a rounded rectangle: neutral inside, pulling from further in near the rim.
  function lensMap(w, h, r, band) {
    const k = .5, W = Math.max(2, Math.round(w * k)), H = Math.max(2, Math.round(h * k));
    const c = document.createElement('canvas'); c.width = W; c.height = H;
    const g = c.getContext('2d'), img = g.createImageData(W, H), d = img.data;
    const hx = w / 2, hy = h / 2, rr = Math.min(r, hx, hy);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const px = (x + .5) / k - hx, py = (y + .5) / k - hy;
      const qx = Math.abs(px) - (hx - rr), qy = Math.abs(py) - (hy - rr);
      let nx, ny, dist;
      if (qx > 0 && qy > 0) { const l = Math.hypot(qx, qy) || 1; dist = rr - l; nx = qx / l; ny = qy / l; }
      else if (qx > qy) { dist = rr - qx; nx = 1; ny = 0; }
      else { dist = rr - qy; nx = 0; ny = 1; }
      nx *= Math.sign(px) || 1; ny *= Math.sign(py) || 1;                // outward normal
      const t = Math.max(0, 1 - Math.max(0, dist) / band), m = t * t * (3 - 2 * t);
      const i = (y * W + x) * 4;
      d[i] = 128 - nx * m * 127; d[i + 1] = 128 - ny * m * 127; d[i + 2] = 128; d[i + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    return c.toDataURL();
  }

  let n = 0;
  const items = [...document.querySelectorAll('.glass')].map(el => {
    const it = { el, bend: +(el.dataset.bend || 28), last: '' };
    if (refract) {
      const id = 'lg' + n++;
      const f = document.createElementNS(NS, 'filter');
      for (const [k, v] of Object.entries({ id, x: '0', y: '0', width: '100%', height: '100%', 'color-interpolation-filters': 'sRGB' })) f.setAttribute(k, v);
      const im = document.createElementNS(NS, 'feImage');
      for (const [k, v] of Object.entries({ x: '0', y: '0', preserveAspectRatio: 'none', result: 'map' })) im.setAttribute(k, v);
      const dm = document.createElementNS(NS, 'feDisplacementMap');
      for (const [k, v] of Object.entries({ in: 'SourceGraphic', in2: 'map', xChannelSelector: 'R', yChannelSelector: 'G', scale: '0' })) dm.setAttribute(k, v);
      f.append(im, dm); defs.append(f);
      Object.assign(it, { im, dm });
      el.style.backdropFilter = `url(#${id}) blur(${el.dataset.blur || 4}px) saturate(1.8)`;
    }
    return it;
  });

  function fit(it) {
    if (!it.im) return;
    const w = it.el.offsetWidth, h = it.el.offsetHeight;
    if (!w || !h || (w === it.w && h === it.h)) return;
    it.w = w; it.h = h;
    const r = parseFloat(getComputedStyle(it.el).borderTopLeftRadius) || h / 2;
    it.im.setAttribute('width', w); it.im.setAttribute('height', h);
    it.im.setAttribute('href', lensMap(w, h, Math.min(r, h / 2), Math.min(24, h * .42)));
  }
  const ro = new ResizeObserver(entries => entries.forEach(e => { const it = items.find(i => i.el === e.target); if (it) fit(it); }));
  items.forEach(it => { fit(it); ro.observe(it.el); });

  let px = -1, py = -1;
  addEventListener('pointermove', e => { px = e.clientX; py = e.clientY; }, { passive: true });
  function pass() {
    items.forEach(it => {
      const el = it.el, o = el.style.opacity === '' ? 1 : +el.style.opacity;
      if (it.dm) {
        const s = (it.bend * Math.min(1, o * 1.25)).toFixed(1);   // the bend arrives with the glass
        if (s !== it.last) { it.dm.setAttribute('scale', s); it.last = s; }
      }
      if (px >= 0 && o > .05) {
        const r = el.getBoundingClientRect();
        el.style.setProperty('--gx', Math.min(130, Math.max(-30, (px - r.left) / r.width * 100)).toFixed(1) + '%');
        el.style.setProperty('--gy', Math.min(170, Math.max(-70, (py - r.top) / r.height * 100)).toFixed(1) + '%');
      }
    });
  }
  function tick() { pass(); requestAnimationFrame(tick); }
  requestAnimationFrame(tick);
  window.__glass = { refract, count: items.length, pass };   // pass(): one update, for checks in a hidden tab
})();
