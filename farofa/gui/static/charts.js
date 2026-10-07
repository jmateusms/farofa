// SVG charts without dependencies: histogram, line chart with intervals,
// stacked areas, dot plot, plus tooltips and SVG/PNG export.
// Colors are written as attributes so an exported SVG stands on its own.
import { download, h } from "./core.js";
import { fmt, fmtSig, t } from "./i18n.js";

export const C = {
  ink: "#2B2B2B", accent: "#1A4E80", muted: "#8A8A86", rule: "#D8D4CC", paper: "#FBFAF7", surface: "#FFFFFF",
  mutedInk: "#5E5E5A", blue: "#2F6DB5", amber: "#C98A12", wine: "#B0456E", teal: "#2A9D8F",
};
/** Timeline states: up, waiting for a team, in repair. */
export const STATE = { up: C.blue, waiting: C.amber, repair: C.wine };
export const UP_OPACITY = 0.42;
const NS = "http://www.w3.org/2000/svg";
const FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
let uid = 0;
export const nextId = (p) => `${p}${++uid}`;

// --------------------------------------------------------------- svg dom --
export function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs || {}) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
export function text(parent, x, y, str, attrs) {
  const e = el("text", Object.assign({ x, y, fill: C.mutedInk }, attrs || {}), parent);
  e.textContent = str;
  return e;
}
export function newSvg(host, W, H, label) {
  host.replaceChildren();
  return el("svg", {
    xmlns: NS, viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": label || "",
    "font-family": FONT, "font-size": 11, style: "font-variant-numeric: tabular-nums",
  }, host);
}

// ------------------------------------------------------------ scales/axes --
export function niceStep(span, count) {
  const raw = span / Math.max(1, count), mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  return (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
}
export function niceTicks(lo, hi, count = 5) {
  if (!(hi > lo)) return { values: [lo], step: 1 };
  const step = niceStep(hi - lo, count), values = [];
  for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + step * 1e-9; v += step) values.push(Math.abs(v) < step * 1e-9 ? 0 : +v.toPrecision(12));
  return { values, step };
}
export function tickFormat(step) {
  const d = step >= 1 ? 0 : Math.min(6, Math.ceil(-Math.log10(step) - 1e-9));
  return (v) => fmt(v, d);
}
export function scale(d0, d1, r0, r1) {
  const span = d1 - d0 || 1;
  const f = (v) => r0 + (v - d0) / span * (r1 - r0);
  f.invert = (p) => d0 + (p - r0) / ((r1 - r0) || 1) * span;
  f.domain = [d0, d1];
  return f;
}
function extent(values) {
  let lo = Infinity, hi = -Infinity;
  for (const v of values) if (Number.isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; }
  return [lo, hi];
}
function padDomain(lo, hi, frac = 0.06, floor = null) {
  if (!Number.isFinite(lo)) return [0, 1];
  if (hi - lo < 1e-12) { const d = Math.abs(hi) * 0.05 || 0.5; lo -= d; hi += d; }
  const p = (hi - lo) * frac;
  lo -= p; hi += p;
  if (floor !== null && lo < floor) lo = floor;
  return [lo, hi];
}
function gridY(g, y, x0, x1, ticks, fmtf) {
  for (const v of ticks.values) {
    const yy = y(v);
    el("line", { x1: x0, x2: x1, y1: yy, y2: yy, stroke: C.rule, "stroke-width": 1 }, g);
    text(g, x0 - 6, yy + 3.5, fmtf(v), { "text-anchor": "end" });
  }
}
function axisX(g, x, y0, x0, x1, ticks, fmtf, label) {
  el("line", { x1: x0, x2: x1, y1: y0, y2: y0, stroke: C.muted }, g);
  for (const v of ticks.values) {
    const xx = x(v);
    if (xx < x0 - 0.5 || xx > x1 + 0.5) continue;
    el("line", { x1: xx, x2: xx, y1: y0, y2: y0 + 4, stroke: C.muted }, g);
    const anchor = xx > x1 - 14 ? "end" : xx < x0 + 10 ? "start" : "middle";
    text(g, xx, y0 + 16, fmtf(v), { "text-anchor": anchor });
  }
  if (label) text(g, x1, y0 + 30, label, { "text-anchor": "end", fill: C.mutedInk });
}
function yLabel(g, x, y, label) { if (label) text(g, x, y, label, { "text-anchor": "start", fill: C.mutedInk }); }

