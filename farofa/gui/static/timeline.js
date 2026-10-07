// Timeline of a traced replication: one row per device (up / waiting for a
// team / in repair, failure markers), queue length and busy teams below, and
// an overview strip with a brush. Drag on the chart to zoom, drag the brush
// to pan, double-click (or "All") to reset; ctrl/⌘ + wheel or pinch zooms.
import { $, S, h, on } from "./core.js";
import { C, STATE, UP_OPACITY, el, newSvg, nextId, niceTicks, scale, svgLegend, text, tickFormat, tip, untip, widthOf, chartCard, responsive } from "./charts.js";
import { fmt, fmtH, fmtInt, t } from "./i18n.js";

const TL = { rep: 0, x0: 0, x1: null, data: null, geo: null, host: null, readout: null, stats: null };

function lastLE(arr, x) {
  let lo = 0, hi = arr.length - 1, ans = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (arr[m] <= x) { ans = m; lo = m + 1; } else hi = m - 1; }
  return ans;
}
const stepAt = (st, x) => { const i = lastLE(st.t, x); return i < 0 ? 0 : st.v[i]; };

function stepSeries(events) {
  events.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const tt = [0], v = [0];
  let c = 0, max = 0;
  for (const [x, d] of events) {
    c += d;
    if (x === tt[tt.length - 1]) v[v.length - 1] = c; else { tt.push(x); v.push(c); }
    if (c > max) max = c;
  }
  return { t: tt, v, max };
}

function prep(r, rep) {
  const tr = r.traces[rep], N = r.n_devices;
  const devs = Array.from({ length: N }, () => ({ a: [], b: [], s: [], f: [] }));
  const qEv = [], bEv = [], dEv = [];
  for (let i = 0; i < tr.state.length; i++) {
    const d = devs[tr.entity[i]], s = tr.state[i], a = tr.start[i], b = tr.end[i];
    d.a.push(a); d.b.push(b); d.s.push(s);
    if (s === 1) qEv.push([a, 1], [b, -1]);
    if (s === 2) bEv.push([a, 1], [b, -1]);
    if (s) dEv.push([a, 1], [b, -1]);
  }
  tr.failure_entity.forEach((e, i) => devs[e].f.push(tr.failure_time[i]));
  return { N, K: r.n_teams, T: r.mission_time, fleet: r.system === "fleet", devs, q: stepSeries(qEv), busy: stepSeries(bEv), down: stepSeries(dEv), nFail: tr.failure_time.length };
}

function stepPath(st, x, y, x0, x1, xa, xb, yBase) {
  let v = stepAt(st, x0);
  let d = `M${xa},${yBase}V${y(v)}`;
  for (let i = lastLE(st.t, x0) + 1; i < st.t.length && st.t[i] < x1; i++) { d += `H${x(st.t[i]).toFixed(2)}V${y(st.v[i]).toFixed(2)}`; v = st.v[i]; }
  return d + `H${xb}V${yBase}Z`;
}

