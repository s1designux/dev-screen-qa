export const componentId = "table";
export const jsRequired = true;

const instances = new WeakMap();

function getParts(root) {
  const headerCheckbox = root.querySelector('[data-s1-part="header-cell"][data-selection] input[type="checkbox"]');
  const rows = [...root.querySelectorAll('[data-s1-part="row"]')];
  const rowCheckboxes = rows
    .map((row) => ({ row, control: row.querySelector('[data-s1-part="cell"][data-selection] input[type="checkbox"]') }))
    .filter((entry) => entry.control);
  return { headerCheckbox, rowCheckboxes };
}

export function init(root) {
  if (!(root instanceof Element) || root.dataset.s1Component !== componentId) return null;
  if (instances.has(root)) return instances.get(root);

  const { headerCheckbox, rowCheckboxes } = getParts(root);
  if (!rowCheckboxes.length) return null;

  const emit = () => {
    const selected = rowCheckboxes.filter((entry) => entry.control.checked).map((entry) => entry.row);
    root.dispatchEvent(new CustomEvent("s1:table:selectionchange", {
      bubbles: true,
      detail: { selectedCount: selected.length, totalCount: rowCheckboxes.length }
    }));
  };

  const syncRow = (entry) => {
    entry.row.setAttribute("data-selected", entry.control.checked ? "true" : "false");
  };

  // 정본 행동 계약(component-behavior.pc.json "Table"):
  //  · 행 체크박스 → 그 행 선택을 토글하고 헤더 체크박스를 다시 계산한다.
  //  · 헤더 체크박스 → 하나라도 안 켜져 있으면 전체 선택, 아니면 전체 해제.
  // 부분선택(indeterminate) 표시는 정본 체크박스에 없어 사용하지 않는다.
  const syncHeader = () => {
    if (!headerCheckbox) return;
    headerCheckbox.checked = rowCheckboxes.every((entry) => entry.control.checked);
  };

  const handleRowChange = (event) => {
    const entry = rowCheckboxes.find((item) => item.control === event.target);
    if (!entry) return;
    syncRow(entry);
    syncHeader();
    emit();
  };

  const handleHeaderChange = () => {
    const shouldSelectAll = rowCheckboxes.some((entry) => !entry.control.checked);
    for (const entry of rowCheckboxes) {
      if (entry.control.disabled) continue;
      entry.control.checked = shouldSelectAll;
      syncRow(entry);
    }
    syncHeader();
    emit();
  };

  for (const entry of rowCheckboxes) {
    entry.control.addEventListener("change", handleRowChange);
    syncRow(entry);
  }
  if (headerCheckbox) headerCheckbox.addEventListener("change", handleHeaderChange);
  syncHeader();

  const api = Object.freeze({
    root,
    getSelectedRows: () => rowCheckboxes.filter((entry) => entry.control.checked).map((entry) => entry.row),
    destroy: () => destroy(root)
  });

  instances.set(root, { api, headerCheckbox, rowCheckboxes, handleRowChange, handleHeaderChange });
  return api;
}

export function destroy(root) {
  const instance = instances.get(root);
  if (!instance) return;
  for (const entry of instance.rowCheckboxes) entry.control.removeEventListener("change", instance.handleRowChange);
  if (instance.headerCheckbox) instance.headerCheckbox.removeEventListener("change", instance.handleHeaderChange);
  instances.delete(root);
}

export const runtime = Object.freeze({ init, destroy });