/** In-SVG legend so exported charts keep it. items: {label, color, kind}. */
export function svgLegend(g, x, y, items, maxX) {
  let cx = x, cy = y;
  for (const it of items) {
    const w = 18 + it.label.length * 6.1 + 14;
    if (maxX && cx + w > maxX && cx > x) { cx = x; cy += 16; }
    if (it.kind === "line" || it.kind === "dash") el("line", { x1: cx, x2: cx + 14, y1: cy - 4, y2: cy - 4, stroke: it.color, "stroke-width": 2, "stroke-dasharray": it.kind === "dash" ? "4 3" : null }, g);
    else if (it.kind === "tri") el("path", { d: `M${cx + 3},${cy - 8} h8 l-4,7 z`, fill: it.color }, g);
    else el("rect", { x: cx, y: cy - 9, width: 14, height: 10, rx: 2, fill: it.color, "fill-opacity": it.opacity == null ? 1 : it.opacity }, g);
    text(g, cx + 19, cy, it.label, { fill: C.ink });
    cx += w;
  }
  return cy;
}

// -------------------------------------------------------------- tooltip ---
let TIP = null;
export function tip(evt, html) {
  if (!TIP) { TIP = h("div", { class: "tip", role: "tooltip" }); document.body.append(TIP); }
  TIP.innerHTML = html;
  TIP.hidden = false;
  const pad = 14, w = TIP.offsetWidth, hh = TIP.offsetHeight;
  let x = evt.clientX + pad, y = evt.clientY + pad;
  if (x + w > window.innerWidth - 8) x = evt.clientX - w - pad;
  if (y + hh > window.innerHeight - 8) y = evt.clientY - hh - pad;
  TIP.style.left = Math.max(8, x) + "px";
  TIP.style.top = Math.max(8, y) + "px";
}
export function untip() { if (TIP) TIP.hidden = true; }
export const swatch = (color, opacity = 1) => `<i style="background:${color};opacity:${opacity}"></i>`;

// ------------------------------------------------------------ responsive --
const observed = new ResizeObserver((entries) => {
  for (const e of entries) {
    const host = e.target, w = Math.round(e.contentRect.width);
    if (!host.__redraw || w === host.__w || w === 0) continue;
    host.__w = w;
    cancelAnimationFrame(host.__raf);
    host.__raf = requestAnimationFrame(() => host.__redraw());
  }
});
/** Draw now and again whenever the host's width changes. */
export function responsive(host, draw) {
  host.__redraw = draw;
  host.__w = Math.round(host.clientWidth);
  observed.observe(host);
  draw();
}
export const widthOf = (host, min = 260) => Math.max(min, Math.floor(host.clientWidth || 600));

// ------------------------------------------------------------- histogram --
/**
 * values: one outcome per replication. o: {color, integer, mean, ci, label,
 * xLabel, fmtX(v), unit, height}. Bars count replications; the dashed line is
 * the mean and the band its confidence interval.
 */