function draw() {
  const host = TL.host, D = TL.data;
  if (!host || !D) return;
  if (TL.head) TL.head.textContent = t("tl.title") + " · " + t("tl.repn", { n: TL.rep + 1 });
  const W = widthOf(host, 320);
  const x0 = TL.x0, x1 = TL.x1 ?? D.T;
  const N = D.N;
  const rowH = N <= 1 ? 34 : N <= 12 ? 24 : N <= 30 ? 15 : Math.max(5, Math.floor(450 / N));
  const m = { l: 70, r: 16 };
  const top = 34, gH = N * rowH, gap = 26, pH = 58;
  const yq = top + gH + gap, yb = yq + pH + gap;
  const yAx = (D.fleet ? yb + pH : top + gH) + 4;
  const yo = yAx + 44, oh = 30, H = yo + oh + 8;
  const svg = newSvg(host, W, H, t("tl.aria"));
  const x = scale(x0, x1, m.l, W - m.r), xo = scale(0, D.T, m.l, W - m.r);
  const xa = m.l, xb = W - m.r;
  TL.geo = { W, H, m, top, rowH, gH, yq, yb, pH, yAx, yo, oh, x, xo, x0, x1 };
  const g = el("g", {}, svg);
  svgLegend(g, m.l, 14, [
    { label: t("state.up"), color: STATE.up, opacity: UP_OPACITY },
    D.fleet ? { label: t("state.waiting"), color: STATE.waiting } : null,
    { label: t("state.repair"), color: STATE.repair },
    { label: t("state.failure"), color: C.ink, kind: "tri" },
  ].filter(Boolean), W - m.r);
  const clip = nextId("tlclip");
  el("rect", { x: xa, y: 0, width: xb - xa, height: H }, el("clipPath", { id: clip }, el("defs", {}, svg)));
  const rows = el("g", { "clip-path": `url(#${clip})` }, g);
  const inset = rowH >= 12 ? 2 : rowH >= 8 ? 1 : 0.5;
  const labelEvery = rowH >= 12 ? 1 : Math.ceil(12 / rowH);
  for (let d = 0; d < N; d++) {
    const y = top + d * rowH + inset, hh = rowH - 2 * inset, dv = D.devs[d];
    el("rect", { x: x(0), y, width: x(D.T) - x(0), height: hh, fill: STATE.up, "fill-opacity": UP_OPACITY }, rows);
    for (let i = 0; i < dv.a.length; i++) {
      if (!dv.s[i] || dv.b[i] <= x0 || dv.a[i] >= x1) continue;
      const a = x(Math.max(dv.a[i], x0)), b = x(Math.min(dv.b[i], x1));
      el("rect", { x: a.toFixed(2), y, width: Math.max(1, b - a).toFixed(2), height: hh, fill: dv.s[i] === 1 ? STATE.waiting : STATE.repair }, rows);
    }
    for (const f of dv.f) {
      if (f < x0 || f > x1) continue;
      const fx = x(f);
      if (rowH >= 12) el("path", { d: `M${(fx - 3.5).toFixed(2)},${y - inset}h7l-3.5,5.5z`, fill: C.ink }, rows);
      else el("line", { x1: fx, x2: fx, y1: y, y2: y + hh, stroke: C.ink, "stroke-width": 1 }, rows);
    }
    if (d % labelEvery === 0 || d === N - 1) {
      text(g, xa - 6, top + d * rowH + rowH / 2 + 4, N === 1 ? t("tl.device1") : t("tl.dev", { n: d + 1 }), { "text-anchor": "end", "font-size": Math.min(11, Math.max(8, rowH - 2)) });
    }
  }
  if (D.fleet) {
    const panels = [
      [yq, D.q, Math.max(1, D.q.max), STATE.waiting, t("tl.queue"), null],
      [yb, D.busy, D.K, STATE.repair, t("tl.busy"), D.K],
    ];
    for (const [y0, st, vmax, col, lab, cap] of panels) {
      const y = scale(0, vmax * 1.08, y0 + pH, y0);
      text(g, xa, y0 - 7, lab, { fill: C.ink, "font-weight": 600 });
      el("rect", { x: xa, y: y0, width: xb - xa, height: pH, fill: C.surface, stroke: C.rule }, g);
      el("path", { d: stepPath(st, x, y, x0, x1, xa, xb, y0 + pH), fill: col, "fill-opacity": 0.3, stroke: col, "stroke-width": 1.4 }, el("g", { "clip-path": `url(#${clip})` }, g));
      text(g, xa - 6, y(vmax) + 4, fmtInt(vmax), { "text-anchor": "end" });
      text(g, xa - 6, y0 + pH + 3, "0", { "text-anchor": "end" });
      if (cap) {
        el("line", { x1: xa, x2: xb, y1: y(cap), y2: y(cap), stroke: C.mutedInk, "stroke-dasharray": "4 3" }, g);
        text(g, xb - 4, y(cap) - 3, `K = ${cap}`, { "text-anchor": "end", fill: C.ink });
      }
    }
  }
  // time axis
  const xt = niceTicks(x0, x1, Math.max(3, Math.floor((xb - xa) / 90)));
  const tf = tickFormat(xt.step);
  el("line", { x1: xa, x2: xb, y1: yAx, y2: yAx, stroke: C.muted }, g);
  for (const v of xt.values) {
    if (v < x0 - 1e-9 || v > x1 + 1e-9) continue;
    const xx = x(v);
    el("line", { x1: xx, x2: xx, y1: yAx, y2: yAx + 4, stroke: C.muted }, g);
    text(g, xx, yAx + 16, tf(v), { "text-anchor": xx > xb - 16 ? "end" : xx < xa + 10 ? "start" : "middle" });
  }
  text(g, xb, yAx + 30, t("axis.time"), { "text-anchor": "end" });
  // overview strip with brush
  text(g, xa - 6, yo + oh / 2 + 4, t("tl.overview"), { "text-anchor": "end" });
  el("rect", { x: xa, y: yo, width: xb - xa, height: oh, fill: C.surface, stroke: C.rule }, g);
  const yov = scale(0, Math.max(1, D.down.max), yo + oh, yo + 2);
  el("path", { d: stepPath(D.down, xo, yov, 0, D.T, xa, xb, yo + oh), fill: C.mutedInk, "fill-opacity": 0.35 }, g);
  const zoomed = x0 > 0 || x1 < D.T;
  el("rect", { x: xo(x0), y: yo, width: Math.max(2, xo(x1) - xo(x0)), height: oh, fill: C.accent, "fill-opacity": zoomed ? 0.14 : 0.05, stroke: C.accent, "stroke-width": zoomed ? 1.5 : 1, class: "brush" }, g);
  // interaction layer (not exported)
  const ui = el("g", { class: "no-export" }, svg);
  TL.cross = el("line", { y1: top - 4, y2: yAx, stroke: C.ink, "stroke-width": 1, visibility: "hidden" }, ui);
  TL.sel = el("rect", { y: top - 4, height: yAx - top + 4, fill: C.accent, "fill-opacity": 0.12, stroke: C.accent, visibility: "hidden" }, ui);
  const main = el("rect", { x: xa, y: top - 4, width: xb - xa, height: yAx - top + 4, fill: "transparent", style: "cursor: crosshair" }, ui);
  const strip = el("rect", { x: xa, y: yo, width: xb - xa, height: oh, fill: "transparent", style: "cursor: grab" }, ui);
  wire(svg, main, strip);
  updateStats();
}

