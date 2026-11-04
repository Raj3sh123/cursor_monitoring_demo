(function () {
  const page = document.getElementById("server-page");
  const initial = JSON.parse(document.getElementById("initial-metrics").textContent);
  const canvas = document.getElementById("history-chart");
  const chart = new Chart(canvas, {
    type: "line",
    data: {
      labels: initial.history.labels,
      datasets: [
        {
          label: "CPU %",
          data: initial.history.cpu,
          borderColor: "#0d6efd",
          backgroundColor: "rgba(13, 110, 253, 0.15)",
          tension: 0.2,
        },
        {
          label: "Memory %",
          data: initial.history.memory,
          borderColor: "#6f42c1",
          backgroundColor: "rgba(111, 66, 193, 0.15)",
          tension: 0.2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { min: 0, max: 100 } },
    },
  });

  function badgeClass(status) {
    if (status === "Alert") return "badge text-bg-danger";
    if (status === "OK") return "badge text-bg-success";
    if (status === "Error") return "badge text-bg-warning";
    return "badge text-bg-secondary";
  }

  function fillTable(tableId, emptyId, rows, cells) {
    const body = document.querySelector("#" + tableId + " tbody");
    body.replaceChildren();
    rows.forEach(function (row) {
      const tr = document.createElement("tr");
      cells(row).forEach(function (value) {
        const td = document.createElement("td");
        td.textContent = value;
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
    document.getElementById(emptyId).classList.toggle("d-none", rows.length > 0);
  }

  function apply(data) {
    const error = document.getElementById("metrics-error");
    error.textContent = data.error || "";
    error.classList.toggle("d-none", !data.error);
    document.getElementById("metrics-alert").classList.toggle("d-none", !data.alert);
    document.getElementById("cpu-value").textContent = data.cpu_display;
    document.getElementById("mem-value").textContent = data.memory.percent_display;
    document.getElementById("mem-detail").textContent =
      data.memory.used_display + " used of " + data.memory.total_display;
    document.getElementById("mem-available").textContent = data.memory.available_display;
    const badge = document.getElementById("status-badge");
    badge.textContent = data.status;
    badge.className = badgeClass(data.status);
    document.getElementById("collected-at").textContent = data.collected_at || "—";
    fillTable("network-table", "network-empty", data.network, function (row) {
      return [row.iface, row.rx_display, row.tx_display, row.rx_rate_display, row.tx_rate_display];
    });
    fillTable("ports-table", "ports-empty", data.ports, function (row) {
      return [row.proto, row.address, String(row.port)];
    });
    chart.data.labels = data.history.labels;
    chart.data.datasets[0].data = data.history.cpu;
    chart.data.datasets[1].data = data.history.memory;
    chart.update();
  }

  async function refresh() {
    const response = await fetch(page.dataset.metricsUrl, { headers: { Accept: "application/json" } });
    if (response.status === 401) {
      window.location = "/login";
      return;
    }
    if (!response.ok) {
      return;
    }
    apply(await response.json());
  }

  window.setInterval(refresh, Number(page.dataset.refreshMs) || 5000);
})();
