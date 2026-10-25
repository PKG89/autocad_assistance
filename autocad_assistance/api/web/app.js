"use strict";

const $ = (id) => document.getElementById(id);
const fields = ["Point", "X", "Y", "Z", "Code", "Comments"];
let csrfToken = null;
let uploadId = null;
let previewColumns = [];
let submitIntent = null;
const retryIntents = new Map();
let jobPoll = null;

function message(text, isError = false) {
  $("status").textContent = text;
  $("status").classList.toggle("error", isError);
}

function item(text) {
  const node = document.createElement("li");
  node.textContent = text;
  return node;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (options.body instanceof FormData) {
    // The browser sets the multipart boundary.
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (options.method && options.method !== "GET" && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(body.error?.message || `Ошибка HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return body;
}

async function busy(button, action, retainOnSuccess = false) {
  if (button.disabled) return;
  button.disabled = true;
  let completed = false;
  try {
    await action();
    completed = true;
  } catch (error) {
    message(error.message || "Не удалось выполнить действие", true);
  } finally {
    button.disabled = retainOnSuccess && completed;
  }
}

function showLogin() {
  clearTimeout(jobPoll);
  jobPoll = null;
  csrfToken = null;
  uploadId = null;
  $("login-panel").hidden = false;
  $("workspace").hidden = true;
  $("logout").hidden = true;
}

async function showWorkspace(session) {
  csrfToken = session.csrfToken;
  $("login-panel").hidden = true;
  $("workspace").hidden = false;
  $("logout").hidden = false;
  message(`Вы вошли как ${session.username}`);
  await loadProjects();
}

async function loadProjects(preferredId = null) {
  const response = await api("/api/v1/projects?page=1&pageSize=50");
  const select = $("project-select");
  const previous = preferredId || select.value;
  select.replaceChildren(new Option("— выберите —", ""));
  for (const project of response.data) {
    select.add(new Option(project.name, project.projectId));
  }
  if (response.data.some((project) => project.projectId === previous)) {
    select.value = previous;
  } else if (response.data.length === 1) {
    select.value = response.data[0].projectId;
  }
  await loadRevisions();
}

async function loadRevisions() {
  const list = $("revision-list");
  list.replaceChildren();
  const revisionSelect = $("job-revision");
  const previousRevision = revisionSelect.value;
  revisionSelect.replaceChildren(new Option("— выберите —", ""));
  const projectId = $("project-select").value;
  if (!projectId) {
    list.append(item("Сначала выберите проект."));
    $("job-submit").disabled = true;
    await loadJobs();
    return;
  }
  const response = await api(`/api/v1/projects/${projectId}/revisions?page=1&pageSize=50`);
  if (!response.data.length) {
    list.append(item("Пока нет сохранённых версий."));
  }
  for (const revision of response.data) {
    list.append(item(`Версия ${revision.sequence} · ${revision.sourceFormat.toUpperCase()} · ${revision.createdAt}`));
    revisionSelect.add(new Option(`Версия ${revision.sequence} · ${revision.createdAt}`, revision.revisionId));
  }
  if (response.data.some((revision) => revision.revisionId === previousRevision)) {
    revisionSelect.value = previousRevision;
  } else if (response.data.length) {
    revisionSelect.value = response.data[0].revisionId;
  }
  $("job-submit").disabled = !revisionSelect.value;
  await loadJobs();
}

function jobAction(label, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", () => busy(button, handler));
  return button;
}

async function loadJobs() {
  clearTimeout(jobPoll);
  jobPoll = null;
  const list = $("job-list");
  list.replaceChildren();
  const projectId = $("project-select").value;
  if (!projectId) {
    list.append(item("Сначала выберите проект."));
    return;
  }
  let response;
  try {
    response = await api(`/api/v1/projects/${projectId}/jobs?page=1&pageSize=50`);
  } catch (error) {
    if (error.status === 404) {
      $("job-panel").hidden = true;
      return;
    }
    throw error;
  }
  $("job-panel").hidden = false;
  if ($("project-select").value !== projectId) return;
  if (!response.data.length) list.append(item("Заданий пока нет."));
  let active = false;
  for (const job of response.data) {
    const row = item(`Версия ${job.revisionId} · ${job.status} · попытка ${job.attempt}${job.errorCode ? ` · ${job.errorCode}` : ""}`);
    row.className = "job-row";
    const actions = document.createElement("div");
    actions.className = "job-actions";
    if (["queued", "running", "cancelling"].includes(job.status)) active = true;
    if (["queued", "running"].includes(job.status)) {
      actions.append(jobAction("Отменить", async () => {
        await api(`/api/v1/jobs/${job.jobId}/cancel`, { method: "POST" });
        await loadJobs();
      }));
    }
    if (["failed", "cancelled"].includes(job.status) && job.attempt <= 2) {
      actions.append(jobAction("Повторить", async () => {
        let key = retryIntents.get(job.jobId);
        if (!key) {
          key = crypto.randomUUID();
          retryIntents.set(job.jobId, key);
        }
        await api(`/api/v1/jobs/${job.jobId}/retry`, {
          method: "POST", headers: { "Idempotency-Key": key },
        });
        retryIntents.delete(job.jobId);
        await loadJobs();
      }));
    }
    if (job.resultReady) {
      const link = document.createElement("a");
      link.href = `/api/v1/jobs/${job.jobId}/result`;
      link.textContent = "Скачать DXF";
      actions.append(link);
    }
    row.append(actions);
    list.append(row);
  }
  if (active) {
    jobPoll = setTimeout(() => loadJobs().catch((error) => message(error.message, true)), 3000);
  }
}

function showPreview(preview) {
  previewColumns = preview.columns;
  $("import-submit").disabled = false;
  $("import-result").textContent = "";
  $("import-warnings").replaceChildren();
  $("preview").hidden = false;
  $("preview-summary").textContent = `${preview.rowCount} строк · ${preview.format.toUpperCase()} · ${preview.encoding}`;
  const head = document.createElement("tr");
  for (const column of preview.columns) {
    const th = document.createElement("th");
    th.textContent = column;
    head.append(th);
  }
  $("preview-head").replaceChildren(head);
  const body = $("preview-body");
  body.replaceChildren();
  for (const row of preview.rows) {
    const tr = document.createElement("tr");
    for (const value of row) {
      const td = document.createElement("td");
      td.textContent = value;
      tr.append(td);
    }
    body.append(tr);
  }
  $("preview-warnings").replaceChildren(...preview.warnings.map((warning) => item(warning.message)));
  const mapping = $("mapping-fields");
  mapping.replaceChildren();
  for (const field of fields) {
    const label = document.createElement("label");
    label.textContent = `Колонка ${field}`;
    const select = document.createElement("select");
    select.dataset.field = field;
    select.add(new Option("— не выбрана —", ""));
    preview.columns.forEach((column, index) => select.add(new Option(`${index + 1}: ${column}`, String(index))));
    const exact = preview.columns.findIndex((column) => column.trim().toLowerCase() === field.toLowerCase());
    if (exact >= 0) select.value = String(exact);
    label.append(select);
    mapping.append(label);
  }
}

function mappingValues() {
  const mapping = {};
  for (const select of $("mapping-fields").querySelectorAll("select")) {
    if (select.value !== "") mapping[select.dataset.field] = Number(select.value);
  }
  for (const required of ["X", "Y", "Z"]) {
    if (mapping[required] === undefined) throw new Error(`Выберите колонку ${required}`);
  }
  return mapping;
}

$("login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  busy(event.submitter, async () => {
    const session = await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: $("username").value, password: $("password").value }),
    });
    $("password").value = "";
    await showWorkspace(session);
  });
});

$("logout").addEventListener("click", (event) => busy(event.currentTarget, async () => {
  await api("/api/v1/auth/logout", { method: "POST" });
  showLogin();
  message("Вы вышли из кабинета.");
}));

$("project-form").addEventListener("submit", (event) => {
  event.preventDefault();
  busy(event.submitter, async () => {
    const project = await api("/api/v1/projects", {
      method: "POST", body: JSON.stringify({ name: $("project-name").value }),
    });
    $("project-name").value = "";
    await loadProjects(project.projectId);
    message("Проект создан.");
  });
});

$("project-select").addEventListener("change", () => {
  submitIntent = null;
  retryIntents.clear();
  loadRevisions().catch((error) => message(error.message, true));
});

$("job-revision").addEventListener("change", () => {
  submitIntent = null;
  $("job-submit").disabled = !$("job-revision").value;
});

$("job-submit").addEventListener("click", (event) => busy(event.currentTarget, async () => {
  const revisionId = $("job-revision").value;
  if (!revisionId) throw new Error("Выберите версию съёмки");
  if (!submitIntent || submitIntent.revisionId !== revisionId) {
    submitIntent = { revisionId, key: crypto.randomUUID() };
  }
  const job = await api("/api/v1/jobs", {
    method: "POST", headers: { "Idempotency-Key": submitIntent.key },
    body: JSON.stringify({ revisionId, tinSettings: {} }),
  });
  submitIntent = null;
  message(`Задание ${job.jobId} принято.`);
  await loadJobs();
}));

$("upload-form").addEventListener("submit", (event) => {
  event.preventDefault();
  busy(event.submitter, async () => {
    if (!$("project-select").value) throw new Error("Сначала выберите проект");
    const file = $("survey-file").files[0];
    if (!file) throw new Error("Выберите файл TXT или CSV");
    uploadId = null;
    $("preview").hidden = true;
    const form = new FormData();
    form.append("file", file);
    const upload = await api("/api/v1/uploads", { method: "POST", body: form });
    uploadId = upload.uploadId;
    try {
      const preview = await api(`/api/v1/uploads/${uploadId}/preview`);
      showPreview(preview);
      message("Файл загружен. Проверьте строки и сопоставьте колонки.");
    } catch (error) {
      uploadId = null;
      throw error;
    }
  });
});

$("import-form").addEventListener("submit", (event) => {
  event.preventDefault();
  busy(event.submitter, async () => {
    const projectId = $("project-select").value;
    if (!projectId) throw new Error("Выберите проект");
    if (!uploadId || !previewColumns.length) throw new Error("Сначала загрузите и проверьте файл");
    const payload = {
      uploadId, mapping: mappingValues(),
      coordinateSystem: $("coordinate-system").value.trim() || null,
      horizontalUnit: $("horizontal-unit").value.trim() || null,
      verticalUnit: $("vertical-unit").value.trim() || null,
      scaleFactor: $("scale-factor").value.trim(),
    };
    const result = await api(`/api/v1/projects/${projectId}/revisions`, {
      method: "POST", body: JSON.stringify(payload),
    });
    $("import-result").textContent = `Сохранена версия ${result.revision.sequence}; ${result.rowCount} строк.`;
    $("import-warnings").replaceChildren(...result.warnings.map((warning) => item(warning.message)));
    uploadId = null;
    await loadRevisions();
    message("Импорт завершён.");
  }, true);
});

api("/api/v1/auth/session")
  .then(showWorkspace)
  .catch((error) => {
    if (error.status === 401) {
      showLogin();
      message("Войдите, чтобы открыть проекты.");
    } else {
      showLogin();
      message(error.message, true);
    }
  });
