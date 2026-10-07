// Estimation view: failure times in, Laplace trend test, the power law and
// Weibull GRP fits (Kijima I/II, renewal) with AIC, observed cumulative
// failures against each fitted curve, the profile likelihood of q, and a
// button that sends a fit to the simulation model.
import { $, S, api, emit, h, on, toast } from "./core.js";
import { C, chartCard, lineChart, responsive } from "./charts.js";
import { fmt, fmtH, fmtInt, fmtP, fmtSig, has, parseNum, t } from "./i18n.js";
import { setFailureFromFit } from "./model.js";

const COLORS = { power_law: C.blue, grp1: C.amber, grp2: C.wine, renewal: C.teal };
const E = { kind: "cumulative", curve: "mean", busy: false, dataset: null };

function setKind(kind) {
  E.kind = kind;
  for (const b of document.querySelectorAll("#est-kind [data-kind]")) b.setAttribute("aria-checked", b.dataset.kind === kind ? "true" : "false");
}

function countPreview() {
  const n = ($("est-text").value.match(/-?\d+(?:[.,]\d+)?(?:e[-+]?\d+)?/gi) || []).length;
  $("est-count").textContent = n ? t("est.count", { n: fmtInt(n) }) : "";
}

function status(text, bad) {
  const el = $("est-status");
  el.textContent = text || "";
  el.classList.toggle("bad", !!bad);
}

async function fit() {
  if (E.busy) return;
  const text = $("est-text").value;
  const endRaw = $("est-end").value.trim();
  const end = endRaw === "" ? null : (Number.isFinite(parseNum(endRaw)) ? parseNum(endRaw) : endRaw);
  E.busy = true;
  $("est-run").disabled = true;
  status(t("est.fitting"));
  try {
    S.est = await api("/api/estimate", { text, end_time: end, intervals: E.kind === "intervals" });
    S.est.dataset = E.dataset;
    status(t("est.read", { n: fmtInt(S.est.n) }) + (S.est.skipped ? " " + t("est.skipped", { n: S.est.skipped }) : ""));
    render();
  } catch (e) {
    const b = e.body || {};
    const msg = b.code && b.code !== "engine" && has(`err.est.${b.code}`) ? t(`err.est.${b.code}`, { detail: b.detail }) : (b.message || e.message);
    status(msg, true);
  } finally {
    E.busy = false;
    $("est-run").disabled = false;
  }
}

const modelName = (key) => t(`est.m.${key}`);

function laplaceVerdict(u, p) {
  if (!(p < 0.05)) return t("est.lap.none");
  return u > 0 ? t("est.lap.worse") : t("est.lap.better");
}

