// Scenario comparison: sweep one parameter (teams, devices, mission time or
// a distribution parameter), same seed at every point, and plot availability,
// waiting and utilization against it with confidence intervals; optional
// cost per hour to find the cheapest number of teams.
import { $, S, download, emit, h, on, startJob } from "./core.js";
import { C, chartCard, lineChart, responsive } from "./charts.js";
import { fmt, fmtCI, fmtH, fmtHn, fmtInt, fmtPct, fmtSig, parseNum, t } from "./i18n.js";
import { M, distParams, errorText, paramLabel, progressText, showProgress, toScenario } from "./model.js";
import { describeRun } from "./results.js";

const CMP = { param: null, from: "", to: "", step: "", reps: "", cTeam: "", cDown: "", ver: -1, job: null, error: "" };
const INTEGER = new Set(["n_teams", "n_devices"]);

function fields() {
  const out = [];
  if (M.system === "fleet") out.push("n_teams", "n_devices");
  out.push("mission_time");
  for (const role of ["failure", "repair"]) for (const p of distParams(M[role].dist)) out.push(`${role}.${p}`);
  return out;
}
export function fieldLabel(f) {
  if (f === "n_teams") return t("cmp.p.n_teams");
  if (f === "n_devices") return t("cmp.p.n_devices");
  if (f === "mission_time") return t("cmp.p.mission_time");
  const [role, p] = f.split(".");
  return `${t(role === "failure" ? "cmp.p.failure" : "cmp.p.repair")}: ${paramLabel(M[role].dist, p)}`;
}
function currentValue(f) {
  if (f === "n_teams") return parseNum(M.k);
  if (f === "n_devices") return parseNum(M.n);
  if (f === "mission_time") return parseNum(M.T);
  const [role, p] = f.split(".");
  return parseNum((M[role].vals[M[role].dist] || {})[p]);
}
function defaults(f) {
  const cur = currentValue(f), n = parseNum(M.n);
  const g = (v) => String(+(+v).toPrecision(6));
  if (f === "n_teams") return { from: "1", to: String(Number.isInteger(n) && n > 0 ? Math.min(n, 30) : 5), step: "1" };
  if (f === "n_devices") { const base = Number.isInteger(n) ? n : 10; return { from: String(Math.max(1, Math.round(base / 2))), to: String(base * 2), step: String(Math.max(1, Math.round(base / 4))) }; }
  if (f.endsWith(".q")) return { from: "0", to: "1", step: "0.1" };
  if (Number.isFinite(cur) && cur > 0) return { from: g(cur / 2), to: g(cur * 2), step: g(cur / 4) };
  if (Number.isFinite(cur)) return { from: g(cur - 1), to: g(cur + 1), step: "0.5" };
  return { from: "", to: "", step: "" };
}

/** Values from/to/step; returns {values} or {error}. */
export function sweepValues(f, from, to, step) {
  const a = parseNum(from), b = parseNum(to), s = parseNum(step);
  if (![a, b, s].every(Number.isFinite)) return { error: t("cmp.err.numbers") };
  if (!(s > 0)) return { error: t("cmp.err.step") };
  if (b < a) return { error: t("cmp.err.order") };
  const n = Math.floor((b - a) / s + 1e-9) + 1;
  const max = S.meta.limits.max_sweep_points;
  if (n > max) return { error: t("cmp.err.max", { max }) };
  const values = [];
  for (let i = 0; i < n; i++) values.push(+(a + i * s).toPrecision(10));
  if (INTEGER.has(f) && !values.every(Number.isInteger)) return { error: t("cmp.err.int") };
  return { values };
}

function costs() {
  const cT = parseNum(CMP.cTeam), cD = parseNum(CMP.cDown);
  const ok = Number.isFinite(cT) && cT >= 0 && Number.isFinite(cD) && cD >= 0 && (cT > 0 || cD > 0);
  return { ok, cT, cD };
}
function costOf(p, c) { return p.n_teams * c.cT + p.n_devices * (1 - p.metrics.availability.value) * c.cD; }

