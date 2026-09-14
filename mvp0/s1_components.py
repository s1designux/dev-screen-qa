"""S-1 디자인가이드 **컴포넌트**(단추·표·탭)를 포털이 그대로 쓰게 한다.

토큰(색·간격)만 맞추면 색은 회사 색이 되지만 **모양은 여전히 포털 모양**이다 —
단추 높이·모서리, 표 머리·줄 높이, 탭 밑줄이 가이드와 다르다. 그 한 층을 여기서 맞춘다.

수치는 가이드 정본(`design/DESIGN.core.md` §4 · `pages/components.html`)의 것이다:
  Button   XSM 34px / XXSM 28px / MD 44px · 모서리 4 · 테두리 1 · 라벨 14 Medium
  Table    머리 위 2px 진한 선 · 아래 1px 진한 선 · 칸 경계 연한 선 · 줄 높이 38(SM)
  Line Tab 높이 40 · 좌우 16 · 고른 것은 아래 2px 파란 줄(칸을 칠하지 않는다)

포털은 낱낱의 화면에서 이 모양을 **덮어쓰지 않는다**(가이드 §9-7). 그래서 여기 선택자는
포털이 이미 쓰고 있는 자리(`button`, `.btn`, `table`, `.tab`)까지 함께 받아 적는다 —
화면 쪽 CSS 에서 같은 것을 다시 적지 않게 하려는 것이다.

여기에도 값을 직접 적지 않는다. 전부 `var(--…)` 다.
"""

