/* نمودارهای SVG دست‌ساز — بدون کتابخانهٔ خارجی تا دمو در شبکهٔ قطع هم کار کند.
   مشخصات از راهنمای طراحی: خط ۲px، نشانگر ≥۸px، انتهای گرد ۴px، فاصلهٔ ۲px بین
   پرها، شبکهٔ کم‌رنگ، متن با رنگ متن نه رنگ سری، تولتیپ روی همه‌ی فرم‌ها. */
'use strict';

const CH = (() => {
  const cs = n => getComputedStyle(document.body).getPropertyValue(n).trim();
  const el = (t, a = {}, ...k) => {
    const n = document.createElement(t);
    for (const [key, v] of Object.entries(a)) {
      if (v == null) continue;
      if (key === 'class') n.className = v;
      else if (key === 'html') n.innerHTML = v;
      else if (key.startsWith('on')) n.addEventListener(key.slice(2), v);
      else n.setAttribute(key, v);
    }
    for (const c of k.flat()) if (c != null) n.append(c.nodeType ? c : document.createTextNode(c));
    return n;
  };
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  /* تیک‌ها باید همیشه بازهٔ داده را بپوشانند.
     نسخهٔ پیشین تیک پایینی را وقتی از min کمتر بود حذف می‌کرد، پس دامنهٔ مقیاس
     از دامنهٔ داده باریک‌تر می‌شد و نقاط بیرون کادر می‌افتادند (برای احتمال
     ماندگاری ۰٫۰۲ تا ۰٫۹۷، تیک‌ها ۰٫۲۵ تا ۰٫۷۵ می‌شد). حالا lo را به پایین و hi
     را به بالا گرد می‌کنیم و هیچ تیکی حذف نمی‌شود. */
  function niceTicks(min, max, n = 4) {
    const span = (max - min) || Math.abs(max) || 1;
    const raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || 10 * mag;
    const lo = Math.floor(min / step) * step;
    const hi = Math.ceil(max / step) * step;
    const out = [];
    for (let v = lo; v <= hi + step * 1e-6; v += step) out.push(+v.toFixed(10));
    return out;
  }

  function tipFor(host) {
    const t = el('div', { class: 'tip' });
    host.append(t);
    return {
      show(html, xFrac) {
        t.innerHTML = html;
        t.style.opacity = '1';
        const w = host.getBoundingClientRect().width;
        t.style.left = Math.max(4, Math.min(w - 170, xFrac * w - 80)) + 'px';
        t.style.top = '2px';
      },
      hide() { t.style.opacity = '0'; },
    };
  }

  /* ─── خطی: یک محور، راست‌به‌چپ ─── */
  function line(host, { series, labels, fmtY = String, fmtV = String, h = 200, suffix = '', xlab }) {
    host.innerHTML = '';
    const W = 760, PL = 46, PR = 54, PT = 10, PB = 24;
    const x0 = PL, x1 = W - PR, y0 = PT, y1 = h - PB, n = labels.length;
    if (!n) { host.append(el('div', { class: 'empty' }, 'داده‌ای نیست.')); return; }
    const all = series.flatMap(s => s.data.filter(v => v != null));
    if (!all.length) { host.append(el('div', { class: 'empty' }, 'داده‌ای نیست.')); return; }
    const tk = niceTicks(Math.min(...all, 0) === 0 ? 0 : Math.min(...all), Math.max(...all), 4);
    const mn = Math.min(...tk), mx = Math.max(...tk);
    const X = i => x1 - (i / (n - 1 || 1)) * (x1 - x0);
    const Y = v => y1 - ((v - mn) / ((mx - mn) || 1)) * (y1 - y0);
    let s = `<svg viewBox="0 0 ${W} ${h}" role="img" preserveAspectRatio="none">`;
    tk.forEach(v => {
      s += `<line x1="${x0}" x2="${x1}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--grid)" stroke-width="1"/>`;
      s += `<text x="${x1 + 7}" y="${Y(v) + 4}" fill="var(--ink-3)" font-size="10.5" class="tnum">${fmtY(v)}</text>`;
    });
    s += `<line x1="${x0}" x2="${x1}" y1="${y1}" y2="${y1}" stroke="var(--axis)" stroke-width="1"/>`;
    const every = Math.max(1, Math.ceil(n / 8));
    labels.forEach((t, i) => {
      if (i % every) return;
      s += `<text x="${X(i)}" y="${y1 + 16}" fill="var(--ink-3)" font-size="10" text-anchor="middle">${esc(xlab ? xlab(t) : t)}</text>`;
    });
    series.forEach(se => {
      const pts = se.data.map((v, i) => v == null ? null : [X(i), Y(v)]).filter(Boolean);
      if (!pts.length) return;
      s += `<path d="${pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ')}" fill="none" stroke="${se.color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`;
      const e = pts[pts.length - 1];
      s += `<circle cx="${e[0]}" cy="${e[1]}" r="4.5" fill="${se.color}" stroke="var(--surface-1)" stroke-width="2"/>`;
      // برچسب مستقیم را داخل کادر نگه می‌داریم: اگر آخرین نقطه روی سقف باشد،
      // برچسب زیرش می‌رود تا با overflow:hidden بریده نشود.
      const ly = e[1] - 9 < y0 + 2 ? e[1] + 14 : e[1] - 9;
      s += `<text x="${e[0] - 8}" y="${ly}" fill="var(--ink-2)" font-size="10.5" text-anchor="end" class="tnum">${fmtV(se.data.filter(v => v != null).slice(-1)[0])}${suffix}</text>`;
    });
    s += `<line id="cx" x1="0" x2="0" y1="${y0}" y2="${y1}" stroke="var(--axis)" stroke-width="1" opacity="0"/>`;
    series.forEach((se, k) => s += `<circle class="hp" data-k="${k}" r="4.5" fill="${se.color}" stroke="var(--surface-1)" stroke-width="2" opacity="0"/>`);
    s += `<rect x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" fill="transparent" id="hit"/></svg>`;
    host.innerHTML = s;
    const tip = tipFor(host), svg = host.querySelector('svg');
    const cx = svg.querySelector('#cx'), hps = [...svg.querySelectorAll('.hp')];
    svg.querySelector('#hit').addEventListener('pointermove', ev => {
      const r = svg.getBoundingClientRect(), vx = (ev.clientX - r.left) / r.width * W;
      let i = Math.round((x1 - vx) / ((x1 - x0) / (n - 1 || 1)));
      i = Math.max(0, Math.min(n - 1, i));
      cx.setAttribute('x1', X(i)); cx.setAttribute('x2', X(i)); cx.setAttribute('opacity', '1');
      hps.forEach((c, k) => {
        const v = series[k].data[i];
        if (v == null) { c.setAttribute('opacity', '0'); return; }
        c.setAttribute('cx', X(i)); c.setAttribute('cy', Y(v)); c.setAttribute('opacity', '1');
      });
      tip.show(`<div class="th">${esc(xlab ? xlab(labels[i]) : labels[i])}</div>` + series.map(se =>
        `<div class="tr"><span>${esc(se.name)}</span><b>${se.data[i] == null ? '—' : fmtV(se.data[i]) + suffix}</b></div>`).join(''),
        X(i) / W);
    });
    svg.querySelector('#hit').addEventListener('pointerleave', () => {
      tip.hide(); cx.setAttribute('opacity', '0'); hps.forEach(c => c.setAttribute('opacity', '0'));
    });
  }

  /* ─── میله‌ای عمودی ─── */
  function bar(host, { labels, data, color, fmtV = String, h = 180, suffix = '', xlab }) {
    host.innerHTML = '';
    const W = 760, PL = 40, PR = 54, PT = 10, PB = 24;
    const x0 = PL, x1 = W - PR, y0 = PT, y1 = h - PB, n = labels.length;
    if (!n) { host.append(el('div', { class: 'empty' }, 'داده‌ای نیست.')); return; }
    const tk = niceTicks(0, Math.max(...data, 1), 4), mx = Math.max(...tk);
    const bw = Math.max(3, ((x1 - x0) / n) - 2);
    const X = i => x1 - ((i + 0.5) / n) * (x1 - x0) - bw / 2;
    let s = `<svg viewBox="0 0 ${W} ${h}" role="img" preserveAspectRatio="none">`;
    tk.forEach(v => {
      const y = y1 - (v / mx) * (y1 - y0);
      s += `<line x1="${x0}" x2="${x1}" y1="${y}" y2="${y}" stroke="var(--grid)" stroke-width="1"/>`;
      s += `<text x="${x1 + 7}" y="${y + 4}" fill="var(--ink-3)" font-size="10.5" class="tnum">${fmtV(v)}</text>`;
    });
    s += `<line x1="${x0}" x2="${x1}" y1="${y1}" y2="${y1}" stroke="var(--axis)" stroke-width="1"/>`;
    const every = Math.max(1, Math.ceil(n / 8));
    labels.forEach((t, i) => {
      if (i % every) return;
      s += `<text x="${X(i) + bw / 2}" y="${y1 + 16}" fill="var(--ink-3)" font-size="10" text-anchor="middle">${esc(xlab ? xlab(t) : t)}</text>`;
    });
    data.forEach((v, i) => {
      const hh = Math.max(1, (v / mx) * (y1 - y0));
      s += `<rect class="bx" data-i="${i}" x="${X(i).toFixed(1)}" y="${(y1 - hh).toFixed(1)}" width="${bw.toFixed(1)}" height="${hh.toFixed(1)}" rx="${Math.min(4, bw / 2)}" fill="${color}"/>`;
    });
    s += '</svg>';
    host.innerHTML = s;
    const tip = tipFor(host), svg = host.querySelector('svg');
    svg.querySelectorAll('.bx').forEach(b => {
      b.addEventListener('pointerenter', () => {
        const i = +b.dataset.i;
        tip.show(`<div class="th">${esc(xlab ? xlab(labels[i]) : labels[i])}</div><div class="tr"><span>مقدار</span><b>${fmtV(data[i])}${suffix}</b></div>`,
          (+b.getAttribute('x') + bw / 2) / W);
      });
      b.addEventListener('pointerleave', tip.hide);
    });
  }

  /* ─── میله افقی رتبه‌ای، رمپ ترتیبی تک‌رنگ ─── */
  function hbar(host, rows, { fmt = String, sub, onClick, max } = {}) {
    host.innerHTML = '';
    const mx = max ?? Math.max(...rows.map(r => Math.abs(r.value)), 1);
    const steps = ['var(--seq-450)', 'var(--seq-450)', 'var(--seq-250)', 'var(--seq-250)'];
    const w = el('div', { class: 'hbars' });
    rows.forEach((r, i) => {
      const pw = Math.max(1.5, Math.abs(r.value) / mx * 100);
      const col = r.color || steps[Math.min(3, Math.floor(i / Math.max(1, rows.length - 1) * 3))];
      const row = el('div', { class: onClick ? 'hbrow clickable' : 'hbrow', onclick: onClick ? () => onClick(r) : null });
      row.append(el('div', { class: 'hblab' },
        el('span', {}, r.label),
        el('span', { class: 'tnum hbval' },
          (r.display != null ? r.display : fmt(r.value)) + (sub ? ' · ' + sub(r) : ''))));
      row.append(el('div', { class: 'hbtrack' }, el('div', { class: 'hbfill', style: `width:${pw}%;background:${col}` })));
      w.append(row);
    });
    host.append(w);
  }

  /* ─── میله‌های واگرا: سهم مثبت و منفی حول صفر ─── */
  function diverging(host, rows, { fmt = v => v.toFixed(2) } = {}) {
    host.innerHTML = '';
    const mx = Math.max(...rows.map(r => Math.abs(r.value)), 0.01);
    const w = el('div', { class: 'divbars' });
    rows.forEach(r => {
      const pos = r.value >= 0;
      const pw = Math.abs(r.value) / mx * 50;
      const row = el('div', { class: 'dvrow' });
      row.append(el('div', { class: 'dvlab' }, r.label,
        r.note ? el('span', { class: 'dvnote' }, r.note) : null));
      const track = el('div', { class: 'dvtrack' });
      track.append(el('div', { class: 'dvmid' }));
      track.append(el('div', {
        class: 'dvfill',
        style: `width:${pw}%;${pos ? 'right:50%' : 'left:50%'};background:${pos ? 'var(--series-1)' : 'var(--crit)'}`,
      }));
      row.append(track);
      row.append(el('div', { class: 'tnum dvval', style: `color:${pos ? 'var(--series-1)' : 'var(--crit)'}` },
        (pos ? '+' : '') + fmt(r.value)));
      row.title = r.tip || '';
      w.append(row);
    });
    host.append(w);
  }

  /* ─── نوار نسبت (احتمال) با درصد و رنگ وضعیت ─── */
  function meters(host, rows) {
    host.innerHTML = '';
    const w = el('div', { class: 'meters' });
    rows.forEach(r => {
      const pctv = Math.round(r.value * 100);
      const row = el('div', { class: 'mtrow' });
      row.append(el('div', { class: 'mtlab' },
        el('span', {}, r.label),
        el('span', { class: 'tnum mtval', style: r.color ? `color:${r.color}` : null }, pctv + '٪')));
      row.append(el('div', { class: 'mttrack' },
        el('div', { class: 'mtfill', style: `width:${Math.max(1.5, pctv)}%;background:${r.color || 'var(--seq-450)'}` })));
      if (r.sub) row.append(el('div', { class: 'mtsub' }, r.sub));
      w.append(row);
    });
    host.append(w);
  }

  /* ─── نوار ترکیبی افقی (مثل تجزیهٔ LTV) با فاصلهٔ ۲px بین پرها ─── */
  function stack(host, parts, { total, fmt = String } = {}) {
    host.innerHTML = '';
    // پرانتز الزامی است: ترکیب ?? و || بدون پرانتز خطای نحوی می‌دهد
    const sum = (total ?? parts.reduce((a, b) => a + Math.abs(b.value), 0)) || 1;
    const wrap = el('div', {});
    const track = el('div', { class: 'sttrack' });
    parts.forEach(p => {
      const pw = Math.abs(p.value) / sum * 100;
      if (pw <= 0) return;
      track.append(el('div', {
        class: 'stseg', style: `width:${pw}%;background:${p.color}`,
        title: `${p.label}: ${fmt(p.value)}`,
      }));
    });
    wrap.append(track);
    wrap.append(el('div', { class: 'stleg' }, parts.map(p =>
      el('span', {}, el('i', { style: `background:${p.color}` }), `${p.label} ${fmt(p.value)}`))));
    host.append(wrap);
  }

  /* ─── پراکندگی: موقعیت خودش چهارخانه را رمزگذاری می‌کند، پس رنگ فقط
         رمپ ترتیبی برای اندازهٔ ارزش است (بدون رنگ دسته‌ای) ─── */
  function scatter(host, pts, { xKey, yKey, xLab, yLab, xMid, yMid, quadLabels, sizeKey, colorKey, fmtC = String, onClick, h = 320 }) {
    host.innerHTML = '';
    const W = 760, PL = 52, PR = 16, PT = 14, PB = 34;
    const x0 = PL, x1 = W - PR, y0 = PT, y1 = h - PB;
    if (!pts.length) { host.append(el('div', { class: 'empty' }, 'داده‌ای نیست.')); return; }
    const xs = pts.map(p => p[xKey]), ys = pts.map(p => p[yKey]);
    const xt = niceTicks(Math.min(...xs), Math.max(...xs), 4);
    const yt = niceTicks(Math.min(...ys), Math.max(...ys), 4);
    const xmn = Math.min(...xt), xmx = Math.max(...xt), ymn = Math.min(...yt), ymx = Math.max(...yt);
    const X = v => x1 - ((v - xmn) / ((xmx - xmn) || 1)) * (x1 - x0);   /* راست‌به‌چپ */
    const Y = v => y1 - ((v - ymn) / ((ymx - ymn) || 1)) * (y1 - y0);
    const sizes = sizeKey ? pts.map(p => Math.abs(p[sizeKey] || 0)) : null;
    const smx = sizes ? Math.max(...sizes, 1) : 1;
    const R = p => sizeKey ? 3 + 7 * Math.sqrt(Math.abs(p[sizeKey] || 0) / smx) : 4;
    const cvals = colorKey ? pts.map(p => p[colorKey] || 0) : null;
    const cmn = cvals ? Math.min(...cvals) : 0, cmx = cvals ? Math.max(...cvals) : 1;
    const ramp = ['var(--seq-100)', 'var(--seq-250)', 'var(--seq-450)', 'var(--seq-600)'];
    const C = p => {
      if (!colorKey) return 'var(--seq-450)';
      const t = (p[colorKey] - cmn) / ((cmx - cmn) || 1);
      return ramp[Math.min(3, Math.floor(t * 4))];
    };
    let s = `<svg viewBox="0 0 ${W} ${h}" role="img" preserveAspectRatio="none">`;
    yt.forEach(v => {
      s += `<line x1="${x0}" x2="${x1}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--grid)" stroke-width="1"/>`;
      s += `<text x="${x1 + 6}" y="${Y(v) + 4}" fill="var(--ink-3)" font-size="10" class="tnum">${v}</text>`;
    });
    xt.forEach(v => s += `<text x="${X(v)}" y="${y1 + 15}" fill="var(--ink-3)" font-size="10" text-anchor="middle" class="tnum">${v}</text>`);
    if (xMid != null) s += `<line x1="${X(xMid)}" x2="${X(xMid)}" y1="${y0}" y2="${y1}" stroke="var(--axis)" stroke-width="1" stroke-dasharray="4 3"/>`;
    if (yMid != null) s += `<line x1="${x0}" x2="${x1}" y1="${Y(yMid)}" y2="${Y(yMid)}" stroke="var(--axis)" stroke-width="1" stroke-dasharray="4 3"/>`;
    if (quadLabels) {
      // در متن راست‌به‌چپ، text-anchor برخلاف انتظار عمل می‌کند: «end» لبهٔ چپ را
      // لنگر می‌کند و «start» لبهٔ راست را. پس برچسب‌های سمت راست باید start
      // بگیرند و سمت چپ end، وگرنه از کادر بیرون می‌زنند.
      const put = (t, x, y, ax) => `<text x="${x}" y="${y}" fill="var(--ink-3)" font-size="10.5" text-anchor="${ax}" opacity="0.85">${esc(t)}</text>`;
      s += put(quadLabels.tr, x1 - 6, y0 + 13, 'start');
      s += put(quadLabels.tl, x0 + 6, y0 + 13, 'end');
      s += put(quadLabels.br, x1 - 6, y1 - 6, 'start');
      s += put(quadLabels.bl, x0 + 6, y1 - 6, 'end');
    }
    pts.forEach((p, i) => {
      s += `<circle class="pt" data-i="${i}" cx="${X(p[xKey]).toFixed(1)}" cy="${Y(p[yKey]).toFixed(1)}" r="${R(p).toFixed(1)}" fill="${C(p)}" fill-opacity="0.72" stroke="var(--surface-1)" stroke-width="1.5"/>`;
    });
    s += `<text x="${(x0 + x1) / 2}" y="${h - 2}" fill="var(--ink-3)" font-size="10.5" text-anchor="middle">${esc(xLab)}</text>`;
    s += `<text x="12" y="${(y0 + y1) / 2}" fill="var(--ink-3)" font-size="10.5" text-anchor="middle" transform="rotate(-90 12 ${(y0 + y1) / 2})">${esc(yLab)}</text>`;
    s += '</svg>';
    host.innerHTML = s;
    const tip = tipFor(host), svg = host.querySelector('svg');
    svg.querySelectorAll('.pt').forEach(c => {
      c.addEventListener('pointerenter', () => {
        const p = pts[+c.dataset.i];
        tip.show(`<div class="th">${esc(p.id)}</div>` +
          `<div class="tr"><span>${esc(yLab)}</span><b>${p[yKey]}</b></div>` +
          `<div class="tr"><span>${esc(xLab)}</span><b>${p[xKey]}</b></div>` +
          (colorKey ? `<div class="tr"><span>ارزش</span><b>${fmtC(p[colorKey])}</b></div>` : '') +
          `<div class="tr"><span>خانه</span><b>${esc(p.quadrant || '—')}</b></div>`,
          +c.getAttribute('cx') / W);
        c.setAttribute('fill-opacity', '1');
      });
      c.addEventListener('pointerleave', () => { tip.hide(); c.setAttribute('fill-opacity', '0.72'); });
      if (onClick) {
        c.style.cursor = 'pointer';
        c.addEventListener('click', () => onClick(pts[+c.dataset.i]));
      }
    });
  }

  /* ─── نقشهٔ حرارتی: رمپ ترتیبی تک‌رنگ، روشن→تیره ─── */
  function heatmap(host, cells, { xKey, yKey, vKey, xLabels, yLabels, xLab, yLab, fmtV = String, onClick }) {
    host.innerHTML = '';
    const nx = xLabels.length, ny = yLabels.length;
    const vals = cells.map(c => c[vKey]);
    const mx = Math.max(...vals, 1);
    const ramp = ['var(--seq-100)', 'var(--seq-150)', 'var(--seq-250)', 'var(--seq-350)', 'var(--seq-450)', 'var(--seq-600)'];
    const map = new Map(cells.map(c => [`${c[xKey]}|${c[yKey]}`, c]));
    const tbl = el('div', { class: 'hm', style: `grid-template-columns:auto repeat(${nx},1fr)` });
    tbl.append(el('div', { class: 'hmcorner' }, yLab + ' ↓ / ' + xLab + ' →'));
    xLabels.forEach(x => tbl.append(el('div', { class: 'hmhx' }, String(x))));
    [...yLabels].reverse().forEach(y => {
      tbl.append(el('div', { class: 'hmhy' }, String(y)));
      xLabels.forEach(x => {
        const c = map.get(`${x}|${y}`);
        const v = c ? c[vKey] : 0;
        const t = v / mx;
        const cell = el('div', {
          class: 'hmcell' + (onClick && c ? ' clickable' : ''),
          style: `background:${v ? ramp[Math.min(5, Math.floor(t * 6))] : 'var(--grid)'};` +
            `color:${t > 0.55 ? '#fff' : 'var(--ink-2)'}`,
          title: c ? `R=${c.R} F=${c.F} — ${fmtV(v)}` : 'بدون مشتری',
          onclick: onClick && c ? () => onClick(c) : null,
        }, v ? String(v) : '');
        tbl.append(cell);
      });
    });
    host.append(tbl);
  }

  return { line, bar, hbar, diverging, meters, stack, scatter, heatmap, cs, el, niceTicks };
})();
