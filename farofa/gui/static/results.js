// Results dashboard: metric cards with intervals, per-replication
// histograms, per-device availability, devices down over time and, for
// exponential times, the exact Markov-chain check.
import { $, S, download, h, on, toast } from "./core.js";
import { C, STATE, chartCard, dotPlot, histogram, responsive, stackedArea } from "./charts.js";
import { fmt, fmtCI, fmtH, fmtHn, fmtInt, fmtPct, fmtSig, t } from "./i18n.js";

export function describeRun(r) {
  const parts = [];
  parts.push(r.system === "fleet"
    ? t("run.fleet", { n: fmtInt(r.n_devices), k: fmtInt(r.n_teams) })
    : t("run.device"));
  parts.push(`T = ${fmtH(r.mission_time)}`);
  parts.push(t("run.reps", { n: fmtInt(r.reps) }));
  parts.push(t("run.seed", { s: r.seed }));
  return parts.join(" · ");
}

function card(parent, { key, value, sub, color, hero, title }) {
  const k = h("div", { class: "k" }, color ? h("i", { style: `background:${color}` }) : null, t(key));
  const c = h("div", { class: "card" + (hero ? " hero" : ""), title: title || null }, k, h("div", { class: "v", html: value }), sub ? h("div", { class: "s", html: sub }) : null);
  parent.append(c);
}
const ciText = (ci, f) => (ci && Number.isFinite(ci[0]) ? `${t("ci95")} ${fmtCI(ci, f)}` : t("ci.na"));

/** Mean number of devices waiting / in repair in each time bin: the time
 *  each state occupies inside the bin, averaged over the traced reps. */
export function occupancy(r, bins = 120) {
  const T = r.mission_time, w = T / bins;
  const grid = Array.from({ length: bins }, (_, i) => (i + 0.5) * w);
  const wait = new Float64Array(bins), rep = new Float64Array(bins);
  for (const tr of r.traces) {
    for (let i = 0; i < tr.state.length; i++) {
      const s = tr.state[i];
      if (!s) continue;
      const target = s === 1 ? wait : rep, a = tr.start[i], b = tr.end[i];
      for (let k = Math.floor(a / w); k < bins && k * w < b; k++) {
        const overlap = Math.min(b, (k + 1) * w) - Math.max(a, k * w);
        if (overlap > 0) target[k] += overlap / w;
      }
    }
  }
  const n = r.traces.length || 1;
  return { grid, wait: Array.from(wait, (v) => v / n), repair: Array.from(rep, (v) => v / n) };
}

// --------------------------------------------- exact check (exponential) --
function lgam(x) {
  const c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  x -= 1;
  let a = c[0];
  const tt = x + 7.5;
  for (let i = 1; i < 9; i++) a += c[i] / (x + i);
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(tt) - tt + Math.log(a);
}
/** Finite-source queue N devices / K teams with exponential times: the
 *  steady state and the expected time average over [0, T] from all-up
 *  (uniformization). Adapted from the owner's repair-simulation page. */