export function histogram(host, values, o = {}) {
  const v = values.filter(Number.isFinite);
  const W = widthOf(host), H = o.height || 200;
  const m = { l: 40, r: 14, t: 18, b: 38 };
  const svg = newSvg(host, W, H, o.label);
  if (!v.length) { text(svg, W / 2, H / 2, "—", { "text-anchor": "middle" }); return svg; }
  let [lo, hi] = extent(v);
  let edges;
  if (o.integer) {
    const span = hi - lo + 1;
    const w = span <= 40 ? 1 : Math.ceil(niceStep(span, 30));
    const start = Math.floor(lo / w) * w;
    edges = [];
    for (let e = start; e <= hi + w; e += w) edges.push(e - 0.5);
    if (edges.length < 2) edges.push(edges[0] + w);
  } else {
    if (hi - lo < 1e-12) { const d = Math.abs(hi) * 1e-3 || 0.5; lo -= d; hi += d; }
    const s = v.slice().sort((a, b) => a - b);
    const iqr = s[Math.floor(s.length * 0.75)] - s[Math.floor(s.length * 0.25)];
    const fd = iqr > 0 ? 2 * iqr / Math.cbrt(s.length) : (hi - lo) / 20;
    const nb = Math.min(40, Math.max(8, Math.round((hi - lo) / fd)));
    const step = niceStep(hi - lo, nb);
    const start = Math.floor(lo / step) * step;
    edges = [];
    for (let e = start; e < hi + step * 0.999; e += step) edges.push(+e.toPrecision(12));
    if (edges[edges.length - 1] <= hi) edges.push(+(edges[edges.length - 1] + step).toPrecision(12));
  }
  const nb = edges.length - 1, counts = new Array(nb).fill(0);
  const bw = edges[1] - edges[0];
  for (const x of v) counts[Math.min(nb - 1, Math.max(0, Math.floor((x - edges[0]) / bw)))]++;
  let x0 = edges[0], x1 = edges[nb];
  const x = scale(x0, x1, m.l, W - m.r);
  const cmax = Math.max(...counts);
  const y = scale(0, cmax * 1.1, H - m.b, m.t);
  const g = el("g", {}, svg);
  const yt = niceTicks(0, cmax * 1.1, 3);
  gridY(g, y, m.l, W - m.r, { values: yt.values.filter((k) => Number.isInteger(k)) }, (k) => fmt(k, 0));
  if (o.ci && Number.isFinite(o.ci[0])) {
    const a = x(Math.max(x0, o.ci[0])), b = x(Math.min(x1, o.ci[1]));
    el("rect", { x: a, y: m.t, width: Math.max(1.5, b - a), height: H - m.b - m.t, fill: C.accent, "fill-opacity": 0.12 }, g);
  }
  const color = o.color || C.blue;
  const n = v.length;
  counts.forEach((c, i) => {
    if (!c) return;
    const xa = x(edges[i]), xb = x(edges[i + 1]);
    const r = el("rect", { x: xa + 0.5, y: y(c), width: Math.max(1, xb - xa - 1), height: y(0) - y(c), fill: color, "fill-opacity": 0.85 }, g);
    const range = o.integer && bw === 1
      ? `<b>${fmt(edges[i] + 0.5, 0)}</b>${o.unit ? " " + o.unit : ""}`
      : `<b>${o.fmtX ? o.fmtX(edges[i]) : fmtSig(edges[i])} – ${o.fmtX ? o.fmtX(edges[i + 1]) : fmtSig(edges[i + 1])}</b>`;
    const html = `${range}<br>${t("chart.reps", { n: fmt(c, 0) })} <span class="dim">(${fmt(100 * c / n, 1)}%)</span>`;
    r.addEventListener("pointermove", (e) => { r.setAttribute("fill-opacity", 1); tip(e, html); });
    r.addEventListener("pointerleave", () => { r.setAttribute("fill-opacity", 0.85); untip(); });
  });
  if (Number.isFinite(o.mean)) {
    const xm = x(o.mean);
    el("line", { x1: xm, x2: xm, y1: m.t - 4, y2: H - m.b, stroke: C.ink, "stroke-width": 1.5, "stroke-dasharray": "4 3" }, g);
    const right = xm < (m.l + W - m.r) / 2;
    text(g, xm + (right ? 4 : -4), m.t - 6, t("chart.mean"), { "text-anchor": right ? "start" : "end", fill: C.ink });
  }
  const xt = niceTicks(x0, x1, Math.max(3, Math.floor((W - m.l - m.r) / 70)));
  const xfmt = o.integer ? (k) => fmt(k, 0) : (o.fmtTick || tickFormat(xt.step));
  axisX(g, x, H - m.b, m.l, W - m.r, o.integer ? { values: xt.values.filter((k) => Number.isInteger(k)) } : xt, xfmt, o.xLabel);
  yLabel(g, 4, 10, t("chart.repsAxis"));
  return svg;
}