function render() {
  const P = $("est-results");
  P.replaceChildren();
  const R = S.est;
  if (!R) {
    P.append(h("div", { class: "headline", style: "margin-top: 14px" }, h("h2", { text: t("est.heading") })));
    P.append(h("div", { class: "empty" }, h("b", { text: t("est.empty.title") }), t("est.empty.body")));
    return;
  }
  const ds = R.dataset ? S.meta.datasets.find((d) => d.key === R.dataset) : null;
  P.append(h("div", { class: "headline", style: "margin-top: 14px" },
    h("h2", { text: ds ? `${t("est.heading")}: ${ds.name}` : t("est.heading") }),
    h("span", { class: "meta", text: t(R.failure_truncated ? "est.window.ft" : "est.window.tt", { n: fmtInt(R.n), T: fmtH(R.end_time) }) })));
  if (ds) P.append(h("p", { class: "note", text: t(`est.ds.${ds.key}.note`) + " " + t("est.source") + " " + ds.source }));

  const models = R.models, byKey = Object.fromEntries(models.map((m) => [m.key, m]));
  const best = R.best ? byKey[R.best] : null;
  const cards = h("div", { class: "cards" });
  const cardEl = (k, v, s, color, hero) => cards.append(h("div", { class: "card" + (hero ? " hero" : "") }, h("div", { class: "k" }, color ? h("i", { style: `background:${color}` }) : null, k), h("div", { class: "v", html: v }), h("div", { class: "s", html: s })));
  cardEl(t("est.c.n"), fmtInt(R.n), t("est.c.n.sub", { a: fmtH(R.times[0]), b: fmtH(R.times[R.times.length - 1]) }));
  cardEl(t("est.c.laplace"), `U = ${fmt(R.laplace.u, 2)}`, `p = ${fmtP(R.laplace.p)} · ${laplaceVerdict(R.laplace.u, R.laplace.p)}`);
  if (best) {
    const second = models.filter((m) => m.aic != null && m !== best).sort((a, b) => a.aic - b.aic)[0];
    cardEl(t("est.c.best"), t(`est.short.${best.key}`), modelName(best.key) + (second ? " · " + t("est.c.best.sub", { m: t(`est.short.${second.key}`), d: fmt(second.delta_aic, 2) }) : ""), COLORS[best.key], true);
  }
  const g1 = byKey.grp1;
  if (g1 && g1.q != null) {
    const iv = R.profile.grp1 && R.profile.grp1.interval;
    cardEl(t("est.c.q"), fmt(g1.q, 3), iv ? t("est.c.q.sub", { lo: fmt(iv[0], 2), hi: fmt(iv[1], 2) }) : "", COLORS.grp1);
  }
  P.append(cards);

  // fits table
  const table = h("table", { class: "data" });
  table.append(h("thead", {}, h("tr", {}, ...[t("est.t.model"), t("est.t.a"), t("est.t.b"), "q", t("est.t.ll"), t("est.t.k"), "AIC", "ΔAIC", ""].map((x) => h("th", { text: x })))));
  const body = h("tbody");
  for (const m of models) {
    const name = h("td", { class: "l" }, h("i", { class: "sw", style: `background:${COLORS[m.key]}` }), modelName(m.key), best === m ? h("span", { class: "tag", text: t("est.best") }) : null);
    if (m.error) {
      body.append(h("tr", {}, name, h("td", { class: "err", colspan: 8, text: `${t("est.t.error")} ${m.error}` })));
      continue;
    }
    const use = h("button", { type: "button", class: "small", text: t("est.use"), title: t("est.use.title"), onclick: () => useFit(m) });
    body.append(h("tr", { class: best === m ? "best" : "" }, name,
      h("td", { text: fmtSig(m.a, 5) }), h("td", { text: fmt(m.b, 3) }),
      h("td", { text: fmt(m.q, 3) + (m.q_fixed || m.key === "power_law" ? " " + t("est.fixed") : "") }),
      h("td", { text: fmt(m.log_likelihood, 2) }), h("td", { text: m.n_params }),
      h("td", { text: fmt(m.aic, 2) }), h("td", { text: fmt(m.delta_aic, 2) }), h("td", {}, use)));
  }
  table.append(body);
  P.append(h("div", { class: "tablebox" }, table));
  P.append(h("p", { class: "note", text: t("est.table.note") }));

  const grid = h("div", { class: "grid" });
  P.append(grid);
  const fitted = models.filter((m) => !m.error);

  // cumulative failures vs fitted curves
  const cum = chartCard(grid, { title: t("est.cum.title"), file: "cumulative-failures", cls: "span2" });
  const toggle = h("div", { class: "seg", role: "radiogroup", "aria-label": t("est.cum.mode") },
    ...["mean", "conditional"].map((k) => {
      const b = h("button", { type: "button", role: "radio", "aria-checked": E.curve === k ? "true" : "false", text: t(`est.cum.${k}`) });
      b.addEventListener("click", () => { E.curve = k; render(); });
      return b;
    }));
  cum.card.insertBefore(h("div", { class: "toolbar" }, toggle), cum.body);
  const mc = fitted.find((m) => m.mean_function && m.mean_function.method === "monte_carlo");
  cum.cap.textContent = E.curve === "mean" ? t("est.cum.cap.mean", { reps: mc ? fmtInt(mc.mean_function.reps) : "—" }) : t("est.cum.cap.cond");
  const obs = [{ x: 0, y: 0 }].concat(R.times.map((tv, i) => ({ x: tv, y: i + 1 })));
  const cumSeries = () => [{ label: t("est.observed"), color: C.ink, step: true, stepTo: R.end_time, width: 1.8, points: obs, endLabel: t("est.observed") }]
    .concat(fitted.map((m) => {
      const curve = E.curve === "mean" ? m.mean_function : m.compensator;
      return { label: modelName(m.key), color: COLORS[m.key], width: 2, dash: m.key === "renewal" ? "6 4" : null, endLabel: t(`est.short.${m.key}`), labelColor: COLORS[m.key] === C.amber ? C.ink : COLORS[m.key], points: curve.t.map((x, i) => ({ x, y: curve.m[i] })) };
    }));
  responsive(cum.body, () => lineChart(cum.body, cumSeries(), {
    height: 340, xLabel: t("axis.optime"), yLabel: t("est.cum.y"), xMin: 0, xMax: R.end_time, yMin: 0,
    events: { times: R.times, end: R.end_time, label: t("est.events") }, label: t("est.cum.title"),
    tipTitle: (x) => `t = ${fmtH(x)}`, fmtY: (v) => fmt(v, 1),
  }));

  // profile likelihood of q
  const prof = R.profile, q = prof.q;
  const profSeries = [], segs = [], rings = [];
  [["grp1", 1], ["grp2", 2]].forEach(([key], i) => {
    const pr = prof[key];
    if (!pr || pr.error || !pr.rel) return;
    profSeries.push({ label: modelName(key), color: COLORS[key], width: 2, endLabel: t(`est.short.${key}`), labelColor: COLORS[key] === C.amber ? C.ink : COLORS[key], points: q.map((x, j) => ({ x, y: pr.rel[j] })).filter((p) => Number.isFinite(p.y)) });
    if (pr.interval) segs.push({ x0: pr.interval[0], x1: pr.interval[1], y: -prof.drop, color: COLORS[key], dy: i ? 5 : -5 });
    if (pr.q_hat != null) rings.push({ x: pr.q_hat, y: 0, color: COLORS[key] });
  });
  if (profSeries.length) {
    const pc = chartCard(grid, { title: t("est.prof.title"), file: "q-profile-likelihood" });
    const iv = (key) => prof[key] && prof[key].interval ? `[${fmt(prof[key].interval[0], 3)}${t("sep")} ${fmt(prof[key].interval[1], 3)}]` : "—";
    pc.cap.textContent = t("est.prof.cap", { i1: iv("grp1"), i2: iv("grp2") });
    responsive(pc.body, () => lineChart(pc.body, profSeries, {
      height: 270, xLabel: t("est.prof.x"), yLabel: t("est.prof.y"), xMin: 0, xMax: 1, yFloor: -8, yMax: 0.6,
      hlines: [{ y: -prof.drop, label: t("est.prof.ci"), pos: "below" }], segments: segs, rings, label: t("est.prof.title"),
      tipTitle: (x) => `q = ${fmt(x, 2)}`, fmtY: (v) => fmt(v, 2),
    }));
  }

  // times between failures
  const gaps = R.times.map((tv, i) => ({ x: i + 1, y: tv - (i ? R.times[i - 1] : 0) }));
  const gc = chartCard(grid, { title: t("est.gaps.title"), file: "times-between-failures", caption: t("est.gaps.cap") });
  responsive(gc.body, () => lineChart(gc.body, [{ label: t("est.gaps.s"), color: C.blue, markers: true, noLine: true, points: gaps }], {
    height: 270, xLabel: t("est.gaps.x"), yLabel: t("est.gaps.y"), yMin: 0, xInteger: true, xPad: 0.02, label: t("est.gaps.title"),
    tipTitle: (x) => t("est.gaps.tip", { i: x }), fmtY: (v) => fmtH(v), snap: true,
  }));
  P.append(h("details", { class: "box" }, h("summary", { text: t("est.notes.title") }), h("div", { class: "note", style: "margin: 8px 0 4px", html: t("est.notes") })));
}