CSS = """
/* ── Button (S-1 코어) ─────────────────────────────────────
   포털의 맨 단추·단추 모양 링크가 이 규격을 그대로 받는다.
   골라 쓰는 것(탭·구역 고르개·후보 카드 토글)은 제 컴포넌트가 따로 있어서,
   :not() 으로 빼지 않고 **뒤에 오는 제 규칙**이 이기게 둔다(특이도를 낮게 유지한다). */
.s1-btn, .btn, .button, button{
  display:inline-flex;align-items:center;justify-content:center;gap:var(--spacing-2);
  height:var(--sizing-34);padding:0 var(--spacing-8);
  font-family:inherit;font-size:var(--font-size-14);font-weight:var(--font-weight-medium);
  line-height:1;letter-spacing:-.28px;white-space:nowrap;
  border:var(--border-width-1) solid var(--color-button-border-secondary--default);
  border-radius:var(--radius-4);
  background:var(--color-button-bg-secondary--default);
  color:var(--color-button-label-secondary--default);
  cursor:pointer;text-decoration:none;
  transition:background .15s,border-color .15s}
.s1-btn:hover, .btn:hover, .button:hover, button:hover{
  background:var(--color-button-bg-secondary--hover);
  border-color:var(--color-button-border-secondary--hover);
  color:var(--color-button-label-secondary--hover)}

.s1-btn-md,.btn.md{height:var(--sizing-44);padding:0 var(--spacing-16)}
.s1-btn-xxsm,.btn.xxsm,
.auto-actions button,.auto-range button,.auto-range-form button,
.passform button,button.upl{height:var(--sizing-28);padding:0 var(--spacing-8)}

.s1-btn-primary,.primary,.passform button{
  background:var(--color-button-bg-primary--default);
  border-color:var(--color-button-border-primary--default);
  color:var(--color-button-label-primary--default)}
.s1-btn-primary:hover,.primary:hover,.passform button:hover{
  background:var(--color-button-bg-primary--hover);
  border-color:var(--color-button-border-primary--hover);
  color:var(--color-button-label-primary--hover)}

.s1-btn-blue-line{
  background:var(--color-button-bg-blue-line--default);
  border-color:var(--color-button-border-blue-line--default);
  color:var(--color-button-label-blue-line--default)}
.s1-btn-blue-line:hover{
  background:var(--color-button-bg-blue-line--hover);
  border-color:var(--color-button-border-blue-line--hover);
  color:var(--color-button-label-blue-line--hover)}

.s1-btn:disabled,.s1-btn.is-disabled,button:disabled{
  background:var(--color-button-bg-disabled);
  border-color:var(--color-button-border-disabled);
  color:var(--color-button-label-disabled);
  cursor:default;pointer-events:none;opacity:1}

/* ── Table (S-1 코어) ──────────────────────────────────────
   머리 위에 진한 2px, 표 아래에 진한 1px, 칸 사이는 연한 선. 줄 높이는 SM(38). */
.s1-table,
.wrap table,main table,.card table,.cards table,dialog table{
  width:100%;border-collapse:collapse;
  border-top:var(--border-width-2) solid var(--color-table-border-strong);
  border-bottom:var(--border-width-1) solid var(--color-table-border-strong)}
.s1-table th,
.wrap table th,main table th,.card table th,.cards table th,dialog table th{
  height:var(--sizing-38);padding:0 var(--spacing-12);
  background:var(--color-table-header-bg);color:var(--color-text-secondary);
  border-bottom:var(--border-width-1) solid var(--color-table-border-default);
  font-size:var(--font-size-14);font-weight:var(--font-weight-medium);
  text-align:left;white-space:nowrap;letter-spacing:-.02em}
.s1-table td,
.wrap table td,main table td,.card table td,.cards table td,dialog table td{
  height:var(--sizing-38);padding:var(--spacing-8) var(--spacing-12);
  background:var(--color-table-cell-default);color:var(--color-text-body-primary);
  border-bottom:var(--border-width-1) solid var(--color-table-border-default);
  font-size:var(--font-size-14);font-weight:var(--font-weight-regular);
  letter-spacing:-.02em;vertical-align:middle}
.s1-table tbody tr:hover td,
.wrap table tbody tr:hover td,main table tbody tr:hover td{
  background:var(--color-table-cell-hover)}
.s1-table tbody tr.is-selected td{background:var(--color-table-cell-selected)}

/* ── Line Tab (S-1 코어) ───────────────────────────────────
   고른 탭은 칸을 칠하지 않고 **아래에 파란 2px 줄**을 둔다. */
.s1-tab,.tabbar{
  display:flex;align-items:flex-end;gap:0;
  background:var(--color-navigation-bg);
  border-bottom:var(--border-width-1) solid var(--color-navigation-indicator-default)}
.s1-tab-item,.tab{
  position:relative;display:inline-flex;align-items:center;justify-content:center;
  height:var(--sizing-40);padding:0 var(--spacing-16);
  margin-bottom:calc(-1 * var(--border-width-1));   /* 아래 줄을 컨테이너 선 위에 겹친다 */
  font-family:inherit;font-size:var(--font-size-14);font-weight:var(--font-weight-medium);
  line-height:var(--line-height-130);letter-spacing:-.28px;white-space:nowrap;
  color:var(--color-navigation-label-default);
  background:none;border:0;border-bottom:var(--border-width-1) solid transparent;
  border-radius:0;cursor:pointer}
.s1-tab-item:hover,.tab:hover{
  color:var(--color-navigation-label-hover);
  border-bottom:var(--border-width-2) solid var(--color-navigation-indicator-hover)}
.s1-tab-item.is-selected,.tab.on{
  color:var(--color-navigation-label-selected);
  background:none;
  border-bottom:var(--border-width-2) solid var(--color-navigation-indicator-selected)}
.s1-tab-item.is-disabled{color:var(--color-text-disabled);cursor:default}

/* ── Input · Select · Textarea (S-1 코어) ──────────────────
   PC XSM 한 크기로 맞춘다 — 포털의 입력칸은 전부 표·카드 안의 좁은 자리다.
   Input 왼 12 오른 8 / Select 왼 16 오른 8 / 모서리 4 / 높이 34. */
.s1-input,
input[type=text],input[type=search],input[type=number],input[type=password],
input[type=email],input[type=url],input[type=date],input:not([type]),
select,.s1-select{
  box-sizing:border-box;height:var(--sizing-34);
  padding:0 var(--spacing-8) 0 var(--spacing-12);
  font-family:inherit;font-size:var(--font-size-14);letter-spacing:-.028em;line-height:var(--line-height-130);
  color:var(--color-form-control-text-default);
  background:var(--color-form-control-bg-default);
  border:var(--border-width-1) solid var(--color-form-control-border-default);
  border-radius:var(--radius-4);
  transition:border-color .15s,background .15s}
select,.s1-select{padding:0 var(--spacing-8) 0 var(--spacing-16);cursor:pointer}
.s1-input::placeholder,input::placeholder{color:var(--color-form-control-text-placeholder)}
.s1-input:hover,input:hover,select:hover{background:var(--color-form-control-bg-hover)}
.s1-input:focus,input:focus,select:focus,textarea:focus{
  outline:none;
  border-color:var(--color-form-control-border-selected);
  background:var(--color-form-control-bg-selected);
  color:var(--color-form-control-text-selected)}
.s1-input:disabled,input:disabled,select:disabled,textarea:disabled{
  background:var(--color-form-control-bg-disabled);
  border-color:var(--color-form-control-border-disabled);
  color:var(--color-form-control-text-disabled);cursor:default}

.s1-textarea,textarea{
  box-sizing:border-box;display:block;width:100%;min-height:80px;
  padding:var(--spacing-10) var(--spacing-12);
  font-family:inherit;font-size:var(--font-size-14);letter-spacing:-.028em;line-height:var(--line-height-140);
  color:var(--color-form-control-text-default);
  background:var(--color-form-control-bg-default);
  border:var(--border-width-1) solid var(--color-form-control-border-default);
  border-radius:var(--radius-4)}

/* ── Checkbox · Radio (S-1 코어) ───────────────────────────
   18×18. 네모는 모서리 2, 동그라미는 원. 켜지면 파랑. */
input[type=checkbox],input[type=radio]{
  appearance:none;-webkit-appearance:none;box-sizing:border-box;
  width:var(--sizing-18);height:var(--sizing-18);margin:0;padding:0;flex:none;
  background:var(--color-control-bg-default);
  border:var(--border-width-1) solid var(--color-control-border-default);
  cursor:pointer;position:relative;transition:all .15s}
input[type=checkbox]{border-radius:var(--radius-2)}
input[type=radio]{border-radius:var(--radius-full)}
input[type=checkbox]:hover:not(:checked):not(:disabled),
input[type=radio]:hover:not(:checked):not(:disabled){background:var(--color-control-bg-hover)}
input[type=checkbox]:checked{
  background:var(--color-control-bg-selected);
  border-color:var(--color-control-border-selected)}
/* 체크 표시 — 아이콘 파일 없이 두 선으로 그린다 */
input[type=checkbox]:checked::after{
  content:"";position:absolute;left:5px;top:1px;width:5px;height:10px;
  border:solid var(--color-control-indicator-selected);
  border-width:0 var(--border-width-2) var(--border-width-2) 0;
  transform:rotate(45deg)}
input[type=radio]:checked{border-color:var(--color-control-border-selected)}
input[type=radio]:checked::after{
  content:"";position:absolute;left:3px;top:3px;
  width:var(--spacing-10);height:var(--spacing-10);border-radius:var(--radius-full);
  background:var(--color-control-indicator-selected-alt)}
input[type=checkbox]:disabled,input[type=radio]:disabled{
  background:var(--color-control-bg-disabled);
  border-color:var(--color-control-border-disabled);cursor:default}

/* ── Chip (S-1 코어) ───────────────────────────────────────
   거르개(고르는 것)는 Line, 카드 안 이름표는 Solid. 둘 다 SM(28). */
.s1-chip,.chip{
  display:inline-flex;align-items:center;gap:var(--spacing-4);
  box-sizing:border-box;height:var(--sizing-28);padding:0 var(--spacing-16);
  border-radius:var(--radius-full);
  border:var(--border-width-1) solid var(--color-chip-line-border-default);
  background:var(--color-chip-line-bg-default);
  color:var(--color-chip-line-label-default);
  font-family:inherit;font-size:var(--font-size-12);font-weight:var(--font-weight-medium);
  line-height:1;white-space:nowrap;text-decoration:none;cursor:pointer;transition:all .15s}
.s1-chip:hover,.chip:hover{background:var(--color-chip-line-bg-hover)}
.s1-chip.is-selected,.chip.on{
  background:var(--color-chip-line-bg-selected);
  border-color:var(--color-chip-line-border-selected);
  color:var(--color-chip-line-label-selected)}
.s1-chip--solid,.tag{
  display:inline-flex;align-items:center;box-sizing:border-box;
  height:var(--sizing-28);padding:0 var(--spacing-16);border-radius:var(--radius-full);
  border:var(--border-width-1) solid var(--chip-solid-default-border);
  background:var(--chip-solid-default-bg);
  color:var(--chip-solid-default-text);
  font-size:var(--font-size-12);font-weight:var(--font-weight-medium);
  line-height:1;white-space:nowrap;cursor:default}

/* ── Multi Toggle (S-1 코어) ───────────────────────────────
   붙은 칸. 바깥쪽 모서리만 4. 고른 칸은 파랑으로 채운다.
   크기는 **SM**(34·안쪽 8·최소폭 56) — 옆에 서는 단추가 XSM(34)이라 눈높이를 맞춘다. */
.s1-mt,.cv-segments{display:inline-flex;align-items:center;gap:0;
  background:none;border:0;border-radius:0;padding:0}
.s1-mt>button,.cv-tools .cv-segments button{
  box-sizing:border-box;height:var(--sizing-34);min-width:56px;
  padding:0 var(--spacing-8);border-radius:0;
  border:var(--border-width-1) solid var(--color-button-border-secondary--default);
  background:var(--color-button-bg-secondary--default);
  color:var(--color-button-label-secondary--default);
  font-family:inherit;font-size:var(--font-size-14);font-weight:var(--font-weight-medium);
  line-height:1;cursor:pointer}
.s1-mt>button+button,.cv-tools .cv-segments button+button{margin-left:calc(-1 * var(--border-width-1))}
.s1-mt>button:first-child,.cv-tools .cv-segments button:first-child{
  border-top-left-radius:var(--radius-4);border-bottom-left-radius:var(--radius-4)}
.s1-mt>button:last-child,.cv-tools .cv-segments button:last-child{
  border-top-right-radius:var(--radius-4);border-bottom-right-radius:var(--radius-4)}
.s1-mt>button[aria-pressed=true],.cv-tools .cv-segments button[aria-pressed=true]{
  background:var(--color-button-bg-primary--default);
  border-color:var(--color-button-border-primary--default);
  color:var(--color-button-label-primary--default);
  box-shadow:none;position:relative;z-index:1}

/* ── Pagination (S-1 코어) ─────────────────────────────────
   앞·뒤 화살표 28×28, 숫자는 테두리 없이. */
.s1-pg,.page-nav{display:inline-flex;align-items:center;gap:var(--spacing-8)}
.s1-pg-arrow,.page-step{
  display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;
  height:var(--sizing-28);min-width:var(--sizing-28);padding:0 var(--spacing-8);
  border:var(--border-width-1) solid var(--color-pagination-control-border-default);
  border-radius:var(--radius-control-xs);
  background:var(--color-pagination-control-bg-default);
  color:var(--color-pagination-control-icon-default);
  font-family:inherit;font-size:var(--font-size-14);font-weight:var(--font-weight-medium);
  line-height:1;text-decoration:none;cursor:pointer}
.s1-pg-arrow:hover,.page-step:hover{background:var(--color-pagination-control-bg-hover)}
.s1-pg-arrow.disabled,.page-step.disabled{
  background:var(--color-pagination-control-bg-disabled);
  border-color:var(--color-pagination-control-border-disabled);
  color:var(--color-pagination-control-icon-disabled);opacity:1;cursor:default}
.s1-pg-num,.page-pos{
  display:inline-flex;align-items:center;justify-content:center;
  height:var(--sizing-28);min-width:var(--sizing-28);
  color:var(--color-pagination-number-selected);
  font-size:var(--font-size-14);font-weight:var(--font-weight-medium);letter-spacing:-.028em}

/* ── Modal (S-1 코어) ──────────────────────────────────────
   모서리 8 · 위아래 20 · 흰 바탕. 딤은 --color-overlay. */
dialog,.s1-modal{
  border:var(--border-width-1) solid var(--color-modal-panel-border);
  border-radius:var(--radius-8);
  padding:var(--spacing-20) 0;
  background:var(--color-surface-default);
  color:var(--color-text-primary);
  font-size:var(--font-size-14)}
/* 좌우 여백은 판이 아니라 **안쪽 덩어리**가 가진다(정본 Modal Content 와 같은 모양). */
.s1-modal-inset{padding-left:var(--spacing-20);padding-right:var(--spacing-20)}
"""
