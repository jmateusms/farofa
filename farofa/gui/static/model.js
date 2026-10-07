// Model panel: system, distributions, run settings, validation, run/cancel,
// presets and scenario files.
import { $, S, api, download, emit, h, on, startJob, toast } from "./core.js";
import { fmt, fmtH, fmtInt, has, parseNum, t } from "./i18n.js";

const clone = (o) => JSON.parse(JSON.stringify(o));
const ROLES = ["failure", "repair"];

export const DEFAULTS = {
  failure: {
    exponential: { rate: "0.01" }, weibull: { a: "300", b: "1.5" }, weibull_min: { a: "300", b: "1.5" },
    weibull_grp: { a: "300", b: "2", q: "0.3" }, weibull_grp2: { a: "300", b: "2", q: "0.3" },
    lognormal: { mu: "5", sigma: "0.5" }, normal: { mu: "150", sigma: "40" }, gamma: { shape: "2", scale: "50" },
  },
  repair: {
    exponential: { rate: "0.1" }, weibull: { a: "11", b: "1.5" }, weibull_min: { a: "11", b: "1.5" },
    weibull_grp: { a: "11", b: "1.5", q: "0" }, weibull_grp2: { a: "11", b: "1.5", q: "0" },
    lognormal: { mu: "2.2", sigma: "0.5" }, normal: { mu: "10", sigma: "3" }, gamma: { shape: "3", scale: "3.5" },
  },
};

// Examples (notes in the i18n dictionary under preset.<key>.note).
export const PRESETS = {
  single: { system: "device", n: 1, k: 1, T: 1000, reps: 5000, seed: 42, trace: 5, failure: ["exponential", { rate: 0.01 }], repair: ["exponential", { rate: 0.1 }] },
  fleet: { system: "fleet", n: 10, k: 2, T: 4000, reps: 400, seed: 42, trace: 20, failure: ["exponential", { rate: 0.01 }], repair: ["exponential", { rate: 0.1 }] },
  grp: { system: "fleet", n: 6, k: 2, T: 4000, reps: 300, seed: 7, trace: 30, failure: ["weibull_grp", { a: 400, b: 2.5, q: 0.3 }], repair: ["gamma", { shape: 3, scale: 4 }] },
  sizing: { system: "fleet", n: 20, k: 2, T: 2000, reps: 200, seed: 2026, trace: 20, failure: ["weibull", { a: 300, b: 1.5 }], repair: ["lognormal", { mu: 2.6, sigma: 0.6 }], costs: { team: 40, down: 120 } },
};

export const M = {
  preset: "fleet", system: "fleet", n: "10", k: "2", T: "4000", reps: "400", seed: "42", trace: "20",
  failure: { dist: "exponential", vals: clone(DEFAULTS.failure) },
  repair: { dist: "exponential", vals: clone(DEFAULTS.repair) },
};

export const distParams = (name) => (S.meta.distributions[name] || { params: [] }).params;
export const paramLabel = (dist, p) => t(has(`param.${dist}.${p}`) ? `param.${dist}.${p}` : `param.${p}`);
const FIELD_INPUT = { n_devices: "f-n_devices", n_teams: "f-n_teams", mission_time: "f-mission_time", reps: "f-reps", seed: "f-seed", trace: "f-trace" };
const KEY_OF = { n: "n_devices", k: "n_teams", T: "mission_time", reps: "reps", seed: "seed", trace: "trace" };

// ----------------------------------------------------------- scenario I/O --
function num(s) {
  if (s === null || s === undefined) return null;
  const str = String(s).trim();
  if (str === "") return null;
  const v = parseNum(str);
  return Number.isFinite(v) ? v : str;
}

/** The scenario as the API expects it (numbers where the text is numeric). */
export function toScenario() {
  const dist = (role) => {
    const d = M[role].dist, vals = M[role].vals[d] || {};
    return { dist: d, params: Object.fromEntries(distParams(d).map((p) => [p, num(vals[p])])) };
  };
  return {
    schema: "farofa-gui-scenario", version: 1, system: M.system,
    n_devices: num(M.n), n_teams: num(M.k), failure: dist("failure"), repair: dist("repair"),
    mission_time: num(M.T), reps: num(M.reps), seed: num(M.seed), trace: num(M.trace) ?? 0,
  };
}

