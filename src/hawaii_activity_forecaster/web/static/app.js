// Hawaii Activity Planner — local web interface (M2 WEB-A).
// Display only: every value comes from the local hafi web API, which returns
// results already validated by the same checks as the CLI.
"use strict";

const app = document.getElementById("app");
const modeChip = document.getElementById("mode");
const state = { status: null, current: null, cache: new Map(), traces: new Map(), filter: "all", sel: null, busy: false, error: null, draft: "" };

// --- request token ---------------------------------------------------------
// hafi web prints a URL with #token=…; keep it for this tab only and drop it from the address bar.
(function takeToken() {
  const match = /(?:^#|&)token=([A-Za-z0-9_-]+)/.exec(location.hash);
  if (match) {
    try { sessionStorage.setItem("haf-token", match[1]); } catch (e) { state.memToken = match[1]; }
    history.replaceState(null, "", location.pathname + "#/plan");
  }
})();
function token() {
  try { return sessionStorage.getItem("haf-token") || state.memToken || ""; } catch (e) { return state.memToken || ""; }
}

// --- helpers ---------------------------------------------------------------
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const list = (items, cls = "") => items && items.length ? `<ul class="${cls}">${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "";
const plural = (n, word, many) => `${n} ${n === 1 ? word : (many || word + "s")}`;
const label = (code) => String(code || "").toLowerCase().replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

async function api(method, path, body) {
  const options = { method, headers: {} };
  if (method === "POST") {
    options.headers["Content-Type"] = "application/json";
    options.headers["X-HAF-Token"] = token();
    options.body = JSON.stringify(body || {});
  }
  const response = await fetch(path, options);
  let data = {};
  try { data = await response.json(); } catch (e) { data = { error: "Unexpected response." }; }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

const ELIG = {
  ELIGIBLE: ["b-ok", "✓ Eligible"], EXCLUDED: ["b-bad", "✕ Excluded"],
  NEEDS_INVESTIGATION: ["b-warn", "◌ Needs evidence"], UNSUPPORTED: ["b-muted", "– Unsupported"],
};
const OUTCOME = {
  RECOMMENDATIONS: ["b-ok", "✓ Recommendations"], NO_RECOMMENDATION: ["b-warn", "◌ No recommendation"],
  ERROR: ["b-bad", "✕ Technical error"], AWAITING_CLARIFICATION: ["b-info", "? Clarification needed"],
};
const RESULT = { PASS: ["t-ok", "✓ PASS"], FAIL: ["t-bad", "✕ FAIL"], UNKNOWN: ["t-warn", "? UNKNOWN"], NOT_APPLICABLE: ["muted", "N/A"] };
const VALID = { ACCEPTED: ["b-ok", "✓ Accepted"], LIMITED: ["b-warn", "◐ Limited"], REJECTED: ["b-bad", "✕ Rejected"], PENDING: ["b-muted", "Pending"] };
const badge = (map, key) => { const [cls, text] = map[key] || ["b-muted", label(key)]; return `<span class="badge ${cls}">${esc(text)}</span>`; };

// --- data ------------------------------------------------------------------
async function refreshStatus() {
  state.status = await api("GET", "/api/status");
  modeChip.textContent = state.status.banner;
  modeChip.classList.toggle("live", state.status.mode !== "authored");
  return state.status;
}
async function getRun(id) {
  if (!state.cache.has(id)) state.cache.set(id, await api("GET", `/api/runs/${encodeURIComponent(id)}`));
  return state.cache.get(id);
}
async function getTrace(key) {
  if (!state.traces.has(key)) {
    const path = key.startsWith("recorded:") ? `/api/evidence/traces/${encodeURIComponent(key.slice(9))}` : `/api/traces/${encodeURIComponent(key)}`;
    state.traces.set(key, await api("GET", path));
  }
  return state.traces.get(key);
}
function runs() { return (state.status && state.status.runs) || []; }
function latest(pred) { const r = runs().filter(pred); return r.length ? r[r.length - 1] : null; }

// --- router ----------------------------------------------------------------
async function route() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  const page = parts[0] || "plan";
  if (state.lastHash !== location.hash) { window.scrollTo(0, 0); state.lastHash = location.hash; }
  document.querySelectorAll("[data-nav]").forEach((a) => { if (a.dataset.nav !== page) a.removeAttribute("aria-current"); else a.setAttribute("aria-current", "page"); });
  try {
    if (!state.status) await refreshStatus();
    if (page === "evidence") return await renderEvidence(parts[1], parts[2]);
    if (page === "inspector") return await renderInspector(parts[1], parts[2]);
    if (page === "recorded") return await renderRecorded();
    return await renderPlan(parts[1]);
  } catch (error) {
    app.innerHTML = `<section class="panel"><div class="notice bad">${esc(error.message)}</div></section>`;
  }
}
window.addEventListener("hashchange", route);

// --- Plan ------------------------------------------------------------------
async function renderPlan(runId) {
  const status = state.status;
  const chosen = runId || state.current || (latest(() => true) || {}).run_id;
  state.current = chosen || null;
  const left = planControls(status, chosen);
  let right = `<section class="panel"><div class="empty">Run an authored demonstration${status.live_enabled ? " or ask a question" : ""} to see a result here.</div></section>`;
  if (chosen) {
    const data = await getRun(chosen);
    right = data.view ? resultPanel(data.summary, data.view) : statusPanel(data.summary);
  }
  app.innerHTML = `<div class="row"><div class="side stack">${left}</div><div class="grow stack" id="result">${right}</div></div>`;
  bindPlan();
  if (chosen) {
    const data = state.cache.get(chosen);
    if (data && data.view && data.view.outcome === "NO_RECOMMENDATION" && data.summary.has_trace) fillTried(chosen);
  }
}

function planControls(status, chosen) {
  const remaining = status.investigations_limit - status.investigations_used;
  const live = status.live_enabled ? `
    <section class="panel">
      <div class="panel-head"><h2>Ask</h2><span class="tiny muted">${esc(plural(remaining, "investigation"))} left in this process</span></div>
      ${status.session.active ? `<div class="notice info small">Follow-ups continue the current session as a new investigation with fresh evidence.</div>` : ""}
      <form id="ask" class="stack">
        <label for="ask-text">${status.session.active ? "Ask a follow-up or change a detail" : "Your request"}</label>
        <textarea id="ask-text" maxlength="4000" placeholder="Where should I snorkel tomorrow morning? I'm intermediate and prefer calm water near Kihei.">${esc(state.draft)}</textarea>
        <div class="btn-row">
          <button type="submit" class="btn primary" ${state.busy || remaining < 1 ? "disabled" : ""}>${status.session.active ? "Send follow-up" : "Start investigation"}</button>
          ${status.session.active ? `<button type="button" class="btn" id="reset" ${state.busy ? "disabled" : ""}>New session</button>` : ""}
        </div>
        <span class="tiny muted">${status.mode === "live" ? "Each investigation makes paid model calls (typically 4–5) and takes about 10 seconds." : "Each investigation calls the configured local model."}
        Fixture clock: ${esc(status.fixture_clock || "")}.</span>
      </form>
    </section>` : "";
  const turns = runs().map((r) => `
      <li><button type="button" class="turn" data-run="${esc(r.run_id)}" aria-current="${r.run_id === chosen}">
        <span class="meta">${esc(r.label)}${r.kind === "authored" ? "" : " · " + esc(r.kind === "live" ? "live model" : "local model")}</span><br>
        ${r.request_text ? esc(r.request_text) : ""}<br>${badge(OUTCOME, r.outcome)}
      </button></li>`).join("");
  return `${live}
    <section class="panel">
      <h2>Authored demonstrations</h2>
      <span class="small muted">Fixed plans through the real validators. Zero model calls.</span>
      <div class="btn-row">
        <button type="button" class="btn" data-demo="advisory" ${state.busy ? "disabled" : ""}>Advisory exclusion</button>
        <button type="button" class="btn" data-demo="outage" ${state.busy ? "disabled" : ""}>Source outage</button>
        <button type="button" class="btn" data-demo="session" ${state.busy ? "disabled" : ""}>Session follow-up</button>
      </div>
    </section>
    ${state.busy ? `<div class="notice info"><span class="busy">Investigating…</span></div>` : ""}
    ${state.error ? `<div class="notice bad" role="alert">${esc(state.error)}</div>` : ""}
    <section class="panel">
      <h2>Runs in this process</h2>
      ${turns ? `<ol class="convo list-plain">${turns}</ol>` : `<span class="small muted">None yet.</span>`}
    </section>`;
}

function bindPlan() {
  app.querySelectorAll("[data-run]").forEach((b) => b.addEventListener("click", () => { location.hash = `#/plan/${b.dataset.run}`; }));
  app.querySelectorAll("[data-demo]").forEach((b) => b.addEventListener("click", () => act(() => api("POST", `/api/demo/${b.dataset.demo}`), (d) => d.runs[d.runs.length - 1].run_id)));
  const form = document.getElementById("ask");
  if (form) {
    const box = document.getElementById("ask-text");
    box.addEventListener("input", () => { state.draft = box.value; });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = box.value.trim();
      if (!text) return;
      act(() => api("POST", "/api/ask", { text }), (d) => { state.draft = ""; return d.run.run_id; });
    });
  }
  const reset = document.getElementById("reset");
  if (reset) reset.addEventListener("click", () => act(() => api("POST", "/api/session/reset"), () => state.current));
  app.querySelectorAll("[data-beach]").forEach((b) => b.addEventListener("click", () => { location.hash = `#/evidence/${state.current}/${b.dataset.beach}`; }));
}

