export const componentId = "multi-toggle";
export const jsRequired = true;
const instances = new WeakMap();

function cells(root) {
  return [...root.querySelectorAll('[data-s1-part="cell"][role="radio"]')];
}

function enabledCells(root) {
  return cells(root).filter((cell) => cell.getAttribute("aria-disabled") !== "true" && !cell.disabled);
}

function select(root, next, { focus = false } = {}) {
  const list = cells(root);
  if (!list.includes(next) || next.getAttribute("aria-disabled") === "true" || next.disabled) return;
  for (const cell of list) {
    const checked = cell === next;
    cell.setAttribute("aria-checked", String(checked));
    cell.tabIndex = checked ? 0 : -1;
  }
  if (focus) next.focus();
  root.dispatchEvent(new CustomEvent("s1:multi-toggle:change", {
    bubbles: true,
    detail: { index: list.indexOf(next), value: next.dataset.value ?? next.textContent.trim(), cell: next }
  }));
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);
  const list = cells(root);
  if (!list.length) return null;
  if (!root.hasAttribute("role")) root.setAttribute("role", "radiogroup");
  for (const cell of list) {
    if (!cell.hasAttribute("role")) cell.setAttribute("role", "radio");
    if (!cell.hasAttribute("type")) cell.setAttribute("type", "button");
  }
  const checked = list.find((cell) => cell.getAttribute("aria-checked") === "true")
    || enabledCells(root)[0]
    || list[0];
  for (const cell of list) {
    cell.setAttribute("aria-checked", String(cell === checked));
    cell.tabIndex = cell === checked ? 0 : -1;
  }

  const onClick = (event) => {
    const cell = event.target.closest('[data-s1-part="cell"]');
    if (cell && root.contains(cell)) select(root, cell);
  };

  const onKeydown = (event) => {
    const current = event.target.closest('[data-s1-part="cell"]');
    if (!current || !root.contains(current)) return;
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      select(root, current, { focus: true });
      return;
    }
    const movable = enabledCells(root);
    if (!movable.length) return;
    const index = movable.indexOf(current);
    if (index === -1) return;
    let target = null;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      target = movable[(index - 1 + movable.length) % movable.length];
    } else if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      target = movable[(index + 1) % movable.length];
    } else if (event.key === "Home") {
      target = movable[0];
    } else if (event.key === "End") {
      target = movable.at(-1);
    }
    if (target) {
      event.preventDefault();
      select(root, target, { focus: true });
    }
  };

  root.addEventListener("click", onClick);
  root.addEventListener("keydown", onKeydown);

  const api = Object.freeze({
    get selected() { return cells(root).find((cell) => cell.getAttribute("aria-checked") === "true"); },
    select: (cell) => select(root, cell),
    destroy() {
      root.removeEventListener("click", onClick);
      root.removeEventListener("keydown", onKeydown);
      instances.delete(root);
    }
  });
  instances.set(root, api);
  return api;
}

export function destroy(root) {
  instances.get(root)?.destroy();
}

export const runtime = Object.freeze({ init, destroy });