export function ctmc(N, K, lam, mu, T) {
  const up = (n) => lam * (N - n), dn = (n) => mu * Math.min(n, K);
  const stats = (p) => {
    let A = 0, U = 0, Lq = 0, thr = 0;
    for (let n = 0; n <= N; n++) { A += p[n] * (N - n) / N; U += p[n] * Math.min(n, K) / K; Lq += p[n] * Math.max(0, n - K); thr += p[n] * dn(n); }
    return { A, U, Lq, W: thr > 0 ? Lq / thr : 0 };
  };
  const w = [1];
  for (let n = 1; n <= N; n++) w[n] = w[n - 1] * up(n - 1) / dn(n);
  const s = w.reduce((a, b) => a + b, 0);
  const ss = stats(w.map((x) => x / s));
  let L = 0;
  for (let n = 0; n <= N; n++) L = Math.max(L, up(n) + dn(n));
  const m = L * T;
  let fin = null;
  if (m * (N + 1) < 3e7) {
    let v = new Float64Array(N + 1), nv = new Float64Array(N + 1);
    const acc = new Float64Array(N + 1);
    v[0] = 1;
    let cdf = 0;
    const lm = Math.log(m);
    for (let k = 0; ; k++) {
      cdf += Math.exp(-m + k * lm - lgam(k + 1));
      const surv = Math.max(0, 1 - cdf);
      for (let n = 0; n <= N; n++) acc[n] += v[n] * surv;
      if (k > m && surv < 1e-15) break;
      if (k > m + 50 * Math.sqrt(m) + 100) break;
      nv.fill(0);
      for (let n = 0; n <= N; n++) {
        const a = up(n) / L, b = dn(n) / L;
        nv[n] += v[n] * (1 - a - b);
        if (n < N) nv[n + 1] += v[n] * a;
        if (n > 0) nv[n - 1] += v[n] * b;
      }
      [v, nv] = [nv, v];
    }
    fin = stats(Array.from(acc, (x) => x / m));
    fin.F = lam * N * T * fin.A;
  }
  return { ss, fin };
}

function analyticBlock(parent, r) {
  const sc = r.scenario;
  if (sc.failure.dist !== "exponential" || sc.repair.dist !== "exponential") return;
  const lam = sc.failure.params.rate, mu = sc.repair.params.rate;
  const N = r.n_devices, K = r.n_teams, T = r.mission_time, fleet = r.system === "fleet";
  const a = ctmc(N, K, lam, mu, T);
  const M = r.metrics;
  const inCI = (x, ci) => ci && Number.isFinite(ci[0]) && Number.isFinite(x) && x >= ci[0] && x <= ci[1];
  const chk = (x, ci) => (a.fin ? (inCI(x, ci) ? `<span class="ok">✓ ${t("yes")}</span>` : `<span class="no">✗ ${t("no")}</span>`) : "—");
  const rows = [
    [t("m.availability"), `${fmt(M.availability.value, 5)} <span class="ci">${fmtCI(M.availability.ci, 5)}</span>`, a.fin ? fmt(a.fin.A, 5) : "—", fmt(a.ss.A, 5), chk(a.fin && a.fin.A, M.availability.ci)],
    [t("m.failures"), `${fmt(M.failures.value, 2)} <span class="ci">${fmtCI(M.failures.ci, 2)}</span>`, a.fin ? fmt(a.fin.F, 2) : "—", fmt(lam * N * T * a.ss.A, 2), chk(a.fin && a.fin.F, M.failures.ci)],
  ];
  if (fleet) {
    rows.push([t("m.utilization"), `${fmt(M.utilization.value, 4)} <span class="ci">${fmtCI(M.utilization.ci, 4)}</span>`, a.fin ? fmt(a.fin.U, 4) : "—", fmt(a.ss.U, 4), chk(a.fin && a.fin.U, M.utilization.ci)]);
    rows.push([t("m.wait"), `${fmtH(M.mean_wait.value)} <span class="ci">${fmtCI(M.mean_wait.ci, 2, fmtHn)}</span>`, "—", fmtH(a.ss.W), "—"]);
  }
  rows.push(["MTTF", fmtH(M.mttf.value), "—", fmtH(1 / lam), "—"], ["MTTR", fmtH(M.mttr.value), "—", fmtH(1 / mu), "—"]);
  const box = h("details", { class: "box", open: true });
  box.append(h("summary", { text: t("exact.title") }));
  box.append(h("p", { class: "note", html: t(fleet ? "exact.note.fleet" : "exact.note.device", { N, K, lam: fmtSig(lam), mu: fmtSig(mu) }) + (a.fin ? "" : " " + t("exact.long")) }));
  const table = h("table", { class: "data" });
  table.innerHTML = `<thead><tr><th>${t("exact.q")}</th><th>${t("exact.sim")}</th><th>${t("exact.mission")}</th><th>${t("exact.ss")}</th><th>${t("exact.inci")}</th></tr></thead><tbody>${rows.map((c) => `<tr>${c.map((x) => `<td>${x}</td>`).join("")}</tr>`).join("")}</tbody>`;
  box.append(h("div", { class: "tablebox" }, table));
  parent.append(box);
}