// ------------------------------------------------------------ line chart --
function valueAt(s, xv) {
  const p = s.points;
  if (!p.length) return null;
  if (xv < p[0].x || xv > p[p.length - 1].x) return null;
  let lo = 0, hi = p.length - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (p[mid].x <= xv) lo = mid; else hi = mid; }
  if (s.step) return p[p[hi].x <= xv ? hi : lo].y;
  const a = p[lo], b = p[hi];
  if (b.x === a.x) return b.y;
  return a.y + (xv - a.x) / (b.x - a.x) * (b.y - a.y);
}

/**
 * series: [{label, color, points: [{x, y, lo, hi}], step, dash, width,
 *           markers, errorBars, endLabel}]
 * o: {height, xLabel, yLabel, xMin, xMax, yMin, yMax, xInteger, fmtX, fmtY,
 *     snap, vlines: [{x, label}], hlines: [{y, label}], segments: [{x0, x1, y, color}],
 *     rings: [{x, y, color}], events: {times, end}, legend: [{label, color, kind}],
 *     tipTitle(x), tipValue(series, point|value)}
 */
export function lineChart(host, series, o = {}) {
  const W = widthOf(host), H = o.height || 230;
  const ends = series.filter((s) => s.endLabel);
  const m = { l: 50, r: ends.length ? Math.min(150, 22 + Math.max(...ends.map((s) => s.endLabel.length)) * 6.2) : 16, t: (o.events ? 46 : 14) + (o.legend ? 18 : 0), b: 38 };
  const svg = newSvg(host, W, H, o.label);
  const all = series.flatMap((s) => s.points);
  const xs = all.map((p) => p.x);
  let [x0, x1] = extent(xs);
  if (o.xMin != null) x0 = o.xMin;
  if (o.xMax != null) x1 = o.xMax;
  if (!(x1 > x0)) { x0 -= 0.5; x1 += 0.5; }
  const ys = all.flatMap((p) => [p.y, p.lo, p.hi]).concat((o.hlines || []).map((l) => l.y));
  let [y0, y1] = padDomain(...extent(ys), 0.06);
  if (o.yMin != null) y0 = o.yMin;              // fixed lower end (e.g. 0)
  if (o.yMax != null) y1 = o.yMax;              // fixed upper end
  if (o.yFloor != null) y0 = Math.max(y0, o.yFloor); // clip, keep data-driven otherwise
  if (o.yCeil != null) y1 = Math.min(y1, o.yCeil);
  if (!(y1 > y0)) y1 = y0 + 1;
  const pad = o.xPad ? (x1 - x0) * o.xPad : 0;
  const x = scale(x0 - pad, x1 + pad, m.l, W - m.r), y = scale(y0, y1, H - m.b, m.t);
  const g = el("g", {}, svg);
  if (o.legend) svgLegend(g, m.l, 12, o.legend, W - m.r);
  const yt = niceTicks(y0, y1, Math.max(3, Math.floor((H - m.t - m.b) / 45)));
  gridY(g, y, m.l, W - m.r, yt, o.fmtTick || tickFormat(yt.step));
  const clip = nextId("clip");
  el("rect", { x: m.l, y: m.t - 2, width: W - m.l - m.r, height: H - m.b - m.t + 4 }, el("clipPath", { id: clip }, el("defs", {}, svg)));
  const plot = el("g", { "clip-path": `url(#${clip})` }, g);

  for (const l of o.vlines || []) {
    const xx = x(l.x);
    el("line", { x1: xx, x2: xx, y1: m.t, y2: H - m.b, stroke: l.color || C.muted, "stroke-dasharray": "3 3" }, plot);
    if (l.label) text(g, xx + 3, m.t + 9, l.label, { fill: C.mutedInk });
  }
  for (const l of o.hlines || []) {
    const yy = y(l.y);
    el("line", { x1: m.l, x2: W - m.r, y1: yy, y2: yy, stroke: l.color || C.muted, "stroke-dasharray": "5 4" }, plot);
    if (l.label) {
      if (l.pos === "left") text(g, m.l + 4, yy + 14, l.label, { fill: C.mutedInk });
      else if (l.pos === "below") text(g, W - m.r - 12, yy + 14, l.label, { "text-anchor": "end", fill: C.mutedInk });
      else text(g, W - m.r - 4, yy - 4, l.label, { "text-anchor": "end", fill: C.mutedInk });
    }
  }
  for (const s of o.segments || []) {
    el("line", { x1: x(s.x0), x2: x(s.x1), y1: y(s.y) + (s.dy || 0), y2: y(s.y) + (s.dy || 0), stroke: s.color, "stroke-width": 4, "stroke-linecap": "round", "stroke-opacity": 0.75 }, plot);
  }
  if (o.events) {
    const ey = 14 + (o.legend ? 18 : 0);
    el("line", { x1: x(0), x2: x(o.events.end), y1: ey, y2: ey, stroke: C.muted }, g);
    for (const tv of o.events.times) el("line", { x1: x(tv), x2: x(tv), y1: ey - 6, y2: ey + 6, stroke: C.ink, "stroke-width": 1 }, g);
    el("line", { x1: x(o.events.end), x2: x(o.events.end), y1: ey - 8, y2: ey + 8, stroke: C.mutedInk, "stroke-width": 2 }, g);
    if (o.events.label) text(g, m.l - 6, ey + 4, o.events.label, { "text-anchor": "end" });
  }
  for (const s of series) {
    const pts = s.points.filter((p) => Number.isFinite(p.y));
    if (s.band) {
      const b = pts.filter((p) => Number.isFinite(p.lo) && Number.isFinite(p.hi));
      if (b.length > 1) el("path", { d: "M" + b.map((p) => `${x(p.x)},${y(p.hi)}`).join("L") + "L" + b.slice().reverse().map((p) => `${x(p.x)},${y(p.lo)}`).join("L") + "Z", fill: s.color, "fill-opacity": 0.13 }, plot);
    }
    if (s.errorBars) {
      for (const p of pts) if (Number.isFinite(p.lo) && Number.isFinite(p.hi)) {
        const xx = x(p.x);
        el("line", { x1: xx, x2: xx, y1: y(p.lo), y2: y(p.hi), stroke: s.color, "stroke-width": 2, "stroke-opacity": 0.5 }, plot);
        el("line", { x1: xx - 4, x2: xx + 4, y1: y(p.lo), y2: y(p.lo), stroke: s.color, "stroke-opacity": 0.6 }, plot);
        el("line", { x1: xx - 4, x2: xx + 4, y1: y(p.hi), y2: y(p.hi), stroke: s.color, "stroke-opacity": 0.6 }, plot);
      }
    }
    if (pts.length && !s.noLine) {
      let d;
      if (s.step) {
        d = `M${x(pts[0].x)},${y(pts[0].y)}`;
        for (let i = 1; i < pts.length; i++) d += `H${x(pts[i].x)}V${y(pts[i].y)}`;
        if (s.stepTo != null) d += `H${x(s.stepTo)}`;
      } else d = "M" + pts.map((p) => `${x(p.x).toFixed(2)},${y(p.y).toFixed(2)}`).join("L");
      el("path", { d, fill: "none", stroke: s.color, "stroke-width": s.width || 2, "stroke-dasharray": s.dash || null, "stroke-linejoin": "round" }, plot);
    }
    if (s.markers) for (const p of pts) el("circle", { cx: x(p.x), cy: y(p.y), r: 3.2, fill: s.color }, plot);
  }
  for (const r of o.rings || []) el("circle", { cx: x(r.x), cy: y(r.y), r: 6, fill: "none", stroke: r.color || C.ink, "stroke-width": 2 }, plot);

  // direct labels at the right end, pushed apart
  if (ends.length) {
    const labs = ends.map((s) => {
      const p = s.points.filter((q) => Number.isFinite(q.y));
      const last = p[p.length - 1];
      return { s, yy: last ? Math.min(H - m.b, Math.max(m.t, y(last.y))) : null };
    }).filter((l) => l.yy !== null).sort((a, b) => a.yy - b.yy);
    for (let i = 1; i < labs.length; i++) if (labs[i].yy - labs[i - 1].yy < 13) labs[i].yy = labs[i - 1].yy + 13;
    for (const l of labs) text(g, W - m.r + 6, l.yy + 4, l.s.endLabel, { fill: l.s.labelColor || C.ink, "font-weight": 600 });
  }

  const xt = o.xInteger
    ? { values: niceTicks(x0, x1, Math.min(10, Math.max(2, Math.round(x1 - x0)))).values.filter(Number.isInteger) }
    : niceTicks(x0, x1, Math.max(3, Math.floor((W - m.l - m.r) / 80)));
  axisX(g, x, H - m.b, m.l, W - m.r, xt, o.fmtX || tickFormat(xt.step || 1), o.xLabel);
  yLabel(g, 4, (o.events ? 46 : 14) + (o.legend ? 18 : 0) - 6, o.yLabel);

  // hover
  const cross = el("line", { y1: m.t, y2: H - m.b, stroke: C.mutedInk, "stroke-width": 1, visibility: "hidden", class: "no-export" }, g);
  const dots = series.map((s) => el("circle", { r: 4, fill: C.surface, stroke: s.color, "stroke-width": 2, visibility: "hidden", class: "no-export" }, g));
  const snapXs = [...new Set(xs)].sort((a, b) => a - b);
  const overlay = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent", class: "no-export" }, svg);
  overlay.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    let xv = x.invert((e.clientX - r.left) * (W / r.width));
    if (o.snap && snapXs.length) xv = snapXs.reduce((a, b) => (Math.abs(b - xv) < Math.abs(a - xv) ? b : a));
    const xx = x(xv);
    cross.setAttribute("x1", xx); cross.setAttribute("x2", xx); cross.setAttribute("visibility", "visible");
    let html = `<b>${o.tipTitle ? o.tipTitle(xv) : fmtSig(xv)}</b>`;
    series.forEach((s, i) => {
      let p = null, val;
      if (o.snap) { p = s.points.find((q) => q.x === xv); val = p ? p.y : null; } else val = valueAt(s, xv);
      if (!Number.isFinite(val)) { dots[i].setAttribute("visibility", "hidden"); return; }
      dots[i].setAttribute("cx", xx); dots[i].setAttribute("cy", y(val));
      dots[i].setAttribute("visibility", val >= y0 && val <= y1 ? "visible" : "hidden");
      const shown = o.tipValue ? o.tipValue(s, p, val) : (o.fmtY ? o.fmtY(val) : fmtSig(val));
      html += `<div class="t-row">${swatch(s.color)}<span>${s.label ? s.label + ": " : ""}<b>${shown}</b></span></div>`;
    });
    tip(e, html);
  });
  overlay.addEventListener("pointerleave", () => {
    cross.setAttribute("visibility", "hidden");
    dots.forEach((d) => d.setAttribute("visibility", "hidden"));
    untip();
  });
  return svg;
}