export function loadScenario(sc) {
  if (sc && sc.scenario && sc.result_kind) sc = sc.scenario;   // a result export
  if (!sc || typeof sc !== "object" || !sc.failure || !sc.repair) throw new Error(t("model.load.bad"));
  const str = (v) => (v === null || v === undefined ? "" : String(v));
  M.system = sc.system === "fleet" ? "fleet" : "device";
  M.n = str(sc.n_devices ?? 1); M.k = str(sc.n_teams ?? 1);
  M.T = str(sc.mission_time); M.reps = str(sc.reps); M.seed = str(sc.seed); M.trace = str(sc.trace ?? 0);
  for (const role of ROLES) {
    const spec = sc[role];
    if (!S.meta.distributions[spec.dist]) throw new Error(t("model.load.bad"));
    M[role].dist = spec.dist;
    const names = distParams(spec.dist);
    const params = Array.isArray(spec.params) ? Object.fromEntries(names.map((p, i) => [p, spec.params[i]])) : (spec.params || {});
    M[role].vals[spec.dist] = Object.fromEntries(names.map((p) => [p, str(params[p])]));
  }
  M.preset = "";
  syncForm();
  changed();
}

/** Put a fitted failure process into the model (from the estimation view). */
export function setFailureFromFit(distribution, endTime) {
  const [dist, ...values] = distribution;
  M.failure.dist = dist;
  M.failure.vals[dist] = Object.fromEntries(distParams(dist).map((p, i) => [p, String(+values[i].toPrecision(6))]));
  if (Number.isFinite(endTime)) M.T = String(+endTime.toPrecision(10));
  M.preset = "";
  syncForm();
  changed();
}

export function applyPreset(key) {
  const p = PRESETS[key];
  if (!p) return;
  M.preset = key;
  M.system = p.system; M.n = String(p.n); M.k = String(p.k); M.T = String(p.T);
  M.reps = String(p.reps); M.seed = String(p.seed); M.trace = String(p.trace);
  for (const role of ROLES) {
    const [dist, vals] = p[role];
    M[role].dist = dist;
    M[role].vals[dist] = Object.fromEntries(Object.entries(vals).map(([k, v]) => [k, String(v)]));
  }
  syncForm();
  changed(true);
  emit("preset", p);
}

// ------------------------------------------------------------------- form --
function buildDistSelect(role) {
  const sel = $(`${role}-dist`);
  sel.replaceChildren(...Object.keys(S.meta.distributions).map((d) => h("option", { value: d, text: t(`dist.${d}`) })));
  sel.value = M[role].dist;
}

function buildParams(role) {
  const d = M[role].dist, box = $(`${role}-params`);
  const vals = M[role].vals[d] || (M[role].vals[d] = clone(DEFAULTS[role][d] || {}));
  box.replaceChildren(...distParams(d).map((p) => {
    const id = `${role}-p-${p}`;
    const input = h("input", { id, inputmode: "decimal", autocomplete: "off", value: vals[p] ?? "" });
    input.addEventListener("input", () => { vals[p] = input.value; M.preset = ""; $("preset").value = ""; changed(); });
    return h("div", { class: "field" }, h("label", { for: id, text: paramLabel(d, p) }), input, h("p", { class: "err", dataset: { err: `${role}.${p}` } }));
  }));
  hint(role);
}

