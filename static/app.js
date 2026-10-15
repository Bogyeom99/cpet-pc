const appState = {
  athletes: [],
  measurements: [],
  lactates: [],
  reportSelection: null,
  reportDirty: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function showMessage(message, type = "info") {
  const box = $("#global-message");
  box.textContent = message;
  box.className = "message";
  if (type === "error") box.classList.add("error");
  if (type === "success") box.classList.add("success");
  box.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function clearMessage() {
  $("#global-message").classList.add("hidden");
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  let payload = null;
  if (contentType.includes("application/json")) {
    payload = await response.json();
  }
  if (!response.ok || (payload && payload.ok === false)) {
    throw new Error(
      (payload && payload.error)
      || `요청 처리에 실패했습니다. (${response.status})`
    );
  }
  return payload;
}

function switchTab(name) {
  $$(".tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  $$(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${name}`);
  });
}

function localDateString() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function numberValue(id, fallback = 0) {
  const value = Number($(id).value);
  return Number.isFinite(value) ? value : fallback;
}

function selectedAthleteId() {
  return Number($("#measurement-athlete").value || 0);
}

function measurementPayload() {
  return {
    athlete_id: selectedAthleteId(),
    test_date: $("#test-date").value,
    height: numberValue("#height"),
    weight: numberValue("#weight"),
    bmi: numberValue("#bmi"),
    vo2max: numberValue("#vo2max"),
    hrmax: numberValue("#hrmax"),
    exercise_time: $("#exercise-time").value,
    load_type: $("#load-type").value,
    max_load: numberValue("#max-load"),
    grade_percent: numberValue("#grade-percent"),
    stage_duration_min: Math.max(1, Math.round(numberValue("#stage-duration", 3))),
    rest_duration_min: Math.max(1, Math.round(numberValue("#rest-duration", 1))),
    show_lt1: $("#show-lt1").checked,
    show_lt2: $("#show-lt2").checked,
  };
}

function updateLoadLabel() {
  const type = $("#load-type").value;
  $("#max-load-label").textContent = (
    type === "Speed"
      ? "최대 Speed(km/h)"
      : "최대 Power(watt)"
  );
}

function renderAthletes() {
  const body = $("#athlete-table-body");
  body.innerHTML = appState.athletes.length
    ? appState.athletes.map((athlete) => `
      <tr>
        <td>${escapeHtml(athlete.name)}</td>
        <td>${escapeHtml(athlete.sex)}</td>
        <td>${escapeHtml(athlete.category)}</td>
      </tr>
    `).join("")
    : '<tr><td colspan="3">등록된 선수가 없습니다.</td></tr>';

  const select = $("#measurement-athlete");
  const previous = select.value;
  select.innerHTML = appState.athletes.length
    ? appState.athletes.map((athlete) => `
      <option value="${athlete.id}">
        ${escapeHtml(athlete.name)} (${escapeHtml(athlete.sex)} / ${escapeHtml(athlete.category)})
      </option>
    `).join("")
    : '<option value="">선수를 먼저 등록하세요.</option>';

  if (
    previous
    && appState.athletes.some((item) => String(item.id) === previous)
  ) {
    select.value = previous;
  }
}

async function loadAthletes() {
  const data = await api("/api/athletes");
  appState.athletes = data.athletes || [];
  renderAthletes();
  await loadMeasurements();
}

async function addAthlete(event) {
  event.preventDefault();
  clearMessage();
  try {
    const data = await api("/api/athletes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("#athlete-name").value,
        sex: $("#athlete-sex").value,
        category: $("#athlete-category").value,
      }),
    });

    appState.athletes = data.athletes || [];
    renderAthletes();
    $("#measurement-athlete").value = String(data.athlete.id);
    $("#athlete-name").value = "";
    await loadMeasurements();
    showMessage(`${data.athlete.name} 선수를 저장했습니다.`, "success");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

