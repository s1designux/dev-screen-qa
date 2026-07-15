-- MVP0 검수 데이터 모델 (CLAUDE.md 6번)
-- 원본은 이 DB다. HTML/JSON은 이 데이터를 렌더링한 출력물일 뿐이다.
-- 참조 무결성은 UUID가, 사람이 읽는 라벨은 human_key가 담당한다 (CLAUDE.md 7번).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project (
    uuid  TEXT PRIMARY KEY,
    name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screen (
    uuid        TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES project(uuid),
    human_key   TEXT NOT NULL,          -- 예: CV-WEB-012
    name        TEXT,
    platform    TEXT,                   -- web / mobile-web / android / ios
    dev_keys    TEXT,                   -- JSON 배열: ["/monitoring/live"]
    states      TEXT,                   -- JSON 배열: ["default","empty"]
    variants    TEXT                    -- JSON 배열: ["desktop-1440"]
);

CREATE TABLE IF NOT EXISTS element_mapping (
    screen_uuid     TEXT NOT NULL REFERENCES screen(uuid),
    design_node_id  TEXT,               -- 디자인 노드 id (하이픈→콜론 변환된 값)
    dev_element_key TEXT                -- 개발 요소 키
);

CREATE TABLE IF NOT EXISTS inspection_run (
    uuid        TEXT PRIMARY KEY,
    screen_id   TEXT NOT NULL REFERENCES screen(uuid),
    round       INTEGER NOT NULL,       -- 1 / 2 / 3
    inspector   TEXT,
    created_at  TEXT,
    pass_fail   TEXT                    -- pass / fail
);

CREATE TABLE IF NOT EXISTS inspection_issue (
    uuid                TEXT PRIMARY KEY,
    screen_id           TEXT NOT NULL REFERENCES screen(uuid),
    run_id              TEXT REFERENCES inspection_run(uuid),  -- 최초 발견 회차
    logical_element_key TEXT,
    box_x    INTEGER, box_y INTEGER, box_w INTEGER, box_h INTEGER,
    category            TEXT,
    expected            TEXT,
    actual              TEXT,
    description         TEXT,
    severity            TEXT,           -- minor / major / critical
    status              TEXT NOT NULL,  -- constants.STATUS_ALL 중 하나 (현재 상태)
    found_round         INTEGER,
    resolved_round      INTEGER,        -- 해결된 회차 (미해결이면 NULL)
    dedup_key           TEXT UNIQUE,    -- {화면}|{요소}|{규칙}|{속성} : 차수 간 동일 오류 연결 키
    properties          TEXT            -- JSON 배열: ["높이","배경색"] (핀 1개 = 요소 1개 + 속성 여러 개)
);

-- append-only. 절대 삭제/수정하지 않는다 (CLAUDE.md 2번-3, 12번).
CREATE TABLE IF NOT EXISTS issue_history (
    uuid         TEXT PRIMARY KEY,
    issue_id     TEXT NOT NULL REFERENCES inspection_issue(uuid),
    from_status  TEXT,                  -- 최초 발견이면 NULL
    to_status    TEXT NOT NULL,
    actor        TEXT,
    at           TEXT,
    note         TEXT,
    seq          INTEGER                -- 이슈 내 순번 (정렬용)
);

-- DesignVersion 스텁 (CLAUDE.md 6번: 필드만 최소화). Figma 참조 3개 값만 담는다.
-- screen 테이블은 손대지 않고, figma 참조는 여기에만 둔다.
CREATE TABLE IF NOT EXISTS design_version (
    uuid                TEXT PRIMARY KEY,
    screen_id           TEXT REFERENCES screen(uuid),
    file_key            TEXT,
    node_id             TEXT,
    dev_capture_node_id TEXT
);

-- MVP0에선 스텁만. MVP1에서 3계층 정책으로 확장 (CLAUDE.md 8번).
CREATE TABLE IF NOT EXISTS comparison_policy (
    scope   TEXT,                       -- system / screen / element
    target  TEXT,
    mode    TEXT                        -- Exact / Style Only / Ignore ...
);