async function act(call, pick) {
  state.busy = true; state.error = null;
  await renderPlan(state.current);
  try {
    const data = await call();
    state.current = pick(data) || state.current;
  } catch (error) {
    state.error = error.message;
  }
  state.busy = false;
  await refreshStatus();
  if (location.hash === `#/plan/${state.current}`) await renderPlan(state.current); else location.hash = `#/plan/${state.current || ""}`;
}

function statusPanel(summary) {
  const cls = summary.outcome === "AWAITING_CLARIFICATION" ? "info" : "bad";
  return `<section class="panel">
    <div class="result-head"><div class="stack">${badge(OUTCOME, summary.outcome)}
      <h1>${summary.outcome === "AWAITING_CLARIFICATION" ? "More detail is needed" : "No validated result is available"}</h1></div></div>
    ${summary.request_text ? `<p class="muted">“${esc(summary.request_text)}”</p>` : ""}
    <div class="notice ${cls}">${esc(summary.message || "")}</div>
    ${list(summary.questions)}
    ${summary.outcome === "ERROR" ? `<span class="small muted">No beach was judged. The session has ended; the next request starts a new one.</span>` : ""}
    ${summary.has_trace ? `<a href="#/inspector/run/${esc(summary.run_id)}">Open the trace in the run inspector →</a>` : ""}
  </section>`;
}

