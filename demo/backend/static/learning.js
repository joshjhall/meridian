// Learning-loop charts (#8), drawn with D3 from GET /api/history. Each chart
// box holds its two series as stacked single-axis panels on a shared week
// axis, with the release flags on both: one y-axis per plot, so lay readers
// never have to match a line to the right axis.

const W = 720;
const H = 220;
const M = { top: 30, right: 24, bottom: 32, left: 56 };
const FLAG_Y = 14;

const tooltip = () => document.getElementById("learning-tooltip");

function fmt(value, unit) {
  return unit === "%" ? `${value.toFixed(1)}%` : `${value.toFixed(value < 10 ? 1 : 0)}${unit}`;
}

// Labels come from the API: always set text with textContent, never innerHTML.
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function showTooltip(lines, x, y) {
  const tip = tooltip();
  tip.replaceChildren(...lines.map(([text, cls]) => el("div", text, cls)));
  tip.hidden = false;
  const pad = 12;
  const { width, height } = tip.getBoundingClientRect();
  const left = Math.min(x + pad, window.innerWidth - width - pad);
  const top = y - height - pad < 0 ? y + pad : y - height - pad;
  tip.style.left = `${left + window.scrollX}px`;
  tip.style.top = `${top + window.scrollY}px`;
}

function hideTooltip() {
  tooltip().hidden = true;
}

function yScale(series) {
  const values = series.points.map((p) => p.value).concat(series.target);
  const [lo, hi] = d3.extent(values);
  // Bars must grow from zero; lines get a padded domain so movement is visible.
  const top = series.unit === "%" ? Math.min(100, hi + 4) : hi + 4;
  const domain = series.mark === "bar" || lo <= 1 ? [0, hi * 1.1] : [Math.max(0, lo - 6), top];
  return d3
    .scaleLinear()
    .domain(domain)
    .nice()
    .range([H - M.bottom, M.top]);
}

function drawAxisY(svg, scale, series) {
  svg
    .append("g")
    .attr("class", "axis axis-left")
    .attr("transform", `translate(${M.left},0)`)
    .call(
      d3
        .axisLeft(scale)
        .ticks(4)
        .tickFormat((v) => `${v}${series.unit}`),
    )
    .select(".domain")
    .remove();
}

function drawTarget(svg, x, scale, series, colorVar) {
  const y = scale(series.target);
  svg
    .append("line")
    .attr("class", "target-line")
    .attr("stroke", `var(${colorVar})`)
    .attr("x1", M.left)
    .attr("x2", W - M.right)
    .attr("y1", y)
    .attr("y2", y);
  svg
    .append("text")
    .attr("class", "target-label")
    .attr("x", x.range()[1] - 4)
    .attr("y", y - 4)
    .attr("text-anchor", "end")
    .text(series.target_label);
}

function drawSeries(svg, x, scale, series, colorVar, band) {
  if (series.mark === "bar") {
    const width = Math.min(24, band - 2);
    const base = scale(0);
    svg
      .append("g")
      .attr("class", "bars")
      .selectAll("path")
      .data(series.points)
      .join("path")
      .attr("fill", `var(${colorVar})`)
      .attr("d", (p) => {
        // 4px rounded data-end, square at the baseline.
        const x0 = x(p.week) - width / 2;
        const top = scale(p.value);
        const r = Math.min(4, (base - top) / 2, width / 2);
        return `M${x0},${base}V${top + r}Q${x0},${top} ${x0 + r},${top}H${x0 + width - r}Q${x0 + width},${top} ${x0 + width},${top + r}V${base}Z`;
      });
    return;
  }
  const line = d3
    .line()
    .x((p) => x(p.week))
    .y((p) => scale(p.value));
  svg
    .append("path")
    .datum(series.points)
    .attr("class", "series-line")
    .attr("stroke", `var(${colorVar})`)
    .attr("d", line);
  const last = series.points.at(-1);
  svg
    .append("circle")
    .attr("class", "end-dot")
    .attr("fill", `var(${colorVar})`)
    .attr("cx", x(last.week))
    .attr("cy", scale(last.value))
    .attr("r", 4);
}