function svgPoint(svg, e) {
  const r = svg.getBoundingClientRect(), k = TL.geo.W / r.width;
  return { px: (e.clientX - r.left) * k, py: (e.clientY - r.top) * k };
}
const clampT = (v) => Math.max(0, Math.min(TL.data.T, v));
function setWindow(a, b) {
  const T = TL.data.T, minW = T / 5000;
  if (b - a < minW) { const c = (a + b) / 2; a = c - minW / 2; b = c + minW / 2; }
  if (a < 0) { b -= a; a = 0; }
  if (b > T) { a -= b - T; b = T; }
  TL.x0 = Math.max(0, a); TL.x1 = Math.min(T, b);
  if (TL.x0 <= 0 && TL.x1 >= T) { TL.x0 = 0; TL.x1 = null; }
  draw();
}
export function zoomBy(factor, center) {
  const D = TL.data;
  if (!D) return;
  const a = TL.x0, b = TL.x1 ?? D.T, c = center ?? (a + b) / 2;
  setWindow(c - (c - a) * factor, c + (b - c) * factor);
}

function wire(svg, main, strip) {
  const G = TL.geo, D = TL.data;
  let drag = null;
  main.addEventListener("pointerdown", (e) => {
    const { px } = svgPoint(svg, e);
    drag = { start: px };
    main.setPointerCapture(e.pointerId);
  });
  main.addEventListener("pointermove", (e) => {
    const { px, py } = svgPoint(svg, e);
    const tv = G.x.invert(px);
    TL.cross.setAttribute("x1", px); TL.cross.setAttribute("x2", px); TL.cross.setAttribute("visibility", "visible");
    if (drag) {
      const a = Math.min(drag.start, px), b = Math.max(drag.start, px);
      TL.sel.setAttribute("x", a); TL.sel.setAttribute("width", b - a); TL.sel.setAttribute("visibility", b - a > 3 ? "visible" : "hidden");
      untip();
    } else hover(e, tv, py);
    readout(tv);
  });
  main.addEventListener("pointerup", (e) => {
    if (!drag) return;
    const { px } = svgPoint(svg, e);
    const a = Math.min(drag.start, px), b = Math.max(drag.start, px);
    drag = null;
    TL.sel.setAttribute("visibility", "hidden");
    if (b - a > 6) setWindow(G.x.invert(Math.max(a, G.m.l)), G.x.invert(Math.min(b, G.W - G.m.r)));
  });
  main.addEventListener("pointerleave", () => { if (!drag) { TL.cross.setAttribute("visibility", "hidden"); untip(); } });
  main.addEventListener("dblclick", () => setWindow(0, D.T));
  svg.addEventListener("wheel", (e) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    const { px } = svgPoint(svg, e);
    zoomBy(Math.exp(e.deltaY * 0.01), clampT(G.x.invert(px)));
  }, { passive: false });
  // overview brush: drag inside to pan, outside to draw a new window, click to centre
  let bdrag = null;
  strip.addEventListener("pointerdown", (e) => {
    const { px } = svgPoint(svg, e);
    const tv = clampT(G.xo.invert(px)), a = TL.x0, b = TL.x1 ?? D.T;
    const zoomed = a > 0 || b < D.T;
    bdrag = zoomed && tv >= a && tv <= b ? { mode: "pan", t0: tv, a, b } : { mode: "new", t0: tv, moved: false };
    strip.setPointerCapture(e.pointerId);
  });
  strip.addEventListener("pointermove", (e) => {
    if (!bdrag) return;
    const tv = clampT(G.xo.invert(svgPoint(svg, e).px));
    cancelAnimationFrame(TL.raf);
    TL.raf = requestAnimationFrame(() => {
      if (!bdrag) return;
      if (bdrag.mode === "pan") setWindow(bdrag.a + tv - bdrag.t0, bdrag.b + tv - bdrag.t0);
      else if (Math.abs(G.xo(tv) - G.xo(bdrag.t0)) > 4) { bdrag.moved = true; setWindow(Math.min(tv, bdrag.t0), Math.max(tv, bdrag.t0)); }
    });
  });
  strip.addEventListener("pointerup", (e) => {
    if (bdrag && bdrag.mode === "new" && !bdrag.moved) {
      const w = (TL.x1 ?? D.T) - TL.x0, c = clampT(G.xo.invert(svgPoint(svg, e).px));
      const span = w >= D.T ? D.T / 5 : w;
      setWindow(c - span / 2, c + span / 2);
    }
    bdrag = null;
  });
}

