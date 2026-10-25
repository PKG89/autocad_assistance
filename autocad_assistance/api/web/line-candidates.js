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

  function show(comparison) {
    const panel = byId("candidate-panel");
    const list = byId("candidate-groups");
    const groups = [];
    for (const group of comparison.groups) {
      const details = document.createElement("details");
      const summary = element("summary", `${group.groupCode} · ${group.pointCount} ${plural(group.pointCount, "точка", "точки", "точек")} · `
        + (group.status === "proposals" ? "два варианта" : "ручная проверка"));
      details.append(summary);
      if (group.status === "proposals") {
        details.append(element("p", group.sameOrder
          ? "Порядок A и B совпадает. Решение пока не принято."
          : "Порядки A и B различаются. Решение пока не принято."));
        const options = document.createElement("ol");
        options.append(...group.candidates.map((candidate) =>
          candidateNode(candidate, comparison.horizontalUnit)));
        details.append(options);
      } else {
        details.append(element("p", group.reasons.map((code) => reasonText[code] || code).join("; ")));
      }
      groups.push(details);
    }
    if (!groups.length) groups.push(element("p", "По поддерживаемым линейным кодам групп нет."));
    list.replaceChildren(...groups);
    byId("candidate-summary").textContent =
      `${comparison.groupCount} ${plural(comparison.groupCount, "группа", "группы", "групп")} · `
      + `${comparison.eligiblePointCount} ${plural(comparison.eligiblePointCount, "точка", "точки", "точек")} · `
      + `алгоритм ${comparison.candidateVersion} · исходный DXF не изменён`;
    panel.hidden = false;
  }

  function hide() {
    byId("candidate-panel").hidden = true;
    byId("candidate-groups").replaceChildren();
  }

  return { show, hide };
})();