function drawStartLabel(svg, x, scale, series) {
  const first = series.points[0];
  svg
    .append("text")
    .attr("class", "start-label")
    .attr("x", x(first.week) + 6)
    .attr("y", scale(first.value) + (series.mark === "bar" ? -6 : 16))
    .text(`Start ${fmt(first.value, series.unit)}`);
}

// Every release is flagged on every panel (shared flags); a release aimed at
// the other chart is drawn muted so the reader sees what changed where. Only
// the top panel of a box shows the glyphs; the one below repeats the rules.
function drawFlags(svg, x, releases, chartId, glyphs) {
  const g = svg.append("g").attr("class", "flags");
  for (const r of releases) {
    const isRollback = r.kind === "rollback";
    const flag = g
      .append("g")
      .attr("class", `flag flag-${r.kind}${r.charts.includes(chartId) ? "" : " flag-other"}`)
      .attr("transform", `translate(${x(r.week)},0)`)
      .attr("tabindex", 0)
      .attr("role", "button")
      .attr("aria-label", `${isRollback ? "Rollback" : "Release"} ${r.version}, week ${r.week}`);
    flag
      .append("line")
      .attr("class", "flag-rule")
      .attr("y1", glyphs ? FLAG_Y : M.top)
      .attr("y2", H - M.bottom);
    if (glyphs) {
      flag
        .append("text")
        .attr("class", "flag-glyph")
        .attr("y", FLAG_Y)
        .attr("text-anchor", "middle")
        .text(isRollback ? "↺" : "▼");
    }
    // Generous hit target: the whole rule, not just the glyph.
    flag
      .append("rect")
      .attr("class", "flag-hit")
      .attr("x", -8)
      .attr("y", 0)
      .attr("width", 16)
      .attr("height", H - M.bottom);
    const lines = [
      [`${isRollback ? "↺ Rollback to" : "Release"} ${r.version}`, "font-semibold"],
      [`Week ${r.week}`, "text-muted-foreground"],
      [r.notes],
    ];
    const show = (event) => {
      event.stopPropagation();
      const box = flag.node().getBoundingClientRect();
      showTooltip(lines, event.clientX ?? box.right, event.clientY ?? box.top);
    };
    flag.on("pointerenter pointermove", show).on("pointerleave blur", hideTooltip);
    flag.on("focus", (event) => {
      const box = flag.node().getBoundingClientRect();
      showTooltip(lines, box.right, box.top + 24);
      event.stopPropagation();
    });
  }
}

// A chart's series top down, each with its panel key and categorical slot (1-based):
// two per box, a third on routing. Slots follow the reference palette's fixed order.
const SLOTS = ["primary", "secondary", "tertiary"];
function seriesOf(chart) {
  return SLOTS.map((key, i) => ({ key, series: chart[key], slot: i + 1 })).filter((s) => s.series);
}

function drawCrosshair(svg, x, chart) {
  const all = seriesOf(chart);
  const { primary } = chart;
  const rule = svg
    .append("line")
    .attr("class", "crosshair")
    .attr("y1", M.top)
    .attr("y2", H - M.bottom);
  rule.attr("visibility", "hidden");
  svg
    .append("rect")
    .attr("class", "crosshair-hit")
    .attr("x", M.left)
    .attr("y", M.top)
    .attr("width", W - M.left - M.right)
    .attr("height", H - M.top - M.bottom)
    .on("pointermove", (event) => {
      const [px] = d3.pointer(event);
      const week = Math.max(0, Math.min(primary.points.length - 1, Math.round(x.invert(px))));
      rule.attr("x1", x(week)).attr("x2", x(week)).attr("visibility", "visible");
      showTooltip(
        [
          [`Week ${week}`, "font-semibold"],
          ...all.map(({ series, slot }) => [
            `${series.label}: ${fmt(series.points[week].value, series.unit)}`,
            `swatch swatch-${slot}`,
          ]),
        ],
        event.clientX,
        event.clientY,
      );
    })
    .on("pointerleave", () => {
      rule.attr("visibility", "hidden");
      hideTooltip();
    });
}

function drawLegend(figure, chart) {
  const legend = figure.querySelector("[data-role=legend]");
  const items = seriesOf(chart).map(({ series: s, slot }) => {
    const item = el("span", undefined, `legend-item swatch-${slot} legend-${s.mark}`);
    item.append(el("span", undefined, "legend-key"));
    item.append(el("span", `${s.label} (${s.unit})`));
    return item;
  });
  const flagKey = el("span", "▼ release", "legend-item legend-flag");
  const rollbackKey = el("span", "↺ rollback", "legend-item legend-rollback");
  legend.replaceChildren(...items, flagKey, rollbackKey);
}