const STATE_NAMES = () => [t("state.up"), t("state.waiting"), t("state.repair")];
function hover(e, tv, py) {
  const G = TL.geo, D = TL.data;
  let html = "";
  if (py >= G.top && py < G.top + G.gH) {
    const d = Math.floor((py - G.top) / G.rowH), dv = D.devs[d];
    if (dv) {
      const i = lastLE(dv.a, tv);
      const s = i >= 0 ? dv.s[i] : 0, a = i >= 0 ? dv.a[i] : 0, b = i >= 0 ? dv.b[i] : D.T;
      const color = [STATE.up, STATE.waiting, STATE.repair][s];
      html = `<b>${D.N === 1 ? t("tl.device1") : t("device.n", { n: d + 1 })}</b>`
        + `<div class="t-row"><i style="background:${color};opacity:${s ? 1 : UP_OPACITY}"></i>${STATE_NAMES()[s]}</div>`
        + `${fmtH(a)} → ${fmtH(b)}<br><span class="dim">${t("tl.duration")}</span> <b>${fmtH(b - a)}</b>`
        + (s && b >= D.T ? ` <span class="dim">(${t("tl.cut")})</span>` : "")
        + `<br><span class="dim">${t("tl.failuresDev", { n: fmtInt(dv.f.filter((f) => f <= tv).length), all: fmtInt(dv.f.length) })}</span>`;
    }
  } else if (D.fleet && py >= G.yq - 16 && py <= G.yq + G.pH) {
    html = `t = ${fmtH(tv)}<br>${t("tl.queue")}: <b>${fmtInt(stepAt(D.q, tv))}</b>`;
  } else if (D.fleet && py >= G.yb - 16 && py <= G.yb + G.pH) {
    html = `t = ${fmtH(tv)}<br>${t("tl.busy")}: <b>${fmtInt(stepAt(D.busy, tv))}</b> ${t("of")} ${D.K}`;
  }
  if (html) tip(e, html); else untip();
}

function readout(tv) {
  const D = TL.data;
  if (!TL.readout || !D) return;
  let up = 0, w = 0, rp = 0;
  for (const dv of D.devs) { const i = lastLE(dv.a, tv); const s = i < 0 ? 0 : dv.s[i]; if (s === 0) up++; else if (s === 1) w++; else rp++; }
  const sw = (c, o = 1) => `<i class="sw" style="background:${c};opacity:${o}"></i>`;
  TL.readout.innerHTML = D.fleet
    ? t("tl.readout.fleet", { t: fmtH(tv), up: `${sw(STATE.up, UP_OPACITY)}<b>${up}</b>`, w: `${sw(STATE.waiting)}<b>${w}</b>`, r: `${sw(STATE.repair)}<b>${rp}</b>`, k: D.K })
    : t(up ? "tl.readout.up" : "tl.readout.down", { t: fmtH(tv) });
}