function understood(view) {
  const r = view.request;
  const items = [view.activity, view.window.display];
  if (r.preferred_area) items.push(`Near ${r.preferred_area} · preference`);
  if (r.experience_level) items.push(r.experience_level);
  r.hard_constraints.forEach((c) => items.push(`${c} · required`));
  r.soft_preferences.forEach((p) => items.push(`${p} · preference`));
  return `<div class="understood" aria-label="Request as understood">${items.map((i) => `<span>${esc(i)}</span>`).join("")}</div>`;
}

function beachCounts(view) {
  const n = (e) => view.beaches.filter((b) => b.eligibility === e).length;
  const parts = [];
  if (view.recommendations.length) parts.push(`<span class="badge b-ok">✓ ${view.recommendations.length} recommended</span>`);
  if (n("EXCLUDED")) parts.push(`<span class="badge b-bad">✕ ${n("EXCLUDED")} excluded</span>`);
  if (n("NEEDS_INVESTIGATION")) parts.push(`<span class="badge b-warn">◌ ${n("NEEDS_INVESTIGATION")} needs more evidence</span>`);
  if (n("UNSUPPORTED")) parts.push(`<span class="badge b-muted">– ${n("UNSUPPORTED")} unsupported</span>`);
  return `<div class="counts">${parts.join("")}</div>`;
}

function resultPanel(summary, view) {
  const head = `<section class="panel">
    <span class="eyebrow">${esc(view.activity)} · ${esc(view.window.display)}</span>
    <div class="result-head">
      <div class="stack grow">
        ${badge(OUTCOME, view.outcome)}
        <h1>${view.outcome === "RECOMMENDATIONS" ? esc(plural(view.recommendations.length, "beach meets", "beaches meet") + " every requirement")
          : view.outcome === "NO_RECOMMENDATION" ? "No beach can be recommended from the available evidence" : "Technical error"}</h1>
        ${understood(view)}
        ${beachCounts(view)}
      </div>
      <div class="tiles side">
        <div class="tile"><div class="num">${view.usage.tool_calls} <span class="of">/ ${view.usage.max_tool_calls}</span></div><div class="tiny muted">tool calls</div></div>
        <div class="tile"><div class="num">${view.usage.iterations} <span class="of">/ ${view.usage.max_iterations}</span></div><div class="tiny muted">iterations</div></div>
      </div>
    </div>
    ${list(view.general_warnings)}
    <div class="btn-row small">
      <span class="muted">${summary.kind === "authored" ? "Authored demonstration · zero model calls" : summary.kind === "live" ? "Live model run" : "Local model run"} · revision ${esc(view.request_revision)}</span>
      ${summary.has_trace ? `<a href="#/inspector/run/${esc(summary.run_id)}">Run inspector →</a>` : ""}
      ${view.beaches.length ? `<a href="#/evidence/${esc(summary.run_id)}">All evidence →</a>` : ""}
    </div>
  </section>`;
  if (view.outcome === "ERROR") {
    return head + `<section class="panel"><div class="notice bad">${esc(view.error.summary)}</div>
      <span class="small muted">No beach was judged. The session has ended; the next request starts a new one.</span></section>`;
  }
  if (view.outcome === "NO_RECOMMENDATION") return head + abstainPanels(summary, view);
  const fav = view.recommendations.filter((r) => r.environmental_suitability === "FAVORABLE");
  const other = view.recommendations.filter((r) => r.environmental_suitability !== "FAVORABLE");
  return head + `
    ${fav.length ? `<section class="panel"><div class="panel-head"><h2>${fav.length > 1 ? "Similarly suitable" : "Recommended"}</h2>
      <span class="small muted">No finer rank is claimed</span></div><div class="cards">${fav.map((r) => recCard(r, view)).join("")}</div></section>` : ""}
    ${other.length ? `<section class="panel"><div class="panel-head"><h2>Also eligible</h2><span class="small muted">Mixed conditions, permitted with disclosure</span></div>
      <div class="cards">${other.map((r) => recCard(r, view)).join("")}</div></section>` : ""}
    <div class="row">
      ${exclusionsPanel(view)}
      <section class="panel side map"><div class="panel-head"><h2>Where they are</h2><span class="tiny muted">Schematic · fictional test coordinates · not for navigation</span></div>${mapSvg(view)}</section>
    </div>
    ${view.general_limitations.length ? `<section class="panel"><h2>General limitations</h2>${list(view.general_limitations)}</section>` : ""}`;
}

