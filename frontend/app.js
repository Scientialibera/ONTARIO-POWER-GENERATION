const state = { market: null, dispatch: null, scenario: null };

const money = value => value == null ? "--" : new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(value);
const num = (value, digits = 0) => value == null ? "--" : Number(value).toLocaleString("en-CA", { maximumFractionDigits: digits });
function setText(id, value) { const el = document.getElementById(id); if (el) el.textContent = value; }

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach(button => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(item => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach(item => item.classList.remove("active"));
      button.classList.add("active");
      document.getElementById(`view-${button.dataset.tab}`).classList.add("active");
      requestAnimationFrame(redrawAll);
    });
  });
}

function setupRanges() {
  const bindings = [
    ["power", "power-out", v => `${v} MW`], ["energy", "energy-out", v => `${v} MWh`],
    ["eff", "eff-out", v => `${v}%`], ["soc", "soc-out", v => `${v}%`],
    ["deg", "deg-out", v => `$${v}/MWh`], ["dc", "dc-out", v => `${v} MW`],
    ["dclf", "dclf-out", v => `${v}%`], ["heat", "heat-out", v => `+${v} C`], ["ev", "ev-out", v => `${v}%`]
  ];
  bindings.forEach(([inputId, outputId, format]) => {
    const input = document.getElementById(inputId); const output = document.getElementById(outputId);
    const update = () => output.textContent = format(input.value); input.addEventListener("input", update); update();
  });
}