async function runSweep() {
  if (S.busy) return;
  const sv = sweepValues(CMP.param, CMP.from, CMP.to, CMP.step);
  if (sv.error) { CMP.error = sv.error; renderConfig(); return; }
  const reps = CMP.reps.trim() === "" ? undefined : parseNum(CMP.reps);
  const sweep = { param: CMP.param, values: sv.values };
  if (reps !== undefined) sweep.reps = Number.isFinite(reps) ? reps : CMP.reps;
  CMP.error = "";
  const ver = S.modelVer;
  const box = $("cmp-progress");
  showProgress(box, { done: 0, total: 0 });
  const job = startJob("/api/sweep", { scenario: toScenario(), sweep }, (st) => showProgress(box, st));
  S.busy = { kind: "sweep", cancel: job.cancel };
  emit("busy");
  try {
    const { result } = await job.promise;
    S.sweep = result; CMP.ver = ver;
    CMP.status = "";
  } catch (e) {
    if (e.cancelled) CMP.status = t("model.cancelled");
    else if (e.body && e.body.errors) CMP.error = e.body.errors.map((x) => `${x.value !== undefined ? fieldLabel(CMP.param) + " = " + fmtSig(x.value) + ": " : ""}${errorText(x)}`).join(" · ");
    else CMP.error = e.message || String(e);
  } finally {
    S.busy = null;
    showProgress(box, null);
    emit("busy");
    renderCompare();
  }
}

function renderConfig() {
  const box = $("cmp-config");
  if (!box) return;
  box.replaceChildren();
  const fs = fields();
  if (!fs.includes(CMP.param)) { CMP.param = fs.includes("n_teams") ? "n_teams" : fs[0]; Object.assign(CMP, defaults(CMP.param)); }
  const input = (key, id, label, attrs) => {
    const el = h("input", Object.assign({ id, value: CMP[key], inputmode: "decimal", autocomplete: "off" }, attrs || {}));
    el.addEventListener("input", () => { CMP[key] = el.value; preview(); if (key === "cTeam" || key === "cDown") renderOutput(); });
    return h("div", { class: "field" }, h("label", { for: id, text: label }), el);
  };
  const sel = h("select", { id: "cmp-param" }, ...fs.map((f) => h("option", { value: f, text: fieldLabel(f) })));
  sel.value = CMP.param;
  sel.addEventListener("change", () => { CMP.param = sel.value; Object.assign(CMP, defaults(CMP.param)); renderConfig(); });
  const fleet = M.system === "fleet";
  const grid = h("div", { class: "form-grid" },
    h("div", { class: "field", style: "grid-column: span 2" }, h("label", { for: "cmp-param", text: t("cmp.param") }), sel),
    input("from", "cmp-from", t("cmp.from")), input("to", "cmp-to", t("cmp.to")), input("step", "cmp-step", t("cmp.step")),
    input("reps", "cmp-reps", t("cmp.reps"), { placeholder: M.reps, inputmode: "numeric" }));
  const costGrid = fleet ? h("div", { class: "form-grid" },
    input("cTeam", "cmp-cteam", t("cmp.cteam"), { placeholder: "—" }), input("cDown", "cmp-cdown", t("cmp.cdown"), { placeholder: "—" }),
    h("p", { class: "hint", style: "grid-column: span 2; margin-bottom: 10px", text: t("cmp.cost.hint") })) : null;
  const runBtn = h("button", { type: "button", class: "primary", id: "cmp-run", text: t("cmp.run"), onclick: runSweep });
  const cancel = h("button", { type: "button", class: "danger", id: "cmp-cancel", text: t("cancel"), hidden: true, onclick: () => S.busy && S.busy.cancel() });
  const status = h("span", { class: "status" + (CMP.error ? " bad" : ""), id: "cmp-status", text: CMP.error || CMP.status || "" });
  box.append(grid, costGrid || "", h("p", { class: "hint", id: "cmp-preview" }),
    h("div", { class: "runbar", style: "margin-bottom: 8px" }, runBtn, cancel, status),
    h("div", { class: "progress", id: "cmp-progress", hidden: true }, h("div", { class: "bar" }, h("i")), h("span", { class: "ptext" })));
  preview();
  buttons();
}