function recCard(rec, view) {
  const beach = view.beaches.find((b) => b.beach_id === rec.beach_id) || {};
  return `<article class="card">
    <div class="card-head"><div><h3>${esc(rec.name)}</h3><span class="small muted">${esc(beach.locality || "")} · ${esc(label(beach.region))}</span></div>
      <span class="badge ${rec.environmental_suitability === "FAVORABLE" ? "b-ok" : "b-warn"}">${esc(label(rec.environmental_suitability))}</span></div>
    <span class="small">Evidence: ${esc(label(rec.evidence_quality))} · ${esc(rec.window.display)}</span>
    <p class="small">${esc(rec.reason)}</p>
    <p class="small muted">${esc(rec.summary)}</p>
    ${rec.warnings.length ? `<div><strong class="small">Warnings and disclosures</strong>${list(rec.warnings, "small")}</div>` : ""}
    ${rec.limitations.length ? `<div><strong class="small">Limitations</strong>${list(rec.limitations, "small")}</div>` : ""}
    ${rec.preferences.length ? `<div><strong class="small">Preferences</strong>${list(rec.preferences, "small")}</div>` : ""}
    ${rec.advisories.length ? `<div><strong class="small">Reported advisories</strong>${list(rec.advisories.map((a) => `${a.type} — ${a.issuer} (${a.effective})`), "small")}</div>` : ""}
    <span class="small muted">${esc(plural(rec.evidence.length, "source"))} · ${esc(rec.attribution.map((a) => a.publisher).join(", "))}</span>
    <button type="button" class="link-btn small" data-beach="${esc(rec.beach_id)}">Open evidence for ${esc(rec.name)} →</button>
  </article>`;
}

function exclusionsPanel(view) {
  if (!view.exclusions.length) return "";
  return `<section class="panel grow"><h2>Not recommended (excluded)</h2>
    <ul class="list-plain">${view.exclusions.map((e) => `<li><strong>${esc(e.name)}</strong>: ${esc(e.reasons.join("; "))}
      <button type="button" class="link-btn small" data-beach="${esc(e.beach_id)}">evidence</button></li>`).join("")}</ul>
    <span class="small muted">Safety exclusions take precedence over preferences and favorable evidence.</span></section>`;
}

function mapSvg(view) {
  const pts = view.beaches.filter((b) => b.latitude != null && b.longitude != null);
  if (!pts.length) return `<span class="small muted">No catalog coordinates.</span>`;
  const lats = pts.map((b) => b.latitude), lons = pts.map((b) => b.longitude);
  const [la0, la1, lo0, lo1] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
  const sx = (v) => 40 + (lo1 === lo0 ? 0.5 : (v - lo0) / (lo1 - lo0)) * 240;
  const sy = (v) => 30 + (la1 === la0 ? 0.5 : 1 - (v - la0) / (la1 - la0)) * 140;
  const rec = new Set(view.recommendations.map((r) => r.beach_id));
  const color = (b) => rec.has(b.beach_id) ? "#1D6B45" : b.eligibility === "EXCLUDED" ? "#A8261D" : b.eligibility === "UNSUPPORTED" ? "#4E6169" : "#8A4700";
  return `<svg viewBox="0 0 320 210" role="img" aria-label="Schematic positions of the candidate beaches">
    <rect x="1" y="1" width="318" height="208" rx="10" fill="#EAF2F4" stroke="#D6DFE2"></rect>
    ${pts.map((b, i) => { const cx = sx(b.longitude) + (i % 2) * 6, cy = sy(b.latitude) + i * 4, left = cx > 170;
      return `<g><circle cx="${cx}" cy="${cy}" r="7" fill="${color(b)}"></circle>
      <text x="${left ? cx - 12 : cx + 12}" y="${cy + 4}" font-size="11" fill="#10242B" text-anchor="${left ? "end" : "start"}">${esc(b.name.replace(/^Fictional /, "").replace(/ \(SYNTHETIC\)$/, ""))}</text></g>`; }).join("")}
  </svg>
  <span class="tiny muted"><span class="t-ok">●</span> recommended <span class="t-warn">●</span> needs evidence <span class="t-bad">●</span> excluded <span class="muted">●</span> unsupported</span>`;
}