// mean of each distribution (first failure for the stateful ones)
function lgam(x) {
  const c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  if (x < 0.5) return Math.log(Math.PI / Math.abs(Math.sin(Math.PI * x))) - lgam(1 - x);
  x -= 1;
  let a = c[0];
  const tt = x + 7.5;
  for (let i = 1; i < 9; i++) a += c[i] / (x + i);
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(tt) - tt + Math.log(a);
}
function erfc(x) {
  const z = Math.abs(x), tt = 1 / (1 + 0.5 * z);
  const r = tt * Math.exp(-z * z - 1.26551223 + tt * (1.00002368 + tt * (0.37409196 + tt * (0.09678418 + tt * (-0.18628806 + tt * (0.27886807 + tt * (-1.13520398 + tt * (1.48851587 + tt * (-0.82215223 + tt * 0.17087277)))))))));
  return x >= 0 ? r : 2 - r;
}
export function meanOf(dist, v) {
  switch (dist) {
    case "exponential": return 1 / v.rate;
    case "weibull": case "weibull_min": case "weibull_grp": case "weibull_grp2": return v.a * Math.exp(lgam(1 + 1 / v.b));
    case "lognormal": return Math.exp(v.mu + v.sigma * v.sigma / 2);
    case "normal": { const z = v.mu / v.sigma; return v.mu + v.sigma * Math.exp(-z * z / 2) / Math.sqrt(2 * Math.PI) / (0.5 * erfc(-z / Math.SQRT2)); }
    case "gamma": return v.shape * v.scale;
    default: return NaN;
  }
}

function hint(role) {
  const d = M[role].dist, raw = M[role].vals[d] || {};
  const v = Object.fromEntries(distParams(d).map((p) => [p, parseNum(raw[p])]));
  const mean = meanOf(d, v);
  let text = t(`distnote.${d}`);
  if (Number.isFinite(mean) && mean > 0) {
    const first = ["weibull_min", "weibull_grp", "weibull_grp2"].includes(d) && role === "failure";
    text += " " + t(first ? "model.mean.first" : "model.mean", { v: fmtH(mean) });
  }
  $(`${role}-hint`).textContent = text;
}

export function syncForm() {
  for (const [key, field] of Object.entries(KEY_OF)) $(FIELD_INPUT[field]).value = M[key];
  for (const b of document.querySelectorAll("#system [data-system]")) b.setAttribute("aria-checked", b.dataset.system === M.system ? "true" : "false");
  $("fleet-fields").hidden = M.system !== "fleet";
  for (const role of ROLES) { buildDistSelect(role); buildParams(role); }
  $("preset").value = M.preset || "";
  presetNote();
}

function buildPresets() {
  const sel = $("preset");
  sel.replaceChildren(h("option", { value: "", text: t("preset.custom") }),
    ...Object.keys(PRESETS).map((k) => h("option", { value: k, text: t(`preset.${k}`) })));
  sel.value = M.preset || "";
}
function presetNote() { $("preset-note").textContent = M.preset ? t(`preset.${M.preset}.note`) : ""; }

// ------------------------------------------------------------- validation --
let vTimer = 0;
S.valid = null;
S.normalized = null;

export function changed(now) {
  S.modelVer++;
  for (const role of ROLES) hint(role);
  presetNote();
  clearTimeout(vTimer);
  vTimer = setTimeout(validateNow, now ? 0 : 220);
  emit("model");
}

async function validateNow() {
  const ver = S.modelVer;
  let res;
  try { res = await api("/api/validate", { scenario: toScenario() }); } catch (e) { setStatus(e.message, true); return; }
  if (ver !== S.modelVer) return;
  S.valid = res.ok;
  S.normalized = res.ok ? res.scenario : null;
  showErrors(res.ok ? [] : res.errors);
  emit("validated");
  updateButtons();
}

export function errorText(e) {
  if (e.code && has(`err.${e.code}`)) return t(`err.${e.code}`, { msg: e.message });
  return e.message;
}

function showErrors(errors) {
  const side = document.querySelector("#view-sim .side");
  side.querySelectorAll("[data-err]").forEach((p) => { p.textContent = ""; });
  side.querySelectorAll("[aria-invalid]").forEach((i) => i.removeAttribute("aria-invalid"));
  for (const e of errors) {
    let slot = side.querySelector(`[data-err="${CSS.escape(e.field)}"]`);
    if (!slot) slot = side.querySelector(`[data-err="${CSS.escape(e.field.split(".")[0])}"]`);
    if (slot) slot.textContent = (slot.textContent ? slot.textContent + " " : "") + errorText(e);
    const [role, p] = e.field.split(".");
    const input = FIELD_INPUT[e.field] ? $(FIELD_INPUT[e.field]) : (p ? $(p === "dist" ? `${role}-dist` : `${role}-p-${p}`) : null);
    if (input) input.setAttribute("aria-invalid", "true");
  }
  if (errors.length) setStatus(t("model.invalid"), true);
  else if (!S.busy) setStatus("");
}

