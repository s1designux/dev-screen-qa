export const componentId = "chip";
export const jsRequired = true;

const instances = new WeakMap();

function isSelected(root) {
  return root.getAttribute("aria-pressed") === "true";
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);
  if (!root.hasAttribute("aria-pressed")) root.setAttribute("aria-pressed", "false");

  const set = (next) => {
    if (root.disabled) return;
    const value = Boolean(next);
    if (value === isSelected(root)) return;
    root.setAttribute("aria-pressed", String(value));
    root.dispatchEvent(new CustomEvent("s1:chip:change", { bubbles: true, detail: { selected: value } }));
  };
  const handleClick = () => set(!isSelected(root));

  root.addEventListener("click", handleClick);

  const api = Object.freeze({
    get selected() { return isSelected(root); },
    set(next) { set(next); },
    destroy() {
      root.removeEventListener("click", handleClick);
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