function drawTable(figure, chart) {
  const details = el("details", undefined, "mt-3 text-sm");
  details.append(el("summary", "Data table"));
  const table = el("table", undefined, "table");
  const all = seriesOf(chart).map((s) => s.series);
  const head = table.createTHead().insertRow();
  for (const h of ["Week", ...all.map((s) => s.label)]) {
    head.append(el("th", h));
  }
  const body = table.createTBody();
  chart.primary.points.forEach((p, i) => {
    const row = body.insertRow();
    row.insertCell().textContent = String(p.week);
    for (const s of all) row.insertCell().textContent = fmt(s.points[i].value, s.unit);
  });
  const sources = el("ul", undefined, "mt-2 text-muted-foreground");
  for (const s of all) {
    sources.append(el("li", `${s.label}, week 0: ${s.source}`));
  }
  details.append(table, sources);
  figure.querySelector("section").append(details);
}

// One single-axis panel: one series, its target, flags and the shared crosshair.
function drawPanel(panel, chart, series, colorVar, releases, weeks, glyphs) {
  panel.querySelector("[data-role=series-title]").textContent = `${series.label} (${series.unit})`;
  panel.querySelector("[data-role=series-title]").style.color = `var(${colorVar})`;
  const svg = d3.select(panel.querySelector("[data-role=plot]"));
  svg.attr("aria-label", `${chart.title}: ${series.label} by week`);

  const x = d3
    .scaleLinear()
    .domain(weeks)
    .range([M.left + 12, W - M.right - 12]);
  const band = (x.range()[1] - x.range()[0]) / (weeks[1] - weeks[0]);
  const y = yScale(series);

  svg
    .append("g")
    .attr("class", "grid")
    .attr("transform", `translate(${M.left},0)`)
    .call(
      d3
        .axisLeft(y)
        .ticks(4)
        .tickSize(-(W - M.left - M.right))
        .tickFormat(""),
    );
  svg
    .append("g")
    .attr("class", "axis axis-x")
    .attr("transform", `translate(0,${H - M.bottom})`)
    .call(
      d3
        .axisBottom(x)
        .ticks(weeks[1] / 4)
        .tickFormat((w) => `Wk ${w}`),
    );
  drawAxisY(svg, y, series);
  drawTarget(svg, x, y, series, colorVar);
  drawSeries(svg, x, y, series, colorVar, band);
  drawStartLabel(svg, x, y, series);
  drawCrosshair(svg, x, chart);
  // Flags above everything so their hover wins over the crosshair.
  drawFlags(svg, x, releases, chart.id, glyphs);
}

function drawChart(figure, chart, releases, weeks) {
  figure.querySelector("[data-role=title]").textContent = chart.title;
  figure.querySelector("[data-role=subtitle]").textContent = chart.subtitle;
  seriesOf(chart).forEach(({ key, series, slot }, i) => {
    const panel = figure.querySelector(`[data-series="${key}"]`);
    if (panel) drawPanel(panel, chart, series, `--series-${slot}`, releases, weeks, i === 0);
  });
  drawLegend(figure, chart);
  drawTable(figure, chart);
}

async function init() {
  const root = document.getElementById("learning-loop");
  const caption = document.getElementById("learning-caption");
  if (!root) return;
  let history;
  try {
    if (typeof d3 === "undefined") throw new Error("D3 did not load");
    const res = await fetch("/api/history");
    if (!res.ok) throw new Error(`GET /api/history returned ${res.status}`);
    history = await res.json();
  } catch (err) {
    caption.textContent = `Learning-loop history could not be loaded (${err.message}).`;
    return;
  }
  caption.textContent = history.caption;
  const allWeeks = history.charts.flatMap((c) => c.primary.points.map((p) => p.week));
  const weeks = d3.extent(allWeeks);
  for (const chart of history.charts) {
    const figure = root.querySelector(`[data-chart="${chart.id}"]`);
    if (figure) drawChart(figure, chart, history.releases, weeks);
  }
}

document.addEventListener("DOMContentLoaded", init);
