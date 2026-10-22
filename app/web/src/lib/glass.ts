const NS = 'http://www.w3.org/2000/svg';

interface GlassPane {
  el: HTMLElement;
  bend: number;
  w: number;
  h: number;
  last: string;
  im?: SVGFEImageElement;
  dm?: SVGFEDisplacementMapElement;
  filter?: SVGFilterElement;
}

const panes = new Set<GlassPane>();
let defs: SVGSVGElement | null = null;
let counter = 0;
let px = -1;
let py = -1;
let running = false;

export function refractionAt(x: number, y: number, hx: number, hy: number, rr: number, band: number): [number, number] {
  const qx = Math.abs(x) - (hx - rr);
  const qy = Math.abs(y) - (hy - rr);
  let nx: number;
  let ny: number;
  let dist: number;
  if (qx > 0 && qy > 0) {
    const l = Math.hypot(qx, qy) || 1;
    dist = rr - l;
    nx = qx / l;
    ny = qy / l;
  } else if (qx > qy) {
    dist = rr - qx;
    nx = 1;
    ny = 0;
  } else {
    dist = rr - qy;
    nx = 0;
    ny = 1;
  }
  nx *= Math.sign(x) || 1;
  ny *= Math.sign(y) || 1;
  const t = Math.max(0, 1 - Math.max(0, dist) / band);
  const m = t * t * (3 - 2 * t);
  return [Math.round(128 - nx * m * 127), Math.round(128 - ny * m * 127)];
}

function refractionMap(w: number, h: number, r: number, band: number): string {
  const k = 0.5;
  const W = Math.max(2, Math.round(w * k));
  const H = Math.max(2, Math.round(h * k));
  const c = document.createElement('canvas');
  c.width = W;
  c.height = H;
  const g = c.getContext('2d');
  if (!g) return '';
  const img = g.createImageData(W, H);
  const d = img.data;
  const hx = w / 2;
  const hy = h / 2;
  const rr = Math.min(r, hx, hy);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const [vr, vg] = refractionAt((x + 0.5) / k - hx, (y + 0.5) / k - hy, hx, hy, rr, band);
      const i = (y * W + x) * 4;
      d[i] = vr;
      d[i + 1] = vg;
      d[i + 2] = 128;
      d[i + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  return c.toDataURL();
}

function supportsRefraction(): boolean {
  const ud = (navigator as Navigator & { userAgentData?: { brands?: { brand: string }[] } }).userAgentData;
  const brands = ud?.brands?.map((b) => b.brand).join(' ') ?? '';
  return /Chromium|Google Chrome|Microsoft Edge/.test(brands);
}

function setAttrs(el: Element, attrs: Record<string, string>) {
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
}

function resize(p: GlassPane) {
  if (!p.im) return;
  const w = p.el.offsetWidth;
  const h = p.el.offsetHeight;
  if (!w || !h || (w === p.w && h === p.h)) return;
  p.w = w;
  p.h = h;
  const r = parseFloat(getComputedStyle(p.el).borderTopLeftRadius) || h / 2;
  setAttrs(p.im, { width: String(w), height: String(h), href: refractionMap(w, h, Math.min(r, h / 2), Math.min(24, h * 0.42)) });
}

function tick() {
  for (const p of panes) {
    const opacity = p.el.style.opacity === '' ? 1 : Number(p.el.style.opacity);
    if (p.dm) {
      const s = (p.bend * Math.min(1, opacity * 1.25)).toFixed(1);
      if (s !== p.last) {
        p.dm.setAttribute('scale', s);
        p.last = s;
      }
    }
    if (px >= 0 && opacity > 0.05) {
      const r = p.el.getBoundingClientRect();
      p.el.style.setProperty('--gx', `${Math.min(130, Math.max(-30, ((px - r.left) / r.width) * 100)).toFixed(1)}%`);
      p.el.style.setProperty('--gy', `${Math.min(170, Math.max(-70, ((py - r.top) / r.height) * 100)).toFixed(1)}%`);
    }
  }
  if (panes.size) requestAnimationFrame(tick);
  else running = false;
}

export function glass(el: HTMLElement, options: { bend?: number; blur?: number } = {}) {
  const p: GlassPane = { el, bend: options.bend ?? 28, w: 0, h: 0, last: '' };
  if (supportsRefraction()) {
    if (!defs) {
      defs = document.createElementNS(NS, 'svg');
      setAttrs(defs, { width: '0', height: '0', 'aria-hidden': 'true' });
      defs.style.position = 'absolute';
      document.body.prepend(defs);
      addEventListener('pointermove', (e) => {
        px = e.clientX;
        py = e.clientY;
      }, { passive: true });
    }
    const id = `glass${counter++}`;
    const filter = document.createElementNS(NS, 'filter');
    setAttrs(filter, { id, x: '0', y: '0', width: '100%', height: '100%', 'color-interpolation-filters': 'sRGB' });
    const im = document.createElementNS(NS, 'feImage');
    setAttrs(im, { x: '0', y: '0', preserveAspectRatio: 'none', result: 'map' });
    const dm = document.createElementNS(NS, 'feDisplacementMap');
    setAttrs(dm, { in: 'SourceGraphic', in2: 'map', xChannelSelector: 'R', yChannelSelector: 'G', scale: '0' });
    filter.append(im, dm);
    defs.append(filter);
    Object.assign(p, { im, dm, filter });
    el.style.backdropFilter = `url(#${id}) blur(${options.blur ?? 4}px) saturate(1.8)`;
  }
  panes.add(p);
  const ro = new ResizeObserver(() => resize(p));
  ro.observe(el);
  resize(p);
  if (!running) {
    running = true;
    requestAnimationFrame(tick);
  }
  return {
    destroy() {
      ro.disconnect();
      panes.delete(p);
      p.filter?.remove();
    },
  };
}