function canvasFrame(canvas) {
  const ratio = window.devicePixelRatio || 1; const width = canvas.clientWidth; const height = Number(canvas.getAttribute("height")) || 260;
  canvas.width = Math.floor(width * ratio); canvas.height = Math.floor(height * ratio);
  const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio); return { ctx, width, height };
}
function drawAxes(ctx, width, height, pad = 34) {
  ctx.strokeStyle = "#dce6dc"; ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) { const y = pad + (height - pad * 2) * i / 4; ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(width - pad, y); ctx.stroke(); }
  return { left: pad, right: width - pad, top: pad, bottom: height - pad };
}
function drawLine(ctx, values, box, min, max, color, width = 2) {
  if (!values.length) return; ctx.beginPath();
  values.forEach((value, i) => { const x = box.left + (box.right - box.left) * i / Math.max(values.length - 1, 1); const y = box.bottom - (box.bottom - box.top) * (value - min) / Math.max(max - min, 1e-9); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
}

function drawMarketChart() {
  const canvas = document.getElementById("market-chart"); if (!canvas || !state.market) return;
  const { ctx, width, height } = canvasFrame(canvas); ctx.clearRect(0, 0, width, height); const box = drawAxes(ctx, width, height);
  const demand = state.market.demand.hourly.map(r => Number(r.ontario_demand_mw)); const prices = state.market.day_ahead_price.hours.map(r => Number(r.price)); if (!demand.length || !prices.length) return;
  drawLine(ctx, demand, box, Math.min(...demand) * .97, Math.max(...demand) * 1.03, "#4f8a5c", 2.4);
  drawLine(ctx, prices, box, Math.min(...prices) - 5, Math.max(...prices) + 5, "#4e91c8", 2.0);
  ctx.fillStyle = "#758278"; ctx.font = "10px system-ui"; for (let i = 0; i < 24; i += 4) { const x = box.left + (box.right - box.left) * i / 23; ctx.fillText(String(i + 1).padStart(2, "0"), x - 6, height - 12); }
}

function drawBatteryChart() {
  const canvas = document.getElementById("battery-chart"); if (!canvas || !state.dispatch) return;
  const { ctx, width, height } = canvasFrame(canvas); ctx.clearRect(0, 0, width, height); const box = drawAxes(ctx, width, height); const rows = state.dispatch.rows;
  const price = rows.map(r => r.price_per_mwh); const soc = rows.map(r => r.soc_mwh); const maxSoc = Math.max(...soc, 1); const maxPower = Math.max(...rows.flatMap(r => [r.charge_mw, r.discharge_mw]), 1); const barW = (box.right - box.left) / rows.length * .55;
  rows.forEach((row, i) => { const x = box.left + (box.right - box.left) * i / Math.max(rows.length - 1, 1); const chargeH = (box.bottom - box.top) * row.charge_mw / maxPower; const dischargeH = (box.bottom - box.top) * row.discharge_mw / maxPower; ctx.fillStyle = "rgba(78,145,200,.65)"; ctx.fillRect(x - barW / 2, box.bottom - chargeH, barW, chargeH); ctx.fillStyle = "rgba(220,133,40,.72)"; ctx.fillRect(x - barW / 2, box.bottom - dischargeH, barW, dischargeH); });
  drawLine(ctx, price, box, Math.min(...price) - 5, Math.max(...price) + 5, "#dc8528", 1.7); drawLine(ctx, soc, box, 0, maxSoc * 1.05, "#4f8a5c", 2.3);
}

function drawScenarioChart() {
  const canvas = document.getElementById("scenario-chart"); if (!canvas || !state.scenario) return;
  const { ctx, width, height } = canvasFrame(canvas); ctx.clearRect(0, 0, width, height); const box = drawAxes(ctx, width, height); const baseline = state.scenario.baseline_mw; const scenario = state.scenario.scenario_mw; const min = Math.min(...baseline, ...scenario) * .96; const max = Math.max(...baseline, ...scenario) * 1.04; drawLine(ctx, baseline, box, min, max, "#4e91c8", 2.2); drawLine(ctx, scenario, box, min, max, "#dc8528", 2.2);
}
function redrawAll() { drawMarketChart(); drawBatteryChart(); drawScenarioChart(); }

function renderMarket() {
  const m = state.market; const demand = m.demand.hourly.map(r => Number(r.ontario_demand_mw)); const da = m.day_ahead_price.hours.map(r => Number(r.price)); const generation = Object.values(m.generation_mix_mw || {}).reduce((a, b) => a + Number(b), 0);
  setText("kpi-demand", num(m.demand.latest_mw)); setText("kpi-rt-price", num(m.realtime_price.price, 2)); setText("kpi-da-peak", da.length ? num(Math.max(...da), 2) : "--"); setText("kpi-generation", generation ? num(generation) : "--"); setText("kpi-peak-demand", demand.length ? num(Math.max(...demand)) : "--");
  setText("detail-hour", m.realtime_price.delivery_hour ?? "--"); setText("detail-price", m.realtime_price.price == null ? "--" : `$${num(m.realtime_price.price, 2)}`); const last = m.realtime_price.intervals?.filter(r => r.price != null).slice(-1)[0] || {}; setText("detail-loss", last.loss == null ? "--" : `$${num(last.loss, 2)}`); setText("detail-congestion", last.congestion == null ? "--" : `$${num(last.congestion, 2)}`); setText("detail-state", m.data_status === "live" ? "LIVE IESO" : "SAMPLE FALLBACK"); setText("as-of", m.as_of === "sample" ? "Sample data" : `Updated ${new Date(m.as_of).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`);
  const sourceDot = document.getElementById("source-dot"); sourceDot.classList.remove("live", "fallback"); sourceDot.classList.add(m.data_status === "live" ? "live" : "fallback"); setText("source-label", m.data_status === "live" ? "IESO Public Reports Live" : "IESO unavailable: sample fallback"); setText("map-condition", m.data_status === "live" ? "Live market feed connected" : "Fallback dataset in use");
  const currentPrice = Number(m.realtime_price.price); const peakPrice = Math.max(...da); const pressure = peakPrice ? currentPrice / peakPrice : 0; const signal = pressure >= .8 ? ["Elevated price pressure", "Current pricing is close to the day-ahead peak. Review the dispatch window."] : pressure >= .5 ? ["Balanced market signal", "Price is within the normal daily operating range."] : ["Favourable charging window", "Current pricing is below the day-ahead peak range."]; setText("signal-label", signal[0]); setText("signal-detail", signal[1]);
  const mix = Object.entries(m.generation_mix_mw || {}).sort((a,b) => b[1]-a[1]); const max = Math.max(...mix.map(([,v]) => Number(v)), 1); const mixBars = document.getElementById("mix-bars"); mixBars.replaceChildren(); mix.forEach(([name, value]) => { const row = document.createElement("div"); row.className = "mix-row"; const label = document.createElement("span"); label.className = "mix-label"; label.textContent = name; const track = document.createElement("div"); track.className = "mix-track"; const fill = document.createElement("div"); fill.className = "mix-fill"; fill.style.width = `${Math.max(3, Number(value) / max * 100)}%`; track.append(fill); const amount = document.createElement("span"); amount.className = "mix-value"; amount.textContent = `${num(value)} MW`; row.append(label, track, amount); mixBars.append(row); }); drawMarketChart();
}

async function loadMarket() { state.market = await api("/api/live"); renderMarket(); await runOptimizer(); await runScenario(); }

async function runOptimizer() {
  const payload = { strategy: document.getElementById("battery-strategy").value, power_mw: Number(document.getElementById("power").value), energy_mwh: Number(document.getElementById("energy").value), round_trip_efficiency: Number(document.getElementById("eff").value) / 100, initial_soc_pct: Number(document.getElementById("soc").value), min_soc_pct: 10, max_soc_pct: 95, degradation_cost_per_mwh: Number(document.getElementById("deg").value) };
  if (state.market) { payload.prices = state.market.day_ahead_price.hours.map(r => Number(r.price)); payload.load_mw = state.market.demand.hourly.map(r => Number(r.ontario_demand_mw)); }
  state.dispatch = await api("/api/battery/optimize", { method: "POST", body: JSON.stringify(payload) }); setText("result-net", money(state.dispatch.net_value)); setText("result-gross", money(state.dispatch.gross_discharge_revenue)); setText("result-charge", money(state.dispatch.charge_cost)); setText("result-deg", money(state.dispatch.degradation_cost)); setText("result-cycles", num(state.dispatch.equivalent_cycles, 2)); setText("result-peak", state.dispatch.peak_reduction_mw == null ? "--" : `${num(state.dispatch.peak_reduction_mw)} MW`);
  document.getElementById("dispatch-body").innerHTML = state.dispatch.rows.map(row => `<tr><td>${String(row.hour).padStart(2, "0")}:00</td><td>$${num(row.price_per_mwh, 2)}</td><td class="charge">${num(row.charge_mw, 1)}</td><td class="discharge">${num(row.discharge_mw, 1)}</td><td>${num(row.soc_mwh, 1)}</td><td>${money(row.gross_margin)}</td></tr>`).join(""); drawBatteryChart();
}

async function runScenario() {
  if (!state.market) return; const baseline = state.market.demand.hourly.map(r => Number(r.ontario_demand_mw)); state.scenario = await api("/api/scenario/load", { method: "POST", body: JSON.stringify({ baseline_mw: baseline, data_centre_mw: Number(document.getElementById("dc").value), data_centre_load_factor: Number(document.getElementById("dclf").value) / 100, heat_wave_delta_c: Number(document.getElementById("heat").value), ev_growth_pct: Number(document.getElementById("ev").value) }) }); setText("scenario-before", `${num(state.scenario.peak_before_mw)} MW`); setText("scenario-after", `${num(state.scenario.peak_after_mw)} MW`); setText("scenario-delta", `${num(state.scenario.peak_after_mw - state.scenario.peak_before_mw)} MW`); drawScenarioChart();
}

setupTabs(); setupRanges(); document.getElementById("run-optimizer").addEventListener("click", () => runOptimizer().catch(console.error)); document.getElementById("run-scenario").addEventListener("click", () => runScenario().catch(console.error)); window.addEventListener("resize", redrawAll); loadMarket().catch(error => { console.error(error); setText("source-label", "Unable to initialize data"); });
