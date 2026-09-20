const API = "";

function fmtMoney(v) {
  return "₹" + Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function riskClass(score) {
  if (score >= 0.75) return "risk-red";
  if (score >= 0.4) return "risk-amber";
  return "risk-green";
}

function tickClock() {
  document.getElementById("clock").textContent = new Date().toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}
setInterval(tickClock, 1000);
tickClock();

/* ============================================================
   VIEW SWITCHING
   ============================================================ */
const VIEWS = ["dashboard", "live", "lookup", "analytics", "model", "settings"];
let currentView = "dashboard";
const viewLoaders = {}; // populated below, one loader fn per view

function switchView(view) {
  if (!VIEWS.includes(view)) return;
  currentView = view;
  VIEWS.forEach(v => {
    document.getElementById("view-" + v).classList.toggle("hidden", v !== view);
  });
  document.querySelectorAll(".nav-item").forEach(el => {
    el.classList.toggle("active", el.dataset.view === view);
  });
  if (viewLoaders[view]) viewLoaders[view]();
}

document.querySelectorAll(".nav-item[data-view]").forEach(el => {
  el.addEventListener("click", () => switchView(el.dataset.view));
});
document.querySelectorAll("[data-goto]").forEach(el => {
  el.addEventListener("click", () => switchView(el.dataset.goto));
});

/* ============================================================
   REUSABLE "CHECK A TRANSACTION" PANEL
   Used by both the Dashboard sidebar panel and the full
   Transaction Lookup page. Built from a template + scoped by
   data-role attributes so both instances can coexist.
   ============================================================ */
function checkPanelTemplate(heading, subtitle) {
  return `
    <h3>⌕ ${heading} <span class="muted small">(Interactive)</span></h3>
    <p class="muted small">${subtitle}</p>
    <div class="check-row">
      <input data-role="input" placeholder="e.g. TXN_789455" />
      <button data-role="checkBtn">Check</button>
    </div>
    <div data-role="resultBlock" class="result-block hidden">
      <div class="result-title">Latest Result</div>
      <div data-role="resultCard" class="result-card">
        <div class="result-badge"><span data-role="resultIcon">🛡️</span> <span data-role="resultDecision">—</span></div>
        <div class="result-sub" data-role="resultSub">—</div>
      </div>
      <div class="grid2">
        <div><label>Transaction ID</label><div data-role="rTxnId">—</div></div>
        <div><label>Amount</label><div data-role="rAmount">—</div></div>
        <div><label>User ID</label><div data-role="rUser">—</div></div>
        <div><label>Merchant</label><div data-role="rMerchant">—</div></div>
        <div><label>Timestamp</label><div data-role="rTs">—</div></div>
        <div><label>Risk Score</label><div data-role="rScore" class="risk">—</div></div>
      </div>
      <div class="reasons">
        <label>Reason for Flag</label>
        <ul data-role="rReasons"></ul>
      </div>
      <div class="ai-box">
        <div class="ai-head">💬 AI Fraud Investigator</div>
        <div data-role="rAi" class="ai-text">—</div>
      </div>
      <div class="action-row">
        <button data-role="markRealBtn" class="btn-green">Mark as Real (Override)</button>
        <button data-role="reportFraudBtn" class="btn-red">Report as Fraud</button>
      </div>
    </div>
    <div data-role="emptyMsg" class="muted small" style="margin-top:6px;"></div>
  `;
}

function wireCheckPanel(root) {
  const q = role => root.querySelector(`[data-role="${role}"]`);
  let currentTxnId = null;

  async function checkTxn(idFromCaller) {
    const id = idFromCaller || q("input").value.trim();
    if (!id) return;
    q("input").value = id;
    const res = await fetch(API + "/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_id: id }),
    }).then(r => r.json());

    const block = q("resultBlock");
    const empty = q("emptyMsg");
    if (!res.found) {
      block.classList.add("hidden");
      empty.textContent = res.message || "Transaction not found.";
      return;
    }
    empty.textContent = "";
    block.classList.remove("hidden");
    currentTxnId = res.transaction_id;

    const card = q("resultCard");
    card.className = "result-card " + res.decision;
    const icon = res.decision === "FRAUD" ? "🛑" : res.decision === "REVIEW" ? "🔍" : "✅";
    q("resultIcon").textContent = icon;
    q("resultDecision").textContent =
      res.decision === "FRAUD" ? "FRAUD" : res.decision === "REVIEW" ? "UNDER REVIEW" : "LEGITIMATE";
    q("resultSub").textContent =
      res.decision === "FRAUD" ? "High risk transaction detected" :
      res.decision === "REVIEW" ? "Needs manual review" : "No significant risk detected";

    q("rTxnId").textContent = res.transaction_id;
    q("rAmount").textContent = fmtMoney(res.amount);
    q("rUser").textContent = res.user_id;
    q("rMerchant").textContent = res.merchant;
    q("rTs").textContent = res.ts;
    const scoreEl = q("rScore");
    scoreEl.textContent = res.risk_score.toFixed(2);
    scoreEl.className = "risk " + riskClass(res.risk_score);

    const ul = q("rReasons");
    ul.innerHTML = "";
    (res.reasons || []).forEach(r => {
      const li = document.createElement("li");
      li.textContent = r;
      ul.appendChild(li);
    });

    q("rAi").textContent = res.ai_explanation || "";
  }

  q("checkBtn").addEventListener("click", () => checkTxn());
  q("input").addEventListener("keydown", e => { if (e.key === "Enter") checkTxn(); });

  q("markRealBtn").addEventListener("click", async () => {
    if (!currentTxnId) return;
    await fetch(API + "/api/transaction/override", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_id: currentTxnId }),
    });
    checkTxn(currentTxnId);
    refreshDashboard();
  });

  q("reportFraudBtn").addEventListener("click", async () => {
    if (!currentTxnId) return;
    await fetch(API + "/api/transaction/report", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_id: currentTxnId }),
    });
    checkTxn(currentTxnId);
    refreshDashboard();
  });

  return { checkTxn };
}