function preview() {
  const el = $("cmp-preview");
  if (!el) return;
  const sv = sweepValues(CMP.param, CMP.from, CMP.to, CMP.step);
  if (sv.error) { el.textContent = sv.error; el.classList.add("err"); return; }
  el.classList.remove("err");
  const reps = CMP.reps.trim() === "" ? parseNum(M.reps) : parseNum(CMP.reps);
  const shown = sv.values.length > 12 ? sv.values.slice(0, 5).map((v) => fmtSig(v)).join(", ") + ", …, " + fmtSig(sv.values[sv.values.length - 1]) : sv.values.map((v) => fmtSig(v)).join(", ");
  el.textContent = t("cmp.preview", { n: sv.values.length, v: shown, reps: Number.isFinite(reps) ? fmtInt(reps) : "—", total: Number.isFinite(reps) ? fmtInt(reps * sv.values.length) : "—" });
}

function buttons() {
  const run = $("cmp-run"), cancel = $("cmp-cancel");
  if (!run) return;
  run.disabled = !!S.busy || S.valid === false;
  cancel.hidden = !(S.busy && S.busy.kind === "sweep");
}

function renderOutput() {
  const out = $("cmp-output");
  if (!out) return;
  out.replaceChildren();
  const R = S.sweep;
  if (!R) { out.append(h("div", { class: "empty" }, h("b", { text: t("cmp.empty.title") }), t("cmp.empty.body"))); return; }
  const fleet = R.system === "fleet", field = R.param, P = R.points;
  const label = fieldLabelFor(R);
  const c = costs(), withCost = fleet && c.ok;
  const best = withCost ? P.reduce((a, p) => (costOf(p, c) < costOf(a, c) ? p : a), P[0]) : null;
  const base = baseValue(R);
  out.append(h("div", { class: "headline" }, h("h2", { text: t("cmp.title", { p: label }) }),
    h("span", { class: "meta", text: t("cmp.base") + " " + describeRun(Object.assign({}, R.scenario, { reps: R.reps, seed: R.seed })) + " · " + t("cmp.crn") }),
    h("span", { class: "grow" }),
    h("button", { type: "button", class: "small", text: "CSV", title: t("cmp.csv"), onclick: () => exportCsv(R, c) }),
    h("button", { type: "button", class: "small", text: "JSON", title: t("cmp.json"), onclick: () => download(`farofa-sweep-${field}.json`, JSON.stringify(R, null, 2) + "\n") })));
  if (CMP.ver !== S.modelVer) out.append(h("div", { class: "banner warn", text: t("stale.sweep") }));
  if (best) {
    const cards = h("div", { class: "cards" });
    cards.append(h("div", { class: "card hero" }, h("div", { class: "k", text: t("cmp.best") }), h("div", { class: "v", text: `${label.split(":").pop().trim()} = ${fmtSig(best.value)}` }),
      h("div", { class: "s", text: t("cmp.best.sub", { c: fmt(costOf(best, c), 2), a: fmt(best.metrics.availability.value, 4) }) })));
    const cur = P.find((p) => p.value === base);
    if (cur && cur !== best) cards.append(h("div", { class: "card" }, h("div", { class: "k", text: t("cmp.current") }), h("div", { class: "v", text: fmt(costOf(cur, c), 2) }), h("div", { class: "s", text: t("cmp.current.sub", { v: fmtSig(cur.value) }) })));
    out.append(cards);
  }
  const grid = h("div", { class: "grid" });
  out.append(grid);
  const xInt = INTEGER.has(field);
  const vlines = Number.isFinite(base) ? [{ x: base, label: t("cmp.now") }] : [];
  const rings = (get) => (best ? [{ x: best.value, y: get(best), color: C.ink }] : []);
  const common = { xLabel: label, xInteger: xInt, snap: true, vlines, xPad: 0.04, tipTitle: (x) => `${label} = ${fmtSig(x)}` };
  const series = (key, color, scaleV = 1) => [{
    label: "", color, markers: true, errorBars: true,
    points: P.map((p) => { const m = p.metrics[key]; return { x: p.value, y: m.value == null ? NaN : m.value * scaleV, lo: m.ci && m.ci[0] != null ? m.ci[0] * scaleV : NaN, hi: m.ci && m.ci[1] != null ? m.ci[1] * scaleV : NaN }; }),
  }];
  const tipCI = (fmtv) => (s, p) => (p ? `${fmtv(p.y)} <span class="dim">${Number.isFinite(p.lo) ? fmtCI([p.lo, p.hi], 4, fmtv) : ""}</span>` : "—");
  const chart = (title, file, draw, caption) => { const cc = chartCard(grid, { title, file, caption }); responsive(cc.body, () => draw(cc.body)); };
  chart(t("cmp.c.avail"), `sweep-availability-${field}`, (b) => lineChart(b, series("availability", C.blue), Object.assign({}, common, { fmtY: (v) => fmt(v, 4), tipValue: tipCI((v) => fmt(v, 4)), rings: rings((p) => p.metrics.availability.value), label: t("cmp.c.avail") })), t("cmp.ci.cap"));
  if (withCost) {
    chart(t("cmp.c.cost"), `sweep-cost-${field}`, (b) => lineChart(b, [{ label: "", color: C.teal, markers: true, points: P.map((p) => ({ x: p.value, y: costOf(p, c) })) }],
      Object.assign({}, common, { tipValue: (s, p) => (p ? fmt(p.y, 2) : "—"), rings: rings((p) => costOf(p, c)), label: t("cmp.c.cost") })),
    t("cmp.cost.cap", { ct: fmtSig(c.cT), cd: fmtSig(c.cD) }));
  }
  if (fleet) {
    chart(t("cmp.c.wait"), `sweep-wait-${field}`, (b) => lineChart(b, series("mean_wait", C.amber), Object.assign({}, common, { yMin: 0, tipValue: (s, p) => (p ? `${fmtH(p.y)} <span class="dim">${Number.isFinite(p.lo) ? fmtCI([p.lo, p.hi], 2, fmtHn) : ""}</span>` : "—"), label: t("cmp.c.wait") })), t("cmp.wait.cap"));
    chart(t("cmp.c.util"), `sweep-utilization-${field}`, (b) => lineChart(b, series("utilization", C.wine, 100), Object.assign({}, common, { yMin: 0, tipValue: tipCI((v) => fmt(v, 1) + "%"), label: t("cmp.c.util"), fmtTick: (v) => fmt(v, 0) + "%" })), t("cmp.util.cap"));
  }
  chart(t("cmp.c.failures"), `sweep-failures-${field}`, (b) => lineChart(b, series("failures", C.blue), Object.assign({}, common, { tipValue: tipCI((v) => fmt(v, 2)), label: t("cmp.c.failures") })), t("cmp.ci.cap"));
  // table
  const head = [label, t("m.availability"), t("m.failures")].concat(fleet ? [t("m.utilization"), t("m.wait"), t("m.pwait"), t("m.maxqueue")] : []).concat(["MTTF", "MTTR"]).concat(withCost ? [t("cmp.costh")] : []);
  const table = h("table", { class: "data" });
  const ci = (m, d) => `${fmt(m.value, d)} <span class="ci">${fmtCI(m.ci, d)}</span>`;
  const rows = P.map((p) => {
    const m = p.metrics;
    const cells = [fmtSig(p.value), ci(m.availability, 4), ci(m.failures, 2)];
    if (fleet) cells.push(`${fmtPct(m.utilization.value, 1)} <span class="ci">[${fmtPct(m.utilization.ci[0], 1)}${t("sep")} ${fmtPct(m.utilization.ci[1], 1)}]</span>`, `${fmtH(m.mean_wait.value)} <span class="ci">${fmtCI(m.mean_wait.ci, 2, fmtHn)}</span>`, m.p_wait.value == null ? "—" : fmtPct(m.p_wait.value, 1), `${fmtInt(m.max_queue.value)} <span class="ci">(${fmt(m.max_queue.mean, 1)})</span>`);
    cells.push(fmtH(m.mttf.value), fmtH(m.mttr.value));
    if (withCost) cells.push(fmt(costOf(p, c), 2));
    const cls = [p.value === base ? "cur" : "", best && p === best ? "best" : ""].join(" ").trim();
    return `<tr class="${cls}">${cells.map((x) => `<td>${x}</td>`).join("")}</tr>`;
  });
  table.innerHTML = `<thead><tr>${head.map((x) => `<th>${x}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody>`;
  out.append(h("div", { class: "tablebox" }, table));
  if (fleet) out.append(h("p", { class: "note", text: t("cmp.table.note") }));
}

function baseValue(R) {
  const sc = R.scenario, f = R.param;
  if (f.includes(".")) { const [role, p] = f.split("."); return sc[role].params[p]; }
  return sc[f];
}
function fieldLabelFor(R) {
  const f = R.param;
  if (!f.includes(".")) return fieldLabel(f);
  const [role, p] = f.split(".");
  return `${t(role === "failure" ? "cmp.p.failure" : "cmp.p.repair")}: ${paramLabel(R.scenario[role].dist, p)}`;
}

function exportCsv(R, c) {
  const fleet = R.system === "fleet";
  const cols = [R.param, "availability", "availability_lo", "availability_hi", "failures", "failures_lo", "failures_hi", "mttf", "mttr"];
  if (fleet) cols.push("utilization", "utilization_lo", "utilization_hi", "mean_wait", "mean_wait_lo", "mean_wait_hi", "p_wait", "max_queue", "mean_max_queue");
  if (fleet && c.ok) cols.push("cost_per_hour");
  const v = (x) => (x === null || x === undefined || !Number.isFinite(x) ? "" : String(x));
  const lines = [cols.join(",")];
  for (const p of R.points) {
    const m = p.metrics;
    const row = [p.value, m.availability.value, m.availability.ci[0], m.availability.ci[1], m.failures.value, m.failures.ci[0], m.failures.ci[1], m.mttf.value, m.mttr.value];
    if (fleet) row.push(m.utilization.value, m.utilization.ci[0], m.utilization.ci[1], m.mean_wait.value, m.mean_wait.ci[0], m.mean_wait.ci[1], m.p_wait.value, m.max_queue.value, m.max_queue.mean);
    if (fleet && c.ok) row.push(costOf(p, c));
    lines.push(row.map(v).join(","));
  }
  download(`farofa-sweep-${R.param}.csv`, lines.join("\n") + "\n", "text/csv");
}

export function renderCompare() {
  const P = $("panel-compare");
  P.replaceChildren(
    h("div", { class: "headline" }, h("h2", { text: t("cmp.heading") })),
    h("p", { class: "note", text: t("cmp.intro") }),
    h("div", { class: "panel", id: "cmp-config" }),
    h("div", { id: "cmp-output" }));
  renderConfig();
  renderOutput();
}

export function initCompare() {
  on("preset", (p) => {
    if (p.costs) { CMP.cTeam = String(p.costs.team); CMP.cDown = String(p.costs.down); } else { CMP.cTeam = ""; CMP.cDown = ""; }
    CMP.param = null;
    renderConfig();
  });
  on("busy", buttons);
  on("validated", buttons);
  on("lang", renderCompare);
  on("model", () => {
    const fs = fields();
    const sel = $("cmp-param");
    if (sel && (sel.options.length !== fs.length || !fs.includes(CMP.param))) renderConfig();
    else preview();
    if (S.sweep && CMP.ver !== S.modelVer && $("cmp-output") && !$("cmp-output").querySelector(".banner.warn")) renderOutput();
  });
  renderCompare();
}
