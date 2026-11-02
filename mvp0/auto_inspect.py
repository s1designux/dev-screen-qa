"""포털 자동 검수(후보 찾기) — 페이지 상세를 열면 저장된 후보가 바로 보이게 한다.

원칙(CLAUDE.md 2번): 자동 검수는 '후보'만 만든다. 확정(지적 등록)은 사람이 누른다.
엔진은 engine/ui.html 한 벌을 그대로 쓴다(복사하지 않는다). 포털은 그 파일을
/engine/ui.html 로 내보내며 맨 끝 시작 줄만 포털용 손잡이(harness)로 바꿔 끼운다.

흐름: 페이지 상세 열림 → (그 차수에 결과가 없으면) 브라우저가 숨은 iframe에서 엔진을 돌려
결과를 POST → 저장 → 다시 열면 저장본이 바로 표시. 후보·판정·등록 이력은 지우지 않는다.
"""
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import 자 as 자모듈                                   # 좌표를 바꾸는 셈은 자.py 한 곳에만 둔다
import card_view
import s1
import figma_elements
import figma_reader
import issue_categories
import policy as policymod
import rule_log
import value_candidates
import design_receive
import 설정

ENGINE_UI = Path(__file__).resolve().parents[1] / 'engine' / 'ui.html'


def uploads_dir():
    return Path(설정.자리('포털.그림보관'))


