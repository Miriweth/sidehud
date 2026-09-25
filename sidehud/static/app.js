(() => {
  const STRINGS = {
    en: {
      connecting: 'connecting', live: 'live', offline: 'no connection',
      gpuLoad: 'GPU load', fps: 'FPS', noGpu: 'no GPU found', last2: 'last 2 minutes',
      fpsHint: 'FPS show up here once MangoHud logs', frametime: 'frametime',
      gpu: 'GPU', cpu: 'CPU', temp: 'Temperature', power: 'Power', clock: 'Clock', fan: 'Fan', load: 'Load',
      of: 'of', memClock: 'memory', memory: 'Memory', used: 'used', tight: 'running out',
      network: 'Network', down: 'Down', up: 'Up', downloadLast: 'download · last 2 minutes',
      procs: 'Top processes', procsSub: 'CPU like in top, 100 % = one thread', quiet: 'all quiet',
      warm: 'warm', hot: 'hot', full: 'full', ago: '{n} s ago', now: 'now',
      map: 'Map', mapFollow: 'follow ×{z}', mapFull: 'whole map',
      hint: 'In Safari: Share, then "Add to Home Screen" for fullscreen. Set Auto-Lock to Never while it runs.',
    },
    de: {
      connecting: 'verbinde', live: 'live', offline: 'keine Verbindung',
      gpuLoad: 'GPU-Auslastung', fps: 'FPS', noGpu: 'keine GPU gefunden', last2: 'letzte 2 Minuten',
      fpsHint: 'FPS erscheinen hier, sobald MangoHud loggt', frametime: 'Frametime',
      gpu: 'GPU', cpu: 'CPU', temp: 'Temperatur', power: 'Leistung', clock: 'Takt', fan: 'Lüfter', load: 'Auslastung',
      of: 'von', memClock: 'Speicher', memory: 'Arbeitsspeicher', used: 'belegt', tight: 'wird knapp',
      network: 'Netzwerk', down: 'Down', up: 'Up', downloadLast: 'Download · letzte 2 Minuten',
      procs: 'Top-Prozesse', procsSub: 'CPU wie in top, 100 % = ein Thread', quiet: 'alles ruhig',
      warm: 'warm', hot: 'heiß', full: 'voll', ago: 'vor {n} s', now: 'jetzt',
      map: 'Karte', mapFollow: 'folgen ×{z}', mapFull: 'ganze Karte',
      hint: 'In Safari: Teilen, dann „Zum Home-Bildschirm“ für Vollbild. Automatische Sperre auf „Nie“ stellen, solange es läuft.',
    },
  };
  const LANG = (new URLSearchParams(location.search).get('lang') || navigator.language || 'en').slice(0, 2) === 'de' ? 'de' : 'en';
  const t = (key, vars) => {
    let s = STRINGS[LANG][key] ?? STRINGS.en[key] ?? key;
    for (const [k, v] of Object.entries(vars || {})) s = s.replace('{' + k + '}', v);
    return s;
  };
  document.documentElement.lang = LANG;
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });

  const $ = id => document.getElementById(id);
  const locale = LANG === 'de' ? 'de-DE' : 'en-US';
  const nf0 = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const f0 = v => v == null ? '–' : nf0.format(v);
  const f1 = v => v == null ? '–' : nf1.format(v);
  const gb = b => b == null ? null : b / 1073741824;
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const COLORS = { gpu: css('--gpu'), cpu: css('--cpu'), mem: css('--mem'), net: css('--net'), ink: css('--ink'), muted: css('--muted'), grid: css('--grid') };
  const SURFACE = css('--surface');

  // ---- sparklines -------------------------------------------------------
  const sparks = {}, scrubbing = {}, captions = {};
  let lastSnap = null;

  function setCaption(id, text) {
    captions[id] = text;
    if (!scrubbing[id]) $(id).textContent = text;
  }

  function spark(id, data, color, opts = {}) {
    if (scrubbing[id]) return;
    const svg = $(id);
    const w = svg.clientWidth, h = svg.clientHeight;
    if (!w || !h) return;
    const pad = 6, N = data.length;
    const vals = data.filter(v => v != null);
    if (!vals.length) { svg.innerHTML = ''; delete sparks[id]; return; }
    const yMax = opts.max ?? Math.max(Math.max(...vals) * 1.15, opts.floor ?? 1);
    const x = i => pad + (w - 2 * pad) * i / (N - 1);
    const y = v => h - pad - (h - 2 * pad) * Math.min(v, yMax) / yMax;
    const pts = [];
    data.forEach((v, i) => { if (v != null) pts.push({ x: x(i), y: y(v), v, age: N - 1 - i }); });
    const line = pts.map((p, i) => (i ? 'L' : 'M') + p.x.toFixed(1) + ' ' + p.y.toFixed(1)).join(' ');
    const first = pts[0], last = pts[pts.length - 1];
    const base = (h - pad).toFixed(1);
    const area = `${line} L${last.x.toFixed(1)} ${base} L${first.x.toFixed(1)} ${base} Z`;
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svg.innerHTML =
      `<line x1="${pad}" x2="${w - pad}" y1="${base}" y2="${base}" stroke="${COLORS.grid}" stroke-width="1"/>` +
      `<path d="${area}" fill="${color}" fill-opacity=".12"/>` +
      `<path d="${line}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>` +
      `<circle cx="${last.x.toFixed(1)}" cy="${last.y.toFixed(1)}" r="4" fill="${color}" stroke="${SURFACE}" stroke-width="2"/>` +
      `<g class="scrub" style="display:none"><line y1="${pad}" y2="${base}" stroke="${COLORS.muted}" stroke-width="1"/>` +
      `<circle r="4" fill="${color}" stroke="${SURFACE}" stroke-width="2"/></g>`;
    sparks[id] = { pts, unit: opts.unit || '', fmt: opts.fmt || f0, caption: opts.caption };
  }

  function enableScrub(id) {
    const svg = $(id);
    const show = e => {
      const s = sparks[id];
      if (!s) return;
      const px = e.clientX - svg.getBoundingClientRect().left;
      let best = s.pts[0];
      for (const p of s.pts) if (Math.abs(p.x - px) < Math.abs(best.x - px)) best = p;
      const g = svg.querySelector('.scrub');
      if (!g) return;
      g.style.display = '';
      const l = g.querySelector('line'), c = g.querySelector('circle');
      l.setAttribute('x1', best.x); l.setAttribute('x2', best.x);
      c.setAttribute('cx', best.x); c.setAttribute('cy', best.y);
      scrubbing[id] = true;
      if (s.caption) $(s.caption).textContent = (best.age ? t('ago', { n: best.age }) : t('now')) + ' · ' + s.fmt(best.v) + ' ' + s.unit;
    };
    const hide = () => {
      scrubbing[id] = false;
      const g = svg.querySelector('.scrub');
      if (g) g.style.display = 'none';
      const s = sparks[id];
      if (s && s.caption) $(s.caption).textContent = captions[s.caption] || '';
    };
    svg.addEventListener('pointerdown', e => { svg.setPointerCapture(e.pointerId); show(e); });
    svg.addEventListener('pointermove', e => { if (e.buttons || e.pointerType === 'mouse') show(e); });
    for (const ev of ['pointerup', 'pointercancel', 'pointerleave']) svg.addEventListener(ev, hide);
  }

  // ---- stats ------------------------------------------------------------
  const statusOf = (v, [warn, crit]) => v == null ? '' : v >= crit ? 'crit' : v >= warn ? 'warn' : '';

  function meter(id, pct, st) {
    const m = $(id);
    m.className = 'meter ' + (st || '');
    m.querySelector('.fill').style.width = Math.max(0, Math.min(100, pct || 0)) + '%';
  }

  function setVal(id, text, st, label) {
    const el = $(id);
    el.textContent = text;
    if (st) {
      const b = document.createElement('span');
      b.className = 'badge ' + st;
      b.textContent = (st === 'crit' ? '⚠ ' : '▲ ') + label;
      el.appendChild(b);
    }
  }

  function render(s) {
    lastSnap = s;
    $('host').textContent = s.host || '';
    $('clock').textContent = new Date(s.time * 1000).toLocaleTimeString(locale);
    const g = s.gpu, c = s.cpu, m = s.mem, n = s.net, h = s.history, th = s.thresholds;
    const fpsLive = s.fps && s.fps.fps != null;

    if (fpsLive) {
      $('hero-label').textContent = t('fps');
      $('hero-sub').textContent = s.fps.game || '';
      $('hero-value').textContent = f0(s.fps.fps);
      $('hero-unit').textContent = 'fps';
      setCaption('hero-caption', (s.fps.frametime != null ? `${t('frametime')} ${f1(s.fps.frametime)} ms · ` : '') + t('last2'));
      spark('hero-spark', h.fps, COLORS.gpu, { floor: 60, unit: 'fps', caption: 'hero-caption' });
      $('gpu-load-block').classList.remove('hidden');
    } else {
      $('hero-label').textContent = t('gpuLoad');
      $('hero-sub').textContent = g ? g.name : t('noGpu');
      $('hero-value').textContent = g ? f0(g.load) : '–';
      $('hero-unit').textContent = '%';
      setCaption('hero-caption', t('last2') + ' · ' + t('fpsHint'));
      spark('hero-spark', h.gpu, COLORS.gpu, { max: 100, unit: '%', caption: 'hero-caption' });
      $('gpu-load-block').classList.add('hidden');
    }

    if (g) {
      $('gpu-name').textContent = g.name;
      $('gpu-load').textContent = f0(g.load);
      $('gpu-load-l').textContent = f0(g.load);
      meter('gpu-meter', g.load);
      const ts = statusOf(g.temp, th.gpu_temp);
      setVal('gpu-temp', g.temp != null ? `${f0(g.temp)} °C` : '–', ts, ts === 'crit' ? t('hot') : t('warm'));
      $('gpu-power').textContent = g.power != null ? `${f0(g.power)} W` + (g.power_limit ? ` ${t('of')} ${f0(g.power_limit)} W` : '') : '–';
      $('gpu-clock').textContent = g.clock != null ? `${f0(g.clock)} MHz` + (g.mem_clock ? ` · ${t('memClock')} ${f0(g.mem_clock)} MHz` : '') : '–';
      const vp = g.vram_total ? g.vram_used / g.vram_total * 100 : 0;
      const vs = statusOf(vp, th.vram);
      setVal('gpu-vram', g.vram_total ? `${f1(g.vram_used / 1024)} ${t('of')} ${f1(g.vram_total / 1024)} GB` : '–', vs, t('full'));
      meter('vram-meter', vp, vs);
      $('gpu-fan').textContent = g.fan != null ? `${f0(g.fan)} %` : '–';
    }

    $('cpu-name').textContent = c.name;
    $('cpu-load').textContent = f0(c.load);
    meter('cpu-meter', c.load);
    const cores = $('cores');
    if (cores.children.length !== c.per_core.length) cores.innerHTML = c.per_core.map(() => '<i></i>').join('');
    c.per_core.forEach((v, i) => { cores.children[i].style.height = Math.max(6, v) + '%'; });
    const cs = statusOf(c.temp, th.cpu_temp);
    setVal('cpu-temp', c.temp != null ? `${f0(c.temp)} °C` : '–', cs, cs === 'crit' ? t('hot') : t('warm'));
    $('cpu-freq').textContent = c.freq != null ? `${nf2.format(c.freq / 1000)} GHz` : '–';
    spark('cpu-spark', h.cpu, COLORS.cpu, { max: 100, unit: '%', caption: 'cpu-caption' });

    $('mem-total').textContent = `${t('of')} ${f1(gb(m.total))} GB`;
    $('mem-used').textContent = f1(gb(m.used));
    const ms = statusOf(m.percent, th.ram);
    meter('mem-meter', m.percent, ms);
    $('mem-caption').textContent = `${f0(m.percent)} % ${t('used')}` + (ms ? ` · ▲ ${t('tight')}` : '');

    $('net-down').textContent = f1(n.down);
    $('net-up').textContent = `${f1(n.up)} Mbit/s`;
    spark('net-spark', h.down, COLORS.net, { floor: 1, unit: 'Mbit/s', fmt: f1, caption: 'net-caption' });

    const maxCpu = Math.max(...s.procs.map(p => p.cpu), 1);
    $('procs-list').innerHTML = s.procs.length
      ? s.procs.map(p => `<div class="row"><span class="name">${esc(p.name)}</span><span class="n">${f0(p.cpu)} %</span><span class="n">${f1(gb(p.mem))} GB</span><div class="bar" style="width:${(p.cpu / maxCpu * 100).toFixed(0)}%"></div></div>`).join('')
      : `<div class="caption">${t('quiet')}</div>`;
  }

  async function tick() {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), 1500);
    try {
      const r = await fetch('/api/stats', { cache: 'no-store', signal: ctrl.signal });
      const s = await r.json();
      if (s.ready) {
        render(s);
        document.body.classList.remove('offline');
        document.body.classList.add('online');
        $('conn').textContent = t('live');
      }
    } catch (e) {
      document.body.classList.remove('online');
      document.body.classList.add('offline');
      $('conn').textContent = t('offline');
    } finally {
      clearTimeout(to);
    }
  }

  // ---- minimap ----------------------------------------------------------
  const MARKER = { player: { color: COLORS.ink, r: 7 }, ally: { color: COLORS.mem, r: 5 }, other: { color: COLORS.net, r: 4 } };
  const map = { canvas: $('map-canvas'), img: null, imgSrc: null, mode: 0, last: null };
  const MODES = [{ follow: true, zoom: 2 }, { follow: true, zoom: 4 }, { follow: false, zoom: 1 }];

  function drawMap(data) {
    map.last = data;
    const c = map.canvas, dpr = devicePixelRatio || 1;
    const w = c.clientWidth, h = c.clientHeight;
    if (!w || !h) return;
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
    const ctx = c.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const def = data.map || {};
    if (def.image && map.imgSrc !== def.image) {
      map.imgSrc = def.image;
      map.img = new Image();
      map.img.onload = () => { if (map.last) drawMap(map.last); };
      map.img.src = def.image;
    }
    const img = map.img && map.img.complete && map.img.naturalWidth ? map.img : null;
    const [ox, oy] = def.origin_px || [0, 0];
    const [sx, sy] = def.px_per_unit || [1, -1];
    const toPx = e => [ox + e.x * sx, oy + e.y * sy];
    const ents = data.entities || [];
    const player = ents.find(e => e.kind === 'player') || ents[0];

    let rect;
    if (img) rect = { x0: 0, y0: 0, w: img.naturalWidth, h: img.naturalHeight };
    else {
      const ps = ents.map(toPx);
      const xs = ps.map(p => p[0]), ys = ps.map(p => p[1]);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
      const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 200) * 1.3;
      rect = { x0: cx - span / 2, y0: cy - span / 2, w: span, h: span };
    }
    const mode = MODES[map.mode];
    let s = Math.min(w / rect.w, h / rect.h);
    let tx = (w - rect.w * s) / 2 - rect.x0 * s, ty = (h - rect.h * s) / 2 - rect.y0 * s;
    if (mode.follow && player) {
      s *= mode.zoom;
      const [px, py] = toPx(player);
      tx = w / 2 - px * s; ty = h / 2 - py * s;
    }

    ctx.save();
    ctx.translate(tx, ty);
    ctx.scale(s, s);
    if (img) ctx.drawImage(img, 0, 0);
    else {
      ctx.strokeStyle = COLORS.grid; ctx.lineWidth = 1 / s;
      const step = 50;
      for (let gx = Math.floor(rect.x0 / step) * step; gx <= rect.x0 + rect.w; gx += step) { ctx.beginPath(); ctx.moveTo(gx, rect.y0); ctx.lineTo(gx, rect.y0 + rect.h); ctx.stroke(); }
      for (let gy = Math.floor(rect.y0 / step) * step; gy <= rect.y0 + rect.h; gy += step) { ctx.beginPath(); ctx.moveTo(rect.x0, gy); ctx.lineTo(rect.x0 + rect.w, gy); ctx.stroke(); }
    }
    ctx.restore();

    ctx.font = '12px system-ui, sans-serif';
    ctx.textBaseline = 'middle';
    for (const e of ents) {
      const [px, py] = toPx(e);
      const X = tx + px * s, Y = ty + py * s;
      const m = MARKER[e.kind] || MARKER.other;
      ctx.beginPath(); ctx.arc(X, Y, m.r, 0, Math.PI * 2);
      ctx.fillStyle = m.color; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = SURFACE; ctx.stroke();
      if (e.heading != null) {
        const a = (e.heading - 90) * Math.PI / 180;
        ctx.beginPath(); ctx.moveTo(X, Y); ctx.lineTo(X + Math.cos(a) * (m.r + 10), Y + Math.sin(a) * (m.r + 10));
        ctx.lineWidth = 3; ctx.strokeStyle = m.color; ctx.stroke();
      }
      if (e.label) { ctx.fillStyle = COLORS.ink; ctx.fillText(e.label, X + m.r + 6, Y); }
    }
    $('map-sub').textContent = [def.name || def.id || data.source, mode.follow ? t('mapFollow', { z: mode.zoom }) : t('mapFull')].filter(Boolean).join(' · ');
  }

  map.canvas.addEventListener('click', () => { map.mode = (map.mode + 1) % MODES.length; if (map.last) drawMap(map.last); });

  async function pollMap() {
    let delay = 1000;
    try {
      const r = await fetch('/api/map', { cache: 'no-store' });
      const data = await r.json();
      if (data.live) {
        const wasHidden = $('map').classList.contains('hidden');
        $('map').classList.remove('hidden');
        document.body.classList.add('has-map');
        if (wasHidden && lastSnap) render(lastSnap);
        drawMap(data);
        delay = 100;
      } else if (!$('map').classList.contains('hidden')) {
        $('map').classList.add('hidden');
        document.body.classList.remove('has-map');
        if (lastSnap) render(lastSnap);
      }
    } catch (e) { /* server away, stats poller reports it */ }
    setTimeout(pollMap, delay);
  }

  // ---- start ------------------------------------------------------------
  setCaption('cpu-caption', t('last2'));
  setCaption('net-caption', t('downloadLast'));
  $('conn').textContent = t('connecting');
  for (const id of ['hero-spark', 'cpu-spark', 'net-spark']) enableScrub(id);
  if (navigator.standalone) $('hint').classList.add('hidden');
  document.addEventListener('pointerdown', () => { navigator.wakeLock?.request('screen').catch(() => {}); }, { once: true });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
  window.addEventListener('resize', () => { if (lastSnap) render(lastSnap); if (map.last) drawMap(map.last); });
  tick();
  setInterval(tick, 1000);
  pollMap();
})();