// Build the two check-panel instances
const dashPanelRoot = document.getElementById("dashCheckPanel");
dashPanelRoot.innerHTML = checkPanelTemplate("Check a Transaction", "Enter a transaction ID to see if it's real or fraud");
const dashCheck = wireCheckPanel(dashPanelRoot);

const lookupPanelRoot = document.getElementById("lookupCheckPanel");
lookupPanelRoot.innerHTML = checkPanelTemplate("Transaction Lookup", "Look up any transaction by ID for a full risk breakdown");
const lookupCheck = wireCheckPanel(lookupPanelRoot);

// Table rows call this global to jump into the dashboard's check panel
function checkTxn(id) {
  dashCheck.checkTxn(id);
}
function checkTxnInLookup(id) {
  switchView("lookup");
  lookupCheck.checkTxn(id);
}

/* ============================================================
   DASHBOARD VIEW
   ============================================================ */
let trendChart, donutChart;

async function loadStats() {
  const s = await fetch(API + "/api/stats").then(r => r.json());
  document.getElementById("statTotal").textContent = s.total.toLocaleString();
  document.getElementById("statFraud").textContent = s.fraud.toLocaleString();
  document.getElementById("statReview").textContent = s.review.toLocaleString();
  document.getElementById("statReal").textContent = s.real.toLocaleString();
  document.getElementById("statFraudPct").textContent = s.fraud_pct + "%";
  document.getElementById("statReviewPct").textContent = s.review_pct + "%";
  document.getElementById("statRealPct").textContent = s.real_pct + "%";
  document.getElementById("processedCount").textContent = s.total.toLocaleString();

  document.getElementById("donutPct").textContent = s.fraud_pct + "%";
  document.getElementById("legendFraud").textContent = `${s.fraud} (${s.fraud_pct}%)`;
  document.getElementById("legendReview").textContent = `${s.review} (${s.review_pct}%)`;
  document.getElementById("legendReal").textContent = `${s.real} (${s.real_pct}%)`;

  const ctx2 = document.getElementById("donutChart");
  const data = [s.real, s.review, s.fraud];
  if (!donutChart) {
    donutChart = new Chart(ctx2, {
      type: "doughnut",
      data: {
        labels: ["Real", "Review", "Fraud"],
        datasets: [{ data, backgroundColor: ["#22c55e", "#f59e0b", "#ef4444"], borderWidth: 0 }],
      },
      options: { cutout: "72%", plugins: { legend: { display: false } } },
    });
  } else {
    donutChart.data.datasets[0].data = data;
    donutChart.update();
  }
}

async function loadTrend() {
  const rows = await fetch(API + "/api/transactions/trend").then(r => r.json());
  const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0") + ":00");
  const byHour = { real: {}, review: {}, fraud: {} };
  rows.forEach(r => {
    const key = r.decision === "REAL" ? "real" : r.decision === "REVIEW" ? "review" : "fraud";
    byHour[key][r.hour] = r.c;
  });
  const real = hours.map((_, h) => byHour.real[h] || 0);
  const review = hours.map((_, h) => byHour.review[h] || 0);
  const fraud = hours.map((_, h) => byHour.fraud[h] || 0);

  const ctx = document.getElementById("trendChart");
  if (!trendChart) {
    trendChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: hours,
        datasets: [
          { label: "Real", data: real, borderColor: "#22c55e", backgroundColor: "transparent", tension: 0.35, pointRadius: 0 },
          { label: "Review", data: review, borderColor: "#f59e0b", backgroundColor: "transparent", tension: 0.35, pointRadius: 0 },
          { label: "Fraud", data: fraud, borderColor: "#ef4444", backgroundColor: "transparent", tension: 0.35, pointRadius: 0 },
        ],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#8291ab", maxTicksLimit: 8 }, grid: { color: "#1f2b42" } },
          y: { ticks: { color: "#8291ab" }, grid: { color: "#1f2b42" } },
        },
      },
    });
  } else {
    trendChart.data.datasets[0].data = real;
    trendChart.data.datasets[1].data = review;
    trendChart.data.datasets[2].data = fraud;
    trendChart.update();
  }
}

