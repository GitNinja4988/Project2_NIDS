(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  const Style = {
    MODEL_ORDER: ["logreg", "rf", "hgb"],
    MODEL_LABEL: { logreg: "LogReg", rf: "RF", hgb: "HGB" },
    MODEL_COLOR: { logreg: "#1f4b6e", rf: "#0d7c6e", hgb: "#c45c26" },
    SPLIT_LABEL: { random: "random", time: "time (Fri)", predefined: "official" },
    SPLIT_ORDER: [["cic", "random"], ["cic", "time"], ["unsw", "random"], ["unsw", "predefined"]],
  };

  const State = {
    scope: "full",
    meta: null,
    datasets: null,
    results: null,
    charts: {},
    eventSource: null,
  };

  const Format = {
    missing(n) {
      return n === null || n === undefined || Number.isNaN(n);
    },
    num(n, digits) {
      if (Format.missing(n)) return "—";
      return Number(n).toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
    },
    int(n) {
      if (Format.missing(n)) return "—";
      return Math.round(Number(n)).toLocaleString();
    },
    pct(n) {
      if (Format.missing(n)) return "—";
      return (100 * Number(n)).toFixed(1) + "%";
    },
    html(s) {
      return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    },
  };

  const Api = {
    async get(url) {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(url + " → " + res.status);
      return res.json();
    },
    async post(url, body) {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      return res.json();
    },
  };

  const PlanView = {
    render(meta) {
      State.meta = meta;
      PlanView.goals(meta.goals);
      PlanView.team(meta.team);
      PlanView.planned(meta.planned_for_final);
      TerminalView.presets(meta.presets);
    },
    goals(goals) {
      const list = $("#goal-list");
      list.innerHTML = "";
      goals.forEach(function (g) {
        const li = document.createElement("li");
        li.innerHTML =
          '<span class="goal-status">' + Format.html(g.status) + "</span>" +
          "<span>" + Format.html(g.title) + "</span>" +
          '<span class="goal-owner">' + Format.html(g.owner) + "</span>";
        list.appendChild(li);
      });
    },
    team(team) {
      const grid = $("#team-grid");
      grid.innerHTML = "";
      team.forEach(function (person) {
        const div = document.createElement("div");
        div.className = "team-person reveal";
        const items = person.role.map(function (r) {
          return "<li>" + Format.html(r) + "</li>";
        }).join("");
        div.innerHTML = "<h3>" + Format.html(person.name) + "</h3><ul>" + items + "</ul>";
        grid.appendChild(div);
      });
    },
    planned(items) {
      const list = $("#planned-list");
      list.innerHTML = "";
      items.forEach(function (item) {
        const li = document.createElement("li");
        li.textContent = item;
        list.appendChild(li);
      });
    },
  };

  const DatasetView = {
    render(data) {
      State.datasets = data;
      DatasetView.panel("cic", data);
      DatasetView.panel("unsw", data);
    },
    panel(key, data) {
      const clean = (data.cleaning && data.cleaning[key]) || {};
      DatasetView.cleaningStats(key, clean);
      DatasetView.balance(key, data.sample_info && data.sample_info[key]);
      DatasetView.splits(key, data.split_sizes_full || {});
    },
    cleaningStats(key, clean) {
      const rows = [
        ["Raw rows", Format.int(clean.rows_raw)],
        ["Duplicates removed", Format.int(clean.rows_dropped_exact_duplicates)],
        ["Label conflicts removed", Format.int(clean.rows_dropped_label_conflicts)],
        ["Clean rows", Format.int(clean.rows_clean)],
      ];
      if (clean.rows_with_inf !== undefined) {
        rows.push(["Rows with ±inf (kept)", Format.int(clean.rows_with_inf)]);
      }
      $("#" + key + "-stats").innerHTML = rows.map(function (pair) {
        return "<div><dt>" + pair[0] + "</dt><dd>" + pair[1] + "</dd></div>";
      }).join("");
      $("#" + key + "-source").textContent = "Source: " + (clean.source || "—");
    },
    balance(key, info) {
      const el = $("#" + key + "-balance");
      if (!info || !info.per_label_full) {
        el.innerHTML = "<p class='source-note'>sample_info.json not found.</p>";
        return;
      }
      const entries = Object.entries(info.per_label_full).sort(function (a, b) {
        return b[1] - a[1];
      });
      const total = entries.reduce(function (s, e) {
        return s + e[1];
      }, 0);
      let html = "<table class='balance-table'><thead><tr><th>Label</th><th>Rows</th><th>Share</th></tr></thead><tbody>";
      entries.forEach(function (e) {
        html += "<tr><td>" + Format.html(e[0]) + "</td><td class='num'>" + Format.int(e[1]) +
          "</td><td class='num'>" + Format.pct(e[1] / total) + "</td></tr>";
      });
      html += "</tbody></table>";
      html += "<p class='source-note'>Source: data/sample/sample_info.json · per_label_full (" +
        Format.int(total) + " rows)</p>";
      el.innerHTML = html;
    },
    splits(key, sizes) {
      const el = $("#" + key + "-splits");
      if (key === "cic") {
        el.innerHTML =
          DatasetView.splitBlock("Random 70/15/15 (stratified by family)", sizes.cic_random) +
          DatasetView.splitBlock("Time: train Mon–Wed · val Thu · test Fri", sizes.cic_time);
      } else {
        el.innerHTML =
          DatasetView.splitBlock("Random 70/15/15 (stratified by family)", sizes.unsw_random) +
          DatasetView.splitBlock("Official predefined train/test files", sizes.unsw_predefined);
      }
    },
    splitBlock(title, split) {
      if (!split) {
        return "<p class='source-note'>" + Format.html(title) + " — run file missing.</p>";
      }
      const parts = ["train", "val", "test"].map(function (p) {
        const block = split[p] || {};
        return "<div><dt>" + p + "</dt><dd>" + Format.int(block.n) + "</dd></div>";
      }).join("");
      let extra = "";
      if (split.families_unseen_in_train && split.families_unseen_in_train.length) {
        extra += "<p class='source-note'>Unseen in train: " + split.families_unseen_in_train.join(", ") + "</p>";
      }
      if (split.val_rows_removed_overlap_with_train != null) {
        extra += "<p class='source-note'>Overlap removed after dropping ports — val " +
          Format.int(split.val_rows_removed_overlap_with_train) + ", test " +
          Format.int(split.test_rows_removed_overlap_with_train) + "</p>";
      }
      return "<h3 style='font-size:1.05rem;margin-top:1.5rem'>" + Format.html(title) + "</h3>" +
        "<dl class='stat-row'>" + parts + "</dl>" + extra +
        "<p class='source-note'>Source: " + Format.html(split.source || "") + "</p>";
    },
    setupTabs() {
      document.querySelectorAll(".dataset-tabs .tab").forEach(function (tab) {
        tab.addEventListener("click", function () {
          const key = tab.getAttribute("data-dataset");
          document.querySelectorAll(".dataset-tabs .tab").forEach(function (t) {
            t.setAttribute("aria-selected", t === tab ? "true" : "false");
          });
          $("#panel-cic").classList.toggle("hidden", key !== "cic");
          $("#panel-unsw").classList.toggle("hidden", key !== "unsw");
        });
      });
    },
  };

  const ChartView = {
    find(rows, dataset, model, split) {
      return rows.find(function (r) {
        return r.dataset === dataset && r.model === model && r.split === split;
      });
    },
    labels(rows) {
      const labels = [];
      Style.SPLIT_ORDER.forEach(function (pair) {
        const has = rows.some(function (r) {
          return r.dataset === pair[0] && r.split === pair[1];
        });
        if (has) {
          labels.push({
            dataset: pair[0],
            split: pair[1],
            label: pair[0].toUpperCase() + " " + (Style.SPLIT_LABEL[pair[1]] || pair[1]),
          });
        }
      });
      return labels;
    },
    series(rows, labels, metric) {
      return Style.MODEL_ORDER.map(function (model) {
        return {
          label: Style.MODEL_LABEL[model],
          data: labels.map(function (lab) {
            const row = ChartView.find(rows, lab.dataset, model, lab.split);
            return row ? row[metric] : null;
          }),
          backgroundColor: Style.MODEL_COLOR[model],
          borderColor: Style.MODEL_COLOR[model],
          borderWidth: 1,
          maxBarThickness: 36,
        };
      });
    },
    options(yTitle) {
      const font = { family: "'IBM Plex Sans', sans-serif", size: 12 };
      return {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 550 },
        plugins: {
          legend: { position: "top", labels: { font: font, color: "#3a4452" } },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                const v = ctx.parsed.y;
                return ctx.dataset.label + ": " + (v == null ? "—" : v.toFixed(4));
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { font: { family: "'IBM Plex Sans', sans-serif", size: 11 }, color: "#3a4452" },
          },
          y: {
            beginAtZero: true,
            max: 1,
            title: { display: true, text: yTitle, font: font, color: "#6b7585" },
            grid: { color: "rgba(18,22,28,0.08)" },
            ticks: { font: { family: "'IBM Plex Mono', monospace", size: 10 }, color: "#6b7585" },
          },
        },
      };
    },
    draw(id, config) {
      const canvas = document.getElementById(id);
      if (!canvas || typeof Chart === "undefined") return;
      if (State.charts[id]) {
        State.charts[id].data = config.data;
        State.charts[id].options = config.options;
        State.charts[id].update();
        return;
      }
      State.charts[id] = new Chart(canvas, config);
    },
    bar(id, rows, labels, metric, yTitle, noMax) {
      const options = ChartView.options(yTitle);
      if (noMax) delete options.scales.y.max;
      ChartView.draw(id, {
        type: "bar",
        data: {
          labels: labels.map(function (l) { return l.label; }),
          datasets: ChartView.series(rows, labels, metric),
        },
        options: options,
      });
    },
    render(data) {
      const rows = data.gap_table;
      const labels = ChartView.labels(rows);
      ChartView.bar("chart-recall", rows, labels, "recall_at_1pct_fpr", "Recall at 1% FPR", false);
      ChartView.bar("chart-auroc", rows, labels, "auroc", "AUROC", false);
      ChartView.bar("chart-auprc", rows, labels, "auprc", "AUPRC", false);
      ChartView.bar("chart-fpr", rows, labels, "test_fpr", "Test FPR", true);
      ChartView.families(data.time_split_family_recall);
    },
    families(rows) {
      if (!rows || !rows.length) {
        ChartView.draw("chart-family", { type: "bar", data: { labels: [], datasets: [] }, options: ChartView.options("Recall") });
        return;
      }
      const datasets = Style.MODEL_ORDER.map(function (model) {
        return {
          label: Style.MODEL_LABEL[model],
          data: rows.map(function (r) { return r[model]; }),
          backgroundColor: Style.MODEL_COLOR[model],
          borderColor: Style.MODEL_COLOR[model],
          borderWidth: 1,
          maxBarThickness: 40,
        };
      });
      ChartView.draw("chart-family", {
        type: "bar",
        data: { labels: rows.map(function (r) { return r.family; }), datasets: datasets },
        options: ChartView.options("Recall on Friday test"),
      });
    },
  };

  const TableView = {
    callout(data) {
      const random = ChartView.find(data.gap_table, "cic", "rf", "random");
      const time = ChartView.find(data.gap_table, "cic", "rf", "time");
      const el = $("#gap-callout");
      if (!random || !time) {
        el.innerHTML = "";
        return;
      }
      const drop = random.recall_at_1pct_fpr - time.recall_at_1pct_fpr;
      el.innerHTML =
        "On CIC, random-forest recall at 1% FPR falls from <strong>" + Format.num(random.recall_at_1pct_fpr, 3) +
        "</strong> on a random split to <strong>" + Format.num(time.recall_at_1pct_fpr, 3) +
        "</strong> on the Friday time split" +
        (drop > 0 ? " — a drop of <strong>" + Format.num(drop, 3) + "</strong>." : ".");
    },
    table(headers, rows, cells) {
      let html = "<table class='data-table'><thead><tr>" + headers.map(function (h) {
        return "<th>" + h + "</th>";
      }).join("") + "</tr></thead><tbody>";
      rows.forEach(function (r) {
        html += "<tr>" + cells(r).map(function (c) {
          return c.num ? "<td class='num'>" + c.text + "</td>" : "<td>" + Format.html(c.text) + "</td>";
        }).join("") + "</tr>";
      });
      return html + "</tbody></table>";
    },
    gap(rows) {
      const wrap = $("#gap-table-wrap");
      if (!rows.length) {
        wrap.innerHTML = "<p class='source-note'>No gap_table.csv rows for this scope.</p>";
        return;
      }
      wrap.innerHTML = TableView.table(
        ["Dataset", "Model", "Split", "AUROC", "AUPRC", "Recall@1%FPR", "Test FPR", "Gap recall"],
        rows,
        function (r) {
          return [
            { text: r.dataset }, { text: r.model }, { text: r.split },
            { text: Format.num(r.auroc, 4), num: true },
            { text: Format.num(r.auprc, 4), num: true },
            { text: Format.num(r.recall_at_1pct_fpr, 4), num: true },
            { text: Format.num(r.test_fpr, 4), num: true },
            { text: Format.num(r.gap_recall_at_1pct_fpr, 4), num: true },
          ];
        }
      );
    },
    main(rows) {
      const wrap = $("#main-table-wrap");
      if (!rows.length) {
        wrap.innerHTML = "<p class='source-note'>No analysis/main_table.csv for this scope yet. Run analysis from the terminal.</p>";
        return;
      }
      wrap.innerHTML = TableView.table(
        ["Dataset", "Split", "Model", "AUROC", "Recall@1%FPR", "Test FPR", "Runs"],
        rows,
        function (r) {
          return [
            { text: r.dataset }, { text: r.split }, { text: r.model },
            { text: Format.num(r.auroc, 4), num: true },
            { text: Format.num(r.recall_at_1pct_fpr, 4), num: true },
            { text: Format.num(r.test_fpr, 4), num: true },
            { text: Format.int(r.runs), num: true },
          ];
        }
      );
    },
  };

  const ResultsView = {
    async load(scope) {
      State.scope = scope;
      const data = await Api.get("/api/results?scope=" + encodeURIComponent(scope));
      State.results = data;
      $("#results-stamp").textContent =
        "Loaded " + scope + " · " + data.gap_table.length + " gap rows · " + new Date().toLocaleTimeString();
      TableView.callout(data);
      ChartView.render(data);
      TableView.gap(data.gap_table);
      TableView.main(data.main_table);
    },
    showError(err) {
      $("#results-stamp").textContent = "Load failed: " + err.message;
    },
    setupControls() {
      $("#scope-select").addEventListener("change", function (e) {
        ResultsView.load(e.target.value).catch(ResultsView.showError);
      });
      $("#refresh-results").addEventListener("click", function () {
        ResultsView.load(State.scope).catch(ResultsView.showError);
      });
    },
  };

  const TerminalView = {
    presets(presets) {
      const row = $("#preset-row");
      row.innerHTML = "";
      presets.forEach(function (p) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn";
        btn.textContent = p.label;
        btn.title = p.command + " — " + p.hint;
        btn.dataset.preset = p.id;
        btn.addEventListener("click", function () {
          $("#term-input").value = p.command;
          TerminalView.start({ preset: p.id });
        });
        row.appendChild(btn);
      });
    },
    print(text, cls) {
      const pre = $("#term-output");
      const line = document.createElement("div");
      line.className = cls || "stdout";
      line.textContent = text;
      pre.appendChild(line);
      pre.scrollTop = pre.scrollHeight;
    },
    status(text) {
      $("#term-status").textContent = text;
    },
    onEvent(data, es) {
      if (data.type === "start") {
        TerminalView.status("running · run #" + data.run_id);
        $("#term-command").textContent = data.command;
        TerminalView.print("$ " + data.command, "sys");
      } else if (data.type === "line") {
        TerminalView.print(data.text, data.stream === "stderr" ? "stderr" : "stdout");
      } else if (data.type === "done") {
        const ok = data.status === "finished" && data.exit_code === 0;
        TerminalView.print("— exit " + data.exit_code + " (" + data.status + ") —", ok ? "ok" : "stderr");
        TerminalView.status(data.status + " · exit " + data.exit_code);
        es.close();
        State.eventSource = null;
        ResultsView.load(State.scope).catch(function (err) {
          TerminalView.print("chart refresh failed: " + err.message, "stderr");
        });
        Api.get("/api/datasets").then(DatasetView.render).catch(function () {});
      }
    },
    connect() {
      if (State.eventSource) {
        State.eventSource.close();
        State.eventSource = null;
      }
      const es = new EventSource("/api/run/stream");
      State.eventSource = es;
      es.onmessage = function (ev) {
        let data;
        try {
          data = JSON.parse(ev.data);
        } catch (e) {
          return;
        }
        TerminalView.onEvent(data, es);
      };
      es.onerror = function () {};
    },
    async start(body) {
      const data = await Api.post("/api/run", body);
      if (!data.ok) {
        TerminalView.print("✗ " + (data.error || "could not start"), "stderr");
        TerminalView.status("error");
        return;
      }
      TerminalView.connect();
    },
    async stop() {
      const data = await Api.post("/api/run/stop");
      if (!data.ok) {
        TerminalView.print(data.error || "nothing to stop", "sys");
      }
    },
    setupControls() {
      $("#term-form").addEventListener("submit", function (e) {
        e.preventDefault();
        const cmd = $("#term-input").value.trim();
        if (!cmd) return;
        TerminalView.start({ command: cmd });
      });
      $("#term-stop").addEventListener("click", TerminalView.stop);
    },
  };

  const App = {
    async boot() {
      DatasetView.setupTabs();
      ResultsView.setupControls();
      TerminalView.setupControls();
      try {
        PlanView.render(await Api.get("/api/meta"));
        DatasetView.render(await Api.get("/api/datasets"));
        await ResultsView.load(State.scope);
        TerminalView.print("Ready. Use a one-click command or type a project command below.", "sys");
        TerminalView.status("idle");
      } catch (err) {
        TerminalView.print("Boot failed: " + err.message, "stderr");
        ResultsView.showError(err);
      }
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", App.boot);
  } else {
    App.boot();
  }
})();
