// Boot: language, metadata, views, tabs and the address-bar route
// (#sim, #sim/timeline, #sim/compare, #sim/code, #est).
import { $, S, api, emit, on, tablist } from "./core.js";
import { applyI18n, lang, setLang } from "./i18n.js";
import { initModel } from "./model.js";
import { initResults } from "./results.js";
import { initTimeline } from "./timeline.js";
import { initCompare } from "./compare.js";
import { initCode } from "./code.js";
import { initEstimate } from "./estimate.js";
import { untip } from "./charts.js";

function langButtons() {
  for (const b of document.querySelectorAll("[data-lang]")) b.setAttribute("aria-pressed", b.dataset.lang === lang() ? "true" : "false");
}

async function boot() {
  applyI18n();
  langButtons();
  try {
    S.meta = await api("/api/meta");
  } catch (e) {
    document.body.insertAdjacentHTML("beforeend", `<div class="banner warn" style="margin:16px">farofa: ${e.message}</div>`);
    return;
  }
  $("version").textContent = `farofa ${S.meta.version}`;
  initModel();
  initResults();
  initTimeline();
  initCompare();
  initCode();
  initEstimate();

  let view = "sim", tab = "dash";
  const route = () => { history.replaceState(null, "", view === "est" ? "#est" : tab === "dash" ? "#sim" : `#sim/${tab}`); };
  const selectTab = tablist(document.querySelector(".tabs"), "tab", (k) => { tab = k; untip(); route(); emit("tab", k); });
  const selectView = tablist(document.querySelector(".views"), "view", (k) => { view = k; untip(); route(); });
  on("goto", (k) => { selectView(k); });
  on("run", () => { if (tab === "code") selectTab("dash"); });

  for (const b of document.querySelectorAll("[data-lang]")) {
    b.addEventListener("click", () => {
      if (b.dataset.lang === lang()) return;
      setLang(b.dataset.lang);
      applyI18n();
      langButtons();
      emit("lang");
    });
  }
  const follow = () => {
    const [v, tb] = (location.hash.slice(1) || "sim").split("/");
    const wantTab = tb && document.querySelector(`[data-tab="${tb}"]`) ? tb : "dash";
    const wantView = v === "est" ? "est" : "sim";
    if (wantView === "sim" && wantTab !== tab) selectTab(wantTab);
    if (wantView !== view) selectView(wantView);
  };
  window.addEventListener("hashchange", follow);
  follow();
}

boot();