async function loadMeasurements() {
  const athleteId = selectedAthleteId();
  const select = $("#saved-measurement");
  if (!athleteId) {
    appState.measurements = [];
    select.innerHTML = '<option value="">새 측정</option>';
    return;
  }

  try {
    const data = await api(`/api/measurements/${athleteId}`);
    appState.measurements = data.measurements || [];
    select.innerHTML = [
      '<option value="">새 측정</option>',
      ...appState.measurements.map((item) => (
        `<option value="${item.id}">${escapeHtml(item.test_date)}</option>`
      )),
    ].join("");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

function fillMeasurement(measurement) {
  if (!measurement) {
    $("#test-date").value = localDateString();
    $("#height").value = "0";
    $("#weight").value = "0";
    $("#bmi").value = "0";
    $("#vo2max").value = "0";
    $("#hrmax").value = "0";
    $("#exercise-time").value = "";
    $("#load-type").value = "Speed";
    $("#max-load").value = "0";
    $("#grade-percent").value = "0";
    $("#stage-duration").value = "3";
    $("#rest-duration").value = "1";
    updateLoadLabel();
    return;
  }

  $("#test-date").value = measurement.test_date || localDateString();
  $("#height").value = measurement.height ?? 0;
  $("#weight").value = measurement.weight ?? 0;
  $("#bmi").value = measurement.bmi ?? 0;
  $("#vo2max").value = measurement.vo2max ?? 0;
  $("#hrmax").value = measurement.hrmax ?? 0;
  $("#exercise-time").value = measurement.exercise_time || "";
  $("#load-type").value = measurement.load_type || "Speed";
  $("#max-load").value = measurement.max_load ?? 0;
  $("#grade-percent").value = measurement.grade_percent ?? 0;
  $("#stage-duration").value = Math.max(
    1,
    Math.round(Number(measurement.stage_duration_min || 3))
  );
  $("#rest-duration").value = Math.max(
    1,
    Math.round(Number(measurement.rest_duration_min || 1))
  );
  updateLoadLabel();
}

async function saveMeasurement() {
  clearMessage();
  if (!selectedAthleteId()) {
    showMessage("선수를 먼저 선택하세요.", "error");
    return;
  }

  try {
    const data = await api("/api/measurement", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(measurementPayload()),
    });
    await loadMeasurements();
    $("#saved-measurement").value = String(data.measurement.id);
    showMessage("측정 정보를 저장했습니다.", "success");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

function renderSummary(rows) {
  $("#summary-table-body").innerHTML = rows.map((row) => `
    <tr>
      <td>${escapeHtml(row.Stage)}</td>
      <td>${escapeHtml(row.Duration)}</td>
      <td>${escapeHtml(row.HR_min ?? "-")}</td>
      <td>${escapeHtml(row.HR_max ?? "-")}</td>
      <td>${escapeHtml(row.HR_mean ?? "-")}</td>
      <td>${escapeHtml(row.VO2_min ?? "-")}</td>
      <td>${escapeHtml(row.VO2_max ?? "-")}</td>
      <td>${escapeHtml(row.VO2_mean ?? "-")}</td>
    </tr>
  `).join("");
  $("#summary-area").classList.remove("hidden");
}

function renderLactates() {
  $("#lactate-table-body").innerHTML = appState.lactates.map((row, index) => `
    <tr>
      <td>${escapeHtml(row.stage)}</td>
      <td>${row.load == null ? "-" : escapeHtml(row.load)}</td>
      <td>
        <input
          class="lactate-input"
          type="number"
          min="0"
          step="0.01"
          data-index="${index}"
          value="${row.lactate == null ? "" : escapeHtml(row.lactate)}"
        >
      </td>
    </tr>
  `).join("");
}

async function uploadExcel() {
  clearMessage();
  const file = $("#excel-file").files[0];
  if (!selectedAthleteId()) {
    showMessage("선수를 먼저 선택하세요.", "error");
    return;
  }
  if (!file) {
    showMessage("Excel 파일을 선택하세요.", "error");
    return;
  }

  const form = new FormData();
  const payload = measurementPayload();
  Object.entries(payload).forEach(([key, value]) => {
    form.append(key, value);
  });
  form.append("file", file);

  try {
    const data = await api("/api/upload", {
      method: "POST",
      body: form,
    });

    renderSummary(data.summary || []);
    appState.lactates = data.lactates || [];
    renderLactates();

    $("#analysis-empty").classList.add("hidden");
    $("#analysis-content").classList.remove("hidden");
    $("#lactate-note").textContent = data.lactate_imported
      ? "Excel의 Lactate 시트에서 값을 불러왔습니다. 필요한 경우 아래 표에서 수정할 수 있습니다."
      : "혈중 젖산염 열에 측정값을 입력하세요. 미측정 구간은 비워두면 됩니다.";

    $("#graphs").classList.add("hidden");
    $("#lt-results").classList.add("hidden");
    setReportReady(false);
    showMessage("Excel 자료를 읽었습니다.", "success");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

function collectLactates() {
  return appState.lactates.map((row, index) => {
    const input = document.querySelector(
      `.lactate-input[data-index="${index}"]`
    );
    const raw = input ? input.value.trim() : "";
    return {
      stage: row.stage,
      load: row.load,
      lactate: raw === "" ? null : Number(raw),
    };
  });
}

function renderLtResult(elementId, item, unit) {
  const box = $(elementId);
  box.className = "result-card";

  if (!item || !item.show) {
    box.textContent = "표시하지 않음";
    return;
  }

  if (!item.valid) {
    box.classList.add("warning");
    box.textContent = `${item.name} 산출 불가: ${item.reason || "계산 결과 없음"}`;
    return;
  }

  box.classList.add("success");
  const hr = item.hr == null ? "" : ` | ${item.hr} bpm`;
  box.textContent = `${item.name} = ${Number(item.load).toFixed(2)} ${unit}${hr}`;
}

function setGraph(id, src) {
  const img = $(id);
  if (src) {
    img.src = src;
    img.closest(".graph-card").classList.remove("hidden");
  } else {
    img.removeAttribute("src");
    img.closest(".graph-card").classList.add("hidden");
  }
}

async function runAnalysis() {
  clearMessage();
  try {
    const data = await api("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lactates: collectLactates(),
        show_lt1: $("#show-lt1").checked,
        show_lt2: $("#show-lt2").checked,
      }),
    });

    const unit = $("#load-type").value === "Speed" ? "km/h" : "watt";
    renderLtResult("#lt1-result", data.lt1, unit);
    renderLtResult("#lt2-result", data.lt2, unit);
    $("#lt-results").classList.remove("hidden");

    setGraph("#lactate-graph", data.lactate_graph);
    setGraph("#basic-graph", data.basic_graph);
    setGraph("#combined-graph", data.combined_graph);
    $("#graphs").classList.remove("hidden");

    setReportReady(Boolean(data.report_ready));
    if (data.report_ready) {
      loadReportPreview();
    }
    showMessage("분석이 완료되었습니다.", "success");
  } catch (error) {
    showMessage(error.message, "error");
  }
}

function setReportReady(ready) {
  $("#report-empty").classList.toggle("hidden", ready);
  $("#report-workspace").classList.toggle("hidden", !ready);
  $("#download-pdf").classList.toggle("disabled", !ready);
  $("#download-excel").classList.toggle("disabled", !ready);
}

function loadReportPreview() {
  const frame = $("#report-frame");
  appState.reportSelection = null;
  appState.reportDirty = false;
  $("#edit-status").textContent = "수정할 문구를 선택하세요.";
  frame.src = `/report-preview?v=${Date.now()}`;
}

function frameDocument() {
  const frame = $("#report-frame");
  return frame.contentDocument || frame.contentWindow.document;
}

function rangeEditable(range) {
  if (!range) return null;
  const doc = frameDocument();
  let node = range.commonAncestorContainer;
  if (node.nodeType === doc.defaultView.Node.TEXT_NODE) {
    node = node.parentElement;
  }
  return node && node.closest
    ? node.closest("[data-edit-key]")
    : null;
}

function rememberReportSelection() {
  const doc = frameDocument();
  const selection = doc.getSelection();
  if (!selection || selection.rangeCount === 0) return;
  const range = selection.getRangeAt(0);
  const editable = rangeEditable(range);
  if (!editable) return;
  appState.reportSelection = range.cloneRange();
}

function restoreReportSelection() {
  if (!appState.reportSelection) return null;
  const doc = frameDocument();
  const range = appState.reportSelection.cloneRange();
  if (!rangeEditable(range)) return null;

  const selection = doc.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  return range;
}

function markReportDirty() {
  appState.reportDirty = true;
  $("#edit-status").textContent = "수정 내용이 아직 저장되지 않았습니다.";
}

function applyReportStyle(styleName, styleValue) {
  const range = restoreReportSelection();
  if (!range || range.collapsed) {
    $("#edit-status").textContent = "먼저 바꿀 글자를 드래그해서 선택하세요.";
    return;
  }

  const doc = frameDocument();
  const span = doc.createElement("span");
  span.style[styleName] = styleValue;

  try {
    const fragment = range.extractContents();
    span.appendChild(fragment);
    range.insertNode(span);

    const selection = doc.getSelection();
    const caret = doc.createRange();
    caret.setStartAfter(span);
    caret.collapse(true);
    selection.removeAllRanges();
    selection.addRange(caret);

    appState.reportSelection = null;
    markReportDirty();
    saveReportComments(true);
  } catch (error) {
    $("#edit-status").textContent = "선택 범위의 서식을 바꾸지 못했습니다.";
  }
}

function clearReportFormat() {
  const range = restoreReportSelection();
  if (!range || range.collapsed) {
    $("#edit-status").textContent = "먼저 바꿀 글자를 드래그해서 선택하세요.";
    return;
  }

  const doc = frameDocument();
  const selection = doc.getSelection();
  doc.execCommand("removeFormat", false, null);
  if (selection.rangeCount) {
    appState.reportSelection = selection.getRangeAt(0).cloneRange();
  }
  markReportDirty();
  saveReportComments(true);
}

function reportComments() {
  const doc = frameDocument();
  const result = {};
  doc.querySelectorAll("[data-edit-key]").forEach((element) => {
    result[element.dataset.editKey] = element.innerHTML;
  });
  return result;
}

async function saveReportComments(silent = false) {
  try {
    await api("/api/report-comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(reportComments()),
    });
    appState.reportDirty = false;
    $("#edit-status").textContent = "수정 내용이 저장되었습니다.";
    if (!silent) {
      showMessage("결과지 수정 내용을 저장했습니다.", "success");
    }
  } catch (error) {
    $("#edit-status").textContent = "저장에 실패했습니다.";
    if (!silent) showMessage(error.message, "error");
  }
}

function setupReportFrame() {
  const frame = $("#report-frame");
  const doc = frameDocument();

  doc.addEventListener("selectionchange", rememberReportSelection);
  doc.querySelectorAll("[data-edit-key]").forEach((element) => {
    element.addEventListener("input", markReportDirty);
    element.addEventListener("mouseup", rememberReportSelection);
    element.addEventListener("keyup", rememberReportSelection);
    element.addEventListener("keydown", (event) => {
      if (
        (event.ctrlKey || event.metaKey)
        && event.key.toLowerCase() === "s"
      ) {
        event.preventDefault();
        saveReportComments();
      }
    });
  });
}

function bindEvents() {
  $$(".tab-button").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });

  $("#athlete-form").addEventListener("submit", addAthlete);
  $("#refresh-athletes").addEventListener("click", async () => {
    try {
      await loadAthletes();
      showMessage("선수 목록을 새로고침했습니다.", "success");
    } catch (error) {
      showMessage(error.message, "error");
    }
  });

  $("#measurement-athlete").addEventListener("change", async () => {
    await loadMeasurements();
    fillMeasurement(null);
  });

  $("#saved-measurement").addEventListener("change", () => {
    const id = $("#saved-measurement").value;
    const measurement = appState.measurements.find(
      (item) => String(item.id) === id
    );
    fillMeasurement(measurement || null);
  });

  $("#load-type").addEventListener("change", updateLoadLabel);
  $("#save-measurement").addEventListener("click", saveMeasurement);
  $("#upload-excel").addEventListener("click", uploadExcel);
  $("#run-analysis").addEventListener("click", runAnalysis);

  $("#report-frame").addEventListener("load", setupReportFrame);

  $$("#report-toolbar [data-format]").forEach((button) => {
    button.addEventListener("mousedown", (event) => event.preventDefault());
    button.addEventListener("click", () => {
      const type = button.dataset.format;
      if (type === "bold") applyReportStyle("fontWeight", "700");
      if (type === "italic") applyReportStyle("fontStyle", "italic");
      if (type === "underline") applyReportStyle("textDecoration", "underline");
    });
  });

  $$("#report-toolbar [data-color]").forEach((button) => {
    button.addEventListener("mousedown", (event) => event.preventDefault());
    button.addEventListener("click", () => {
      applyReportStyle("color", button.dataset.color);
    });
  });

  $("#clear-format").addEventListener("mousedown", (event) => event.preventDefault());
  $("#clear-format").addEventListener("click", clearReportFormat);
  $("#save-report").addEventListener("click", () => saveReportComments(false));

  $("#download-pdf").addEventListener("click", (event) => {
    if (appState.reportDirty) {
      event.preventDefault();
      showMessage("수정 내용을 먼저 저장하세요.", "error");
    }
  });

  $("#download-excel").addEventListener("click", (event) => {
    if (appState.reportDirty) {
      event.preventDefault();
      showMessage("수정 내용을 먼저 저장하세요.", "error");
    }
  });
}

async function initialize() {
  bindEvents();
  $("#test-date").value = localDateString();
  updateLoadLabel();
  setReportReady(false);

  try {
    await loadAthletes();
  } catch (error) {
    showMessage(error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", initialize);
