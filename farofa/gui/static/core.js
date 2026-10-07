// Shared state, DOM helpers, events and the API client.

export const S = {
  meta: null,        // /api/meta
  modelVer: 0,       // bumps on every model edit
  run: null,         // last simulation payload
  runJob: null,      // job id of S.run (for the JSON export)
  runVer: -1,        // modelVer when S.run was produced
  sweep: null,       // last sweep payload
  est: null,         // last estimation payload
  busy: null,        // running job handle {kind, cancel}
};

export const $ = (id) => document.getElementById(id);

/** h("div", {class: "x", text: "…", onclick}, child, …) */
export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(el.dataset, v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ------------------------------------------------------------------ events --
const listeners = {};
export function on(evt, fn) { (listeners[evt] = listeners[evt] || []).push(fn); }
export function emit(evt, data) { (listeners[evt] || []).forEach((fn) => fn(data)); }

// --------------------------------------------------------------------- api --
export class ApiError extends Error {
  constructor(status, body) {
    super((body && body.message) || `HTTP ${status}`);
    this.status = status;
    this.body = body || {};
  }
}

export async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

/** Start a job and poll it. Returns {promise, cancel}; the promise resolves
 *  with {result, id} or rejects with {cancelled: true} / an ApiError-like. */
export function startJob(path, body, onProgress) {
  let id = null, cancelled = false, timer = 0;
  const promise = new Promise((resolve, reject) => {
    const poll = async () => {
      let st;
      try { st = await api(`/api/jobs/${id}`); } catch (e) { reject(e); return; }
      if (onProgress) onProgress(st);
      if (st.status === "running") { timer = setTimeout(poll, 180); return; }
      if (st.status === "done") resolve({ result: st.result, id });
      else if (st.status === "cancelled") reject({ cancelled: true });
      else reject(new ApiError(422, st.error || { message: "error" }));
    };
    api(path, body).then((st) => {
      id = st.id;
      if (onProgress) onProgress(st);
      if (cancelled) api(`/api/jobs/${id}/cancel`, {}).catch(() => {});
      timer = setTimeout(poll, 120);
    }).catch(reject);
  });
  const cancel = () => {
    cancelled = true;
    if (id) api(`/api/jobs/${id}/cancel`, {}).catch(() => {});
  };
  return { promise, cancel, get id() { return id; }, stop() { clearTimeout(timer); } };
}

// ---------------------------------------------------------------- browser --
export function download(filename, content, type = "application/json") {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const a = h("a", { href: URL.createObjectURL(blob), download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

let toastTimer = 0;
export function toast(message, ms = 6000) {
  const el = $("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, ms);
}

export function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value);
  } catch { /* storage blocked */ }
  return null;
}

/** Wire a role="tablist" of buttons with data-<attr> to show/hide panels. */
export function tablist(container, attr, onSelect) {
  const buttons = [...container.querySelectorAll(`[data-${attr}]`)];
  const select = (key, focus) => {
    for (const b of buttons) {
      const on = b.dataset[attr] === key;
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(b.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
      if (on && focus) b.focus();
    }
    if (onSelect) onSelect(key);
  };
  buttons.forEach((b, i) => {
    b.addEventListener("click", () => select(b.dataset[attr]));
    b.addEventListener("keydown", (e) => {
      const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      select(buttons[(i + d + buttons.length) % buttons.length].dataset[attr], true);
    });
  });
  return select;
}
