// Apple-style headline motion: each word rises out of a blur when its step arrives, and drifts up into
// a blur as the reader scrolls past (scrubbed by scroll, so scrolling back brings it back).
// Contract with the scene script: it drives style.opacity (arrival) and data-exit, 0 to 1 (how far the
// reader is past the step), on each .step. This file only watches them.
(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches || location.search.includes('reduce');   // ?reduce for testing
  const css = document.createElement('style');
  css.textContent = '.kw{display:inline-block;white-space:nowrap;will-change:transform,opacity,filter}';
  document.head.append(css);

  function split(h) {
    // Screen readers get the whole headline once; the word spans are hidden from them.
    h.setAttribute('aria-label', [...h.childNodes].map(n => n.nodeType === 3 ? n.textContent : ' ').join('').replace(/\s+/g, ' ').trim());
    const words = [];
    [...h.childNodes].forEach(n => {
      if (n.nodeType !== 3) return;                                       // keep <br>
      const frag = document.createDocumentFragment();
      n.textContent.split(/(\s+)/).forEach(part => {
        if (!part) return;
        if (/^\s+$/.test(part)) { frag.append(part); return; }
        const w = document.createElement('span'); w.className = 'kw'; w.setAttribute('aria-hidden', 'true'); w.textContent = part;
        frag.append(w); words.push(w);
      });
      n.replaceWith(frag);
    });
    return words;
  }

  const FROM = { y: 28, opacity: 0, filter: 'blur(14px)' };
  const REST = { y: 0, opacity: 1, filter: 'blur(0px)' };
  const GONE = { y: -22, opacity: 0, filter: 'blur(12px)' };

  const items = [...document.querySelectorAll('.step')].map(step => {
    const it = {
      step, words: split(step.querySelector('h1,h2')), eb: step.querySelector('.eyebrow'),
      rest: [step.querySelector('.lede'), step.querySelector('.actions')].filter(Boolean), on: false, tl: null, exit: 0,
    };
    // Leaving, built once and scrubbed: progress 0 is the resting step, 1 is gone.
    const out = gsap.timeline({ paused: true });
    if (reduce) out.fromTo([it.eb, ...it.words, ...it.rest].filter(Boolean), { opacity: 1 }, { opacity: 0, duration: .5, ease: 'none', immediateRender: false }, 0);
    else {
      if (it.rest.length) out.fromTo(it.rest, REST, { y: -12, opacity: 0, filter: 'blur(8px)', duration: .35, ease: 'power2.in', immediateRender: false }, 0);
      if (it.eb) out.fromTo(it.eb, { opacity: 1 }, { opacity: 0, duration: .3, ease: 'none', immediateRender: false }, .05);
      out.fromTo(it.words, REST, { ...GONE, duration: .5, ease: 'power2.in', stagger: .045, immediateRender: false }, .1);
    }
    it.out = out;
    return it;
  });

  function play(it) {
    it.tl?.kill();
    if (reduce) { gsap.set([it.eb, ...it.words, ...it.rest].filter(Boolean), REST); it.tl = null; return; }
    const tl = gsap.timeline();
    if (it.eb) tl.fromTo(it.eb, { y: 10, opacity: 0 }, { y: 0, opacity: 1, duration: .7, ease: 'power3.out' }, 0);
    tl.fromTo(it.words, FROM, { ...REST, duration: 1.1, ease: 'power3.out', stagger: .07 }, .08);
    if (it.rest.length) tl.fromTo(it.rest, { y: 16, opacity: 0, filter: 'blur(8px)' }, { ...REST, duration: .9, ease: 'power3.out', stagger: .12 }, .35);
    it.tl = tl;
  }
  function reset(it) {
    it.tl?.kill(); it.tl = null;
    it.out.progress(0); it.exit = 0;
    gsap.set(it.words, FROM);
    gsap.set([it.eb, ...it.rest].filter(Boolean), { opacity: 0 });
  }
  items.forEach(reset);

  function check() {
    items.forEach(it => {
      const o = parseFloat(it.step.style.opacity || '0');
      const x = parseFloat(it.step.dataset.exit || '0');
      if (!it.on && o > .3) { it.on = true; if (x < .02) play(it); }   // landing mid-exit: the scrub below draws it
      else if (it.on && o < .02) { it.on = false; reset(it); return; }
      if (!it.on || x === it.exit) return;
      if (x > 0 && it.tl && it.tl.progress() < 1) { it.tl.progress(1); it.tl = null; }   // arrival must finish before leaving starts
      it.out.progress(x); it.exit = x;
    });
  }
  gsap.ticker.add(check);
  // For automated checks in a hidden tab, where requestAnimationFrame barely runs.
  window.__typeDone = () => { check(); items.forEach(it => it.tl?.progress(1)); check(); };
})();