export function setStatus(text, bad) {
  const el = $("model-status");
  el.textContent = text;
  el.classList.toggle("bad", !!bad);
}

export function updateButtons() {
  $("run").disabled = !!S.busy || S.valid === false;
  $("run-cancel").hidden = !(S.busy && S.busy.kind === "simulate");
}

// --------------------------------------------------------------------- run --
export function progressText(st) {
  const done = st.done || 0, total = st.total || 0;
  return total ? `${fmtInt(done)} / ${fmtInt(total)}` : "…";
}

export function showProgress(box, st) {
  box.hidden = !st;
  if (!st) return;
  const bar = box.querySelector(".bar"), frac = st.total ? st.done / st.total : 0;
  bar.classList.toggle("indet", !st.total);
  bar.querySelector("i").style.width = st.total ? `${(100 * frac).toFixed(1)}%` : "";
  box.querySelector(".ptext").textContent = progressText(st);
}

async function run() {
  if (S.busy) return;
  const scenario = toScenario(), ver = S.modelVer, box = $("run-progress");
  showProgress(box, { done: 0, total: 0 });
  setStatus(t("model.running"));
  const job = startJob("/api/simulate", { scenario }, (st) => showProgress(box, st));
  S.busy = { kind: "simulate", cancel: job.cancel };
  emit("busy");
  const t0 = performance.now();
  try {
    const { result, id } = await job.promise;
    S.run = result; S.runJob = id; S.runVer = ver;
    setStatus(t("model.done", { s: fmt((performance.now() - t0) / 1000, 1) }));
    emit("run");
  } catch (e) {
    if (e.cancelled) setStatus(t("model.cancelled"));
    else if (e.body && e.body.errors) showErrors(e.body.errors);
    else setStatus(e.message || String(e), true);
  } finally {
    S.busy = null;
    showProgress(box, null);
    emit("busy");
  }
}

// --------------------------------------------------------------- startup --
export function initModel() {
  buildPresets();
  for (const [key, field] of Object.entries(KEY_OF)) {
    const input = $(FIELD_INPUT[field]);
    input.addEventListener("input", () => { M[key] = input.value; changed(); });
  }
  for (const b of document.querySelectorAll("#system [data-system]")) {
    b.addEventListener("click", () => {
      if (M.system === b.dataset.system) return;
      M.system = b.dataset.system;
      if (M.system === "fleet" && !(parseNum(M.n) > 1)) { M.n = "10"; M.k = "2"; }
      M.preset = "";
      syncForm();
      changed();
    });
  }
  for (const role of ROLES) {
    $(`${role}-dist`).addEventListener("change", (e) => { M[role].dist = e.target.value; M.preset = ""; $("preset").value = ""; buildParams(role); changed(); });
  }
  $("preset").addEventListener("change", (e) => { if (e.target.value) applyPreset(e.target.value); else { M.preset = ""; presetNote(); } });
  $("seed-new").addEventListener("click", () => { M.seed = String(Math.floor(Math.random() * 1e6)); $("f-seed").value = M.seed; changed(); });
  $("run").addEventListener("click", run);
  $("run-cancel").addEventListener("click", () => S.busy && S.busy.cancel());
  $("scenario-save").addEventListener("click", () => {
    const sc = S.normalized && S.valid ? Object.assign({}, S.normalized) : toScenario();
    download("farofa-scenario.json", JSON.stringify(sc, null, 2) + "\n");
  });
  $("scenario-open").addEventListener("click", () => $("scenario-file").click());
  $("scenario-file").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    try { loadScenario(JSON.parse(await file.text())); toast(t("model.loaded", { name: file.name })); } catch (err) { toast(t("model.load.fail", { msg: err.message })); }
  });
  on("busy", updateButtons);
  on("lang", () => { buildPresets(); syncForm(); validateNow(); });
  syncForm();
  changed(true);
}