function abstainPanels(summary, view) {
  const ab = view.abstention;
  const missing = view.beaches.map((b) => `<tr><th scope="row">${esc(b.name)}</th>
      <td>${badge(ELIG, b.eligibility)}</td><td>${esc(label(b.evidence_quality))}</td>
      <td>${list(b.evidence_limitations.filter((l) => /^Missing|unavailable|not cover/i.test(l)), "small") || `<span class="small muted">—</span>`}</td></tr>`).join("");
  const u = view.usage;
  return `<section class="panel">
      <p>${esc(ab.explanation)}</p>
      <div class="notice info small"><strong>This is not a technical error.</strong> The investigation finished normally and abstained. Missing information is never treated as good conditions.</div>
    </section>
    <section class="panel"><div class="panel-head"><h2>What's missing, by beach</h2><span class="small muted">From the validated assessments</span></div>
      <div class="scroll"><table><thead><tr><th scope="col">Beach</th><th scope="col">Status</th><th scope="col">Evidence</th><th scope="col">Missing or unavailable</th></tr></thead><tbody>${missing}</tbody></table></div>
    </section>
    <div class="row">
      <section class="panel grow"><h2>What was tried</h2><ol class="list-plain tried" id="tried"><li><span></span><span class="small muted">${summary.has_trace ? "Reading the trace…" : "No trace is available for this run."}</span><span></span></li></ol>
        ${summary.has_trace ? `<a href="#/inspector/run/${esc(summary.run_id)}">See every step in the run inspector →</a>` : ""}</section>
      <div class="side stack">
        <section class="panel"><h2>Limits used</h2><div class="tiles">
          <div class="tile"><div class="num">${u.tool_calls} <span class="of">/ ${u.max_tool_calls}</span></div><div class="tiny muted">tool calls</div></div>
          <div class="tile"><div class="num">${u.iterations} <span class="of">/ ${u.max_iterations}</span></div><div class="tiny muted">iterations</div></div>
          <div class="tile"><div class="num">${u.retries} <span class="of">/ ${u.max_retries}</span></div><div class="tiny muted">retries per failed call</div></div>
          <div class="tile"><div class="num">${u.fallback_attempted ? "yes" : "no"}</div><div class="tiny muted">fallback attempted</div></div>
        </div><span class="small muted">The system stops at these limits instead of searching until something looks good.</span></section>
        ${ab.next_steps.length ? `<section class="panel"><h2>What you can do</h2>${list(ab.next_steps)}<span class="small muted">Each starts a new investigation; none has been checked yet.</span></section>` : ""}
      </div>
    </div>
    ${ab.unresolved.length ? `<section class="panel"><h2>Unresolved questions</h2>${list(ab.unresolved, "small")}</section>` : ""}
    ${exclusionsPanel(view)}
    ${view.general_limitations.length ? `<section class="panel"><h2>Limitations</h2>${list(view.general_limitations)}</section>` : ""}`;
}

async function fillTried(runId) {
  const box = document.getElementById("tried");
  if (!box) return;
  try {
    const trace = await getTrace(runId);
    const rows = trace.events.filter((e) => /^(TOOL_|RETRY_INITIATED|FALLBACK_INITIATED)/.test(e.type) && e.type !== "TOOL_CALLED");
    const field = (e, k) => { const v = (e.fields.find((f) => f[0] === k) || [])[1]; return v === "null" ? "" : v; };
    box.innerHTML = rows.map((e) => {
      const failed = e.type === "TOOL_FAILED", rec = /RETRY|FALLBACK/.test(e.type);
      const glyph = failed ? `<span class="t-bad">✕</span>` : rec ? `<span class="t-warn">↻</span>` : `<span class="t-ok">✓</span>`;
      const what = rec ? label(e.type) : `${field(e, "tool_name") || "tool"} ${failed ? "failed" : "completed"}`;
      const why = field(e, "error_code") || field(e, "reason") || "";
      return `<li>${glyph}<span><strong>${esc(what)}</strong>${why ? `<br><span class="small muted">${esc(why)}</span>` : ""}</span><span class="mono muted">#${e.seq}</span></li>`;
    }).join("") || `<li><span></span><span class="small muted">No tool activity recorded.</span><span></span></li>`;
  } catch (error) {
    box.innerHTML = `<li><span></span><span class="small t-bad">${esc(error.message)}</span><span></span></li>`;
  }
}

