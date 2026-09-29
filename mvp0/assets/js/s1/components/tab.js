export const componentId = "tab";
export const jsRequired = true;
const instances = new WeakMap();

function tabs(root) { return [...root.querySelectorAll('[data-s1-part="tab"][role="tab"]')]; }
function select(root, next, { focus = false } = {}) {
  const list = tabs(root);
  if (!list.includes(next)) return;
  for (const tab of list) {
    const selected = tab === next;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    const panelId = tab.getAttribute("aria-controls");
    const panel = panelId ? root.querySelector(`#${CSS.escape(panelId)}`) : null;
    if (panel) panel.hidden = !selected;
  }
  if (focus) next.focus();
  root.dispatchEvent(new CustomEvent("s1:tab:change", { bubbles: true, detail: { tab: next, value: next.dataset.value ?? next.textContent.trim() } }));
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);
  const list = tabs(root);
  if (!list.length) return null;
  if (!root.hasAttribute("role")) root.setAttribute("role", "tablist");
  const selected = list.find((tab) => tab.getAttribute("aria-selected") === "true") || list[0];
  for (const tab of list) { if (!tab.hasAttribute("type")) tab.setAttribute("type", "button"); tab.setAttribute("role", "tab"); }
  select(root, selected);
  const onClick = (event) => { const tab = event.target.closest('[data-s1-part="tab"]'); if (tab && root.contains(tab)) select(root, tab); };
  const onKeydown = (event) => {
    const current = event.target.closest('[data-s1-part="tab"]');
    if (!current || !root.contains(current)) return;
    const index = list.indexOf(current);
    const target = event.key === "ArrowLeft" ? list[(index - 1 + list.length) % list.length]
      : event.key === "ArrowRight" ? list[(index + 1) % list.length]
      : event.key === "Home" ? list[0] : event.key === "End" ? list.at(-1) : null;
    if (target) { event.preventDefault(); select(root, target, { focus: true }); }
  };
  root.addEventListener("click", onClick); root.addEventListener("keydown", onKeydown);
  const api = Object.freeze({ get selected() { return tabs(root).find((tab) => tab.getAttribute("aria-selected") === "true"); }, select: (tab) => select(root, tab), destroy() { root.removeEventListener("click", onClick); root.removeEventListener("keydown", onKeydown); instances.delete(root); } });
  instances.set(root, api); return api;
}
export function destroy(root) { instances.get(root)?.destroy(); }
export const runtime = Object.freeze({ init, destroy });