// ------------------------------------------------------- stacked areas ---
/** grid: x values; layers: [{label, color, values}] stacked bottom-up. */
export function stackedArea(host, grid, layers, o = {}) {
  const W = widthOf(host), H = o.height || 200;
  const m = { l: 44, r: 14, t: 30, b: 38 };
  const svg = newSvg(host, W, H, o.label);
  const tot = grid.map((_, i) => layers.reduce((s, l) => s + (l.values[i] || 0), 0));
  const ymax = Math.max(o.yMin || 0, ...tot) * 1.1 || 1;
  const x = scale(grid[0], grid[grid.length - 1], m.l, W - m.r), y = scale(0, ymax, H - m.b, m.t);
  const g = el("g", {}, svg);
  svgLegend(g, m.l, 12, layers.map((l) => ({ label: l.label, color: l.color, opacity: 0.85 })), W - m.r);
  const yt = niceTicks(0, ymax, 3);
  gridY(g, y, m.l, W - m.r, yt, o.fmtTick || tickFormat(yt.step));
  const base = grid.map(() => 0);
  for (const l of layers) {
    const top = base.map((b, i) => b + (l.values[i] || 0));
    let d = `M${x(grid[0])},${y(base[0])}`;
    for (let i = 0; i < grid.length; i++) d += `L${x(grid[i]).toFixed(2)},${y(top[i]).toFixed(2)}`;
    for (let i = grid.length - 1; i >= 0; i--) d += `L${x(grid[i]).toFixed(2)},${y(base[i]).toFixed(2)}`;
    el("path", { d: d + "Z", fill: l.color, "fill-opacity": 0.85, stroke: "none" }, g);
    top.forEach((v, i) => { base[i] = v; });
  }
  for (const l of o.hlines || []) {
    el("line", { x1: m.l, x2: W - m.r, y1: y(l.y), y2: y(l.y), stroke: C.mutedInk, "stroke-dasharray": "5 4" }, g);
    if (l.label) text(g, W - m.r - 4, y(l.y) - 4, l.label, { "text-anchor": "end" });
  }
  const xt = niceTicks(grid[0], grid[grid.length - 1], Math.max(3, Math.floor((W - m.l - m.r) / 80)));
  axisX(g, x, H - m.b, m.l, W - m.r, xt, tickFormat(xt.step), o.xLabel);
  const cross = el("line", { y1: m.t, y2: H - m.b, stroke: C.mutedInk, visibility: "hidden", class: "no-export" }, g);
  const overlay = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent", class: "no-export" }, svg);
  overlay.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const xv = x.invert((e.clientX - r.left) * (W / r.width));
    let i = 0, best = Infinity;
    grid.forEach((gv, k) => { const d = Math.abs(gv - xv); if (d < best) { best = d; i = k; } });
    cross.setAttribute("x1", x(grid[i])); cross.setAttribute("x2", x(grid[i])); cross.setAttribute("visibility", "visible");
    let html = `<b>${o.tipTitle ? o.tipTitle(grid[i]) : fmtSig(grid[i])}</b>`;
    for (const l of layers.slice().reverse()) html += `<div class="t-row">${swatch(l.color, 0.85)}<span>${l.label}: <b>${fmt(l.values[i], 2)}</b></span></div>`;
    tip(e, html);
  });
  overlay.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); untip(); });
  return svg;
}

