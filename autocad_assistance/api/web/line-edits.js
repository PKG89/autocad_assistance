"use strict";

window.GeoaiLineEdits = (() => {
  const byId = (id) => document.getElementById(id);
  const plural = (count, one, few, many) => {
    const last = count % 10;
    const teens = count % 100;
    if (last === 1 && teens !== 11) return one;
    if (last >= 2 && last <= 4 && (teens < 12 || teens > 14)) return few;
    return many;
  };
  const text = (tag, value) => {
    const node = document.createElement(tag);
    node.textContent = value;
    return node;
  };
  const field = (label, value = "", type = "text") => {
    const wrapper = document.createElement("label");
    wrapper.textContent = label;
    const input = document.createElement("input");
    input.type = type;
    input.value = value;
    wrapper.append(input);
    return [wrapper, input];
  };
  const choice = (label, values, selected) => {
    const wrapper = document.createElement("label");
    wrapper.textContent = label;
    const select = document.createElement("select");
    for (const [value, caption] of values) select.add(new Option(caption, value));
    if (selected) select.value = selected;
    wrapper.append(select);
    return [wrapper, select];
  };
  const button = (label, callback) => {
    const item = text("button", label);
    item.type = "button";
    item.addEventListener("click", async () => {
      item.disabled = true;
      try { await callback(); } finally { item.disabled = false; }
    });
    return item;
  };
  const rowText = (rows, pointIds) => rows.map((row) => `${pointIds.get(row) || "?"} (#${row})`).join(" → ");

  function show(state, history, comparison, onSave) {
    const panel = byId("edit-panel");
    const list = byId("edit-lines");
    const model = state.model;
    const pointIds = new Map();
    for (const group of comparison.groups) {
      for (const candidate of group.candidates || []) {
        for (const vertex of candidate.vertices || []) pointIds.set(vertex.rowIndex, vertex.pointId);
      }
    }
    byId("edit-summary").textContent = `Версия ${state.version} · ${model.lines.length} `
      + `${plural(model.lines.length, "линия", "линии", "линий")} · `
      + `${model.sourceRowIndexes.length} ${plural(model.sourceRowIndexes.length, "исходная точка", "исходные точки", "исходных точек")} · SHA-256 модели ${state.modelSha256}`
      + (state.staleDecisions ? " · решения A/B изменились: сбросьте модель перед новой правкой или расчётом" : "");
    const nodes = [];
    if (!model.lines.length) nodes.push(text("p", "Нет групп с однозначными ID для правки."));
    for (const line of model.lines) {
      const details = document.createElement("details");
      details.append(text("summary", `${line.groupCode} · ${line.lineId} · ${line.rowIndexes.length} `
        + plural(line.rowIndexes.length, "точка", "точки", "точек")));
      details.append(text("p", rowText(line.rowIndexes, pointIds)));
      if (!state.staleDecisions) {
        const reorder = document.createElement("div");
        reorder.className = "inline-form";
        const [orderLabel, orderInput] = field("Порядок индексов через запятую", line.rowIndexes.join(","));
        reorder.append(orderLabel, button("Переставить", () => onSave({
          type: "reorder", lineId: line.lineId,
          rowIndexes: orderInput.value.split(",").map((value) => Number(value.trim())),
        })));
        details.append(reorder);
        if (line.rowIndexes.length >= 2) {
          const split = document.createElement("div");
          split.className = "inline-form";
          const [atLabel, atInput] = field("После позиции", "1", "number");
          atInput.min = "1";
          atInput.max = String(line.rowIndexes.length - 1);
          split.append(atLabel, button("Разорвать", () => onSave({
            type: "split", lineId: line.lineId, at: Number(atInput.value),
            newLineId: crypto.randomUUID(),
          })));
          details.append(split);
        }
        const others = model.lines.filter((item) => item.lineId !== line.lineId);
        if (others.length) {
          const join = document.createElement("div");
          join.className = "inline-form";
          const [otherLabel, otherInput] = choice("Добавить линию", others.map((item) =>
            [item.lineId, `${item.groupCode} · ${item.lineId}`]));
          const [codeLabel, codeInput] = choice("Итоговый код линии",
            model.editableGroupCodes.map((code) => [code, code]), line.groupCode);
          join.append(otherLabel, codeLabel, button("Объединить", () => onSave({
            type: "join", firstLineId: line.lineId, secondLineId: otherInput.value,
            groupCode: codeInput.value,
          })));
          details.append(join);
          const move = document.createElement("div");
          move.className = "inline-form";
          const [rowLabel, rowInput] = choice("Перенести точку", line.rowIndexes.map((row) =>
            [String(row), `${pointIds.get(row) || "?"} (#${row})`]));
          const [targetLabel, targetInput] = choice("В линию", others.map((item) =>
            [item.lineId, `${item.groupCode} · ${item.lineId}`]));
          const [positionLabel, positionInput] = field("Позиция с 0", "0", "number");
          positionInput.min = "0";
          move.append(rowLabel, targetLabel, positionLabel, button("Перенести", () => onSave({
            type: "move", fromLineId: line.lineId, toLineId: targetInput.value,
            rowIndex: Number(rowInput.value), position: Number(positionInput.value),
          })));
          details.append(move);
        }
      }
      nodes.push(details);
    }
    const actions = document.createElement("div");
    actions.className = "inline-form";
    if (state.version > 0 && !state.staleDecisions) {
      const [versionLabel, versionInput] = field("Вернуть версию (0 = исходная)", "0", "number");
      versionInput.min = "0";
      versionInput.max = String(state.version - 1);
      actions.append(versionLabel, button("Отменить до версии", () => onSave({
        type: "undo", targetVersion: Number(versionInput.value),
      })));
    }
    actions.append(button("Сбросить к текущим A/B", () => onSave({ type: "reset" })));
    nodes.push(actions);
    list.replaceChildren(...nodes);
    const log = byId("edit-history");
    const events = history.events || [];
    log.replaceChildren(text("h4", "История версий"), ...events.map((event) =>
      text("p", `v${event.version} · ${event.operation.type} · ${event.createdAt} · ${event.authorId}`)));
    panel.hidden = false;
  }

  function hide() {
    byId("edit-panel").hidden = true;
    byId("edit-lines").replaceChildren();
    byId("edit-history").replaceChildren();
  }

  return { show, hide };
})();
