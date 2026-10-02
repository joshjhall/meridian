// Learning-loop charts (#8): two dual-axis charts sharing a week axis and
// release flags, drawn with D3 from GET /api/history.
//
// Dual y-axes are a deliberate choice for this view. Each axis is labeled with
// its own unit and colored to match its series, and the caption says the
// scaling between the two axes is arbitrary.

const W = 720;
const H = 320;
const M = { top: 44, right: 64, bottom: 36, left: 56 };
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
  const domain = series.mark === "bar" || lo <= 1 ? [0, hi * 1.1] : [lo - 6, Math.min(100, hi + 4)];
  return d3
    .scaleLinear()
    .domain(domain)
    .nice()
    .range([H - M.bottom, M.top]);
}

function drawAxisY(svg, scale, series, side, colorVar) {
  const isLeft = side === "left";
  const axis = (isLeft ? d3.axisLeft : d3.axisRight)(scale)
    .ticks(5)
    .tickFormat((v) => `${v}${series.unit}`);
  const g = svg
    .append("g")
    .attr("class", `axis axis-${side}`)
    .attr("transform", `translate(${isLeft ? M.left : W - M.right},0)`)
    .call(axis);
  // Inline style, not the fill attribute, so the color-match beats the ink rule in app.css.
  g.selectAll("text").style("fill", `var(${colorVar})`);
  g.select(".domain").style("stroke", `var(${colorVar})`);
  // Title runs along its axis, outside the tick labels and clear of the flag row.
  const tx = isLeft ? M.left - 44 : W - M.right + 52;
  const ty = (M.top + H - M.bottom) / 2;
  svg
    .append("text")
    .attr("class", "axis-title")
    .style("fill", `var(${colorVar})`)
    .attr("text-anchor", "middle")
    .attr("transform", `translate(${tx},${ty}) rotate(${isLeft ? -90 : 90})`)
    .text(`${series.label} (${series.unit})`);
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

// Every release is flagged on both charts (shared flags); a release aimed at
// the other chart is drawn muted so the reader sees what changed where.
function drawFlags(svg, x, releases, chartId) {
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
      .attr("y1", FLAG_Y)
      .attr("y2", H - M.bottom);
    flag
      .append("text")
      .attr("class", "flag-glyph")
      .attr("y", FLAG_Y)
      .attr("text-anchor", "middle")
      .text(isRollback ? "↺" : "▼");
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

function drawCrosshair(svg, x, chart) {
  const { primary, secondary } = chart;
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
      const a = primary.points[week];
      const b = secondary.points[week];
      showTooltip(
        [
          [`Week ${week}`, "font-semibold"],
          [`${primary.label}: ${fmt(a.value, primary.unit)}`, "swatch swatch-1"],
          [`${secondary.label}: ${fmt(b.value, secondary.unit)}`, "swatch swatch-2"],
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
  const items = [
    [chart.primary, "swatch-1", chart.primary.mark],
    [chart.secondary, "swatch-2", chart.secondary.mark],
  ].map(([s, cls, mark]) => {
    const item = el("span", undefined, `legend-item ${cls} legend-${mark}`);
    item.append(el("span", undefined, "legend-key"));
    item.append(
      el("span", `${s.label} (${s.unit}, ${s === chart.primary ? "left" : "right"} axis)`),
    );
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
  const head = table.createTHead().insertRow();
  for (const h of ["Week", chart.primary.label, chart.secondary.label]) {
    head.append(el("th", h));
  }
  const body = table.createTBody();
  chart.primary.points.forEach((p, i) => {
    const row = body.insertRow();
    row.insertCell().textContent = String(p.week);
    row.insertCell().textContent = fmt(p.value, chart.primary.unit);
    row.insertCell().textContent = fmt(chart.secondary.points[i].value, chart.secondary.unit);
  });
  const sources = el("ul", undefined, "mt-2 text-muted-foreground");
  for (const s of [chart.primary, chart.secondary]) {
    sources.append(el("li", `${s.label}, week 0: ${s.source}`));
  }
  details.append(table, sources);
  figure.querySelector("section").append(details);
}

function drawChart(figure, chart, releases, weeks) {
  figure.querySelector("[data-role=title]").textContent = chart.title;
  figure.querySelector("[data-role=subtitle]").textContent = chart.subtitle;
  const svg = d3.select(figure.querySelector("[data-role=plot]"));
  svg.attr(
    "aria-label",
    `${chart.title}: ${chart.primary.label} and ${chart.secondary.label} by week`,
  );

  const x = d3
    .scaleLinear()
    .domain(weeks)
    .range([M.left + 12, W - M.right - 12]);
  const band = (x.range()[1] - x.range()[0]) / (weeks[1] - weeks[0]);
  const yL = yScale(chart.primary);
  const yR = yScale(chart.secondary);

  svg
    .append("g")
    .attr("class", "grid")
    .attr("transform", `translate(${M.left},0)`)
    .call(
      d3
        .axisLeft(yL)
        .ticks(5)
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
  drawAxisY(svg, yL, chart.primary, "left", "--series-1");
  drawAxisY(svg, yR, chart.secondary, "right", "--series-2");

  // Draw order: bars behind, lines on top, flags above everything.
  const ordered = [
    [chart.secondary, yR, "--series-2"],
    [chart.primary, yL, "--series-1"],
  ].sort(([a], [b]) => (a.mark === "bar" ? -1 : b.mark === "bar" ? 1 : 0));
  for (const [series, scale, color] of ordered) {
    drawTarget(svg, x, scale, series, color);
    drawSeries(svg, x, scale, series, color, band);
    drawStartLabel(svg, x, scale, series);
  }
  drawCrosshair(svg, x, chart);
  drawFlags(svg, x, releases, chart.id);
  drawLegend(figure, chart);
  drawTable(figure, chart);
}

async function init() {
  const root = document.getElementById("learning-loop");
  if (!root || typeof d3 === "undefined") return;
  const history = await (await fetch("/api/history")).json();
  document.getElementById("learning-caption").textContent = history.caption;
  const allWeeks = history.charts.flatMap((c) => c.primary.points.map((p) => p.week));
  const weeks = d3.extent(allWeeks);
  for (const chart of history.charts) {
    const figure = root.querySelector(`[data-chart="${chart.id}"]`);
    if (figure) drawChart(figure, chart, history.releases, weeks);
  }
}

document.addEventListener("DOMContentLoaded", init);