// --- Evidence --------------------------------------------------------------
async function renderEvidence(runId, beachId) {
  const id = runId || state.current || (latest((r) => r.has_view) || {}).run_id;
  if (!id) { app.innerHTML = `<section class="panel"><div class="empty">Run something on the Plan page first.</div></section>`; return; }
  const data = await getRun(id);
  const view = data.view;
  if (!view || !view.beaches.length) { app.innerHTML = `<section class="panel"><div class="empty">This run has no beach assessments to show.</div></section>`; return; }
  const beach = view.beaches.find((b) => b.beach_id === beachId) || view.beaches.find((b) => view.recommendations.some((r) => r.beach_id === b.beach_id)) || view.beaches[0];
  const tabs = view.beaches.map((b) => `<a class="chip" href="#/evidence/${esc(id)}/${esc(b.beach_id)}" ${b.beach_id === beach.beach_id ? 'aria-current="page"' : ""}>${esc(b.name.replace(/ \(SYNTHETIC\)$/, ""))}</a>`).join("");
  const checks = (items, desc) => items.length ? `<ul class="list-plain small">${items.map((i) => { const [cls, t] = RESULT[i.result] || RESULT[i.alignment] || ["muted", label(i.result || i.alignment)];
      return `<li><span class="${cls}">${esc(t)}</span> ${esc(desc(i))}</li>`; }).join("")}</ul>` : `<span class="small muted">None.</span>`;
  const cat = beach.catalog;
  app.innerHTML = `
    <section class="panel">
      <span class="small muted"><a href="#/plan/${esc(id)}">Plan</a> / ${esc(view.activity)}, ${esc(view.window.display)}</span>
      <h1>${esc(beach.name)}</h1>
      <span class="small muted">${esc(beach.locality)} · ${esc(label(beach.region))}${beach.geographic_preference_match ? " · " + esc(label(beach.geographic_preference_match)) : ""}</span>
      <div class="btn-row">${tabs}</div>
    </section>
    <div class="grid2">
      <section class="panel"><span class="eyebrow">Eligibility</span>${badge(ELIG, beach.eligibility)}</section>
      <section class="panel"><span class="eyebrow">Environmental suitability</span><strong>${esc(label(beach.environmental_suitability))}</strong></section>
      <section class="panel"><span class="eyebrow">Evidence quality</span><strong>${esc(label(beach.evidence_quality))}</strong></section>
    </div>
    <span class="small muted">These three judgments are independent. None is a score, and together they are not a guarantee of safety.</span>
    <section class="panel timeline"><div class="panel-head"><h2>When each source applies</h2><span class="small muted">Shaded band: your window</span></div>${timelineSvg(view, [...beach.supporting, ...beach.conflicting, ...beach.rejected])}</section>
    <div class="row">
      <div class="grow stack">
        <section class="panel"><h2>Evidence used</h2>${beach.supporting.map(sourceBlock).join("") || `<span class="small muted">None accepted for this beach.</span>`}</section>
        ${beach.conflicting.length ? `<section class="panel"><h2>Conflicting evidence</h2>${beach.conflicting.map(sourceBlock).join("")}</section>` : ""}
        ${beach.rejected.length ? `<section class="panel"><h2>Evidence not used</h2>${beach.rejected.map(sourceBlock).join("")}</section>` : ""}
      </div>
      <div class="side stack">
        <section class="panel"><h2>Checks</h2>
          <strong class="small">Safety policy</strong>${checks(beach.policy_checks, (i) => i.explanation)}
          <strong class="small">Your hard constraints</strong>${checks(beach.hard_constraints, (i) => i.description)}
          <strong class="small">Your preferences</strong>${checks(beach.preferences, (i) => `${i.description}: ${i.explanation}`)}
          <span class="tiny muted">Unknown is never counted as a pass. Preferences can't override safety rules.</span>
        </section>
        ${beach.evidence_limitations.length || beach.safety_limitations.length ? `<section class="panel"><h2>Limitations</h2>${list([...beach.evidence_limitations, ...beach.safety_limitations], "small")}</section>` : ""}
        ${beach.remaining_questions.length ? `<section class="panel"><h2>Remaining questions</h2>${list(beach.remaining_questions, "small")}</section>` : ""}
        <section class="panel"><h2>About this beach</h2><span class="tiny muted">Stable catalog facts, separate from today's conditions</span>
          <dl class="kv">
            ${cat.shore_type ? `<dt>Shore</dt><dd>${esc(label(cat.shore_type))}</dd>` : ""}
            ${cat.reef_presence ? `<dt>Reef</dt><dd>${esc(label(cat.reef_presence))}</dd>` : ""}
            ${cat.lifeguard_status ? `<dt>Lifeguard</dt><dd>${esc(label(cat.lifeguard_status))}</dd>` : ""}
            <dt>Activities</dt><dd>${esc(cat.supported_activities.join(", "))}</dd>
            <dt>Verified</dt><dd>${esc(cat.last_verified)} · fictional test catalog</dd>
          </dl>
          ${cat.sources.map((s) => `<span class="ref">${esc(s.title)} — ${esc(s.reference)}</span>`).join("")}
        </section>
      </div>
    </div>`;
}

function sourceBlock(f) {
  const when = [f.valid_from && f.valid_until ? `Applies ${f.valid_from.display} to ${f.valid_until.display}` : "",
    f.issued_at ? `issued ${f.issued_at.display}` : "", f.observed_at ? `observed ${f.observed_at.display}` : "",
    `retrieved ${f.retrieved_at.display}`].filter(Boolean).join(" · ");
  return `<div class="source">
    <div class="card-head"><strong>${esc(f.provider)}</strong>${badge(VALID, f.validation_status)}</div>
    <span class="small">${esc(f.finding_type)} · ${esc(f.coverage_type)}: ${esc(f.coverage)}</span>
    ${list(f.measurements, "small")}
    ${f.advisories.length ? list(f.advisories.map((a) => `${a.type} — ${a.issuer}; ${a.area}; ${a.effective}`), "small") : ""}
    ${f.limitations.length ? `<span class="tiny muted">${esc(f.limitations.join(" "))}</span>` : ""}
    <span class="tiny muted">${esc(when)}</span>
    ${f.reference ? `<span class="ref">${esc(f.reference)}</span>` : ""}
  </div>`;
}

function timelineSvg(view, findings) {
  const items = findings.filter((f, i, all) => all.findIndex((g) => g.finding_id === f.finding_id) === i);
  if (!items.length) return `<span class="small muted">No sources for this beach.</span>`;
  const times = [view.window.start.iso, view.window.end.iso];
  items.forEach((f) => [f.valid_from, f.valid_until, f.issued_at, f.observed_at, f.retrieved_at].forEach((t) => t && times.push(t.iso)));
  const ms = times.map((t) => Date.parse(t));
  const t0 = Math.min(...ms), t1 = Math.max(...ms), span = Math.max(t1 - t0, 1);
  const X = (t) => 240 + ((Date.parse(t) - t0) / span) * 450;
  const rowH = 26, h = 30 + items.length * rowH;
  const fill = { ACCEPTED: "#1D6B45", LIMITED: "#8A4700", REJECTED: "#A8261D" };
  const bars = items.map((f, i) => {
    const y = 24 + i * rowH;
    const start = f.valid_from || f.observed_at || f.issued_at || f.retrieved_at, end = f.valid_until || start;
    const x0 = X(start.iso), x1 = Math.max(X(end.iso), x0 + 4);
    return `<text x="8" y="${y + 13}" font-size="11.5" fill="#10242B">${esc(f.provider.length > 36 ? f.provider.slice(0, 35) + "…" : f.provider)}</text>
      <rect x="${x0}" y="${y + 3}" width="${x1 - x0}" height="14" rx="3" fill="${fill[f.validation_status] || "#4E6169"}" opacity="${f.validation_status === "ACCEPTED" ? 1 : 0.55}"></rect>
      ${f.issued_at ? `<circle cx="${X(f.issued_at.iso)}" cy="${y + 10}" r="3" fill="#10242B"></circle>` : ""}`;
  }).join("");
  return `<div class="scroll"><svg viewBox="0 0 700 ${h}" role="img" aria-label="Source applicability against the requested window">
    <rect x="${X(view.window.start.iso)}" y="14" width="${X(view.window.end.iso) - X(view.window.start.iso)}" height="${h - 14}" fill="#E1EFF1"></rect>
    <text x="${X(view.window.start.iso)}" y="10" font-size="10.5" fill="#0B5F6C">your window</text>${bars}
  </svg></div><span class="tiny muted">Bar: applicability or observation time · dot: issued · green accepted, amber limited, red rejected</span>`;
}