function updateStats() {
  const r = S.run, D = TL.data;
  if (!TL.stats || !r || !D) return;
  const per = r.per_rep;
  let txt = t("tl.stats", { f: fmtInt(D.nFail), a: fmt(per.availability[TL.rep], 4) });
  if (D.fleet) txt += " · " + t("tl.stats.queue", { q: fmtInt(per.max_queue[TL.rep]) });
  const w = (TL.x1 ?? D.T) - TL.x0;
  if (w < D.T) txt += " · " + t("tl.window", { a: fmtH(TL.x0), b: fmtH(TL.x0 + w) });
  TL.stats.textContent = txt;
}

export function renderTimeline() {
  const P = $("panel-timeline");
  P.replaceChildren();
  untip();
  const r = S.run;
  TL.host = null;
  TL.head = null;
  if (!r) { P.append(h("div", { class: "empty" }, h("b", { text: t("tl.empty.title") }), t("dash.empty.body"))); return; }
  if (!r.traces || !r.traces.length) { P.append(h("div", { class: "empty" }, h("b", { text: t("tl.notrace.title") }), t("tl.notrace.body"))); return; }
  if (TL.rep >= r.traces.length) TL.rep = 0;
  TL.data = prep(r, TL.rep);
  const sel = h("select", { id: "tl-rep", "aria-label": t("tl.rep") }, ...r.traces.map((_, i) => h("option", { value: i, text: fmtInt(i + 1) })));
  sel.value = String(TL.rep);
  const pick = (i) => { TL.rep = (i + r.traces.length) % r.traces.length; sel.value = String(TL.rep); TL.data = prep(r, TL.rep); draw(); };
  sel.addEventListener("change", () => pick(+sel.value));
  TL.stats = h("span", { class: "muted" });
  const bar = h("div", { class: "toolbar" },
    h("label", { for: "tl-rep", text: t("tl.rep") }),
    h("button", { type: "button", class: "small", "aria-label": t("tl.prev"), title: t("tl.prev"), onclick: () => pick(TL.rep - 1) }, "‹"),
    sel,
    h("button", { type: "button", class: "small", "aria-label": t("tl.next"), title: t("tl.next"), onclick: () => pick(TL.rep + 1) }, "›"),
    h("span", { class: "muted", text: t("tl.of", { k: fmtInt(r.traces.length) }) }),
    h("span", { class: "grow" }),
    h("button", { type: "button", class: "small", onclick: () => zoomBy(0.5), title: t("tl.zoomin") }, "+"),
    h("button", { type: "button", class: "small", onclick: () => zoomBy(2), title: t("tl.zoomout") }, "−"),
    h("button", { type: "button", class: "small", onclick: () => setWindow(0, TL.data.T), text: t("tl.all") }));
  P.append(h("div", { class: "headline" }, h("h2", { text: t("tl.title") }), h("span", { class: "meta", text: t("tl.meta", { k: r.traces.length }) })));
  if (S.runVer !== S.modelVer) P.append(h("div", { class: "banner warn", text: t("stale.run") }));
  P.append(bar);
  const c = chartCard(P, { title: t("tl.title") + " · " + t("tl.repn", { n: TL.rep + 1 }), file: "timeline", caption: t("tl.help") });
  c.body.classList.add("tl-wrap");
  TL.readout = h("div", { class: "readout", html: "&nbsp;" });
  c.card.insertBefore(h("div", { class: "toolbar" }, TL.stats), c.body);
  c.card.append(TL.readout);
  TL.host = c.body;
  TL.head = c.card.querySelector("h3");
  responsive(c.body, draw);
}

export function initTimeline() {
  on("run", () => { TL.rep = 0; TL.x0 = 0; TL.x1 = null; renderTimeline(); });
  on("lang", renderTimeline);
  on("model", () => {
    const P = $("panel-timeline"), head = P.querySelector(".headline");
    if (S.run && head && S.runVer !== S.modelVer && !P.querySelector(".banner.warn")) head.after(h("div", { class: "banner warn", text: t("stale.run") }));
  });
  renderTimeline();
}