PLUGIN_UI = ENGINE_UI  # (옛 이름) 2026-09-14 피그마 플러그인 폐기 — 엔진 원본은 engine/ui.html 한 벌뿐이다
ENGINE_MARKER = 'if(location.search.indexOf("selftest=1")>=0)runSelfTest();else post({type:"request-selection-status"});'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS design_elements (
 design_id TEXT PRIMARY KEY REFERENCES intake_design(id), fetched_at TEXT NOT NULL, source_version TEXT,
 frame TEXT NOT NULL, elements TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auto_run (
 id TEXT PRIMARY KEY, page_id TEXT NOT NULL REFERENCES inspection_page(uuid), run_id TEXT NOT NULL REFERENCES inspection_run(uuid),
 status TEXT NOT NULL CHECK(status IN ('pending','done','failed')), engine TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, finished_at TEXT, error TEXT NOT NULL DEFAULT '',
 alignment TEXT NOT NULL DEFAULT '', range TEXT NOT NULL DEFAULT '', notices TEXT NOT NULL DEFAULT '[]',
 capture_w INTEGER, capture_h INTEGER, design_id TEXT NOT NULL DEFAULT '',
 source TEXT NOT NULL DEFAULT 'engine', capture_sig TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS auto_range (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES inspection_run(uuid),
 top INTEGER, bottom INTEGER, actor TEXT NOT NULL DEFAULT '', at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS auto_range_no_update BEFORE UPDATE ON auto_range BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS auto_range_no_delete BEFORE DELETE ON auto_range BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TABLE IF NOT EXISTS auto_candidate (
 id TEXT PRIMARY KEY, auto_run_id TEXT NOT NULL REFERENCES auto_run(id), no INTEGER NOT NULL,
 kind TEXT NOT NULL, label TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', confidence INTEGER,
 status TEXT NOT NULL CHECK(status IN ('open','excluded','variable')), engine_status TEXT NOT NULL,
 policy TEXT NOT NULL DEFAULT '', box_x REAL, box_y REAL, box_w REAL, box_h REAL,
 design_box TEXT NOT NULL DEFAULT '', design_node_ids TEXT NOT NULL DEFAULT '[]', design_values TEXT NOT NULL DEFAULT '',
 issue_id TEXT REFERENCES inspection_issue(uuid)
);
CREATE TABLE IF NOT EXISTS auto_candidate_event (
 id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES auto_candidate(id),
 from_status TEXT NOT NULL, to_status TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '', at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS auto_candidate_event_no_update BEFORE UPDATE ON auto_candidate_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS auto_candidate_event_no_delete BEFORE DELETE ON auto_candidate_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
'''

STATUS_LABEL = {'open': '수정필요', 'excluded': '제외', 'variable': '가변 글자·요소'}
ENGINE_STATUS = {'confirmed': 'open', 'excluded': 'excluded', 'variable': 'variable'}
# 후보 종류 → 포털 이슈 분류(issue_categories.ALIASES 키)
KIND_CATEGORY = {'text': 'text', 'fixed': 'text', 'variable': 'text', 'missing': 'missing', 'area': 'mixed',
                 'position': 'position', 'icon': 'icon', 'image': 'image', 'shape': 'size', 'spacing': 'spacing'}

# 갈래는 **카드에 적힌 말**을 따른다. 요소 종류로 나누면 같은 말이 서로 다른 갈래로 흩어진다.
# (예: '디자인에 없는 요소'는 요소를 짚었든 자리로만 짚었든 '요소 추가·누락'이다.)
LABEL_CATEGORY = [
    ('디자인에 없는 요소', 'structure'),
    ('디자인에 있는 요소', 'structure'),
    ('아이콘 또는 이미지', 'icon'),
    ('색상이 다르게', 'color'),
    ('요소의 모양 또는 크기', 'shape'),
    ('요소의 위치 또는 정렬', 'position'),
    ('화면 맨 위 여백', 'position'),
    ('글자', 'text'),
    ('줄바꿈 또는 말줄임', 'text'),
    ('폰트 모양', 'text'),
]


def candidate_category(k):
    label = str(k['label'] or '')
    for prefix, cat in LABEL_CATEGORY:
        if label.startswith(prefix):
            return cat
    return KIND_CATEGORY.get(k['kind'], 'other')


def uid():
    return uuid.uuid4().hex


def migrate(c):
    """(호환용) 같은 연결 안에서는 외래키 검사를 끌 수 없어 표를 고칠 수 없다. Store.init()이 repair(경로)를 부른다."""
    return


def _table_sql(name):
    m = re.search(r'CREATE TABLE IF NOT EXISTS ' + name + r' \((.*?)\n\);', SCHEMA, re.S)
    return m.group(1)


def repair(database):
    """옛 모양의 자동 검수 표를 지금 모양으로 다시 세운다. 행은 하나도 버리지 않는다.
    - auto_run: design_id·source가 없거나 (run_id, design_id) 유일 제약이 남아 있으면(검수 범위를 바꿔 다시 돌리면 회차가 여러 개) 다시 세운다.
    - auto_candidate / auto_candidate_event: 참조가 이름 바뀐 옛 표(auto_run_v1 등)를 가리키면 다시 세운다.
    - 이름 바꾸다 남은 auto_run_v0/v1, auto_candidate_v0의 행은 합치고 표는 지운다.
    외래키 검사를 끈 별도 연결에서 한다(같은 연결·트랜잭션 안에서는 끌 수 없어 참조가 꼬였다)."""
    conn = sqlite3.connect(str(database))
    conn.execute('PRAGMA foreign_keys=OFF')
    conn.execute('PRAGMA legacy_alter_table=ON')  # 이름을 바꿀 때 다른 표의 참조를 건드리지 않는다
    try:
        def names():
            return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def sql_of(n):
            r = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (n,)).fetchone()
            return r[0] if r else ''
        def cols(n):
            return [r[1] for r in conn.execute(f'PRAGMA table_info("{n}")')]
        def rebuild(table):
            conn.execute(f'CREATE TABLE "{table}__new" ({_table_sql(table)})')
            shared = [c for c in cols(table) if c in cols(table + '__new')]
            conn.execute(f'INSERT INTO "{table}__new"({",".join(shared)}) SELECT {",".join(shared)} FROM "{table}"')
            conn.execute(f'DROP TABLE "{table}"')
            conn.execute(f'ALTER TABLE "{table}__new" RENAME TO "{table}"')
        def merge(into, leftover):
            if leftover not in names():
                return
            shared = [c for c in cols(leftover) if c in cols(into)]
            conn.execute(f'INSERT INTO "{into}"({",".join(shared)}) SELECT {",".join(shared)} FROM "{leftover}" WHERE id NOT IN (SELECT id FROM "{into}")')
            conn.execute(f'DROP TABLE "{leftover}"')
        with conn:
            conn.executescript(SCHEMA)  # 없는 표·트리거를 만든다(있는 것은 그대로)
            for t in ('auto_run__new', 'auto_candidate__new', 'auto_candidate_event__new'):
                if t in names():
                    conn.execute(f'DROP TABLE "{t}"')  # 전에 고치다 만 자취
            if 'design_id' not in cols('auto_run') or 'source' not in cols('auto_run') or 'capture_sig' not in cols('auto_run') or 'UNIQUE(' in sql_of('auto_run'):
                rebuild('auto_run')
            merge('auto_run', 'auto_run_v1')
            merge('auto_run', 'auto_run_v0')
            if not re.search(r'REFERENCES\s+"?auto_run"?\s*\(id\)', sql_of('auto_candidate')):
                rebuild('auto_candidate')
            merge('auto_candidate', 'auto_candidate_v0')
            if not re.search(r'REFERENCES\s+"?auto_candidate"?\s*\(id\)', sql_of('auto_candidate_event')):
                rebuild('auto_candidate_event')
            conn.executescript(SCHEMA)  # 다시 세운 표의 트리거
    finally:
        conn.close()


_CAPTURE_SIG = {}


def capture_sig(run):
    """그 차수 개발 화면 그림의 지문. 그림을 바꾸면 값이 달라진다.
    파일 이름만으로는 모자란다 — 포털에서 올리는 그림은 이름이 늘 같고 내용만 바뀐다."""
    name = (run['dev_img'] if run else None) or ''
    if not name:
        return ''
    try:
        f = uploads_dir() / name
        st = f.stat()
    except OSError:
        return ''
    key = (name, st.st_size, st.st_mtime_ns)
    지문 = _CAPTURE_SIG.get(key)      # 여럿이 동시에 부르면 옆 요청이 표를 비울 수 있다 — 꺼낸 값으로 답한다
    if 지문 is None:
        try:
            지문 = hashlib.sha1(f.read_bytes()).hexdigest()[:12]
        except OSError:
            return ''
        if len(_CAPTURE_SIG) > 200:
            _CAPTURE_SIG.clear()
        _CAPTURE_SIG[key] = 지문
    return 지문


def _stale(r, rev, sig):
    """저장된 회차가 지금 재료와 어긋나는가 — 검수 규칙이 바뀌었거나 개발 화면 그림이 바뀌었으면 참."""
    if rev and (r['engine'] or '') != rev:
        return True
    try:
        saved = r['capture_sig']
    except (IndexError, KeyError):
        return False
    return bool(sig) and (saved or '') != sig


def now():
    return datetime.now().isoformat(timespec='seconds')


def engine_html():
    """플러그인 ui.html + 포털용 손잡이. 파일을 복사하지 않고 매 요청마다 읽는다(규칙을 고치면 바로 반영)."""
    src = PLUGIN_UI.read_text(encoding='utf-8')
    if ENGINE_MARKER not in src:
        raise RuntimeError('검수기 시작 줄을 찾지 못했습니다(engine/ui.html).')
    return src.replace(ENGINE_MARKER, HARNESS_JS, 1)


_ENGINE_REV = {}
_PICTURE_REV = ''     # PICTURE_JS 가 정해진 뒤 채운다


def engine_rev(design=None):
    """지금 검수 규칙(엔진 파일)의 지문. 파일이 바뀌면 값이 달라진다.
    그림으로 넣은 시안(design_receive.PASTED)은 그림끼리 견주기 규칙의 지문을 덧붙인다 —
    그 규칙을 고치면 그 페이지들만 다시 돈다(부품 검수 페이지는 그대로)."""
    if design is not None and design['provider'] == design_receive.PASTED:
        return engine_rev() + ':p' + _PICTURE_REV
    try:
        stamp = PLUGIN_UI.stat().st_mtime_ns
    except OSError:
        return ''
    if _ENGINE_REV.get('stamp') != stamp:
        try:
            _ENGINE_REV.update(stamp=stamp, rev=hashlib.sha1(PLUGIN_UI.read_bytes()).hexdigest()[:12])
        except OSError:
            return ''
    return _ENGINE_REV.get('rev', '')


# ── 그림끼리 견주기 (river 확정 2026-10-30, C안) ───────────────────────────
# 시안을 그림으로만 붙여 넣으면 부품 정보가 없어 검수기(engine/ui.html)가 견줄 것이 없다.
# 그때는 두 그림을 같은 폭으로 맞춰 세로 자리만 찾고, 색이 눈에 띄게 다른 구역을 **후보**로 짚는다.
# 무엇이 다른지(글자·색·크기)는 가리지 않는다 — 사람이 보고 정한다(2번-2).
# 검수 규칙(엔진 파일)은 건드리지 않는다. 포털 손잡이에만 둔다.
PICTURE_NOTE = '시안을 그림으로 넣어 그림끼리 견줬습니다. 피그마 플러그인으로 보내면 글자·색·크기를 나눠 봅니다.'
PICTURE_JS = r"""

// 글자 줄을 원래 크기로 한 줄씩 견준다. 돌려주는 것: [{seg:{x0,x1,y0,y1}(시안 px, 본 자리), cand:{...}|null}]
function __portalTextLines(D,C,W,H,Ch,cell,gw,gh,dg,best,cTop,cBot){
  function gray(img,w,h){var c=canvasFor(w,h),g=c.getContext("2d");g.fillStyle="#fff";g.fillRect(0,0,w,h);g.drawImage(img,0,0,w,h);
    var d=g.getImageData(0,0,w,h).data,o=new Uint8Array(w*h);for(var i=0;i<w*h;i++)o[i]=(d[i*4]*299+d[i*4+1]*587+d[i*4+2]*114)/1000;return o;}
  var dG=gray(D,W,H),cG=gray(C,W,Ch),out=[];
  // 줄 찾기: 칸 줄마다 그 줄에서 가장 흔한 색과 크게 다른 칸이 있으면 글자가 있는 줄
  var rowInk=new Uint8Array(gh);
  for(var r=0;r<gh;r++){var cnt={},m=-1,mn=0;for(var x=0;x<gw;x++){var i=(r*gw+x)*4,key=(dg[i]>>4)+","+(dg[i+1]>>4)+","+(dg[i+2]>>4);cnt[key]=(cnt[key]||0)+1;if(cnt[key]>mn){mn=cnt[key];m=i;}}
    for(var x=0;x<gw;x++){var i=(r*gw+x)*4;if(Math.max(Math.abs(dg[i]-dg[m]),Math.abs(dg[i+1]-dg[m+1]),Math.abs(dg[i+2]-dg[m+2]))>40){rowInk[r]=1;break;}}}
  var bands=[];for(var r=0;r<gh;r++){if(!rowInk[r])continue;var r0=r;while(r+1<gh&&rowInk[r+1])r++;if(r-r0+1>=2&&r-r0+1<=10)bands.push([r0,r]);}
  function at(G,w,h,x,y){return(x<0||y<0||x>=w||y>=h)?-1:G[y*w+x];}
  bands.forEach(function(bd){
    var Y0=Math.max(0,bd[0]*cell-2),Y1=Math.min(H-1,(bd[1]+1)*cell+1),lh=Y1-Y0+1;
    // 줄 안의 덩어리: 바탕과 다른 세로줄이 이어진 곳(줄 높이만큼 비면 끊는다)
    var bgc={},bg=0,bn=0;for(var x=0;x<W;x++){var v=dG[Y0*W+x]>>3;bgc[v]=(bgc[v]||0)+1;if(bgc[v]>bn){bn=bgc[v];bg=dG[Y0*W+x];}}
    var ink=new Uint8Array(W);for(var x=0;x<W;x++)for(var y=Y0;y<=Y1;y++)if(Math.abs(dG[y*W+x]-bg)>60){ink[x]=1;break;}
    var runs=[],a=-1,gap=0;for(var x=0;x<=W;x++){if(x<W&&ink[x]){if(a<0)a=x;gap=0;b=x;}else if(a>=0&&(++gap>lh||x===W)){runs.push([a,b]);a=-1;gap=0;}}
    runs.forEach(function(rn){var da=rn[0],db=rn[1];if(db-da<lh)return;
      // 덩어리 둘레가 한 색이어야 글자 줄로 본다(그림·표 칸 안은 칸 비교에 맡긴다)
      var same=0,all=0;for(var x=Math.max(0,da-4);x<=Math.min(W-1,db+4);x++){[Y0,Y1].forEach(function(y){all++;if(Math.abs(dG[y*W+x]-bg)<=12)same++;});}
      if(same<all*0.9)return;
      // 개발 쪽 같은 줄: 세로는 전체 자리(best) 언저리 ±칸 안에서 가장 닮은 곳
      // 줄 높이 두 배까지 위아래로 찾는다 — 화면 전체 자리와 따로 놀며 옮겨진 글자를 '빠짐'으로 잘못 읽지 않게(검증 2026-10-30)
      //    가로로 밀려도(가운데 맞춤) 흔들리지 않게 줄마다 잉크 양(가로 넓게)으로 견준다.
      var oy0=-best*cell,bestDy=oy0,bsc=1e18,reach=Math.max(cell,lh*2);
      var wl=Math.max(0,da-Math.round((db-da)*0.6)),wh=Math.min(W-1,db+Math.round((db-da)*0.6));
      var pd=[];for(var y=Y0;y<=Y1;y++){var n=0;for(var x=wl;x<=wh;x++)if(Math.abs(dG[y*W+x]-bg)>60)n++;pd.push(n);}
      var tot=pd.reduce(function(a,b){return a+b;},0)||1;
      for(var dy=oy0-reach;dy<=oy0+reach;dy++){var sc=0;
        for(var y=Y0;y<=Y1;y++){var yy=y+dy,n=0;if(yy<0||yy>=Ch){sc+=pd[y-Y0];continue;}var cb0=cG[yy*W+Math.max(0,wl-4)];
          for(var x=wl;x<=wh;x++)if(Math.abs(cG[yy*W+x]-bg)>60)n++;sc+=Math.abs(n-pd[y-Y0]);}
        sc=sc/tot+Math.abs(dy-oy0)*0.01;if(sc<bsc){bsc=sc;bestDy=dy;}}
      var moved=Math.abs(bestDy-oy0)>cell+1;
      if(Y0+bestDy<cTop||Y1+bestDy>=cBot)return;
      var cbg=at(cG,W,Ch,Math.max(0,da-4),Y0+bestDy);if(cbg<0)return;
      var lo=Math.max(0,da-Math.round((db-da)*0.6)),hi=Math.min(W-1,db+Math.round((db-da)*0.6));
      var cink=new Uint8Array(W);for(var x=lo;x<=hi;x++)for(var y=Y0;y<=Y1;y++){var c=at(cG,W,Ch,x,y+bestDy);if(c>=0&&Math.abs(c-cbg)>60){cink[x]=1;break;}}
      // 개발 덩어리: 시안 덩어리와 겹치는 잉크에서 시작해 줄 높이만큼 비기 전까지 넓힌다
      var ca=-1,cb=-1;for(var x=da;x<=db;x++)if(cink[x]){if(ca<0)ca=x;cb=x;}
      if(ca<0){out.push({seg:{x0:da,x1:db+1,y0:Y0,y1:Y1+1},cand:mk(da,db,Y0,Y1,null,null,"gone")});return;}
      var g2=0;for(var x=cb+1;x<=hi;x++){if(cink[x]){cb=x;g2=0;}else if(++g2>lh)break;}
      g2=0;for(var x=ca-1;x>=lo;x--){if(cink[x]){ca=x;g2=0;}else if(++g2>lh)break;}
      // 한 세로줄이 다른가: 둘레 1px 안에서 가장 닮은 값과도 크게 다른 점이 둘 이상(양쪽으로 본다)
      function colBad(xd,sx){var n=0;for(var y=Y0;y<=Y1;y++){var dv=dG[y*W+xd],m1=255,m2=255;
          for(var oy=-1;oy<=1;oy++)for(var ox=-1;ox<=1;ox++){var c=at(cG,W,Ch,xd+sx+ox,y+bestDy+oy);if(c>=0)m1=Math.min(m1,Math.abs(dv-c));
            var e=at(dG,W,H,xd+ox,y+oy);var cv=at(cG,W,Ch,xd+sx,y+bestDy);if(e>=0&&cv>=0)m2=Math.min(m2,Math.abs(e-cv));}
          if(Math.max(m1,m2)>90&&++n>=2)return true;}return false;}
      // 그리는 프로그램이 달라 글자 사이가 조금씩 벌어지면(한 줄에 몇 px) 그만큼은 따라간다 — 줄 높이만큼 지나야 1px 더 옮길 수 있다
      function scan(from,to,step,s0){var s=s0,last=from;for(var x=from;step>0?x<=to:x>=to;x+=step){
        if(!colBad(x,s))continue;
        if(Math.abs(x-last)>=lh){var fix=null;[1,-1,2,-2].some(function(o){if(!colBad(x,s+o)&&!colBad(x+step,s+o)){fix=o;return true;}return false;});
          if(fix!==null){s+=fix;last=x;continue;}}
        var nx=x+step;if((step>0?nx<=to:nx>=to)&&colBad(nx,s))return x;}
        return null;}
      var sL=ca-da,sR=cb-db,p=scan(da,db,1,sL),q=scan(db,da,-1,sR);
      var dlen=(cb-ca)-(db-da),dl0=db-da+1;
      // 글자 높이(잉크가 있는 줄 수) — 높이가 다르면 빠짐·더해짐이 아니라 크기·굵기가 다른 것이다(검증 2026-10-30)
      function inkH(G,w,h,x0,x1,oy,b0){var top=-1,bot=-1;for(var y=Y0-2;y<=Y1+2;y++){var yy=y+oy;if(yy<0||yy>=h)continue;
        for(var x=x0;x<=x1;x+=1)if(Math.abs(G[yy*w+x]-b0)>60){if(top<0)top=y;bot=y;break;}}return top<0?0:bot-top+1;}
      var hd=inkH(dG,W,H,da,db,0,bg),hc=inkH(cG,W,Ch,ca,cb,bestDy,cbg);
      var small=Math.max(4,Math.round(dl0*0.03));
      if(p==null&&q==null&&Math.abs(dlen)<small){out.push({seg:{x0:da,x1:db+1,y0:Y0,y1:Y1+1},cand:(moved||(Math.abs(sL)>2&&Math.abs(sR)>2&&sL*sR>0))?mk(da,db,Y0,Y1,{ca:ca,cb:cb,dy:bestDy,sL:sL,sR:sR,x0:da,x1:db,shiftY:moved?bestDy-oy0:0,shiftX:Math.round((sL+sR)/2)},dlen,"moved"):null});return;}
      if(p==null)p=q;if(q==null)q=p;
      // 길이가 같고 앞뒤가 같은 만큼 옮겨졌으면 낱말이 바뀐 것이 아니라 자리가 옮겨진 것이다(그리는 방식 차이로 조금 어긋날 뿐)
      if(Math.abs(dlen)<small&&Math.abs(sL)>2&&Math.abs(sR)>2&&sL*sR>0){out.push({seg:{x0:Math.min(da,ca),x1:Math.max(db,cb)+1,y0:Y0,y1:Y1+1},
        cand:mk(da,db,Y0,Y1,{ca:ca,cb:cb,dy:bestDy,sL:sL,sR:sR,x0:da,x1:db,shiftY:moved?bestDy-oy0:0,shiftX:Math.round((sL+sR)/2)},dlen,"moved")});return;}
      var x0=Math.min(p,q),x1=Math.max(p,q);
      out.push({seg:{x0:Math.min(da,ca),x1:Math.max(db,cb)+1,y0:Y0,y1:Y1+1},cand:mk(da,db,Y0,Y1,{ca:ca,cb:cb,dy:bestDy,sL:sL,sR:sR,x0:x0,x1:x1,hd:hd,hc:hc},dlen,"diff")});
    });
  });
  function mk(da,db,Y0,Y1,m,dlen,how){
    var dl=db-da+1,label,detail,vals,bx0,bx1,rx0,rx1,dy=m?m.dy:-best*cell;
    var type="other";
    if(how==="moved"){var dir=[];if(m.shiftY)dir.push(Math.abs(m.shiftY)+"px "+(m.shiftY>0?"아래":"위"));if(Math.abs(m.shiftX)>2)dir.push(Math.abs(m.shiftX)+"px "+(m.shiftX>0?"오른쪽":"왼쪽"));
      label="글자 자리가 다른 곳";detail="글자는 같은데 시안보다 "+dir.join(" · ")+"에 있습니다.";vals=(m.shiftY?"세로 "+(m.shiftY>0?"+":"")+m.shiftY+"px ":"")+(Math.abs(m.shiftX)>2?"가로 "+(m.shiftX>0?"+":"")+m.shiftX+"px":"");bx0=da;bx1=db;rx0=m.ca;rx1=m.cb;}
    else if(how==="gone"){label="글자가 보이지 않는 곳";detail="시안의 이 줄이 개발 화면의 같은 자리에서 보이지 않습니다. 빠졌거나, 가려졌거나, 다른 자리로 옮겨졌을 수 있습니다.";vals="줄 길이 "+dl+"px → 0px";bx0=da;bx1=db;rx0=da;rx1=db;}
    else{var cl=m.cb-m.ca+1,whole=(m.x1-m.x0)>=dl*0.8;bx0=m.x0;bx1=m.x1;
      rx0=Math.min(m.x0+m.sL,m.x1+m.sR);rx1=Math.max(m.x0+m.sL,m.x1+m.sR);
      vals="줄 길이 "+dl+"px → "+cl+"px";
      var sm=3;   // 어긋난 자리를 찾은 줄이라 3px 만 짧아도(마침표 하나) 빠짐으로 본다
      var span=m.x1-m.x0+1,lhh=Y1-Y0+1;
      if(m.hd&&m.hc&&Math.abs(m.hc-m.hd)>=Math.max(2,m.hd*0.08)){label="글자 크기가 다른 곳";detail="글자 높이가 시안 "+m.hd+"px → 개발 "+m.hc+"px 로 다릅니다. 글꼴 크기나 굵기가 다를 수 있습니다.";
        vals="글자 높이 "+m.hd+"px → "+m.hc+"px · 줄 길이 "+dl+"px → "+cl+"px";bx0=da;bx1=db;rx0=m.ca;rx1=m.cb;}
      else if(span>Math.abs(dlen)+lhh*3&&Math.abs(dlen)<Math.max(4,dl*0.015)){label="글자가 다른 곳";type="soft";
        detail="줄 길이는 거의 같고 넓은 구간이 조금씩 다릅니다. 글자가 바뀌었거나, 같은 글자를 그리는 방식만 다를 수 있습니다.";}
      // 빠짐·더해짐이라 말하려면 그 자리 말고는 앞뒤가 맞아야 한다(맞은 부분이 짧은 쪽 줄의 6할 이상) —
      // 문장이 통째로 바뀌어 길이도 달라진 줄을 '빠짐'으로 말하지 않게(검증 2026-10-30)
      else if(Math.abs(dlen)>=sm&&(m.x0-da)+(db-m.x1)<Math.min(dl,cl)*0.6){label="글자가 다른 곳";bx0=da;bx1=db;rx0=m.ca;rx1=m.cb;
        detail="줄 길이도 다르고 글자도 대부분 다릅니다. 다른 문장으로 바뀌었을 수 있습니다.";}
      else if(whole&&Math.abs(dlen)<dl*0.3){label="글자가 다른 곳";detail="줄 전체가 시안과 다릅니다. 다른 글자이거나 글꼴·굵기·크기가 다를 수 있습니다.";bx0=da;bx1=db;rx0=m.ca;rx1=m.cb;}
      else if(dlen<=-sm){bx1=Math.max(bx1,bx0-dlen-1);  /* 빠진 자리는 적어도 줄어든 길이만큼 짚는다 */ label="글자가 빠진 곳";type="del";detail="시안의 짚은 글자(약 "+(bx1-bx0+1)+"px)가 개발 화면에 없어 줄이 "+(-dlen)+"px 짧습니다. 개발 화면에서는 그 자리가 당겨져 붙었습니다.";}
      else if(dlen>=sm){label="글자가 더해진 곳";type="add";detail="개발 화면의 짚은 자리에 시안에 없는 글자가 있어 줄이 "+dlen+"px 깁니다.";}
      else{label="글자가 다른 곳";detail="줄 길이는 같은데 짚은 자리의 글자가 시안과 다릅니다. 다른 낱말로 바뀌었을 수 있습니다.";}}
    var bw=Math.max(8,bx1-bx0+1),rw=Math.max(8,rx1-rx0+1);
    return{x0:Math.floor(bx0/cell),y0:Math.floor(Y0/cell),x1:Math.floor(bx1/cell),y1:Math.floor(Y1/cell),cnt:999,
      meta:{type:type,hd:m&&m.hd||0,da:da,db:db,Y0:Y0,Y1:Y1,dl:dl,cl:m?m.cb-m.ca+1:0,ca:m?m.ca:da,cb:m?m.cb:db,bx0:m?m.x0:da,rx0:m?m.x0+m.sL:da,dy:dy},
      ready:{status:"confirmed",kind:"text",label:label,detail:detail,confidence:80,policy:{source:"picture",variable:false,reason:""},
        rawBox:{x:Math.round(rx0*C.width/W),y:Math.round((Y0+dy)*C.width/W),w:Math.round(rw*C.width/W),h:Math.round(Y1-Y0+1)*C.width/W},
        designBox:{x:bx0,y:Y0,w:bw,h:Y1-Y0+1},designNodeIds:[],designValues:vals}};}
  // 한 문단에서 이어진 줄들이 함께 달라졌으면 하나로 — 낱말이 빠지거나 더해지면 줄바꿈이 밀려 아래 줄까지 달라진다.
  // 이어진 줄(왼쪽 끝이 같고 줄 높이 안으로 붙음) 가운데 **빠짐·더해짐이 하나라도 있을 때만** 묶는다 —
  // 그리는 방식만 달라 흐릿하게 다른 줄끼리는 문단으로 묶지 않는다(검증 2026-10-30).
  out.sort(function(a,b){return a.seg.y0-b.seg.y0;});
  for(var i=0;i<out.length;i++){var A=out[i];if(!A.cand||!A.cand.meta)continue;
    var grp=[i],last=A,a=A.cand.meta,lh=a.Y1-a.Y0+1;
    for(var j=i+1;j<out.length;j++){var B=out[j];if(B.seg.y0-last.seg.y1>lh)break;
      if(!B.cand||!B.cand.meta||Math.abs(B.cand.meta.da-a.da)>4)continue;grp.push(j);last=B;}
    var lines=grp.map(function(g){return out[g].cand.meta;});
    if(lines.length<2||!lines.some(function(z){return z.type==="del"||z.type==="add";}))continue;
    var hs=lines.map(function(z){return z.hd;}).filter(Boolean),wmax=Math.max.apply(null,lines.map(function(z){return z.dl;}));
    if(hs.length&&Math.max.apply(null,hs)>Math.min.apply(null,hs)*1.15+1)continue;
    if(lines.slice(0,-1).some(function(z){return z.dl<wmax*0.85;}))continue;
    var f=lines[0],l=lines[lines.length-1],c=A.cand;
    var right=Math.max.apply(null,lines.map(function(z){return Math.max(z.db,z.cb);}));
    c.x1=Math.floor(right/cell);c.y1=Math.floor(l.Y1/cell);
    c.ready.label="글자 배치가 달라진 문단";
    c.ready.detail="문단에서 글자가 빠지거나 더해져 줄바꿈이 달라졌습니다. 처음 달라진 자리부터 문단 끝까지 짚었습니다.";
    c.ready.designValues="줄 길이 시안 "+lines.map(function(z){return z.dl;}).join("·")+" → 개발 "+lines.map(function(z){return z.cl;}).join("·")+" px";
    c.ready.designBox={x:f.bx0,y:f.Y0,w:Math.max(8,right-f.bx0+1),h:l.Y1-f.Y0+1};
    var kk=C.width/W;c.ready.rawBox={x:Math.round(Math.min(f.rx0,f.ca)*kk),y:Math.round((f.Y0+f.dy)*kk),w:Math.round((right-Math.min(f.rx0,f.ca)+1)*kk),h:Math.round((l.Y1-f.Y0+1)*kk)};
    A.seg={x0:Math.min.apply(null,grp.map(function(g){return out[g].seg.x0;})),x1:Math.max.apply(null,grp.map(function(g){return out[g].seg.x1;})),y0:A.seg.y0,y1:out[grp[grp.length-1]].seg.y1};
    for(var g=grp.length-1;g>0;g--)out.splice(grp[g],1);}
  return out;
}
function __portalPicture(D,C,topTrim,bottomTrim){
  var W=D.width,H=D.height,k=C.width/W,Ch=Math.round(C.height/k);
  var cell=Math.max(4,Math.round(W/240)),gw=Math.ceil(W/cell),gh=Math.ceil(H/cell),gc=Math.max(1,Math.round(Ch/cell));
  function grid(img,w,h){var c=canvasFor(w,h),g=c.getContext("2d");g.imageSmoothingEnabled=true;g.imageSmoothingQuality="high";
    g.fillStyle="#fff";g.fillRect(0,0,w,h);g.drawImage(img,0,0,w,h);return g.getImageData(0,0,w,h).data;}
  var dg=grid(D,gw,gh),cg=grid(C,gw,gc);
  var t0=Math.ceil((topTrim||0)/k/cell),t1=gc-Math.ceil((bottomTrim||0)/k/cell);
  function diff(cr,dr,x){var i=(cr*gw+x)*4,j=(dr*gw+x)*4;
    return Math.max(Math.abs(cg[i]-dg[j]),Math.abs(cg[i+1]-dg[j+1]),Math.abs(cg[i+2]-dg[j+2]));}
  // 세로 자리: 시안 줄 dr 은 개발 줄 dr-ty 에 온다. 화면 전체로 한 번만 찾는다(많이 밀수록 조금씩 깎아 0 근처를 먼저 믿는다).
  // 띠마다 따로 옮기지 않는다 — 다른 곳을 피해 가는 자리가 점수가 좋아 실제 차이를 감춘다(검증 2026-10-30).
  function rowsScore(d0,d1,ty,step){var sum=0,n=0;
    for(var dr=d0;dr<d1;dr+=step){var r=dr-ty;if(r<t0||r>=t1)continue;for(var x=0;x<gw;x+=2){sum+=diff(r,dr,x);n++;}}
    return n?sum/n:1e9;}
  var lim=Math.round(gh*0.1),best=0,bs=1e9;
  for(var ty=-lim;ty<=lim;ty++){var sc=rowsScore(0,gh,ty,2)+Math.abs(ty)*0.05;if(sc<bs){bs=sc;best=ty;}}
  var shift=new Int32Array(gh).fill(best);
  // 어느 자리에 얹어도 크게 다르면(어둡게 덮인 창·다른 상태의 화면) 자리를 믿을 수 없다 — 낱낱이 짚으면 틀린 말을 한다.
  // 화면 전체를 한 곳으로 올리고 사람이 보게 한다. 보통 화면은 15 아래, 덮인 화면은 70 언저리(검증 2026-10-30).
  if(bs>30){var kk=C.width/W;return{candidates:[{no:1,status:"confirmed",kind:"area",label:"화면 전체가 다른 곳",
      detail:"시안과 개발 화면이 크게 달라 자리를 맞추지 못했습니다. 어둡게 덮인 창이 떠 있거나 다른 상태의 화면인지 확인합니다.",
      confidence:90,policy:{source:"picture",variable:false,reason:""},rawBox:{x:0,y:0,w:C.width,h:C.height},
      designBox:{x:0,y:0,w:W,h:H},designNodeIds:[],designValues:""}],notices:[],
    alignment:{mode:"picture",s:kk,tx:0,ty:0,score:Math.round(bs*100)/100,fit:null,rescued:false,thin:true},
    range:{captureTop:0,captureBottom:0,manual:false,manualBottom:false}};}
  // 한두 칸 어긋난 글자 가장자리는 차이로 보지 않는다 — 둘레 한 칸 안에서 가장 닮은 자리와 견준다.
  // 양쪽으로 다 본다: 시안 칸이 개발 둘레에 없거나(빠짐) 개발 칸이 시안 둘레에 없으면(더해짐) 다른 곳이다.
  // 한쪽만 보면 흰 바탕 위의 가는 아이콘이 둘레의 흰 칸과 닮아 묻힌다.
  function px(a,i,b,j){return Math.max(Math.abs(a[i]-b[j]),Math.abs(a[i+1]-b[j+1]),Math.abs(a[i+2]-b[j+2]));}
  function near(dr,x){var r=dr-shift[dr],m1=1e9,m2=1e9,ci=(r*gw+x)*4,di=(dr*gw+x)*4;
    for(var o=-1;o<=1;o++)for(var q=-1;q<=1;q++){var xx=x+q;if(xx<0||xx>=gw)continue;
      var yy=r+o;if(yy>=t0&&yy<t1){var v=px(cg,(yy*gw+xx)*4,dg,di);if(v<m1)m1=v;}
      var zz=dr+o;if(zz>=0&&zz<gh){var w=px(dg,(zz*gw+xx)*4,cg,ci);if(w<m2)m2=w;}}
    return Math.max(m1,m2);}
  var T=28,mask=new Uint8Array(gw*gh),val=new Float32Array(gw*gh),lo=gh,hi=-1;
  for(var dr=0;dr<gh;dr++){var r=dr-shift[dr];if(r<t0||r>=t1)continue;lo=Math.min(lo,dr);hi=Math.max(hi,dr);
    for(var x=0;x<gw;x++){var v=near(dr,x);if(v>T){mask[dr*gw+x]=1;val[dr*gw+x]=v;}}}
  // 이웃 두 칸 안의 다른 칸은 한 구역으로 묶는다
  function comps(m,R,minCnt){var seen=new Uint8Array(gw*gh),out=[];
    for(var i=0;i<gw*gh;i++){if(!m[i]||seen[i])continue;
      var st=[i],x0=gw,y0=gh,x1=-1,y1=-1,cnt=0,tot=0;seen[i]=1;
      while(st.length){var q=st.pop(),qx=q%gw,qy=(q-qx)/gw;cnt++;tot+=val[q];
        if(qx<x0)x0=qx;if(qx>x1)x1=qx;if(qy<y0)y0=qy;if(qy>y1)y1=qy;
        for(var yy=Math.max(0,qy-R);yy<=Math.min(gh-1,qy+R);yy++)for(var xx=Math.max(0,qx-R);xx<=Math.min(gw-1,qx+R);xx++){
          var z=yy*gw+xx;if(m[z]&&!seen[z]){seen[z]=1;st.push(z);}}}
      if(cnt>=minCnt)out.push({x0:x0,y0:y0,x1:x1,y1:y1,cnt:cnt,mean:tot/cnt,parts:1});}
    return out;}
  var boxes=comps(mask,2,1);
  // 줄 띠(rows y0..y1)에서 바탕색과 다른 칸(=글자 잉크)이 있는 세로줄. 바탕은 띠에서 가장 흔한 색이다.
  function dRow(y){return y;}function cRow(y){var r=y-shift[y];return(r>=t0&&r<t1)?r:-1;}
  function inkCols(g,rowOf,y0,y1){var cnt={},bg=-1,bn=0,out=new Uint8Array(gw);
    for(var y=y0;y<=y1;y++){var r=rowOf(y);if(r<0)continue;for(var x=0;x<gw;x++){var i=(r*gw+x)*4,key=(g[i]>>4)+","+(g[i+1]>>4)+","+(g[i+2]>>4);cnt[key]=(cnt[key]||0)+1;if(cnt[key]>bn){bn=cnt[key];bg=i;}}}
    if(bg<0)return null;
    for(var x=0;x<gw;x++)for(var y=y0;y<=y1;y++){var r=rowOf(y);if(r<0)continue;var i=(r*gw+x)*4;
      if(Math.max(Math.abs(g[i]-g[bg]),Math.abs(g[i+1]-g[bg+1]),Math.abs(g[i+2]-g[bg+2]))>40){out[x]=1;break;}}
    return out;}
  // ① 한 줄에서 나온 차이는 하나로 묶는다 — 글자 하나가 빠지면 뒤 글자가 당겨져 조각조각 다르게 보인다(river 2026-10-30).
  //    세로로 반 넘게 겹치고, 둘 사이가 **시안에서 이어진 글자**(줄 높이보다 긴 빈칸이 없음)일 때만 같은 줄로 본다 —
  //    라벨과 값처럼 떨어져 놓인 둘은 묶지 않는다(검증 2026-10-30).
  function sameRun(A,B){var y0=Math.min(A.y0,B.y0),y1=Math.max(A.y1,B.y1),lh=y1-y0+1;if(lh>10)return false;
    var ink=inkCols(dg,dRow,y0,y1);if(!ink)return false;var x0=Math.min(A.x1,B.x1),x1=Math.max(A.x0,B.x0),run=0;
    for(var x=x0+1;x<x1;x++){if(ink[x])run=0;else if(++run>=Math.max(3,lh))return false;}return true;}
  var merged=true;
  while(merged){merged=false;
    for(var i=0;i<boxes.length&&!merged;i++)for(var j=i+1;j<boxes.length&&!merged;j++){var A=boxes[i],B=boxes[j];
      var ov=Math.min(A.y1,B.y1)-Math.max(A.y0,B.y0)+1,hh=Math.min(A.y1-A.y0,B.y1-B.y0)+1;
      if(ov>=hh*0.5&&(Math.max(A.x0,B.x0)<=Math.min(A.x1,B.x1)+1||sameRun(A,B))){
        boxes[i]={x0:Math.min(A.x0,B.x0),y0:Math.min(A.y0,B.y0),x1:Math.max(A.x1,B.x1),y1:Math.max(A.y1,B.y1),
          cnt:A.cnt+B.cnt,mean:(A.mean*A.cnt+B.mean*B.cnt)/(A.cnt+B.cnt),parts:A.parts+B.parts};boxes.splice(j,1);merged=true;}}}
  // 그 줄의 글자 덩어리가 시안과 개발에서 어디서 시작해 어디서 끝나는지(틈 6칸까지는 한 줄)
  function inkEnd(g,rowOf,y0,y1,xs){var ink=inkCols(g,rowOf,y0,y1);if(!ink)return null;
    var a=-1,b=-1;for(var x=xs[0];x<=xs[1];x++)if(ink[x]){if(a<0)a=x;b=x;}
    if(a<0)return null;var gapN=0;for(var x=b+1;x<gw;x++){if(ink[x]){b=x;gapN=0;}else if(++gapN>6)break;}
    gapN=0;for(var x=a-1;x>=0;x--){if(ink[x]){a=x;gapN=0;}else if(++gapN>6)break;}
    return{a:a,b:b};}
  // ② 넓게 한 색으로 칠한 면은 작은 색 차이도 본다 — 글자 테두리 흔들림을 거르는 문턱(28)으로는 버튼 색이 조금 바뀐 것을 놓친다.
  //    둘레 여덟 칸이 모두 같은 색인 칸(양쪽 다)만 보고, 문턱은 6.
  function flat(g,r,x,rows){var i=(r*gw+x)*4;for(var o=-1;o<=1;o++)for(var q=-1;q<=1;q++){var yy=r+o,xx=x+q;
    if(yy<0||yy>=rows||xx<0||xx>=gw)return false;if(px(g,(yy*gw+xx)*4,g,i)>4)return false;}return true;}
  // 면이 자리를 옮긴 것이면 색이 바뀐 것이 아니다 — 둘레(가로 2칸·세로 8칸) 안에 서로의 색이 있으면 뺀다(검증 2026-10-30)
  function moved(dr,r,x){var di=(dr*gw+x)*4,ci=(r*gw+x)*4;
    for(var o=-8;o<=8;o++)for(var q=-2;q<=2;q++){var xx=x+q;if(xx<0||xx>=gw)continue;
      var yy=r+o;if(yy>=0&&yy<gc&&px(cg,(yy*gw+xx)*4,dg,di)<=4)return true;
      var zz=dr+o;if(zz>=0&&zz<gh&&px(dg,(zz*gw+xx)*4,cg,ci)<=4)return true;}
    return false;}
  var fmask=new Uint8Array(gw*gh);
  for(var dr=0;dr<gh;dr++){var r=cRow(dr);if(r<0)continue;
    for(var x=0;x<gw;x++){var di=(dr*gw+x)*4,ci=(r*gw+x)*4;
      if(mask[dr*gw+x]||!flat(dg,dr,x,gh)||!flat(cg,r,x,gc))continue;var v=px(dg,di,cg,ci);if(v>6&&!moved(dr,r,x)){fmask[dr*gw+x]=1;val[dr*gw+x]=v;}}}
  function hex(g,i){return"#"+[g[i],g[i+1],g[i+2]].map(function(v){return("0"+v.toString(16)).slice(-2);}).join("").toUpperCase();}
  var colors=comps(fmask,1,6).map(function(b){var cx=Math.round((b.x0+b.x1)/2),cy=Math.round((b.y0+b.y1)/2);
    // 가운데 칸이 면 밖이면 면 안의 첫 칸으로
    if(!fmask[cy*gw+cx]){outer:for(var y=b.y0;y<=b.y1;y++)for(var x=b.x0;x<=b.x1;x++)if(fmask[y*gw+x]){cx=x;cy=y;break outer;}}
    b.kind="color";b.from=hex(dg,(cy*gw+cx)*4);b.to=hex(cg,(cRow(cy)*gw+cx)*4);
    b.x0=Math.max(0,b.x0-1);b.y0=Math.max(0,b.y0-1);b.x1=Math.min(gw-1,b.x1+1);b.y1=Math.min(gh-1,b.y1+1);return b;});
  boxes=boxes.filter(function(b){return b.cnt>=3||b.parts>1;});
  // ③ 글자 줄은 원래 크기 그대로 한 줄씩 다시 본다(river 2026-10-30) — 칸으로 뭉개 보면 같은 너비로 바뀐 낱말,
  //    마침표 하나, 줄 끝에서 빠진 낱말을 놓친다. 줄의 앞에서부터, 뒤에서부터 각각 맞춰 보며 처음 어긋나는 자리를 찾는다.
  //    앞에서 어긋난 곳(p)~뒤에서 어긋난 곳(q)이 바뀐 자리다 — 왼쪽·가운데·오른쪽 맞춤 모두 같은 셈으로 짚힌다.
  var texts=__portalTextLines(D,C,W,H,Ch,cell,gw,gh,dg,best,t0*cell,t1*cell);
  if(texts.length){
    boxes=boxes.filter(function(b){var X0=b.x0*cell,X1=(b.x1+1)*cell,Y0=b.y0*cell,Y1=(b.y1+1)*cell;
      var area=(X1-X0)*(Y1-Y0),cov=0;
      texts.forEach(function(t){if(!t.seg)return;var ix=Math.min(X1,t.seg.x1)-Math.max(X0,t.seg.x0),iy=Math.min(Y1,t.seg.y1)-Math.max(Y0,t.seg.y0);if(ix>0&&iy>0)cov+=ix*iy;});
      return cov<area*0.5;});
    texts.forEach(function(t){if(t.cand)boxes.push(t.cand);});}
  boxes=boxes.concat(colors);
  boxes.sort(function(a,b){return b.cnt-a.cnt;});var capped=boxes.length>40;boxes=boxes.slice(0,40);
  boxes.sort(function(a,b){return a.y0-b.y0||a.x0-b.x0;});
  var cands=boxes.map(function(b,n){
    if(b.ready){var c=b.ready;c.no=n+1;return c;}
    var dx=b.x0*cell,dy=b.y0*cell,dw=Math.min(W,(b.x1+1)*cell)-dx,dh=Math.min(H,(b.y1+1)*cell)-dy;
    var label="그림이 다른 곳",kind="area",detail="시안과 개발 화면의 그림이 이 구역에서 다릅니다. 무엇이 다른지는 나란히 보기로 확인합니다.",vals="";
    if(b.kind==="color"){kind="shape";label="색상이 다르게 보이는 곳";detail="이 면의 색이 시안과 다릅니다.";vals="시안 "+b.from+" → 개발 "+b.to;}
    return{no:n+1,status:"confirmed",kind:kind,label:label,detail:detail,
      confidence:Math.min(99,Math.round(b.kind==="color"?60+b.mean*2:b.mean/2.55)),policy:{source:"picture",variable:false,reason:""},
      rawBox:{x:Math.round(dx*k),y:Math.round((dy-best*cell)*k),w:Math.round(dw*k),h:Math.round(dh*k)},
      designBox:{x:dx,y:dy,w:dw,h:dh},designNodeIds:[],designValues:vals};});
  var notices=[];if(capped)notices.push("다른 곳이 많아 큰 것부터 40곳만 짚었습니다.");
  var gap=Math.round(((gh-1-hi)*cell));if(hi>=0&&gap>H*0.05)notices.push("개발 화면이 시안보다 짧아 시안 아래쪽 "+gap+"px는 견주지 않았습니다.");
  return{candidates:cands,notices:notices,
    alignment:{mode:"picture",s:k,tx:0,ty:Math.round(-best*cell*k),score:Math.round(bs*100)/100,fit:null,rescued:false,thin:false},
    range:{captureTop:0,captureBottom:0,manual:false,manualBottom:false}};  // 좌표는 자르지 않은 그림 기준이다
}
"""


HARNESS_JS = r'''
window.__portal=true;
function __portalLoad(u){return new Promise(function(res,rej){var im=new Image();im.onload=function(){res(im);};im.onerror=function(){rej(new Error("이미지를 읽지 못했어요: "+u));};im.src=u;});}
function __portalLite(c){function rb(b){return b?{x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.w),h:Math.round(b.h)}:null;}
  return{no:c.no,status:c.status,policy:c.policy?{source:c.policy.source,variable:!!c.policy.variable,reason:c.policy.reason||""}:null,kind:c.kind||"area",label:c.label||"",detail:c.detail||"",confidence:c.confidence==null?null:Math.round(c.confidence),rawBox:rb(c.rawBox),designBox:rb(c.designBox),designNodeIds:c.designNodeIds||[],designValues:c.designValues||""};}
window.addEventListener("message",async function(e){var m=e.data;if(!m||m.type!=="portal-run")return;
  try{
    var full=await __portalLoad(m.design.pngUrl);var dc=canvasFor(full.width,full.height);dc.getContext("2d").drawImage(full,0,0);
    var cap=await __portalLoad(m.capture.pngUrl);
    if(m.design.mode==="image"){var g=__portalPicture(full,cap,m.capture.topTrim||0,m.capture.bottomTrim||0);
      parent.postMessage({type:"portal-result",autoRunId:m.autoRunId,alignment:g.alignment,range:g.range,notices:g.notices,candidates:g.candidates,capture:{w:cap.width,h:cap.height}},"*");return;}
    var design={id:m.design.id,name:m.design.name,width:m.design.width,height:m.design.height,elements:m.design.elements||[],policy:m.design.policy||null};
    var capture={img:cap,width:cap.width,height:cap.height};
    if(m.capture.topTrim!=null)capture.topTrim=m.capture.topTrim;
    if(m.capture.bottomTrim!=null)capture.bottomTrim=m.capture.bottomTrim;
    var r=comparePair({id:"portal"},design,capture,dc),a=r.alignment||{};
    parent.postMessage({type:"portal-result",autoRunId:m.autoRunId,alignment:{mode:a.mode,s:a.s,tx:a.tx,ty:a.ty,score:a.score,fit:a.fit==null?null:a.fit,rescued:!!a.rescued,thin:!!a.thin},range:r.range||null,notices:r.candidates.notices||[],candidates:r.candidates.map(__portalLite),capture:{w:cap.width,h:cap.height}},"*");
  }catch(err){parent.postMessage({type:"portal-error",autoRunId:m.autoRunId,message:String(err&&err.message||err)},"*");}
});
parent.postMessage({type:"portal-ready"},"*");
'''
HARNESS_JS = PICTURE_JS + HARNESS_JS
_PICTURE_REV = hashlib.sha1(PICTURE_JS.encode('utf-8')).hexdigest()[:8]


class Auto:
    def __init__(self, store):
        self.store = store

    def init(self):
        with self.store.connect() as c:
            c.executescript(SCHEMA)

    # ── 페이지 ↔ 디자인 ─────────────────────────────────────────────
    def design_of_page(self, c, page_id):
        r = c.execute('SELECT design_id FROM page_design_link WHERE page_id=?', (page_id,)).fetchone()  # 플러그인에서 바로 받은 시안이 우선
        if not r:
            r = c.execute('SELECT design_id FROM design_case WHERE page_id=? AND design_id IS NOT NULL', (page_id,)).fetchone()
        if not r:
            r = c.execute('SELECT design_id FROM intake_item WHERE page_id=? AND design_id IS NOT NULL', (page_id,)).fetchone()
        if not r:
            return None
        return c.execute('SELECT d.*,a.filename,a.width,a.height FROM intake_design d JOIN intake_asset a ON a.id=d.asset_id WHERE d.id=?', (r['design_id'],)).fetchone()

    def ensure_elements(self, c, design):
        """디자인 요소 목록(검수기 입력). 없으면 Figma에서 프레임 전체를 읽어 저장한다."""
        row = c.execute('SELECT * FROM design_elements WHERE design_id=?', (design['id'],)).fetchone()
        if row:
            return {'frame': json.loads(row['frame']), 'elements': json.loads(row['elements'])}
        if design['provider'] == 'Figma 플러그인':
            raise ValueError('요소 목록이 없는 시안입니다. Figma 플러그인에서 그 프레임을 골라 「검수 시안 바꾸기」를 누르세요.')
        if design['provider'] != 'Figma REST' or design['file_key'] == 'local-design':
            raise ValueError('Figma 시안이 아니라 요소를 읽을 수 없습니다. 시안을 Figma 링크로 연결하세요.')
        data = figma_reader.api('files/' + design['file_key'] + '/nodes?ids=' + design['node_id'] + '&plugin_data=shared')
        item = (data.get('nodes') or {}).get(design['node_id'])
        if not item or not item.get('document'):
            raise ValueError('Figma에서 시안 프레임을 찾지 못했습니다. 시안을 다시 연결하세요.')
        got = figma_elements.collect(item['document'])
        c.execute('INSERT OR REPLACE INTO design_elements VALUES (?,?,?,?,?)',
                  (design['id'], now(), data.get('version'), json.dumps(got['frame'], ensure_ascii=False), json.dumps(got['elements'], ensure_ascii=False)))
        return got

    # ── 자동 검수 회차 ─────────────────────────────────────────────
    def run_for(self, c, run_id, page_id=None):
        """그 차수 + 지금 시안의 자동 검수. 시안이 바뀌면 새로 돈다(옛 결과는 남는다)."""
        design = self.design_of_page(c, page_id) if page_id else None
        return c.execute("SELECT * FROM auto_run WHERE run_id=? AND design_id=? AND source='engine' ORDER BY rowid DESC LIMIT 1",
                         (run_id, design['id'] if design else '')).fetchone()

    # ── 검수 범위(사람이 정한 위·아래 제외 px) ────────────────────────
    def current_range(self, c, run_id):
        """그 차수 개발 화면에 사람이 마지막으로 정한 검수 범위. 없으면 None(자동)."""
        try:
            return c.execute('SELECT * FROM auto_range WHERE run_id=? ORDER BY rowid DESC LIMIT 1', (run_id,)).fetchone()
        except sqlite3.OperationalError:
            return None

    def set_range(self, page_id, run_id, top, bottom, actor='', note=''):
        """검수 범위를 기록하고(append-only) 그 차수·지금 시안의 자동 검수를 새 회차로 다시 돌게 한다. 옛 회차·후보는 남는다.
        top/bottom이 둘 다 None이면 '자동으로 되돌림'."""
        def px(v, name):
            if v is None or v == '':
                return None
            try:
                v = int(round(float(v)))
            except (TypeError, ValueError):
                raise ValueError(f'{name} 값이 숫자가 아닙니다.')
            if v < 0:
                raise ValueError(f'{name} 값은 0 이상이어야 해요.')
            return v
        top, bottom = px(top, '위쪽'), px(bottom, '아래쪽')
        with self.store.connect() as c:
            run = c.execute('SELECT * FROM inspection_run WHERE uuid=?', (run_id,)).fetchone()
            if not run or not run['dev_img']:
                raise ValueError('이 차수에 개발 화면이 없습니다.')
            h = run['dev_img_h'] or 0
            if h and (top or 0) + (bottom or 0) >= h - 8:
                raise ValueError('위·아래를 합치면 화면이 남지 않습니다.')
            design = self.design_of_page(c, page_id)
            if not design:
                raise ValueError('이 페이지에 연결된 Figma 시안이 없습니다.')
            c.execute('INSERT INTO auto_range VALUES (?,?,?,?,?,?,?)', (uid(), run_id, top, bottom, actor, now(), note))
            new_id = uid()
            c.execute('INSERT INTO auto_run(id,page_id,run_id,status,engine,created_at,design_id,capture_sig) VALUES(?,?,?,?,?,?,?,?)',
                      (new_id, page_id, run_id, 'pending', engine_rev(design), now(), design['id'], capture_sig(run)))
            return new_id

    def ensure_run(self, page_id, run_id):
        """그 차수·지금 시안의 자동 검수가 없으면 '대기'로 만든다. 디자인이 안 붙은 페이지면 None.

        개발 화면 그림을 바꿨거나 검수 규칙(엔진)이 바뀌었으면 새 회차로 다시 돌린다 — 옛 회차·후보·이력은 그대로 남는다
        (검수 범위를 바꿀 때와 같은 방식). 규칙을 고쳐 놓고 옛 결과를 계속 보여 주면
        고친 것이 화면에 반영되지 않는다.
        """
        with self.store.connect() as c:
            run = c.execute('SELECT * FROM inspection_run WHERE uuid=?', (run_id,)).fetchone()
            sig = capture_sig(run)
            design = self.design_of_page(c, page_id)
            rev = engine_rev(design)
            r = self.run_for(c, run_id, page_id)
            if r and (r['status'] != 'done' or not _stale(r, rev, sig)):
                return r
            if not design:
                return r
            c.execute('INSERT INTO auto_run(id,page_id,run_id,status,engine,created_at,design_id,capture_sig) VALUES(?,?,?,?,?,?,?,?)',
                      (uid(), page_id, run_id, 'pending', rev, now(), design['id'], sig))
            return self.run_for(c, run_id, page_id)

    def retry(self, page_id, run_id):
        with self.store.connect() as c:
            r = self.run_for(c, run_id, page_id)
            if r and r['status'] == 'failed':
                c.execute("UPDATE auto_run SET status='pending',error='',engine=? WHERE id=?", (engine_rev(self.design_of_page(c, page_id)), r['id']))

    def materials(self, page_id, run_id):
        """브라우저 엔진에 줄 재료(POST). 회차가 없으면 여기서 만든다. 실패하면 회차를 failed로 남기고 ValueError."""
        r = self.ensure_run(page_id, run_id)
        if not r:
            raise ValueError('이 페이지에 연결된 Figma 시안이 없습니다.')
        try:
            with self.store.connect() as c:
                run = c.execute('SELECT * FROM inspection_run WHERE uuid=?', (run_id,)).fetchone()
                design = self.design_of_page(c, page_id)
                if not design:
                    raise ValueError('이 페이지에 연결된 Figma 시안이 없습니다.')
                if not run or not run['dev_img']:
                    raise ValueError('이 차수에 개발 화면이 없습니다.')
                got = self.ensure_elements(c, design)
        except ValueError as e:
            self.fail(r['id'], str(e))  # 실패 사유를 남긴다(같은 연결 안에서 쓰면 예외와 함께 되돌려지므로 따로)
            raise
        with self.store.connect() as c:
            settings = json.loads(design['qa_settings']) if design['qa_settings'] else {}
            frame = got['frame']
            # 정책 값은 층으로 겹친다: 시스템 → 서비스 → 화면 → 요소. 피그마 프레임에서 따라온 설정은 포털 행이 없을 때만.
            pol = policymod.Policy(self.store)
            merged = pol.engine_policy(c, run['screen_id'], settings.get('policy'))
            out = {
                'autoRunId': r['id'],
                'design': {'id': design['node_id'], 'name': design['name'], 'pngUrl': '/uploads/' + design['filename'],
                           'width': frame.get('width') or design['width'], 'height': frame.get('height') or design['height'],
                           'elements': got['elements'], 'policy': merged or None,
                           # 그림만 붙여 넣은 시안은 부품이 없어 그림끼리 견준다(design_receive.PASTED)
                           'mode': 'image' if design['provider'] == design_receive.PASTED else 'parts'},
                'capture': {'pngUrl': '/uploads/' + run['dev_img'], 'width': run['dev_img_w'], 'height': run['dev_img_h']},
            }
            # 검수 범위: 이 차수에 직접 정한 것 > 화면·서비스 층에 정한 것 > 자동 규칙
            top, bottom = pol.capture_range(c, run['screen_id'])
            rng = self.current_range(c, run_id)
            if rng:
                top, bottom = rng['top'], rng['bottom']
            if top is not None:
                out['capture']['topTrim'] = top
            if bottom is not None:
                out['capture']['bottomTrim'] = bottom
            return out

    def save_result(self, auto_run_id, result):
        with self.store.connect() as c:
            r = c.execute('SELECT * FROM auto_run WHERE id=?', (auto_run_id,)).fetchone()
            if not r:
                raise ValueError('자동 검수 회차가 없습니다.')
            if r['status'] == 'done':
                return r['id']  # 같은 결과가 두 번 오면 첫 결과를 지킨다
            cap = result.get('capture') or {}
            c.execute('UPDATE auto_run SET status=?,finished_at=?,alignment=?,range=?,notices=?,capture_w=?,capture_h=? WHERE id=?',
                      ('done', now(), json.dumps(result.get('alignment') or {}, ensure_ascii=False), json.dumps(result.get('range') or {}, ensure_ascii=False),
                       json.dumps(result.get('notices') or [], ensure_ascii=False), cap.get('w'), cap.get('h'), auto_run_id))
            for cand in result.get('candidates') or []:
                b = cand.get('rawBox') or {}
                c.execute('INSERT INTO auto_candidate VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                          (uid(), auto_run_id, int(cand.get('no') or 0), str(cand.get('kind') or 'area'), str(cand.get('label') or ''),
                           str(cand.get('detail') or ''), cand.get('confidence'), ENGINE_STATUS.get(cand.get('status'), 'open'), str(cand.get('status') or ''),
                           json.dumps(cand.get('policy') or {}, ensure_ascii=False), b.get('x'), b.get('y'), b.get('w'), b.get('h'),
                           json.dumps(cand.get('designBox') or {}, ensure_ascii=False), json.dumps(cand.get('designNodeIds') or [], ensure_ascii=False),
                           str(cand.get('designValues') or ''), None))
            return auto_run_id

    def fail(self, auto_run_id, message):
        with self.store.connect() as c:
            c.execute("UPDATE auto_run SET status='failed',error=?,finished_at=? WHERE id=? AND status<>'done'", (str(message)[:500], now(), auto_run_id))

    def candidates(self, c, auto_run_id):
        return c.execute('SELECT * FROM auto_candidate WHERE auto_run_id=? ORDER BY no', (auto_run_id,)).fetchall()

    # ── 미리 돌릴 것 고르기 ────────────────────────────────────────
    def pending_pages(self, screen_id):
        """그 화면에서 아직 자동 검수 결과가 없는 페이지(읽기만 한다 — 여기서 회차를 만들지 않는다).

        페이지를 열 때와 같은 잣대로 고른다: 마지막 차수에 개발 화면과 시안이 다 있고,
        결과가 없거나 · 개발 화면이 바뀌었거나 · 검수 규칙이 바뀐 것. 한 번 실패한 것은 넣지 않는다
        (사람이 '다시 돌리기'를 누를 때만 다시 돈다)."""
        out = []
        try:
            with self.store.connect() as c:
                pages = c.execute(
                    'SELECT uuid, seq, name FROM inspection_page WHERE screen_id=? AND removed_at IS NULL ORDER BY seq',
                    (screen_id,)).fetchall()
                for p in pages:
                    run = c.execute('SELECT * FROM inspection_run WHERE page_id=? ORDER BY round DESC LIMIT 1',
                                    (p['uuid'],)).fetchone()
                    design = self.design_of_page(c, p['uuid']) if run and run['dev_img'] else None
                    if not design:
                        continue
                    r = self.run_for(c, run['uuid'], p['uuid'])
                    if r and (r['status'] == 'failed'
                              or (r['status'] == 'done' and not _stale(r, engine_rev(design), capture_sig(run)))):
                        continue
                    out.append({'page': p['uuid'], 'run': run['uuid'], 'seq': p['seq'], 'name': p['name'] or ''})
        except sqlite3.OperationalError:
            return []          # 옛 DB(자동 검수 표 없음) — 미리 돌릴 것도 없다
        return out

    # ── 사람의 판정 ───────────────────────────────────────────────
    def set_status(self, candidate_id, status, actor='', note=''):
        if status not in STATUS_LABEL:
            raise ValueError('알 수 없는 판정입니다.')
        with self.store.connect() as c:
            k = c.execute('SELECT * FROM auto_candidate WHERE id=?', (candidate_id,)).fetchone()
            if not k:
                raise ValueError('후보가 없습니다.')
            if k['issue_id'] and status != 'open':
                raise ValueError('이미 수정필요로 올린 후보입니다. 수정필요 칸에서 처리하세요.')
            if k['status'] == status:
                return
            c.execute('UPDATE auto_candidate SET status=? WHERE id=?', (status, candidate_id))
            c.execute('INSERT INTO auto_candidate_event VALUES (?,?,?,?,?,?,?)', (uid(), candidate_id, k['status'], status, actor, now(), note))
            rule_log.record(c, k, status, actor=actor, note=note)  # 어느 규칙이 이 후보를 그 자리에 뒀는지 함께 남긴다
            self._remember(c, k, status, actor)

    def _remember(self, c, k, status, actor):
        """사람이 후보에 내린 판정을 그 화면의 **요소 층 정책**으로 쌓는다 — 다음 차수·다음 시안에서도 기억하게.
        가변 ↔ 고정(open)은 글자에만, 제외는 어떤 요소든. 요소를 여럿 가리키는 후보는 하나하나에 쓴다."""
        if value_candidates.값후보인가(k):
            return                                   # 값 대조 후보의 판정은 그림 검수 규칙이 아니다 — 요소 층에 쌓지 않는다
        ids = json.loads(k['design_node_ids'] or '[]')
        if not ids:
            return
        run = c.execute('SELECT r.screen_id FROM auto_run a JOIN inspection_run r ON r.uuid=a.run_id WHERE a.id=?', (k['auto_run_id'],)).fetchone()
        if not run:
            return
        pol = policymod.Policy(self.store)
        for nid in ids:
            if status == 'variable':
                pol.set(c, 'element', 'text.variable', True, target=run['screen_id'], key=nid, actor=actor, note=f'후보 #{k["no"]}에서 가변으로')
            elif status == 'excluded':
                pol.set(c, 'element', 'element.exclude', True, target=run['screen_id'], key=nid, actor=actor, note=f'후보 #{k["no"]}에서 제외로')
            else:  # open: 가변·제외를 거둔다. 글자면 '고정'으로 못 박는다(사람이 정한 것이 규칙보다 앞선다)
                pol.set(c, 'element', 'element.exclude', None, target=run['screen_id'], key=nid, actor=actor, note=f'후보 #{k["no"]}를 되돌림')
                if k['kind'] in ('text', 'fixed', 'variable'):
                    pol.set(c, 'element', 'text.variable', False, target=run['screen_id'], key=nid, actor=actor, note=f'후보 #{k["no"]}에서 고정으로')
                else:
                    pol.set(c, 'element', 'text.variable', None, target=run['screen_id'], key=nid, actor=actor, note=f'후보 #{k["no"]}를 되돌림')

    def register(self, candidate_id, actor, rnd):
        """후보 → 지적(inspection_issue). 사람이 누를 때만. dedup_key가 이미 있으면 그 지적에 잇는다."""
        with self.store.connect() as c:
            k = c.execute('SELECT k.*,r.page_id,r.run_id,r.capture_w,r.capture_h FROM auto_candidate k JOIN auto_run r ON r.id=k.auto_run_id WHERE k.id=?', (candidate_id,)).fetchone()
            if not k:
                raise ValueError('후보가 없습니다.')
            if k['issue_id']:
                return k['issue_id']
            if k['status'] != 'open':
                raise ValueError('제외·가변으로 둔 후보는 먼저 되돌린 뒤 등록해 주세요.')
            page = c.execute('SELECT * FROM inspection_page WHERE uuid=?', (k['page_id'],)).fetchone()
            run = c.execute('SELECT * FROM inspection_run WHERE uuid=?', (k['run_id'],)).fetchone()
            # 후보를 잰 촬영본 → 지금 화면이 쓰는 좌표 기준 (자.py)
            ㅈ = 자모듈.그림자(run['coord_ref_w'], k['capture_w'])
            b = ㅈ.개발그림_화면({'x': k['box_x'] or 0, 'y': k['box_y'] or 0,
                             'w': k['box_w'] or 0, 'h': k['box_h'] or 0})
            box = [int(round(b['x'])), int(round(b['y'])), int(round(b['w'])), int(round(b['h']))]
            node_ids = json.loads(k['design_node_ids'] or '[]')
            anchor = node_ids[0] if node_ids else f'{box[0]},{box[1]},{box[2]},{box[3]}'
            dedup = f"{k['page_id']}|{anchor}|{k['kind']}|auto"
            category = candidate_category(k)
            existing = c.execute('SELECT uuid,status FROM inspection_issue WHERE dedup_key=?', (dedup,)).fetchone()
            note = f"자동 검수 후보 #{k['no']} 등록: {k['label']}"
            if existing:
                issue_id = existing['uuid']
                self._history(c, issue_id, existing['status'], existing['status'], actor, f'{rnd}차 자동 후보 #{k["no"]} 재확인', rnd)
            else:
                issue_id = uid()
                c.execute('''INSERT INTO inspection_issue(uuid,screen_id,page_id,run_id,logical_element_key,box_x,box_y,box_w,box_h,category,expected,actual,description,severity,status,found_round,resolved_round,dedup_key,properties)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          (issue_id, page['screen_id'], k['page_id'], k['run_id'], k['label'] or issue_categories.label(category), box[0], box[1], box[2], box[3],
                           category, k['design_values'], '', k['detail'], '', '발견', rnd, None, dedup, json.dumps([issue_categories.label(category)], ensure_ascii=False)))
                self._history(c, issue_id, None, '발견', actor, note, rnd)
            c.execute('UPDATE auto_candidate SET issue_id=? WHERE id=?', (issue_id, candidate_id))
            c.execute('INSERT INTO auto_candidate_event VALUES (?,?,?,?,?,?,?)', (uid(), candidate_id, k['status'], 'open', actor, now(), note))
            rule_log.record(c, k, 'open', actor=actor, action='register', note=note)  # 사람이 진짜 오류로 인정 — 규칙이 맞았다는 기록
            return issue_id

    @staticmethod
    def _history(c, issue_id, from_status, to_status, actor, note, rnd):
        seq = c.execute('SELECT COALESCE(MAX(seq),-1)+1 s FROM issue_history WHERE issue_id=?', (issue_id,)).fetchone()['s']
        c.execute('INSERT INTO issue_history(uuid,issue_id,from_status,to_status,actor,at,note,seq,round) VALUES (?,?,?,?,?,?,?,?,?)',
                  (uid(), issue_id, from_status, to_status, actor, now(), note, seq, rnd))

    # ── 화면 조각 ─────────────────────────────────────────────────
    def view(self, page_id, run):
        """페이지 상세에 넣을 재료 — 그림 검수 후보 + 값 대조 후보(valueqa)를 한 목록으로."""
        return value_candidates.붙이기(self.store, page_id, run, self._engine_view(page_id, run))

    def _engine_view(self, page_id, run):
        """그림 검수(engine/ui.html) 쪽 재료(읽기 전용 — 페이지를 여는 것만으로는 아무것도 쓰지 않는다).
        결과가 없으면 가상의 '대기' 상태를 돌려주고, 실제 회차 생성·엔진 실행은 페이지 JS의 POST가 한다."""
        if not run:
            return None
        try:
            with self.store.connect() as c:
                design = self.design_of_page(c, page_id)
                if not design:
                    return None
                fr = c.execute('SELECT frame FROM design_elements WHERE design_id=?', (design['id'],)).fetchone()
                try:
                    dframe = json.loads(fr['frame']) if fr else {}
                except (TypeError, ValueError):
                    dframe = {}
                design_frame = {'w': dframe.get('width') or design['width'], 'h': dframe.get('height') or design['height']}
                r = self.run_for(c, run['uuid'], page_id)
                rng = self.current_range(c, run['uuid'])
                range_view = {'manual_top': rng['top'] if rng else None, 'manual_bottom': rng['bottom'] if rng else None,
                              'dev_img': run['dev_img'], 'w': run['dev_img_w'], 'h': run['dev_img_h']}
                rev = engine_rev(design)
                stale = bool(r) and r['status'] == 'done' and _stale(r, rev, capture_sig(run))
                if not r or stale:
                    # 개발 화면을 바꿨거나 검수 규칙을 고쳤으면 옛 결과를 그대로 보여 주지 않는다. 페이지 JS가 새 회차를 돌려 저장한다.
                    return {'run': {'id': '', 'run_id': run['uuid'], 'status': 'pending', 'error': '', 'notices': '[]'},
                            'candidates': [], 'issue_numbers': {}, 'round': run['round'], 'scale': 1, 'range': range_view,
                            'screen_id': run['screen_id'], 'design_frame': design_frame}
                cands = [dict(k) for k in self.candidates(c, r['id'])] if r['status'] == 'done' else []
                numbers = {}
                if any(k['issue_id'] for k in cands):
                    rows = c.execute('SELECT rowid rid,uuid FROM inspection_issue WHERE page_id=? ORDER BY rowid', (page_id,)).fetchall()
                    numbers = {row['uuid']: n + 1 for n, row in enumerate(rows)}
        except sqlite3.OperationalError:
            return None  # 옛 DB(접수·자동검수 표 없음)는 자동 검수 없이 그대로 보여준다
        try:
            al = json.loads(r['alignment'] or '{}')
        except (TypeError, ValueError, IndexError):
            al = {}
        return {'run': dict(r), 'candidates': cands, 'issue_numbers': numbers, 'round': run['round'], 'range': range_view,
                'screen_id': run['screen_id'], 'design_frame': design_frame, 'alignment': al,
                'scale': (1.0 / 자모듈.그림자(run['coord_ref_w'], r['capture_w']).개발그림배) if r['status'] == 'done' else 1}


def _e(v):
    return str(v if v is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def panel_html(view, page_id, person_options='', which='open'):
    """자동 검수 내용. which='open'이면 '수정필요' 칸(대기·실패 안내와 검수 범위도 여기), 'excluded'면 '제외' 칸."""
    if which != 'open':
        items = [k for k in view['candidates'] if k['status'] != 'open']
        cards = ''.join(card_html(k, view['issue_numbers'], page_id, view['round']) for k in items)
        return f'<div class="grid">{cards}</div>' if cards else '<p class="empty">항목 없음</p>'
    r = view['run']
    df = view.get('design_frame') or {}
    al = view.get('alignment') or {}
    try:
        ctop = (json.loads(r['range'] or '{}') or {}).get('captureTop') or 0   # 엔진이 잘라낸 위쪽 띠 — 맞춤값이 잘린 그림 기준이라 되돌려 줘야 한다
    except (TypeError, ValueError, IndexError, KeyError):
        ctop = 0
    head = (f'<div id="auto-state" data-status="{r["status"]}" data-page="{page_id}" data-run="{_e(r["run_id"])}" '
            f'data-round="{view["round"]}" data-scale="{view["scale"]}" '
            f'data-dw="{df.get("w") or 0}" data-dh="{df.get("h") or 0}" '
            f'data-as="{al.get("s") or 0}" data-atx="{al.get("tx") or 0}" data-aty="{al.get("ty") or 0}" '
            f'data-actop="{ctop}"></div>')
    def grid(items):
        cards = _cards(items, view, page_id)
        return f'<div class="grid">{cards}</div>' if cards else ''
    열린것 = [k for k in view['candidates'] if k['status'] == 'open']
    # 그림 검수가 아직 돌고 있거나 못 돌았어도 값 대조 후보는 이미 나와 있다 — 먼저 보여 준다.
    값것 = [k for k in 열린것 if value_candidates.값후보인가(k)]
    if r['status'] == 'pending':
        줄 = ' inline' if 값것 else ''
        return head + (f'<p class="empty auto-wait{줄}"><span class="auto-spin" aria-hidden="true"></span>'
                       '<span id="auto-msg">검수중입니다.</span></p>') + grid(값것)
    if r['status'] == 'failed':
        return head + (f'<p class="empty auto-msg">자동 검수를 못 했어요 — {_e(r["error"])}</p>'
                       f'<form method="post" action="/auto/{_e(page_id)}/retry">'
                       f'<input type="hidden" name="run" value="{_e(r["run_id"])}">'
                       + s1.단추('다시 시도', 종류='submit') + '</form>'
                       + range_html(view, person_options)) + grid(값것)
    # 그림으로 넣은 시안이면 어떻게 견줬는지 한 줄 알린다(무엇이 다른지는 사람이 본다)
    그림만 = (f'<p class="auto-note">{_e(PICTURE_NOTE)}</p>' if al.get('mode') == 'picture' else '')
    return head + 그림만 + range_html(view, person_options) + grid(열린것)


# 시안을 얹은 자리가 미덥지 않을 때 붙이던 빨간 줄은 보이지 않는다(river 2026-09-17).
# 재던 값(rescued·thin·fit)은 그대로 남는다 — 겹쳐보기로 사람이 본다.


def range_html(view, person_options=''):
    """검수 범위 카드: 지금 개발 화면에서 위·아래 몇 px를 비교에서 뺐는지 + '조정'(선 두 개 끌기 → 그 범위로 다시 검수)."""
    rv = view.get('range') or {}
    if view.get('값만') or not rv.get('dev_img'):
        return ''
    r = view['run']
    try:
        eng = json.loads(r.get('range') or '{}') if isinstance(r, dict) else {}
    except (TypeError, ValueError):
        eng = {}
    top, bottom = eng.get('captureTop') or 0, eng.get('captureBottom') or 0
    rules = {}
    for x in eng.get('rules') or []:
        rules.setdefault(x.get('edge'), []).append(x.get('title') or '')
    def how(edge, manual, px):
        if manual is not None:
            return '직접 정함'
        if not px:
            return '자동 · 뺀 것 없음'
        return '자동 · ' + ('·'.join(rules[edge]) if rules.get(edge) else ('브라우저 틀' if edge == 'top' else '하단 띠'))
    mt, mb = rv.get('manual_top'), rv.get('manual_bottom')
    if r.get('status') == 'done':
        summary = f'위쪽 {top}px ({how("top", mt, top)}) · 아래쪽 {bottom}px ({how("bottom", mb, bottom)})'
    else:
        summary = '직접 정한 범위로 검수함' if (mt is not None or mb is not None) else '자동'
    # 요약 줄은 보이지 않는다 — 범위 값은 '검수범위 설정' 창에서 본다(river 2026-09-16).
    # 이 칸은 그림·범위 값을 담아 두는 자리로만 남긴다.
    정책단추 = (s1.단추('화면규칙', 크기='xxsm', **{"class": "auto-range-btn"},
                     onclick="location.href='/policy/screen/%s'" % _e(view["screen_id"]))
              if view.get('screen_id') else '')
    창속 = (f'<p class="auto-hint">지금 범위는 {_e(summary)} 입니다.</p>'
          '<p class="auto-hint">상태바·주소창·키보드가 끝나는 곳으로 붉은 선을 끌어 주세요.'
          ' 선 바깥은 비교하지 않습니다.</p>'
          '<div class="auto-range-stage"><img id="auto-range-img" alt="개발 화면">'
          '<div class="auto-range-line" id="auto-range-top"></div>'
          '<div class="auto-range-line" id="auto-range-bottom"></div>'
          '<div class="auto-range-shade" id="auto-range-shade-top"></div>'
          '<div class="auto-range-shade" id="auto-range-shade-bottom"></div></div>'
          '<form class="auto-range-form" onsubmit="return autoRangeSave(this,false)">'
          '<label for="auto-range-top-px">위쪽 제외</label>'
          + s1.입력('top', '', 종류='number', 칸id='auto-range-top-px', min='0', step='1')
          + '<label for="auto-range-bottom-px">아래쪽 제외</label>'
          + s1.입력('bottom', '', 종류='number', 칸id='auto-range-bottom-px', min='0', step='1')
          + person_options
          + s1.단추('이 범위로 다시 검수', 'primary', 종류='submit')
          + s1.단추('자동으로 되돌리기', onclick='autoRangeSave(this.form,true)')
          + s1.닫기단추('닫기') + '</form>')
    return (f'<div class="auto-range" id="auto-range" hidden data-img="/uploads/{_e(rv["dev_img"])}" data-w="{rv.get("w") or 0}" data-h="{rv.get("h") or 0}" '
            f'data-top="{top}" data-bottom="{bottom}" data-mtop="{"" if mt is None else mt}" data-mbottom="{"" if mb is None else mb}" '
            f'data-sum="{_e(summary)}"></div>'
            + '<span class="auto-range-tools" id="auto-range-tools">' + 정책단추
            + s1.단추('검수범위 설정', 크기='xxsm', id='auto-range-btn',
                     onclick='autoRangeOpen()', **{"class": "auto-range-btn"}) + '</span>'
            + s1.대화창('auto-range-editor', '검수범위 설정', 창속,
                      겉속성={"class": "auto-range-editor"}))


def _cards(items, view, page_id):
    """후보 하나 = 카드 한 장. 한 컴포넌트에서 여럿 나와도 묶지 않는다(river 2026-09-16 — 묶으니 보기 불편).

    묶어 보여 주던 것을 되돌린 것이라 자료는 손대지 않는다 — 제외·되돌림은 예전처럼 낱낱에 걸린다.
    """
    return ''.join(card_html(k, view['issue_numbers'], page_id, view['round']) for k in items)


def card_html(k, numbers, page_id, rnd):
    cat = candidate_category(k)
    kind_lbl = issue_categories.label(cat)
    color = issue_categories.color(cat)
    conf = f'<span class="sev">신뢰도 {k["confidence"]}%</span>' if k['confidence'] is not None else ''
    if k['issue_id']:
        n = numbers.get(k['issue_id'])
        foot = f'<div class="passed">✓ 수정필요 #{n}</div>' if n else '<div class="passed">✓ 수정필요로 올림</div>'
        ex = ''
    else:
        foot = ''
        # 카드 머리 오른쪽에 '제외' · '가변' 두 단추 — 누르면 그 칸으로, 다시 누르면 '수정필요'로 돌아온다(river 2026-10-13).
        고른것 = {'excluded': '제외', 'variable': '가변'}.get(k['status'])
        def 고르기(글, 값):
            js = "event.stopPropagation();autoStatus('%s','%s')" % (k["id"], 'open' if 고른것 == 글 else 값)
            return s1.칩(글, 크기='sm', 고름=(고른것 == 글), onclick=js)
        ex = '<span class="auto-ex">' + 고르기('제외', 'excluded') + 고르기('가변', 'variable') + '</span>'
    from_value = value_candidates.값후보인가(k)
    # 성질·출처는 줄을 따로 두지 않고 **제목 옆 작은 글씨**로 붙인다 — 칩 한 줄이 카드만 키웠다(river 2026-09-14).
    # 낱개 카드는 제목이 곧 성질이라(예: '색상이 다르게 적용됨') 출처만 적는다.
    # 컴포넌트·요소 이름·출처를 한 줄에 모은다 — 요소 이름만 아래로 내려가 두 줄이 되던 것을 합쳤다(river 2026-09-16).
    곁 = card_view.곁말들(k, page_id) + (['값 대조'] if from_value else [])
    meta = f'<span class="meta">· {_e(" · ".join(곁))}</span>' if 곁 else ''
    # 본문(무엇이 기준인지 · 지금 개발은 어떤지 · 개발이 볼 자리)은 card_view가 줄을 갈라 그린다.
    return (f'<div class="issue auto-card st-{k["status"]}{" registered" if k["issue_id"] else ""}" id="cand-{k["id"]}" data-cand="{k["id"]}" data-types="{_e(kind_lbl)}" onclick="autoFocus(\'{k["id"]}\')">'
            f'<div class="ihead"><span class="pinno auto-no" style="background:{color}">{k["no"]}</span>{conf}{ex}<b>{_e(card_view.제목(k))}</b>{meta}</div>'
            f'{card_view.body_html(k, page_id, 이름빼기=True)}{foot}</div>')


def _design_box(k):
    """후보의 디자인 쪽 자리(시안 좌표). 없으면 None — 그때는 개발 쪽 자리를 그대로 쓴다."""
    try:
        b = json.loads(k.get('design_box') or '') if isinstance(k, dict) else ''
    except (TypeError, ValueError):
        return None
    if not isinstance(b, dict) or not b.get('w') or not b.get('h'):
        return None
    return [b.get('x') or 0, b.get('y') or 0, b['w'], b['h']]


def overlay_json(view):
    """개발 화면 위에 그릴 것. **후보마다 핀 하나** — 카드와 핀이 일대일이다(river 2026-09-16)."""
    나온것 = []
    for k in view['candidates']:
        나온것.append({'id': k['id'], 'ids': [k['id']], 'no': k['no'],
                     'status': k['status'], 'registered': bool(k['issue_id']),
                     'color': issue_categories.color(candidate_category(k)),
                     'box': [k['box_x'] or 0, k['box_y'] or 0, k['box_w'] or 0, k['box_h'] or 0],
                     'dbox': _design_box(k), 'issue': k['issue_id']})
    return json.dumps(나온것, ensure_ascii=False)


CSS = '''
.auto-overlay{pointer-events:none}.auto-overlay .abox,.auto-overlay .abadge rect{pointer-events:auto}
.auto-overlay .abox{fill:none;stroke-width:3;stroke-dasharray:10 6;cursor:pointer}
.auto-overlay .abox.dim{opacity:.25}
.auto-overlay .abadge rect{stroke:var(--color-surface-default);stroke-width:2;cursor:pointer}
.auto-overlay .abadge text{fill:var(--color-surface-default);font:bold 24px sans-serif;text-anchor:middle;pointer-events:none}
.auto-overlay .abadge.dim{opacity:.35}
.auto-overlay .abadge.sel rect{stroke:var(--color-text-primary);stroke-width:4}
.auto-overlay .abox.sel{stroke-width:6;stroke-dasharray:none}
.auto-head{display:flex;flex-direction:column;gap:var(--spacing-4);margin:var(--spacing-4) 0 var(--spacing-10);font-size:var(--font-size-14)}
.auto-sum{font-weight:var(--font-weight-bold)}.auto-hint{color:var(--color-text-caption)}
.auto-group{margin-bottom:var(--spacing-10)}.auto-group summary{cursor:pointer;font-weight:var(--font-weight-bold);margin-bottom:var(--spacing-6)}
.auto-card{position:relative}.auto-card .auto-no{border-radius:var(--radius-4)}
.auto-card .auto-ex{display:flex;gap:var(--spacing-6);margin-left:auto;flex-shrink:0}
.auto-card.st-excluded,.auto-card.st-variable{opacity:.7}
.auto-actions{display:flex;gap:var(--spacing-6);margin-top:var(--spacing-6);flex-wrap:wrap}


.auto-msg{color:var(--color-text-tertiary)}
.auto-note{margin:0 0 var(--spacing-8);font-size:var(--font-size-12);color:var(--color-text-body-tertiary)}
.auto-range-editor [data-s1-part="panel"]{width:min(900px,92vw);max-height:90vh}
.auto-range-editor [data-s1-part="body"]{overflow:auto}
.auto-range-title{display:block;margin:0 0 var(--spacing-8);font-size:var(--font-size-14)}
.cv-tools .auto-range-tools{position:absolute;right:0;top:50%;transform:translateY(-50%);display:flex;align-items:center;gap:var(--spacing-8)}   /* 가운데 단추들이 한가운데 오도록 오른쪽 단추는 따로 붙인다 */
@media (max-width:760px){.cv-tools .auto-range-tools{position:static;transform:none;margin-left:auto}}
.auto-range-editor .auto-hint{margin:0 0 var(--spacing-8);font-size:var(--font-size-12);color:var(--color-text-caption)}
.auto-range-stage{position:relative;display:inline-block;max-width:100%;line-height:0;user-select:none;touch-action:none}
.auto-range-stage img{max-width:100%;max-height:60vh;display:block;border:1px solid var(--color-border-default)}
.auto-range-line{position:absolute;left:0;right:0;height:0;border-top:2px solid var(--color-text-danger);cursor:ns-resize;z-index:2}
.auto-range-line::after{content:"";position:absolute;left:0;right:0;top:-8px;height:18px}
.auto-range-shade{position:absolute;left:0;right:0;background:var(--color-status-error);opacity:.18;pointer-events:none;z-index:1}
.auto-range-form{display:flex;flex-wrap:wrap;gap:var(--spacing-8);align-items:center;margin-top:var(--spacing-8);font-size:var(--font-size-12)}
.auto-range-form [data-s1-component="input"]{width:90px}
.auto-wait.inline{position:static;flex-direction:row;justify-content:flex-start;gap:var(--spacing-8);margin:0 0 var(--spacing-10);font-size:var(--font-size-14)}
.auto-wait.inline .auto-spin{width:18px;height:18px;border-width:var(--border-width-2)}

.auto-wait{color:var(--color-text-tertiary);position:absolute;inset:0;margin:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:var(--spacing-14)}
.auto-spin{width:var(--sizing-44);height:var(--sizing-44);flex:none;border:4px solid var(--color-border-subtle);border-top-color:var(--color-action-primary-default);border-radius:50%;animation:auto-spin .8s linear infinite}
@keyframes auto-spin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.auto-spin{animation-duration:2.4s}}
'''


# ── 미리 검수: 한 장씩 열어 기다리지 않게, 아직 결과가 없는 페이지를 숨은 자리에서 먼저 돌려 둔다 ──
# 판정은 페이지를 직접 열 때와 똑같다(같은 엔진·같은 재료·같은 저장 길). 한 번에 한 장씩만 돌린다.
PREWARM_JS = r"""
(function(){
  function 보내기(길,몸){return fetch(길,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(몸)}).then(function(r){return r.json();});}
  function 한장(it){
    return 보내기('/auto/'+it.page+'/materials',{run:it.run}).then(function(m){
      if(!m||m.error)return false;
      return new Promise(function(끝냄){
        var f=document.createElement('iframe'),끝=false;
        f.setAttribute('aria-hidden','true');
        f.style.cssText='position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;left:-9999px';
        function 치우기(약속){
          if(끝)return;끝=true;clearTimeout(시계);window.removeEventListener('message',받기);
          (약속||Promise.resolve()).catch(function(){}).then(function(){
            if(f.parentNode)f.parentNode.removeChild(f);끝냄(true);});
        }
        function 받기(e){
          var d=e.data;if(!d||!d.type||끝)return;
          if(d.type==='portal-ready'&&f.contentWindow&&e.source===f.contentWindow){f.contentWindow.postMessage(Object.assign({type:'portal-run'},m),'*');}
          else if(d.type==='portal-result'&&d.autoRunId===m.autoRunId){치우기(보내기('/auto/'+it.page+'/result',d));}
          else if(d.type==='portal-error'&&d.autoRunId===m.autoRunId){치우기(보내기('/auto/'+it.page+'/fail',{autoRunId:m.autoRunId,message:d.message}));}
        }
        var 시계=setTimeout(function(){치우기(보내기('/auto/'+it.page+'/fail',{autoRunId:m.autoRunId,message:'시간이 너무 오래 걸려 멈췄습니다(3분).'}));},180000);
        window.addEventListener('message',받기);
        f.src='/engine/ui.html';document.body.appendChild(f);
      });
    }).catch(function(){return false;});
  }
  window.qa미리검수=function(화면,옵션){
    옵션=옵션||{};
    var 알림=옵션.알림?document.getElementById(옵션.알림):null;
    fetch('/auto/screen/'+화면+'/pending').then(function(r){return r.json();}).then(function(j){
      var 목록=(j&&j.pages)||[];
      if(옵션.지금페이지){
        // 페이지 상세에서는 바로 다음 한 장만 미리 돌린다 — 보고 있는 화면이 굼떠지지 않게.
        var 뒤=목록.filter(function(x){return x.page!==옵션.지금페이지&&x.seq>(옵션.지금순번||0);});
        목록=(뒤.length?뒤:목록.filter(function(x){return x.page!==옵션.지금페이지;})).slice(0,1);
      }
      if(!목록.length)return;
      var i=0;
      (function 다음(){
        if(i>=목록.length){if(알림)알림.textContent='';return;}
        if(알림)알림.textContent='다른 장을 미리 검수하고 있습니다 · '+(i+1)+' / '+목록.length+'장';
        한장(목록[i]).then(function(){i++;setTimeout(다음,50);});
      })();
    }).catch(function(){});
  };
})();
"""

JS = r'''
(function(){
  var st=document.getElementById('auto-state');if(!st)return;
  var page=st.dataset.page,run=st.dataset.run;
  // ── 저장된 후보를 개발 화면 위에 그린다(점선 상자 + 네모 번호) ──
  var dataEl=document.getElementById('auto-data'),svg=document.querySelector('svg.auto-overlay');
  if(dataEl&&svg){
    var items=JSON.parse(dataEl.textContent||'[]'),k=Number(st.dataset.scale)||1,ns='http://www.w3.org/2000/svg';
    window.qaPinOf=window.qaPinOf||{};var qaPinOf=window.qaPinOf;
    window.qaDesignRef={w:Number(st.dataset.dw)||0,h:Number(st.dataset.dh)||0};
    window.qaAlign={s:Number(st.dataset.as)||0,tx:Number(st.dataset.atx)||0,ty:Number(st.dataset.aty)||0,ctop:Number(st.dataset.actop)||0};
    window.qaDesignBox=window.qaDesignBox||{};
    items.forEach(function(c){
      if(c.dbox){window.qaDesignBox[c.id]=c.dbox;if(c.issue)window.qaDesignBox[c.issue]=c.dbox;
        (c.ids||[]).forEach(function(x){window.qaDesignBox[x]=c.dbox;});}
      (c.ids||[]).forEach(function(x){qaPinOf[x]=c.id;});
      var b=c.box.map(function(v){return v*k;}),dim=c.status!=='open'?' dim':'';
      var r=document.createElementNS(ns,'rect');r.setAttribute('x',b[0]);r.setAttribute('y',b[1]);r.setAttribute('width',b[2]);r.setAttribute('height',b[3]);r.setAttribute('rx',4);
      r.setAttribute('class','abox'+dim);r.setAttribute('id','abox-'+c.id);r.style.stroke=c.color;r.onclick=function(){autoFocus(c.id);};svg.appendChild(r);
      var g=document.createElementNS(ns,'g');g.setAttribute('class','abadge'+dim);g.setAttribute('id','abadge-'+c.id);
      var bx=Math.max(0,b[0]-8),by=Math.max(0,b[1]-36);
      var w=Math.max(44,String(c.no).length*15+18);
      var q=document.createElementNS(ns,'rect');q.setAttribute('x',bx);q.setAttribute('y',by);q.setAttribute('width',w);q.setAttribute('height',32);q.setAttribute('rx',6);q.style.fill=c.color;q.onclick=function(){autoFocus(c.id);};
      var t=document.createElementNS(ns,'text');t.setAttribute('x',bx+w/2);t.setAttribute('y',by+24);t.textContent=String(c.no);
      g.appendChild(q);g.appendChild(t);svg.appendChild(g);
    });
  }
  // ── 아직 결과가 없으면 숨은 엔진을 돌려 저장하고 다시 연다 ──
  if(st.dataset.status!=='pending')return;
  var msg=document.getElementById('auto-msg');
  function say(t){if(msg)msg.textContent=t;}
  function post(url,body){return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json();});}
  post('/auto/'+page+'/materials',{run:run}).then(function(m){
    if(m.error){say('자동 검수를 못 했어요 — '+m.error);setTimeout(function(){location.reload();},1500);return;}
    var f=document.createElement('iframe');f.src='/engine/ui.html';f.setAttribute('aria-hidden','true');f.style.cssText='position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;left:-9999px';
    var done=false;
    window.addEventListener('message',function(e){var d=e.data;if(!d||!d.type||done)return;
      if(d.type==='portal-ready'){f.contentWindow.postMessage(Object.assign({type:'portal-run'},m),'*');}
      else if(d.type==='portal-result'){done=true;post('/auto/'+page+'/result',d).then(function(){location.reload();});}
      else if(d.type==='portal-error'){done=true;post('/auto/'+page+'/fail',{autoRunId:m.autoRunId,message:d.message}).then(function(){location.reload();});}
    });
    document.body.appendChild(f);
    setTimeout(function(){if(!done){done=true;post('/auto/'+page+'/fail',{autoRunId:m.autoRunId,message:'시간이 너무 오래 걸려 멈췄어요(3분).'}).then(function(){location.reload();});}},180000);
  }).catch(function(){say('자동 검수 재료를 받지 못했습니다.');});
})();
function autoFocus(id){
  document.querySelectorAll('.auto-overlay .sel').forEach(function(e){e.classList.remove('sel');});
  document.querySelectorAll('.auto-card.hl').forEach(function(e){e.classList.remove('hl');});
  var pin=(window.qaPinOf&&window.qaPinOf[id])||id;
  var b=document.getElementById('abox-'+pin),g=document.getElementById('abadge-'+pin);
  var c=document.getElementById('cand-'+id);
  if(c&&!c.classList.contains('auto-card'))c=c.closest('.auto-card')||c;
  if(b)b.classList.add('sel');if(g){g.classList.add('sel');g.parentNode.appendChild(g);}
  if(c){var panel=c.closest('.panel');if(panel&&window.showTab)showTab(panel.id.replace('panel-',''));c.classList.add('hl');var d=c.closest('details');if(d)d.open=true;var box=document.getElementById('cards');if(box)box.scrollTop=c.offsetTop-40;}
  if(window.qaCompareIssue)window.qaCompareIssue(id);
}
function autoStatus(id,status){
  var st=document.getElementById('auto-state');
  fetch('/auto/'+st.dataset.page+'/candidate/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:status})})
    .then(function(r){return r.json();}).then(function(j){if(j.error){alert(j.error);return;}location.reload();});
}
// ── 검수 범위 조정: 개발 화면 위에 선 두 개를 끌어 위·아래 제외 px를 정하고, 그 범위로 새 회차를 돌린다 ──
var __rangeEd=null;
function autoRangeOpen(){
  var box=document.getElementById('auto-range'),ed=document.getElementById('auto-range-editor');if(!box||!ed)return;
  if(!ed.open){if(ed.showModal)ed.showModal();else ed.setAttribute('open','');}
  var img=document.getElementById('auto-range-img'),H=Number(box.dataset.h)||0,form=ed.querySelector('form');
  var top=box.dataset.mtop!==''?Number(box.dataset.mtop):Number(box.dataset.top)||0,bottom=box.dataset.mbottom!==''?Number(box.dataset.mbottom):Number(box.dataset.bottom)||0;
  __rangeEd={box:box,ed:ed,img:img,H:H,form:form,top:top,bottom:bottom};
  function draw(){var e=__rangeEd,k=e.img.clientHeight/(e.H||1);
    document.getElementById('auto-range-top').style.top=(e.top*k)+'px';document.getElementById('auto-range-bottom').style.top=(e.img.clientHeight-e.bottom*k)+'px';
    var st=document.getElementById('auto-range-shade-top'),sb=document.getElementById('auto-range-shade-bottom');st.style.top='0';st.style.height=(e.top*k)+'px';sb.style.bottom='0';sb.style.height=(e.bottom*k)+'px';
    e.form.top.value=e.top;e.form.bottom.value=e.bottom;}
  __rangeEd.draw=draw;
  img.onload=draw;img.src=box.dataset.img;if(img.complete)draw();
  function drag(lineId,which){var line=document.getElementById(lineId);
    line.onpointerdown=function(ev){ev.preventDefault();line.setPointerCapture(ev.pointerId);
      line.onpointermove=function(mv){var e=__rangeEd,rect=e.img.getBoundingClientRect(),k=e.img.clientHeight/(e.H||1),y=Math.max(0,Math.min(rect.height,mv.clientY-rect.top));
        var px=Math.round(y/k);if(which==='top')e.top=Math.max(0,Math.min(px,e.H-e.bottom-8));else e.bottom=Math.max(0,Math.min(e.H-px,e.H-e.top-8));draw();};
      line.onpointerup=line.onpointercancel=function(){line.onpointermove=null;};};}
  drag('auto-range-top','top');drag('auto-range-bottom','bottom');
  form.top.oninput=function(){__rangeEd.top=Math.max(0,Number(this.value)||0);draw();};
  form.bottom.oninput=function(){__rangeEd.bottom=Math.max(0,Number(this.value)||0);draw();};
  window.addEventListener('resize',draw);
}
function autoRangeClose(){var ed=document.getElementById('auto-range-editor');if(!ed)return;if(ed.close)ed.close();else ed.removeAttribute('open');}
function autoRangeSave(form,reset){
  var st=document.getElementById('auto-state'),e=__rangeEd;if(!st||!e)return false;
  var body=reset?{run:st.dataset.run,top:null,bottom:null,actor:form.actor.value||''}:{run:st.dataset.run,top:e.top,bottom:e.bottom,actor:form.actor.value||''};
  fetch('/auto/'+st.dataset.page+'/range',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json();}).then(function(j){if(j.error){alert(j.error);return;}location.reload();});
  return false;
}
// ── '조정' 단추를 비교 보기 줄 오른쪽 끝으로 · 팝업은 어느 탭에서 눌러도 뜨도록 몸통으로 ──
(function(){
  function move(){
    var btn=document.getElementById('auto-range-tools'),tools=document.querySelector('.cv-tools');
    if(btn&&tools&&btn.parentNode!==tools)tools.appendChild(btn);
    var ed=document.getElementById('auto-range-editor');
    if(ed&&ed.parentNode!==document.body)document.body.appendChild(ed);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',move);else move();
})();
function autoRegister(form,id){
  var st=document.getElementById('auto-state'),actor=(form.actor.value||'').trim();
  if(!actor){alert('담당자를 골라 주세요.');return false;}
  fetch('/auto/'+st.dataset.page+'/candidate/'+id+'/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor:actor,round:Number(st.dataset.round)||1})})
    .then(function(r){return r.json();}).then(function(j){if(j.error){alert(j.error);return;}location.reload();});
  return false;
}
'''


# ── HTTP ─────────────────────────────────────────────────────────
def _json(handler, obj, code=200):
    data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Content-Length', str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _body_json(handler):
    length = int(handler.headers.get('Content-Length', 0) or 0)
    raw = handler.rfile.read(length) if length else b''
    try:
        return json.loads(raw.decode('utf-8')) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def get(handler, store, path, q):
    """GET /engine/ui.html (엔진 한 벌 + 포털 손잡이) · /auto/screen/<화면>/pending (미리 돌릴 페이지)"""
    if path.startswith('/auto/screen/') and path.endswith('/pending'):
        _json(handler, {'pages': Auto(store).pending_pages(path.split('/')[3])})
        return True
    if path == '/engine/ui.html':
        data = engine_html().encode('utf-8')
        handler.send_response(200)
        handler.send_header('Content-Type', 'text/html; charset=utf-8')
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('Content-Length', str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
        return True
    return False


def post(handler, store, path):
    """POST /auto/<page>/materials · /result · /fail · /retry · /range · /candidate/<id>/status · /candidate/<id>/register"""
    parts = path.strip('/').split('/')
    if len(parts) < 3 or parts[0] != 'auto':
        return False
    auto = Auto(store)
    page_id, action = parts[1], parts[2]
    try:
        if action == 'materials' and len(parts) == 3:
            body = _body_json(handler)
            _json(handler, auto.materials(page_id, str(body.get('run') or '')))
        elif action == 'result' and len(parts) == 3:
            body = _body_json(handler)
            _json(handler, {'ok': auto.save_result(str(body.get('autoRunId') or ''), body)})
        elif action == 'fail' and len(parts) == 3:
            body = _body_json(handler)
            auto.fail(str(body.get('autoRunId') or ''), body.get('message') or '알 수 없는 오류')
            _json(handler, {'ok': True})
        elif action == 'retry' and len(parts) == 3:
            from urllib.parse import parse_qs
            length = int(handler.headers.get('Content-Length', 0) or 0)
            form = parse_qs(handler.rfile.read(length).decode('utf-8')) if length else {}
            auto.retry(page_id, (form.get('run') or [''])[0])
            handler.send_response(303)
            handler.send_header('Location', handler.headers.get('Referer') or '/')
            handler.end_headers()
        elif action == 'range' and len(parts) == 3:
            body = _body_json(handler)
            _json(handler, {'ok': True, 'autoRunId': auto.set_range(page_id, str(body.get('run') or ''), body.get('top'), body.get('bottom'), str(body.get('actor') or ''))})
        elif action == 'candidate' and len(parts) == 5 and parts[4] == 'status':
            body = _body_json(handler)
            auto.set_status(parts[3], str(body.get('status') or ''), str(body.get('actor') or ''), str(body.get('note') or ''))
            _json(handler, {'ok': True})
        elif action == 'candidate' and len(parts) == 5 and parts[4] == 'register':
            body = _body_json(handler)
            _json(handler, {'ok': True, 'issue': auto.register(parts[3], str(body.get('actor') or ''), int(body.get('round') or 1))})
        else:
            return False
    except ValueError as e:
        _json(handler, {'error': str(e)}, 200)
    return True