// --- Run inspector ---------------------------------------------------------
async function renderInspector(kind, key) {
  let traceKey = null, title = "";
  if (kind === "recorded" && key) { traceKey = `recorded:${key}`; title = key; }
  else {
    const id = (kind === "run" && key) || (latest((r) => r.has_trace) || {}).run_id;
    if (id) { traceKey = id; const r = runs().find((x) => x.run_id === id); title = r ? `${r.label}${r.request_text ? " · " + r.request_text : ""}` : id; }
  }
  if (!traceKey) { app.innerHTML = `<section class="panel"><div class="empty">No trace yet. Run something on the Plan page, or open a <a href="#/recorded">recorded run</a>.</div></section>`; return; }
  const t = await getTrace(traceKey);
  if (state.selKey !== traceKey) { state.sel = (t.events.find((e) => /FAILED|REJECTED|ABSTAINED/.test(e.type) || e.fields.some((f) => f[0] === "valid" && f[1] === "false")) || t.events[0] || {}).seq; state.selKey = traceKey; state.filter = "all"; }
  const m = t.metrics;
  const modeText = t.model_identifier ? `${t.model_identifier} · ${t.profile_id || ""} · ${t.execution_mode || ""}` : "Authored demonstration · no model";
  const filters = [["all", "All"], ["tool", "Agents and tools"], ["evidence", "Evidence"], ["safety", "Validation and safety"], ["lifecycle", "Lifecycle"]];
  const shown = t.events.filter((e) => state.filter === "all" || e.group === state.filter);
  const sel = t.events.find((e) => e.seq === state.sel) || t.events[0];
  const typeCls = (ty, e) => /FAILED|REJECTED/.test(ty) || e.fields.some((f) => f[0] === "valid" && f[1] === "false") ? "bad" : /RETRY|FALLBACK|LIMIT/.test(ty) ? "warn" : "";
  app.innerHTML = `
    <div class="result-head">
      <div class="stack grow"><span class="mono muted">trace ${esc(t.trace_id)} · digest ${esc(t.digest.slice(0, 16))}…</span>
        <h1>${esc(title)}</h1><span class="small muted">${esc(modeText)}</span></div>
      <div class="btn-row">${badge(OUTCOME, t.metrics.outcome)}
        <span class="badge ${t.complete ? "b-ok" : "b-warn"}">${t.complete ? "✓ Trace complete and valid" : "Incomplete trace"}</span>
        ${t.raw_payloads_retained === false ? `<span class="badge b-muted">Raw payloads not retained</span>` : ""}</div>
    </div>
    <section class="tiles" aria-label="Run totals">
      ${[["duration", `${(m.duration_ms / 1000).toFixed(2)} s`], ["iterations", m.iterations], ["tool calls", m.tool_calls], ["model calls", m.model_calls],
         ["retries", m.retries], ["fallbacks", m.fallbacks], ["evidence accepted", m.evidence_accepted], ["evidence limited/rejected", `${m.evidence_limited}/${m.evidence_rejected}`]]
        .map(([k, v]) => `<div class="tile panel"><div class="num">${esc(v)}</div><div class="tiny muted">${esc(k)}</div></div>`).join("")}
    </section>
    <section class="panel lanes"><div class="panel-head"><h2>Who did what, when</h2><span class="small muted">Recorded timestamps · ${esc(t.event_count)} events</span></div>${lanesSvg(t)}</section>
    <div class="row">
      <section class="panel grow">
        <div class="panel-head"><h2>Events</h2><div class="btn-row" role="group" aria-label="Filter events">
          ${filters.map(([k, l]) => `<button type="button" class="chip" data-filter="${k}" aria-pressed="${state.filter === k}">${l}</button>`).join("")}</div></div>
        <div class="scroll"><div class="events">
          <div class="ev head"><span>#</span><span>time</span><span>event</span><span>actor</span><span>summary</span></div>
          ${shown.map((e) => `<button type="button" class="ev" data-seq="${e.seq}" aria-pressed="${e.seq === state.sel}">
            <span class="muted">${e.seq}</span><span class="muted">+${e.t.toFixed(3)}</span><span class="type ${typeCls(e.type, e)}">${esc(e.type)}</span>
            <span>${esc(e.actor)}</span><span class="sum">${esc(e.summary)}</span></button>`).join("")}
        </div></div>
        <span class="small muted">Showing ${shown.length} of ${t.event_count} events, read from the validated JSONL trace.</span>
      </section>
      <aside class="panel dark side detail" aria-label="Event detail">
        ${sel ? `<span class="eyebrow">Event ${sel.seq} · +${sel.t.toFixed(3)} s · ${esc(sel.actor)}</span><h2 class="mono">${esc(sel.type)}</h2>
          <dl>${sel.fields.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>` : ""}
        <span class="tiny muted">Stored, sanitized fields only. No credentials, raw source payloads or model reasoning are recorded.</span>
      </aside>
    </div>`;
  app.querySelectorAll("[data-filter]").forEach((b) => b.addEventListener("click", () => { state.filter = b.dataset.filter; renderInspector(kind, key); }));
  app.querySelectorAll("[data-seq]").forEach((b) => b.addEventListener("click", () => { state.sel = Number(b.dataset.seq); renderInspector(kind, key); }));
}

function lanesSvg(t) {
  const actors = [...new Set(t.events.map((e) => e.actor))];
  const dur = Math.max(t.duration_s, 0.001), W = 820, L = 130, rowH = 28;
  const X = (s) => L + (s / dur) * (W - L - 10);
  const color = (e) => /FAILED|REJECTED/.test(e.type) || e.fields.some((f) => f[0] === "valid" && f[1] === "false") ? "#A8261D"
    : /RETRY|FALLBACK|LIMIT/.test(e.type) ? "#8A4700" : e.group === "tool" ? "#1D6B45" : e.group === "lifecycle" ? "#2456A6" : "#4E6169";
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => `<text x="${X(f * dur)}" y="12" font-size="10" fill="#4E6169" text-anchor="middle">${(f * dur).toFixed(1)} s</text>`).join("");
  const rows = actors.map((a, i) => {
    const y = 22 + i * rowH;
    const marks = t.events.filter((e) => e.actor === a).map((e) => `<rect x="${X(e.t) - 1.5}" y="${y + 4}" width="3" height="16" fill="${color(e)}"><title>#${e.seq} ${esc(e.type)}</title></rect>`).join("");
    return `<text x="0" y="${y + 16}" font-size="11.5" fill="#10242B">${esc(a.toLowerCase())}</text><rect x="${L}" y="${y + 2}" width="${W - L - 10}" height="20" rx="4" fill="#F0F4F5"></rect>${marks}`;
  }).join("");
  return `<div class="scroll"><svg viewBox="0 0 ${W} ${26 + actors.length * rowH}" role="img" aria-label="Event timeline by actor">${ticks}${rows}</svg></div>
    <span class="tiny muted"><span class="t-ok">■</span> tools <span class="t-warn">■</span> retry/fallback/limit <span class="t-bad">■</span> failed or rejected · grey: validation · blue: lifecycle</span>`;
}