function txnRowHtml(t, gotoLookup) {
  const time = t.ts.split(" ")[1] || t.ts;
  const onclick = gotoLookup ? `checkTxnInLookup('${t.transaction_id}')` : `checkTxn('${t.transaction_id}')`;
  return `
    <tr>
      <td>${time}</td>
      <td>${t.transaction_id}</td>
      <td>${t.user_id}</td>
      <td>${fmtMoney(t.amount)}</td>
      <td>${t.merchant}</td>
      <td><span class="badge ${t.decision}">${t.decision}</span></td>
      <td class="${riskClass(t.risk_score)}">${t.risk_score.toFixed(2)}</td>
      <td><a class="view-all" onclick="${onclick}">View</a></td>
    </tr>`;
}

async function loadRecent() {
  const rows = await fetch(API + "/api/transactions/recent?limit=8").then(r => r.json());
  document.getElementById("txnBody").innerHTML = rows.map(t => txnRowHtml(t, false)).join("");
}

async function refreshDashboard() {
  await Promise.all([loadStats(), loadTrend(), loadRecent()]);
}
viewLoaders.dashboard = refreshDashboard;

/* ============================================================
   LIVE TRANSACTIONS VIEW
   ============================================================ */
let liveFilter = "ALL";
document.querySelectorAll(".filter-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    liveFilter = btn.dataset.filter;
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.toggle("active", b === btn));
    loadLive();
  });
});

async function loadLive() {
  const rows = await fetch(API + "/api/transactions/recent?limit=60").then(r => r.json());
  const filtered = liveFilter === "ALL" ? rows : rows.filter(r => r.decision === liveFilter);
  document.getElementById("liveTxnBody").innerHTML = filtered.map(t => txnRowHtml(t, true)).join("");
}
viewLoaders.live = loadLive;

/* ============================================================
   TRANSACTION LOOKUP VIEW
   ============================================================ */
viewLoaders.lookup = () => {}; // nothing to preload; panel is interactive

/* ============================================================
   ANALYTICS VIEW
   ============================================================ */
let merchantChart, amountChart;

async function loadAnalytics() {
  const data = await fetch(API + "/api/analytics").then(r => r.json());

  const merchants = data.merchant_breakdown;
  const mCtx = document.getElementById("merchantChart");
  const mLabels = merchants.map(m => m.merchant);
  const mData = merchants.map(m => m.fraud_rate);
  if (!merchantChart) {
    merchantChart = new Chart(mCtx, {
      type: "bar",
      data: { labels: mLabels, datasets: [{ label: "Fraud rate %", data: mData, backgroundColor: "#ef4444" }] },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#8291ab", maxRotation: 60, minRotation: 60 }, grid: { display: false } },
          y: { ticks: { color: "#8291ab" }, grid: { color: "#1f2b42" } },
        },
      },
    });
  } else {
    merchantChart.data.labels = mLabels;
    merchantChart.data.datasets[0].data = mData;
    merchantChart.update();
  }

  const amounts = data.amount_by_decision;
  const order = ["REAL", "REVIEW", "FRAUD"];
  const sorted = order.map(d => amounts.find(a => a.decision === d) || { decision: d, avg_amount: 0 });
  const aCtx = document.getElementById("amountChart");
  const aData = sorted.map(a => a.avg_amount);
  const aColors = ["#22c55e", "#f59e0b", "#ef4444"];
  if (!amountChart) {
    amountChart = new Chart(aCtx, {
      type: "bar",
      data: { labels: order, datasets: [{ label: "Avg amount", data: aData, backgroundColor: aColors }] },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#8291ab" }, grid: { display: false } },
          y: { ticks: { color: "#8291ab" }, grid: { color: "#1f2b42" } },
        },
      },
    });
  } else {
    amountChart.data.datasets[0].data = aData;
    amountChart.update();
  }

  document.getElementById("merchantBody").innerHTML = merchants.map(m => `
    <tr>
      <td>${m.merchant}</td>
      <td>${m.total}</td>
      <td class="risk-red">${m.fraud}</td>
      <td class="risk-amber">${m.review}</td>
      <td>${m.fraud_rate}%</td>
      <td>${fmtMoney(m.avg_amount)}</td>
    </tr>`).join("");
}
viewLoaders.analytics = loadAnalytics;

