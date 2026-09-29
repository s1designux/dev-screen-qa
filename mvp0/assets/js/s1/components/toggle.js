export const componentId = "toggle";
export const jsRequired = true;

const instances = new WeakMap();

function isOn(root) {
  return root.getAttribute("aria-checked") === "true";
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);
  if (root.getAttribute("role") !== "switch") return null;
  if (!root.hasAttribute("aria-checked")) root.setAttribute("aria-checked", "false");

  const set = (next) => {
    if (root.disabled) return;
    const value = Boolean(next);
    if (value === isOn(root)) return;
    root.setAttribute("aria-checked", String(value));
    root.dispatchEvent(new CustomEvent("s1:toggle:change", { bubbles: true, detail: { checked: value } }));
  };
  const handleClick = () => set(!isOn(root));

  root.addEventListener("click", handleClick);

  const api = Object.freeze({
    get checked() { return isOn(root); },
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
