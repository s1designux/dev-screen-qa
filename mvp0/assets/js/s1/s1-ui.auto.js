import { init as init_input } from "./components/input.js";
import { init as init_toggle } from "./components/toggle.js";
import { init as init_chip } from "./components/chip.js";
import { init as init_dropdown } from "./components/dropdown.js";
import { init as init_select } from "./components/select.js";
import { init as init_filterChip } from "./components/filter-chip.js";
import { init as init_tab } from "./components/tab.js";
import { init as init_pagination } from "./components/pagination.js";
import { init as init_multiToggle } from "./components/multi-toggle.js";
import { init as init_modal } from "./components/modal.js";
import { init as init_table } from "./components/table.js";
import { init as init_timePicker } from "./components/time-picker.js";
import { init as init_datePicker } from "./components/date-picker.js";
import { init as init_gnb } from "./components/gnb.js";
import { init as init_modalContent } from "./components/modal-content.js";
import { init as init_bottomSheet } from "./components/bottom-sheet.js";
export * as input from "./components/input.js";
export * as button from "./components/button.js";
export * as checkbox from "./components/checkbox.js";
export * as radio from "./components/radio.js";
export * as toggle from "./components/toggle.js";
export * as chip from "./components/chip.js";
export * as dropdown from "./components/dropdown.js";
export * as select from "./components/select.js";
export * as filterChip from "./components/filter-chip.js";
export * as tab from "./components/tab.js";
export * as pagination from "./components/pagination.js";
export * as textarea from "./components/textarea.js";
export * as multiToggle from "./components/multi-toggle.js";
export * as modal from "./components/modal.js";
export * as table from "./components/table.js";
export * as mobileBottomNav from "./components/mobile-bottom-nav.js";
export * as mobileHeader from "./components/mobile-header.js";
export * as timePicker from "./components/time-picker.js";
export * as datePicker from "./components/date-picker.js";
export * as gnb from "./components/gnb.js";
export * as gnbSubMenuItem from "./components/gnb-sub-menu-item.js";
export * as gnbSubMenu from "./components/gnb-sub-menu.js";
export * as assistButton from "./components/assist-button.js";
export * as textButton from "./components/text-button.js";
export * as modalContent from "./components/modal-content.js";
export * as bottomSheetOption from "./components/bottom-sheet-option.js";
export * as bottomSheet from "./components/bottom-sheet.js";
export * as listRow from "./components/list-row.js";

export function autoInit(scope = document) {
  const instances = [
    ...[...scope.querySelectorAll('[data-s1-component="input"]')].map((root) => init_input(root)),
    ...[...scope.querySelectorAll('[data-s1-component="toggle"]')].map((root) => init_toggle(root)),
    ...[...scope.querySelectorAll('[data-s1-component="chip"]')].map((root) => init_chip(root)),
    ...[...scope.querySelectorAll('[data-s1-component="dropdown"]')].map((root) => init_dropdown(root)),
    ...[...scope.querySelectorAll('[data-s1-component="select"]')].map((root) => init_select(root)),
    ...[...scope.querySelectorAll('[data-s1-component="filter-chip"]')].map((root) => init_filterChip(root)),
    ...[...scope.querySelectorAll('[data-s1-component="tab"]')].map((root) => init_tab(root)),
    ...[...scope.querySelectorAll('[data-s1-component="pagination"]')].map((root) => init_pagination(root)),
    ...[...scope.querySelectorAll('[data-s1-component="multi-toggle"]')].map((root) => init_multiToggle(root)),
    ...[...scope.querySelectorAll('[data-s1-component="modal"]')].map((root) => init_modal(root)),
    ...[...scope.querySelectorAll('[data-s1-component="table"]')].map((root) => init_table(root)),
    ...[...scope.querySelectorAll('[data-s1-component="time-picker"]')].map((root) => init_timePicker(root)),
    ...[...scope.querySelectorAll('[data-s1-component="date-picker"]')].map((root) => init_datePicker(root)),
    ...[...scope.querySelectorAll('[data-s1-component="gnb"]')].map((root) => init_gnb(root)),
    ...[...scope.querySelectorAll('[data-s1-component="modal-content"]')].map((root) => init_modalContent(root)),
    ...[...scope.querySelectorAll('[data-s1-component="bottom-sheet"]')].map((root) => init_bottomSheet(root))
  ];
  return Object.freeze(instances.filter(Boolean));
}