// --- Recorded runs ---------------------------------------------------------
async function renderRecorded() {
  const data = await api("GET", "/api/evidence");
  if (!data.available) { app.innerHTML = `<section class="panel"><div class="empty">The evidence package (docs/evaluation-evidence) was not found. Start hafi web from the repository root.</div></section>`; return; }
  const g = (data.summary.trace_groups || [])[0] || {};
  app.innerHTML = `
    <section class="panel">
      <h1>Recorded genuine-model runs</h1>
      <p class="small">Six unchanged traces from the M1 evaluation (<span class="mono">gpt-6-luna</span>, profile 0.8), published in <span class="mono">docs/evaluation-evidence</span>.
        They are representative examples: 6 of 52 investigations. Opening them makes no model calls.</p>
      <div class="tiles">
        <div class="tile"><div class="num">${esc(data.summary.valid_investigations)}</div><div class="tiny muted">valid traces</div></div>
        <div class="tile"><div class="num">${esc(data.summary.issues)}</div><div class="tiny muted">input issues</div></div>
        ${g.operational_success ? `<div class="tile"><div class="num">${g.operational_success.numerator} <span class="of">/ ${g.operational_success.denominator}</span></div><div class="tiny muted">operational successes (these 6)</div></div>` : ""}
      </div>
    </section>
    <section class="panel"><div class="scroll"><table><thead><tr><th scope="col">Example</th><th scope="col">Scenario</th><th scope="col">Round</th><th scope="col">Outcome</th><th scope="col">Model</th><th scope="col"></th></tr></thead>
      <tbody>${data.traces.map((r) => `<tr><th scope="row">${esc(r.demonstrates)}</th><td>${esc(r.scenario_id)}${r.scenario_step > 1 ? " step " + esc(r.scenario_step) : ""}</td>
        <td>${esc(r.evaluation_round)}</td><td>${badge(OUTCOME, r.investigation_outcome)}</td><td class="mono">${esc(r.model_identifier)} · ${esc(r.execution_mode)}</td>
        <td><a href="#/inspector/recorded/${esc(r.name)}">Inspect →</a></td></tr>`).join("")}</tbody></table></div>
      <span class="small muted">Model identity and mode are recorded by the application; they are not independent proof of network inference.</span>
    </section>`;
}

route();