// ----------------------------------------------------------------- render --
const histCap = (r) => t("hist.cap", { n: fmtInt(r.reps) }) + (r.per_rep_shown < r.reps ? " " + t("hist.part", { k: fmtInt(r.per_rep_shown) }) : "");

export function renderDashboard() {
  const P = $("panel-dash");
  P.replaceChildren();
  const r = S.run;
  if (!r) {
    P.append(h("div", { class: "empty" }, h("b", { text: t("dash.empty.title") }), t("dash.empty.body")));
    return;
  }
  const fleet = r.system === "fleet", M = r.metrics;
  const exportLink = h("button", { type: "button", class: "small", text: t("dash.export"), title: t("dash.export.title"), onclick: async () => {
    try {
      const res = await fetch(`/api/jobs/${S.runJob}/export`);
      if (!res.ok) throw new Error(String(res.status));
      download(`farofa-result-${r.seed}.json`, await res.blob());
    } catch { toast(t("dash.export.gone")); }
  } });
  P.append(h("div", { class: "headline" }, h("h2", { text: t("dash.title") }), h("span", { class: "meta", text: describeRun(r) }), h("span", { class: "grow" }), exportLink));
  if (S.runVer !== S.modelVer) P.append(h("div", { class: "banner warn", text: t("stale.run") }));

  const cards = h("div", { class: "cards" });
  card(cards, { key: "m.availability", hero: true, color: STATE.up, value: fmt(M.availability.value, 4), sub: ciText(M.availability.ci, 4), title: t("m.availability.title") });
  card(cards, { key: "m.failures", value: fmt(M.failures.value, 2), sub: ciText(M.failures.ci, 2) + (M.failures.std != null ? ` · ${t("sd")} ${fmt(M.failures.std, 2)}` : "") });
  card(cards, { key: "m.mttf", value: fmtH(M.mttf.value), sub: t("m.mttf.sub") });
  card(cards, { key: "m.mttr", value: fmtH(M.mttr.value), sub: t(fleet ? "m.mttr.sub.fleet" : "m.mttr.sub") });
  card(cards, { key: "m.rate", value: `${fmtSig(M.failure_rate.value, 3)} <small>/h</small>`, sub: t(fleet ? "m.rate.sub.fleet" : "m.rate.sub") });
  if (fleet) {
    card(cards, { key: "m.utilization", color: STATE.repair, value: fmtPct(M.utilization.value, 1), sub: M.utilization.ci && Number.isFinite(M.utilization.ci[0]) ? `${t("ci95")} [${fmtPct(M.utilization.ci[0], 1)}${t("sep")} ${fmtPct(M.utilization.ci[1], 1)}]` : t("ci.na") });
    card(cards, { key: "m.wait", color: STATE.waiting, value: fmtH(M.mean_wait.value), sub: (M.mean_wait.ci && Number.isFinite(M.mean_wait.ci[0]) ? `${t("ci95")} ${fmtCI(M.mean_wait.ci, 2, fmtHn)} h` : t("ci.na")) + ` · ${t("m.wait.sub")}`, title: t("m.wait.title") });
    card(cards, { key: "m.pwait", color: STATE.waiting, value: M.p_wait.value == null ? "—" : fmtPct(M.p_wait.value, 1), sub: t("m.pwait.sub") });
    card(cards, { key: "m.maxqueue", color: STATE.waiting, value: fmtInt(M.max_queue.value), sub: t("m.maxqueue.sub", { v: fmt(M.max_queue.mean, 1) }) });
  }
  P.append(cards);

  const grid = h("div", { class: "grid" });
  P.append(grid);
  const per = r.per_rep;
  {
    const c = chartCard(grid, { title: t("hist.avail"), file: "availability-histogram", caption: histCap(r) });
    responsive(c.body, () => histogram(c.body, per.availability, { color: C.blue, mean: M.availability.value, ci: M.availability.ci, xLabel: t("axis.avail"), label: t("hist.avail"), fmtX: (v) => fmt(v, 4) }));
  }
  {
    const c = chartCard(grid, { title: t("hist.failures"), file: "failures-histogram", caption: histCap(r) });
    responsive(c.body, () => histogram(c.body, per.failures, { color: C.blue, integer: true, mean: M.failures.value, ci: M.failures.ci, xLabel: t("axis.failures"), label: t("hist.failures"), unit: t("unit.failures") }));
  }
  if (fleet) {
    {
      const c = chartCard(grid, { title: t("hist.util"), file: "utilization-histogram", caption: histCap(r) });
      responsive(c.body, () => histogram(c.body, per.utilization, { color: C.wine, mean: M.utilization.value, ci: M.utilization.ci, xLabel: t("axis.util"), label: t("hist.util"), fmtX: (v) => fmtPct(v, 1), fmtTick: (v) => fmtPct(v, 0) }));
    }
    {
      const waits = per.mean_wait.filter((v) => v !== null);
      const c = chartCard(grid, { title: t("hist.wait"), file: "wait-histogram", caption: t("hist.wait.cap", { n: fmtInt(waits.length) }) });
      responsive(c.body, () => histogram(c.body, waits, { color: C.amber, mean: M.mean_wait.value, ci: M.mean_wait.ci, xLabel: t("axis.wait"), label: t("hist.wait"), fmtX: (v) => fmt(v, 2) }));
    }
    {
      const c = chartCard(grid, { title: t("dev.title"), file: "per-device-availability", caption: t("dev.cap") });
      responsive(c.body, () => dotPlot(c.body, r.per_device.availability, {
        color: C.blue, ref: M.availability.value, refLabel: t("dev.ref"), xLabel: t("axis.device"), label: t("dev.title"),
        tip: (i, v) => `${t("device.n", { n: i + 1 })}<br>${t("m.availability")}: <b>${fmt(v, 4)}</b><br>${t("dev.failures")}: <b>${fmt(r.per_device.failures[i], 2)}</b>`,
      }));
    }
  }
  if (r.traces && r.traces.length) {
    const occ = occupancy(r);
    const c = chartCard(grid, { title: t(fleet ? "occ.title" : "occ.title.device"), file: "devices-down-over-time", cls: fleet ? "" : "", caption: t("occ.cap", { k: r.traces.length }) });
    const layers = [{ label: t("state.repair"), color: STATE.repair, values: occ.repair }];
    if (fleet) layers.push({ label: t("state.waiting"), color: STATE.waiting, values: occ.wait });
    responsive(c.body, () => stackedArea(c.body, occ.grid, layers, {
      xLabel: t("axis.time"), label: t("occ.title"), yMin: fleet ? r.n_teams : 1,
      hlines: fleet ? [{ y: r.n_teams, label: t("occ.k", { k: r.n_teams }) }] : [],
      tipTitle: (x) => `t = ${fmtH(x)}`,
    }));
  }
  analyticBlock(P, r);
}

export function initResults() {
  on("run", renderDashboard);
  on("lang", renderDashboard);
  on("model", () => {
    const P = $("panel-dash");
    if (!S.run) return;
    const stale = P.querySelector(".banner.warn");
    if (S.runVer !== S.modelVer && !stale) P.querySelector(".headline").after(h("div", { class: "banner warn", text: t("stale.run") }));
  });
  renderDashboard();
}
