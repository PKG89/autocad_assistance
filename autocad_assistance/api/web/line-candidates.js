"use strict";

window.GeoaiLineCandidates = (() => {
  const reasonText = {
    RECORDED_SURVEY_ORDER: "Порядок строк исходной съёмки",
    EXISTING_ANCHORED_NEAREST_NEIGHBOR: "Текущий алгоритм: от первой точки к ближайшей следующей",
    REVIEW_REQUIRED: "Варианты требуют подтверждения специалистом",
    TOO_FEW_POINTS: "В группе меньше двух точек",
    EMPTY_POINT_ID: "Есть точка без ID",
    DUPLICATE_POINT_ID: "В группе повторяются ID точек",
  };
  const actionText = { A: "Подтверждён A", B: "Подтверждён B",
    skip: "Пропущено", manual: "Ручная проверка" };
  const byId = (id) => document.getElementById(id);
  const plural = (count, one, few, many) => {
    const last = count % 10;
    const teens = count % 100;
    if (last === 1 && teens !== 11) return one;
    if (last >= 2 && last <= 4 && (teens < 12 || teens > 14)) return few;
    return many;
  };

  function element(name, content) {
    const node = document.createElement(name);
    node.textContent = content;
    return node;
  }

  function candidateNode(candidate, unit) {
    const item = document.createElement("li");
    item.className = "candidate-option";
    item.append(element("strong", `Вариант ${candidate.label}`));
    item.append(element("p", candidate.pointIds.join(" → ")));
    item.append(element("p", `Длина в плане: ${candidate.length2D.toFixed(3)} ${unit || "ед. X/Y"}; `
      + `изменённых позиций: ${candidate.reorderedPositions}.`));
    item.append(element("p", candidate.reasons.map((code) => reasonText[code] || code).join("; ")));
    return item;
  }

  function show(comparison, history = { events: [] }, onSave = null) {
    const panel = byId("candidate-panel");
    const list = byId("candidate-groups");
    const groups = [];
    const current = new Map();
    for (const event of history.latest || []) current.set(event.groupCode, event);
    for (const group of comparison.groups) {
      const details = document.createElement("details");
      const summary = element("summary", `${group.groupCode} · ${group.pointCount} ${plural(group.pointCount, "точка", "точки", "точек")} · `
        + (group.status === "proposals" ? "два варианта" : "ручная проверка"));
      details.append(summary);
      if (group.status === "proposals") {
        details.append(element("p", group.sameOrder
          ? "Порядок A и B совпадает."
          : "Порядки A и B различаются."));
        const options = document.createElement("ol");
        options.append(...group.candidates.map((candidate) =>
          candidateNode(candidate, comparison.horizontalUnit)));
        details.append(options);
      } else {
        details.append(element("p", group.reasons.map((code) => reasonText[code] || code).join("; ")));
      }
      const saved = current.get(group.groupCode);
      details.append(element("p", saved
        ? `${actionText[saved.action]} · версия ${saved.version} · ${saved.createdAt} · автор ${saved.authorId}`
        : "Решение не сохранено."));
      if (onSave) {
        const controls = document.createElement("div");
        controls.className = "inline-form";
        const actions = group.status === "proposals" ? ["A", "B", "skip", "manual"] : ["skip", "manual"];
        for (const action of actions) {
          const button = element("button", ({ A: "Подтвердить A", B: "Подтвердить B",
            skip: "Пропустить", manual: "На ручную проверку" })[action]);
          button.type = "button";
          button.addEventListener("click", async () => {
            for (const child of controls.children) child.disabled = true;
            try { await onSave(group.groupCode, saved?.version || 0, action); }
            finally { for (const child of controls.children) child.disabled = false; }
          });
          controls.append(button);
        }
        details.append(controls);
      }
      groups.push(details);
    }
    if (!groups.length) groups.push(element("p", "По поддерживаемым линейным кодам групп нет."));
    list.replaceChildren(...groups);
    byId("candidate-summary").textContent =
      `${comparison.groupCount} ${plural(comparison.groupCount, "группа", "группы", "групп")} · `
      + `${comparison.eligiblePointCount} ${plural(comparison.eligiblePointCount, "точка", "точки", "точек")} · `
      + `алгоритм ${comparison.candidateVersion} · решения применяются только к новым заданиям DXF`;
    panel.hidden = false;
  }

  function hide() {
    byId("candidate-panel").hidden = true;
    byId("candidate-groups").replaceChildren();
  }

  return { show, hide };
})();