function useFit(m) {
  setFailureFromFit(m.distribution, S.est.end_time);
  emit("goto", "sim");
  toast(t("est.used", { m: modelName(m.key), T: fmtH(S.est.end_time) }), 9000);
}

function markDataset() {
  for (const b of document.querySelectorAll("#datasets [data-ds]")) b.setAttribute("aria-pressed", b.dataset.ds === E.dataset ? "true" : "false");
}

function loadDataset(key) {
  const ds = S.meta.datasets.find((d) => d.key === key);
  E.dataset = key;
  markDataset();
  $("est-text").value = ds.times.join(", ");
  $("est-end").value = ds.end_time == null ? "" : String(ds.end_time);
  setKind("cumulative");
  countPreview();
  fit();
}

function buildDatasets() {
  const box = $("datasets");
  box.replaceChildren(...S.meta.datasets.map((d) => h("button", { type: "button", "aria-pressed": E.dataset === d.key ? "true" : "false", dataset: { ds: d.key }, onclick: () => loadDataset(d.key) },
    h("b", { text: d.name }), h("span", { text: t(`est.ds.${d.key}`) }))));
}

export function initEstimate() {
  buildDatasets();
  setKind("cumulative");
  for (const b of document.querySelectorAll("#est-kind [data-kind]")) b.addEventListener("click", () => { setKind(b.dataset.kind); E.dataset = null; markDataset(); });
  $("est-text").addEventListener("input", () => { E.dataset = null; markDataset(); countPreview(); });
  $("est-end").addEventListener("input", () => { E.dataset = null; markDataset(); });
  $("est-text").addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") fit(); });
  $("est-run").addEventListener("click", fit);
  $("est-open").addEventListener("click", () => $("est-file").click());
  $("est-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    $("est-text").value = await file.text();
    E.dataset = null;
    countPreview();
    status(t("est.file.loaded", { name: file.name }));
  });
  on("lang", () => { buildDatasets(); countPreview(); render(); });
  render();
}
