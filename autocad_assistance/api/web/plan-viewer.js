"use strict";

// DXF coordinates remain local survey coordinates. Only SVG display positions
// are shifted near zero so large eastings/northings retain visible detail.
window.GeoaiPlanViewer = (() => {
  const ns = "http://www.w3.org/2000/svg";
  let plan = null;
  let visible = new Set();
  let frame = null;
  let base = null;
  let drag = null;
  let selected = null;

  const byId = (id) => document.getElementById(id);
  const svgNode = (name) => document.createElementNS(ns, name);
  const label = (name, value) => `${name}: ${value}`;

  function screen(point) {
    return [point[0] - base.minX, base.maxY - point[1]];
  }

  function appendShape(group, entity, root) {
    if (!visible.has(entity.layer)) return;
    const type = entity.type;
    let shape = null;
    if (type === "INSERT") {
      for (const child of entity.children || []) appendShape(group, child, root);
      if (!(entity.children || []).length) {
        shape = svgNode("circle");
        const [x, y] = screen(entity.point);
        shape.setAttribute("cx", x);
        shape.setAttribute("cy", y);
        shape.setAttribute("r", base.marker);
      }
    } else if (type === "POINT") {
      shape = svgNode("circle");
      const [x, y] = screen(entity.point);
      shape.setAttribute("cx", x);
      shape.setAttribute("cy", y);
      shape.setAttribute("r", base.marker);
    } else if (type === "CIRCLE") {
      shape = svgNode("circle");
      const [x, y] = screen(entity.center);
      shape.setAttribute("cx", x);
      shape.setAttribute("cy", y);
      shape.setAttribute("r", entity.radius);
    } else if (Array.isArray(entity.points)) {
      shape = svgNode(entity.closed ? "polygon" : "polyline");
      shape.setAttribute("points", entity.points.map((point) => screen(point).join(",")).join(" "));
    } else if ((type === "TEXT" || type === "MTEXT") && entity.point) {
      shape = svgNode("text");
      const [x, y] = screen(entity.point);
      shape.setAttribute("x", x);
      shape.setAttribute("y", y);
      shape.setAttribute("font-size", base.font);
      shape.textContent = entity.text || "";
    }
    if (shape) {
      shape.setAttribute("data-layer", entity.layer);
      group.append(shape);
      group.dataset.entityId = root.id;
    }
  }

  function attributes(entity) {
    const items = [
      label("Тип", entity.type), label("Слой", entity.layer),
      label("ID просмотра", entity.id),
    ];
    if (entity.point) items.push(label("X, Y, Z", entity.point.join(", ")));
    if (entity.center) items.push(label("Центр X, Y, Z", entity.center.join(", ")));
    if (entity.points) items.push(label("Вершины", entity.points.length));
    if (entity.name) items.push(label("Блок", entity.name));
    if (entity.scale) items.push(label("Масштаб блока", entity.scale.join(", ")));
    if (entity.rotation !== undefined) items.push(label("Поворот блока", entity.rotation));
    if (entity.complete === false) items.push("Блок показан не полностью");
    if (entity.approximate) items.push("Дуга показана отрезками");
    if (entity.text) items.push(label("Текст", entity.text));
    byId("plan-attributes").replaceChildren(...items.map((value) => {
      const line = document.createElement("li");
      line.textContent = value;
      return line;
    }));
  }

  function draw() {
    const svg = byId("plan-svg");
    const groups = [];
    for (const entity of plan.entities) {
      const group = svgNode("g");
      group.classList.add("plan-entity");
      if (selected === entity.id) group.classList.add("selected");
      group.setAttribute("tabindex", "0");
      group.setAttribute("role", "button");
      group.setAttribute("aria-label", `${entity.type}, слой ${entity.layer}`);
      appendShape(group, entity, entity);
      if (!group.childNodes.length) continue;
      const select = () => {
        selected = entity.id;
        attributes(entity);
        draw();
      };
      group.addEventListener("click", select);
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select();
        }
      });
      groups.push(group);
    }
    svg.replaceChildren(...groups);
    svg.setAttribute("viewBox", `${frame.x} ${frame.y} ${frame.w} ${frame.h}`);
  }

  function fit() {
    if (!base) return;
    const width = Math.max(base.maxX - base.minX, 1);
    const height = Math.max(base.maxY - base.minY, 1);
    const padding = Math.max(width, height) * 0.06;
    frame = { x: -padding, y: -padding,
      w: width + 2 * padding, h: height + 2 * padding };
    draw();
  }

  function zoom(factor, x = 0.5, y = 0.5) {
    if (!frame) return;
    const w = frame.w * factor;
    const h = frame.h * factor;
    if (w < 1e-9 || w > 1e12) return;
    frame.x += (frame.w - w) * x;
    frame.y += (frame.h - h) * y;
    frame.w = w;
    frame.h = h;
    draw();
  }

  function hide() {
    byId("plan-panel").hidden = true;
    byId("plan-svg").replaceChildren();
    byId("plan-attributes").replaceChildren();
    plan = null;
    frame = null;
    base = null;
    selected = null;
  }

  function show(value) {
    plan = value;
    selected = null;
    const bounds = value.bounds || { minX: 0, minY: 0, maxX: 1, maxY: 1 };
    base = { ...bounds,
      marker: Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY, 1) * 0.003,
      font: Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY, 1) * 0.012 };
    visible = new Set(value.layers.map((layer) => layer.name));
    const switches = value.layers.map((layer) => {
      const line = document.createElement("label");
      line.className = "plan-layer";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = true;
      input.addEventListener("change", () => {
        if (input.checked) visible.add(layer.name);
        else visible.delete(layer.name);
        draw();
      });
      const name = document.createElement("span");
      name.textContent = `${layer.name} (${layer.count})`;
      line.append(input, name);
      return line;
    });
    byId("plan-layers").replaceChildren(...switches);
    const missing = Object.entries(value.unsupported).map(([kind, count]) => `${kind}: ${count}`);
    byId("plan-summary").textContent =
      `Локальные координаты · ${value.entities.length} объектов · ${value.layers.length} слоёв`
      + (missing.length ? ` · Не отображено: ${missing.join(", ")}` : "");
    if (!value.bounds) byId("plan-summary").textContent += " · Отображаемой геометрии нет";
    byId("plan-panel").hidden = false;
    fit();
  }

  byId("plan-fit").addEventListener("click", fit);
  byId("plan-zoom-in").addEventListener("click", () => zoom(0.8));
  byId("plan-zoom-out").addEventListener("click", () => zoom(1.25));
  byId("plan-close").addEventListener("click", hide);
  const svg = byId("plan-svg");
  svg.addEventListener("wheel", (event) => {
    if (!frame) return;
    event.preventDefault();
    const rect = svg.getBoundingClientRect();
    zoom(event.deltaY < 0 ? 0.8 : 1.25,
      (event.clientX - rect.left) / rect.width,
      (event.clientY - rect.top) / rect.height);
  }, { passive: false });
  svg.addEventListener("pointerdown", (event) => {
    if (!frame || event.target !== svg) return;
    drag = { x: event.clientX, y: event.clientY };
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener("pointermove", (event) => {
    if (!drag || !frame) return;
    const rect = svg.getBoundingClientRect();
    frame.x -= (event.clientX - drag.x) * frame.w / rect.width;
    frame.y -= (event.clientY - drag.y) * frame.h / rect.height;
    drag = { x: event.clientX, y: event.clientY };
    draw();
  });
  svg.addEventListener("pointerup", () => { drag = null; });
  svg.addEventListener("pointercancel", () => { drag = null; });

  return { show, hide };
})();
