// "Python" tab: the script that reproduces the current model with farofa.
import { $, S, download, h, on } from "./core.js";
import { t } from "./i18n.js";

const py = (x) => (typeof x === "number" ? String(x) : JSON.stringify(x));

export function pythonCode(sc) {
  const fleet = sc.system === "fleet";
  const obj = fleet ? "fleet" : "device";
  const args = (d) => [`'${d.dist}'`, ...Object.values(d.params).map(py)].join(", ");
  const L = [t("code.c.head"), "import farofa", ""];
  L.push(fleet ? `fleet = farofa.Fleet(n_devices=${sc.n_devices}, n_teams=${sc.n_teams})` : "device = farofa.SimpleDevice()");
  L.push(`${obj}.set_failure_dist(${args(sc.failure)})`, `${obj}.set_repair_dist(${args(sc.repair)})`, `${obj}.set_mission_time(${py(sc.mission_time)})`, "");
  const seed = sc.seed === null || sc.seed === undefined || sc.seed === "" ? "None" : py(sc.seed);
  L.push(`result = ${obj}.simulate(reps=${py(sc.reps)}, seed=${seed}, trace=${py(sc.trace || 0)})`, "print(result)");
  L.push(`print(${JSON.stringify(t("code.ci.avail"))}, result.availability_confidence_interval())`);
  L.push(`print(${JSON.stringify(t("code.ci.fail"))}, result.failure_count_confidence_interval())`);
  if (fleet) L.push(`print(${JSON.stringify(t("code.ci.util"))}, result.server_utilization_confidence_interval())`);
  if (sc.trace) L.push("", t("code.c.trace"), "for row in result.timeline(0)[:10]:", "    print(row)");
  L.push("", t("code.c.export"), "result.export_json('farofa-result.json')");
  if (fleet) {
    L.push("", t("code.c.sweep"), `for k in range(1, ${sc.n_devices} + 1):`,
      `    f = farofa.Fleet(n_devices=${sc.n_devices}, n_teams=k)`,
      `    f.set_failure_dist(${args(sc.failure)})`, `    f.set_repair_dist(${args(sc.repair)})`, `    f.set_mission_time(${py(sc.mission_time)})`,
      `    r = f.simulate(reps=${py(sc.reps)}, seed=${seed})`,
      "    print(k, round(r.fleet_availability, 4), round(r.server_utilization, 3), round(r.mean_wait_time, 2))");
  }
  return L.join("\n") + "\n";
}

export function renderCode() {
  const P = $("panel-code");
  P.replaceChildren();
  const sc = S.valid && S.normalized ? S.normalized : null;
  P.append(h("div", { class: "headline" }, h("h2", { text: t("code.title") })), h("p", { class: "note", text: t("code.intro") }));
  const pre = h("pre", { class: "code" });
  pre.textContent = sc ? pythonCode(sc) : t("code.invalid");
  const msg = h("span", { class: "status" });
  P.append(pre, h("div", { class: "row" },
    h("button", { type: "button", class: "small", text: t("code.copy"), disabled: !sc, onclick: async () => {
      try { await navigator.clipboard.writeText(pre.textContent); msg.textContent = t("code.copied"); } catch { msg.textContent = t("code.copyfail"); }
    } }),
    h("button", { type: "button", class: "small", text: t("code.download"), disabled: !sc, onclick: () => download("farofa_run.py", pre.textContent, "text/x-python") }),
    msg));
}

export function initCode() {
  on("validated", renderCode);
  on("lang", renderCode);
  renderCode();
}