// ------------------------------------------------------------- dot plot --
/** One dot per item (e.g. device), with a reference line (e.g. fleet mean). */
export function dotPlot(host, values, o = {}) {
  const W = widthOf(host), H = o.height || 200;
  const m = { l: 50, r: 14, t: 18, b: 38 };
  const svg = newSvg(host, W, H, o.label);
  const n = values.length;
  const [lo, hi] = padDomain(...extent(values.concat(Number.isFinite(o.ref) ? [o.ref] : [])), 0.12);
  const x = scale(0.5, n + 0.5, m.l, W - m.r), y = scale(lo, hi, H - m.b, m.t);
  const g = el("g", {}, svg);
  const yt = niceTicks(lo, hi, 4);
  gridY(g, y, m.l, W - m.r, yt, o.fmtTick || tickFormat(yt.step));
  if (Number.isFinite(o.ref)) {
    el("line", { x1: m.l, x2: W - m.r, y1: y(o.ref), y2: y(o.ref), stroke: C.ink, "stroke-dasharray": "4 3", "stroke-width": 1.3 }, g);
    if (o.refLabel) text(g, W - m.r - 2, y(o.ref) - 5, o.refLabel, { "text-anchor": "end", fill: C.ink });
  }
  const step = Math.max(1, Math.ceil(n / Math.max(4, Math.floor((W - m.l - m.r) / 28))));
  values.forEach((v, i) => {
    const cx = x(i + 1), cy = y(v);
    el("line", { x1: cx, x2: cx, y1: H - m.b, y2: cy, stroke: C.rule }, g);
    const c = el("circle", { cx, cy, r: n > 60 ? 2.5 : 4, fill: o.color || C.blue }, g);
    c.addEventListener("pointermove", (e) => tip(e, o.tip ? o.tip(i, v) : `${i + 1}: <b>${fmtSig(v)}</b>`));
    c.addEventListener("pointerleave", untip);
    if ((i + 1) % step === 0 || i === 0) text(g, cx, H - m.b + 16, String(i + 1), { "text-anchor": "middle" });
  });
  el("line", { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: C.muted }, g);
  if (o.xLabel) text(g, W - m.r, H - m.b + 30, o.xLabel, { "text-anchor": "end" });
  if (o.yLabel) yLabel(g, 4, 10, o.yLabel);
  return svg;
}