/* ============================================================
   MODEL PERFORMANCE VIEW
   ============================================================ */
let featureChart;

async function loadModelPerformance() {
  const s = await fetch(API + "/api/model/performance").then(r => r.json());
  const metrics = s.metrics || {};
  const hasMetrics = metrics && Object.keys(metrics).length > 0;

  document.getElementById("modelNoMetrics").classList.toggle("hidden", hasMetrics);
  document.getElementById("modelMetricsWrap").classList.toggle("hidden", !hasMetrics);
  if (!hasMetrics) return;

  const cards = [
    ["Accuracy", metrics.accuracy, "blue"],
    ["Precision", metrics.precision, "green"],
    ["Recall", metrics.recall, "amber"],
    ["F1 Score", metrics.f1, "red"],
  ];
  document.getElementById("modelCards").innerHTML = cards.map(([label, val, color]) => `
    <div class="stat-card">
      <div class="stat-label">${label}</div>
      <div class="stat-value">${val != null ? (val * 100).toFixed(1) + "%" : "—"}</div>
      <div class="stat-delta ${color}">on held-out test set</div>
    </div>`).join("");

  const fi = metrics.feature_importances || {};
  const labels = Object.keys(fi);
  const values = Object.values(fi);
  const fCtx = document.getElementById("featureChart");
  if (!featureChart) {
    featureChart = new Chart(fCtx, {
      type: "bar",
      data: { labels, datasets: [{ label: "Importance", data: values, backgroundColor: "#3b82f6" }] },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "#8291ab" }, grid: { color: "#1f2b42" } },
          y: { ticks: { color: "#8291ab" }, grid: { display: false } },
        },
      },
    });
  } else {
    featureChart.data.labels = labels;
    featureChart.data.datasets[0].data = values;
    featureChart.update();
  }

  document.getElementById("modelInfoGrid").innerHTML = `
    <div><label>ROC AUC</label><div>${metrics.roc_auc ?? "—"}</div></div>
    <div><label>Trained at</label><div>${s.trained_at ?? "—"}</div></div>
    <div><label>Train rows</label><div>${metrics.train_rows ?? "—"}</div></div>
    <div><label>Test rows</label><div>${metrics.test_rows ?? "—"}</div></div>
    <div><label>Fraud threshold</label><div>${s.fraud_threshold}</div></div>
    <div><label>Review threshold</label><div>${s.review_threshold}</div></div>
  `;
}
viewLoaders.model = loadModelPerformance;

/* ============================================================
   SETTINGS VIEW
   ============================================================ */
async function loadSettings() {
  const s = await fetch(API + "/api/settings").then(r => r.json());
  document.getElementById("fraudThresholdInput").value = s.fraud_threshold;
  document.getElementById("reviewThresholdInput").value = s.review_threshold;
  document.getElementById("groqStatus").innerHTML = s.groq_configured
    ? `<span class="dot green"></span> Groq API key detected — using live LLM explanations`
    : `<span class="dot amber"></span> No Groq API key set — using built-in rule-based explanations`;
  document.getElementById("settingsInfoGrid").innerHTML = `
    <div><label>Model loaded</label><div>${s.model_loaded ? "Yes" : "No"}</div></div>
    <div><label>Trained at</label><div>${s.trained_at ?? "—"}</div></div>
    <div><label>Dataset rows</label><div>${s.dataset_rows.toLocaleString()}</div></div>
  `;
}
viewLoaders.settings = loadSettings;

document.getElementById("saveThresholdsBtn").addEventListener("click", async () => {
  const fraud_threshold = parseFloat(document.getElementById("fraudThresholdInput").value);
  const review_threshold = parseFloat(document.getElementById("reviewThresholdInput").value);
  const msg = document.getElementById("thresholdMsg");
  msg.textContent = "Saving…";
  try {
    const res = await fetch(API + "/api/settings/thresholds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fraud_threshold, review_threshold }),
    });
    if (!res.ok) {
      const err = await res.json();
      msg.textContent = "Error: " + (err.detail || "could not save");
      msg.style.color = "var(--red)";
      return;
    }
    msg.textContent = "Saved. New transactions will use the updated thresholds.";
    msg.style.color = "var(--green)";
  } catch (e) {
    msg.textContent = "Network error while saving.";
    msg.style.color = "var(--red)";
  }
});

/* ============================================================
   INIT + POLLING
   ============================================================ */
refreshDashboard();
setInterval(() => {
  if (currentView === "dashboard") refreshDashboard();
  if (currentView === "live") loadLive();
}, 5000);