// ---------------------------------------------------------- chart cards --
/** A titled card with SVG/PNG export buttons for the chart in its body. */
export function chartCard(parent, { title, caption, file, cls }) {
  const body = h("div", { class: "body" });
  const cap = h("p", { class: "cap" });
  if (caption) cap.innerHTML = caption;
  const svgOf = () => body.querySelector("svg");
  const head = h("h3", { text: title });
  const tools = h("div", { class: "tools" },
    h("button", { type: "button", class: "small ghost", title: t("export.svg"), onclick: () => svgOf() && exportSvg(svgOf(), file, head.textContent) }, "SVG"),
    h("button", { type: "button", class: "small ghost", title: t("export.png"), onclick: () => svgOf() && exportPng(svgOf(), file, head.textContent) }, "PNG"));
  const card = h("div", { class: "chart " + (cls || "") }, h("div", { class: "chart-head" }, head, tools), body, cap);
  parent.append(card);
  return { card, body, cap };
}

export function svgString(svg, title) {
  const W = +svg.getAttribute("width"), H = +svg.getAttribute("height");
  const top = title ? 30 : 8, side = 10;
  const out = el("svg", {
    xmlns: NS, width: W + 2 * side, height: H + top + 10, viewBox: `0 0 ${W + 2 * side} ${H + top + 10}`,
    "font-family": FONT, "font-size": 11, style: "font-variant-numeric: tabular-nums",
  });
  el("rect", { width: "100%", height: "100%", fill: C.paper }, out);
  if (title) text(out, side, 20, title, { fill: C.ink, "font-size": 14, "font-weight": 650 });
  const inner = svg.cloneNode(true);
  inner.querySelectorAll(".no-export").forEach((n) => n.remove());
  inner.setAttribute("x", side);
  inner.setAttribute("y", top);
  out.appendChild(inner);
  return '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(out);
}
const safeName = (s) => (s || "farofa-chart").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase();
export function exportSvg(svg, file, title) {
  download(safeName(file || title) + ".svg", svgString(svg, title), "image/svg+xml");
}
export function exportPng(svg, file, title, ratio = 2) {
  const s = svgString(svg, title);
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = img.width * ratio;
    canvas.height = img.height * ratio;
    const ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    ctx.drawImage(img, 0, 0);
    canvas.toBlob((blob) => blob && download(safeName(file || title) + ".png", blob, "image/png"), "image/png");
  };
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(s);
}
