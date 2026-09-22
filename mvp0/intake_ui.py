"""Server-rendered intake screens: browser holds no authoritative state."""
import gnb as gnb_bar
import html
import json
from urllib.parse import quote
import figma_reader
import s1_tokens


def e(v):
    return html.escape(str(v if v is not None else ''))


STATUS={'unlinked':'디자인 미연결','pending':'짝 확인 대기','confirmed':'짝 확인됨','held':'보류','excluded':'이번 연결 제외'}
CSS='''
body{margin:0;background:var(--color-bg-subtle);color:var(--color-text-primary);font:14px -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif}*{box-sizing:border-box}a{color:inherit;text-decoration:none}header{background:var(--color-surface-default);border-bottom:1px solid var(--color-border-subtle);padding:var(--spacing-16) var(--spacing-32);display:flex;align-items:center;gap:var(--spacing-24)}header strong{font-size:var(--font-size-18)}nav{margin-left:auto;display:flex;gap:var(--spacing-20);color:var(--color-text-caption)}main{max-width:1320px;margin:auto;padding:var(--spacing-28) var(--spacing-32) 70px}h1{font-size:var(--font-size-24);margin:0 0 var(--spacing-10)}h2{font-size:var(--font-size-16);margin:0 0 var(--spacing-16)}h3{font-size:var(--font-size-14);margin:0 0 var(--spacing-12)}p{line-height:1.6}.muted,small{color:var(--color-text-caption)}.sub{margin:0 0 var(--spacing-24);color:var(--color-text-caption)}.card{background:var(--color-surface-default);border:1px solid var(--color-border-subtle);border-radius:var(--radius-12);padding:var(--spacing-20);margin:var(--spacing-16) 0}.row{display:flex;gap:var(--spacing-12);align-items:center;flex-wrap:wrap}.spread{justify-content:space-between}.badge{display:inline-block;font-size:var(--font-size-12);border-radius:var(--radius-6);background:var(--color-bg-subtle);padding:var(--spacing-4) var(--spacing-8);color:var(--color-text-caption)}.confirmed{background:var(--color-action-primary-subtle);color:var(--color-status-success)}.pending{background:var(--color-action-primary-subtle);color:var(--color-action-primary-default)}.held,.error{background:var(--color-red-50);color:var(--color-text-state-caution)}.notice{padding:var(--spacing-14) var(--spacing-16);border-radius:var(--radius-8);background:var(--color-action-primary-subtle);margin:var(--spacing-14) 0;line-height:1.6}.notice.error{background:var(--color-red-50);color:var(--color-text-danger)}label{display:block;font-size:var(--font-size-14);color:var(--color-text-caption);margin:var(--spacing-8) 0}input:not([type=checkbox]):not([type=radio]),select,textarea{max-width:100%;width:100%}input[type=file]{padding:var(--spacing-16);background:var(--color-bg-default)}textarea{min-height:65px}.field{flex:1;min-width:180px}.drop{border:1px dashed var(--color-text-helper);padding:var(--spacing-20);border-radius:var(--radius-10);background:var(--color-bg-default);margin:var(--spacing-16) 0}.steps{display:flex;gap:var(--spacing-20);margin:0 0 var(--spacing-24);color:var(--color-text-caption);font-size:var(--font-size-14)}.steps b{color:var(--color-action-primary-default)}.thumb{width:42px;height:82px;object-fit:contain;background:var(--color-border-subtle);border-radius:var(--radius-4)}.intake-item{display:grid;grid-template-columns:60px 1fr 1fr 1fr 190px;gap:var(--spacing-16);align-items:start;border-top:1px solid var(--color-border-subtle);padding:var(--spacing-16) 0}.intake-item input{font-size:var(--font-size-14)}.intake-item small{display:block;margin-top:var(--spacing-8);overflow-wrap:anywhere}.workspace{display:grid;grid-template-columns:225px minmax(0,1fr);gap:var(--spacing-20)}.states{background:var(--color-surface-default);border:1px solid var(--color-border-subtle);border-radius:var(--radius-10);padding:var(--spacing-8);align-self:start}.state{display:block;padding:var(--spacing-14);border-radius:var(--radius-8);border:1px solid transparent;margin-bottom:var(--spacing-4)}.state.active{border-color:var(--color-border-focus);background:var(--color-action-primary-subtle)}.state small{display:block;margin-top:var(--spacing-6)}.compare{display:grid;grid-template-columns:1fr 1fr;gap:var(--spacing-16)}.pane{background:var(--color-surface-default);border:1px solid var(--color-border-subtle);border-radius:var(--radius-10);overflow:hidden}.pane h3{padding:var(--spacing-14) var(--spacing-16);margin:0;border-bottom:1px solid var(--color-bg-subtle)}.canvas{height:540px;background:var(--color-bg-subtle);padding:var(--spacing-16);display:flex;align-items:center;justify-content:center}.canvas img{width:100%;height:100%;object-fit:contain}.canvas .empty{max-width:230px;text-align:center;color:var(--color-text-caption);line-height:1.7}.caption{font-size:var(--font-size-12);padding:var(--spacing-10) var(--spacing-16);color:var(--color-text-caption);overflow-wrap:anywhere}.designs{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:var(--spacing-12)}.designs form{border:1px solid var(--color-border-subtle);border-radius:var(--radius-8);padding:var(--spacing-10)}.designs img{width:100%;height:170px;object-fit:contain;background:var(--color-bg-subtle)}.designs p{font-size:var(--font-size-12);min-height:36px}.designs button{width:100%;font-size:var(--font-size-12)}.actions{position:sticky;bottom:0;background:color-mix(in srgb, var(--color-bg-subtle) 96%, transparent);padding:var(--spacing-16) 0;margin-top:var(--spacing-12);z-index:2}.section-link{color:var(--color-action-primary-default)}.count{font-size:var(--font-size-32);font-weight:var(--font-weight-bold)}details{margin:var(--spacing-16) 0}summary{cursor:pointer;color:var(--color-text-tertiary)}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:var(--font-size-12);color:var(--color-text-caption)}.history{font-size:var(--font-size-12)}.history li{padding:var(--spacing-8) 0;line-height:1.7}.spacer{flex:1}@media(max-width:850px){main{padding:var(--spacing-20) var(--spacing-16)}.workspace{grid-template-columns:1fr}.states{display:flex;overflow:auto}.state{min-width:155px}.intake-item{grid-template-columns:45px 1fr}.intake-item>*:last-child{grid-column:2}.canvas{height:420px}.row{align-items:stretch}header{padding:var(--spacing-16)}nav{gap:var(--spacing-10);font-size:var(--font-size-12)}}@media(max-width:520px){.compare{grid-template-columns:1fr}.steps{gap:var(--spacing-10);font-size:var(--font-size-12)}}
'''


def page(title,body,notice='',error=False):
    banner=f'<div class="notice {"error" if error else ""}" role="status">{e(notice)}</div>' if notice else ''
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} · 검수 포털</title>{s1_tokens.링크()}<style>{CSS}</style></head><body>{gnb_bar.바("intake")}<header><strong>{e(title)}</strong><nav><a href="/intake/new">촬영본 가져오기</a></nav></header><main>{banner}{body}</main></body></html>'''


def hidden(name,value):
    return f'<input type="hidden" name="{e(name)}" value="{e(value)}">'


def form(action,body):
    return f'<form method="post" action="{e(action)}">{body}</form>'


def inbox(store,notice=''):
    rows=''
    for b in store.batches():
        rows+=f'''<tr><td><a class="section-link" href="/intake/{b['id']}">{e(b['project_name'])}</a><small style="display:block">{e(b['created_at'][:10])} · {e(b['platform'])}</small></td><td>{b['total']}장</td><td>{b['confirmed'] or 0}장</td><td>{b['excluded'] or 0}장</td><td><a class="button" href="/intake/{b['id']}">가져온 내용 보기</a></td></tr>'''
    return page('가져온 기록',f'''<div class="row spread"><div><h1>가져온 기록</h1><p class="sub">가져온 원본과 제외 사유를 확인하세요. 검수는 화면 목록에서 이어집니다.</p></div><a class="button primary" href="/intake/new">촬영본 가져오기</a></div><section class="card"><table><thead><tr><th>프로젝트 · 접수일</th><th>촬영본</th><th>짝 확인</th><th>제외</th><th></th></tr></thead><tbody>{rows or '<tr><td colspan="5">아직 가져온 촬영본이 없습니다.</td></tr>'}</tbody></table></section>''',notice)


def new(store,notice='',error=False):
    options=''.join(f'<option value="{r["uuid"]}">{e(r["name"])}</option>' for r in store.projects())
    return page('촬영본 가져오기',f'''<p><a class="section-link" href="/">← 화면 목록</a></p><h1>촬영본 가져오기</h1><p class="sub">촬영한 폴더 또는 PNG와 찍은목록.json을 함께 선택하세요.</p><form method="post" enctype="multipart/form-data" action="/intake/import"><section class="card"><h2>어느 프로젝트의 촬영본인가요?</h2><div class="row"><div class="field"><label for="project">프로젝트</label><select id="project" name="project_id"><option value="">새 프로젝트 이름으로 접수</option>{options}</select></div><div class="field"><label for="project-name">새 프로젝트 이름</label><input id="project-name" name="project_name" placeholder="예: 삼성통근버스 앱" maxlength="120"></div><div class="field"><label for="platform">플랫폼</label><select id="platform" name="platform"><option value="android">Android</option><option value="ios">iOS</option><option value="web">PC 웹</option><option value="mobile-web">모바일 웹</option></select></div></div><div class="drop"><label for="folder">폴더 선택</label><input id="folder" type="file" name="files" webkitdirectory multiple><p class="muted">또는 파일을 직접 선택</p><label for="files">PNG 여러 장 + 찍은목록.json</label><input id="files" type="file" name="files" accept="image/png,.json" multiple><small>한 번에 100장 · 한 장 최대 25MB · 전체 최대 100MB</small></div><p class="muted">화면 번호가 없어도 이름과 상태로 접수할 수 있습니다. 촬영 원본은 그대로 보관합니다.</p><button class="primary">가져오고 이름 확인</button></section></form>''',notice,error)


def batch_page(store,batch,notice='',error=False):
    b,items,events=store.batch(batch)
    rows=''
    for r in items:
        image=f'<img class="thumb" src="/uploads/{r["filename"]}" alt="{e(r["state_name"])} 촬영본">' if r['filename'] else '<span class="badge error">파일 확인</span>'
        if r['page_id']:
            controls=f'<span class="badge confirmed">검수 시작됨</span><a class="section-link" href="/intake/{batch}/connect?item={r["id"]}">연결 보기</a>'
            fields=f'<div>{e(r["screen_name"])}</div><div>{e(r["state_name"])}</div><div>{e(STATUS[r["status"]])}</div><div>{controls}</div>'
        else:
            options=''.join(f'<option value="{v}" {"selected" if (r["status"]==v or (v=="include" and r["status"] not in ("held","excluded"))) else ""}>{label}</option>' for v,label in [('include','연결 대상'),('held','보류'),('excluded','이번 연결 제외')])
            fields=f'''<div><label>화면 이름<input aria-label="화면 이름 {r['seq']}" name="screen" value="{e(r['screen_name'])}" required maxlength="120"></label><small>공식 번호 미정</small></div><div><label>촬영 상태<input aria-label="촬영 상태 {r['seq']}" name="state" value="{e(r['state_name'])}" required maxlength="120"></label></div><div><label>이번 연결 대상<select name="status" aria-label="연결 대상 {r['seq']}">{options}</select></label><label>보류·제외 사유<input name="reason" value="{e(r['reason'])}" maxlength="1000"></label></div><div><span class="badge {r['status']}">{e(STATUS[r['status']])}</span><p><button>변경 저장</button></p></div>'''
        inner=hidden('item',r['id'])+hidden('revision',r['revision'])+f'<div>{image}</div>'+fields
        row=f'<div class="intake-item">{inner}</div><small>{e(r["source_name"])}{(" · "+e(r["error"])) if r["error"] else ""}</small>'
        rows+=row if r['page_id'] else form(f'/intake/{batch}/edit',row)
    confirmed=sum(r['status']=='confirmed' for r in items)
    excluded=sum(r['status']=='excluded' for r in items)
    metadata=json.loads(b['metadata'])
    meta=' · '.join(str(metadata[k]) for k in ('촬영일','찍은때','기기','해상도','화면크기','촬영방법') if metadata.get(k))
    history=''.join(f'<li>{e(r["at"])} · {e(r["action"])}<details><summary>기록 보기</summary><pre>{e(r["detail"])}</pre></details></li>' for r in events)
    return page('이름·상태 확인',f'''<p><a class="section-link" href="/">← 화면 목록</a></p><h1>{e(b['project_name'])}</h1><p class="sub">촬영본 {len(items)}장 · 짝 확인 {confirmed}장 · 제외 {excluded}장</p><p class="muted">{e(meta)}</p><section class="card"><div class="row spread"><h2>이름·상태 확인</h2><a class="button primary" href="/intake/{batch}/pages">검수 페이지 목록으로</a></div><p class="muted">이름과 대상을 수정했다면 해당 줄의 ‘변경 저장’을 눌러 주세요.</p>{rows}</section><details><summary>접수·연결 이력 ({len(events)}개, 최근 100개)</summary><ol class="history">{history}</ol></details>''',notice,error)





def group_url(batch,item):
    return f'/intake/{batch}/screen/{item}'


def page_list(store,batch,item_id='',notice='',error=False):
    from design_plan import Plans
    planned=next((p for p in Plans(store).plans() if p['batch_id']==batch),None)
    if planned:
        from design_plan_ui import listing
        return listing(store,planned['id'],notice)
    b,items,_=store.batch(batch)
    if item_id and not any(r['id']==item_id for r in items):
        raise ValueError('이 화면의 검수 페이지를 선택해 주세요.')
    selected=next((r for r in items if r['id']==item_id),None) or next((r for r in items if r['status']!='excluded'),None)
    if not selected:
        return batch_page(store,batch,notice or '연결 대상이 없습니다. 제외 사유를 확인하세요.',error)
    same=[r for r in items if r['screen_name']==selected['screen_name']]
    active=[r for r in same if r['status']!='excluded']
    rows=''
    import queries
    with store.connect() as c:
        for seq,r in enumerate(active,1):
            total=un=0;pf=None
            if r['page_id']:
                p=c.execute('SELECT screen_id FROM inspection_page WHERE uuid=?',(r['page_id'],)).fetchone()
                info=next(x for x in queries.pages_of_screen(c,p['screen_id']) if x['uuid']==r['page_id'])
                total,un,pf=info['total'],info['unresolved'],info['pass_fail']
            href=store.page_destination(r['id'])
            status='파일 확인 필요' if r['error'] else STATUS[r['status']]
            rows+=f'<tr data-href="{e(href)}" onclick="location.href=this.dataset.href"><td>{seq}</td><td><a class="section-link" href="{href}"><strong>{e(r["state_name"])}</strong></a></td><td><span class="badge {r["status"]}">{e(status)}</span></td><td><span class="badge">{e(pf.upper() if pf else "미검수")}</span></td><td>{un} / {total}</td><td><a class="button" href="{href}">페이지 열기</a></td></tr>'
    excluded=[r for r in same if r['status']=='excluded']
    extra=f'<p class="muted">이번 연결 제외 {len(excluded)}장 · <a class="section-link" href="/intake/{batch}">원본·사유 보기</a></p>' if excluded else ''
    return page('검수 페이지 목록',f'''<div class="row"><a class="section-link" href="/">← 화면 목록</a><h1 style="font-size:var(--font-size-18);margin:0">{e(selected['screen_name'])}</h1><span class="muted">공식 번호 미정 · {e(b['platform'])}</span></div><section class="card" style="max-width:1040px;margin:var(--spacing-24) auto"><div class="row spread"><h2>검수 페이지 · {len(active)}개</h2><a class="button" href="/intake/{batch}">촬영본 이름·대상 관리</a></div><p class="muted">같은 화면의 상태·단계를 선택하세요. 재검수 차수는 각 페이지 안에서 확인합니다.</p><table><thead><tr><th>순번</th><th>검수 페이지</th><th>디자인 연결</th><th>Pass/Fail</th><th>미해결 / 전체</th><th></th></tr></thead><tbody>{rows}</tbody></table>{extra}</section>''',notice,error)


def connect_page(store,batch,item_id='',notice='',error=False):
    # One renderer for both unlinked captures and registered inspection pages.
    import portal
    b, items, _ = store.batch(batch)
    r = next((x for x in items if x['id']==item_id),None) or next((x for x in items if x['status']!='excluded'),None)
    if r is None:
        return batch_page(store,batch,'연결 대상이 없습니다.',True)
    message = notice or r['error']
    if r['page_id']:
        return portal.render_page(r['page_id'],notice=message,store=store)
    return portal.render_page(r['id'],notice=message,draft=(b,r),store=store)


def design_dialog(store,batch,r):
    available=list(store.designs())
    if r['design_id'] and not any(d['id']==r['design_id'] for d in available):
        with store.connect() as conn:
            current=conn.execute('SELECT d.*,a.filename FROM intake_design d JOIN intake_asset a ON a.id=d.asset_id WHERE d.id=?',(r['design_id'],)).fetchone()
        if current:
            available.insert(0,current)
    designs=sorted(available,key=lambda d:(d['id']!=r['design_id'], -sum(word in d['name'] for word in r['screen_name'].split()),d['name']))
    chosen=next((d for d in designs if d['id']==r['design_id']),None) or (designs[0] if designs else None)
    controls=hidden('item',r['id'])+hidden('revision',r['revision'])
    options=''
    for d in designs:
        checked=d['id']==(chosen['id'] if chosen else '')
        options+=f'<label class="pick-option"><input type="radio" name="design" value="{e(d["id"])}" data-src="/uploads/{e(d["filename"])}" data-name="{e(d["name"])}" {"checked" if checked else ""}><span>{e(d["name"])}{ " · 현재 선택" if d["id"]==r["design_id"] else ""}</span></label>'
    design_image=f'<img id="pick-design-image" src="/uploads/{e(chosen["filename"])}" alt="비교할 디자인">' if chosen else '<p>가져온 시안이 없습니다.</p>'
    capture=f'<img src="/uploads/{e(r["filename"])}" alt="개발 촬영본 {e(r["state_name"])}">' if r['filename'] else '<p>촬영본 없음</p>'
    reason=store.recommendation(r['id']) if r['status']=='pending' else ''
    comparison=f'<div class="pick-layout"><div class="pick-pair"><section><h3>디자인</h3><div class="pick-image">{design_image}</div><p id="pick-design-name">{e(chosen["name"] if chosen else "")}</p></section><section><h3>개발 · {e(r["state_name"])}</h3><div class="pick-image">{capture}</div><p>촬영 원본</p></section></div><aside class="pick-list"><b>다른 시안 둘러보기</b><p>현재 선택을 먼저 표시합니다.</p>{options}</aside></div>'
    body=controls+comparison+f'<div class="pick-footer"><span>시안을 눌러 대조한 뒤 적용하세요. 짝 확정은 상세에서 합니다.</span><button {"disabled" if not chosen or r["status"] in ("held","excluded") or not r["asset_id"] else ""}>이 디자인 선택</button></div>'
    linkform=form(f'/intake/{batch}/fetch',hidden('item',r['id'])+'<label for="figma-link">Figma 프레임 또는 페이지 링크</label><div class="row"><input style="flex:1" type="url" id="figma-link" name="link" placeholder="https://www.figma.com/design/…" required><button>디자인 불러오기</button></div>')
    setting=form(f'/intake/{batch}/token',hidden('item',r['id'])+'<label>Figma 읽기 연결 키<input type="password" name="token" autocomplete="off" required></label><p class="muted">이 실행 중에만 보관합니다.</p><button>이 실행에 연결</button>')
    return f'''<dialog id="design-picker"><style>
#design-picker{{width:96vw;max-width:1500px;height:92vh;max-height:92vh;box-sizing:border-box;overflow:auto}}
#design-picker .dialog-head{{display:flex;align-items:center;justify-content:space-between;gap:var(--spacing-12)}}#design-picker h2{{margin:0;font-size:var(--font-size-16)}}
#design-picker .pick-layout{{display:grid;grid-template-columns:minmax(0,1fr) 235px;gap:var(--spacing-16);height:60vh;min-height:300px}}
#design-picker .pick-pair{{display:grid;grid-template-columns:1fr 1fr;gap:var(--spacing-12);min-height:0;min-width:0}}
#design-picker .pick-pair section{{display:flex;flex-direction:column;min-height:0;min-width:0;background:var(--color-surface-default);border:1px solid var(--color-border-subtle);border-radius:var(--radius-10);overflow:hidden}}
#design-picker .pick-pair h3,#design-picker .pick-pair p{{padding:var(--spacing-8) var(--spacing-12);margin:0;font-size:var(--font-size-12);flex:none}}
#design-picker .pick-image{{flex:1;min-height:0;display:flex;justify-content:center;background:var(--color-bg-subtle)}}
#design-picker .pick-image img{{width:100%;height:100%;object-fit:contain}}
#design-picker .pick-list{{overflow-y:auto;min-height:0;font-size:var(--font-size-12)}}#design-picker .pick-list p{{color:var(--color-text-caption)}}
#design-picker label.pick-option{{display:flex;align-items:center;gap:var(--spacing-8);padding:var(--spacing-10);background:var(--color-surface-default);border:1px solid var(--color-border-subtle);border-radius:var(--radius-8);margin:var(--spacing-8) 0;cursor:pointer}}
#design-picker .pick-option:has(input:checked){{border-color:var(--color-action-primary-default);background:var(--color-action-primary-subtle)}}#design-picker input[type=radio]{{width:auto;flex:none}}
#design-picker .pick-footer{{position:sticky;bottom:-18px;background:var(--color-bg-subtle);padding:var(--spacing-10) 0;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:var(--spacing-12);margin-top:var(--spacing-12);font-size:var(--font-size-12)}}
#design-picker .pick-footer button{{background:var(--color-text-primary);color:var(--color-surface-default)}}#design-picker .pick-note{{font-size:var(--font-size-12);color:var(--color-text-caption);margin:var(--spacing-10) 0}}
@media(max-width:900px){{#design-picker .pick-layout{{grid-template-columns:1fr;height:auto}}#design-picker .pick-pair{{height:50vh}}#design-picker .pick-list{{max-height:110px}}}}
</style><div class="s1-modal-inset"><div class="dialog-head"><h2>디자인·개발 대조</h2><button type="button" onclick="document.getElementById('design-picker').close()">닫기</button></div><p class="pick-note">{"초기 추천 이유: "+e(reason) if reason else "디자인을 바꿔도 개발 촬영본은 고정됩니다."}</p>{form(f'/intake/{batch}/select',body)}<details><summary>목록에 없는 Figma 시안 가져오기</summary>{linkform}<details><summary>Figma 읽기 연결 설정</summary>{setting}</details></details></div></dialog><script>
(function(){{const picker=document.getElementById('design-picker');picker.addEventListener('close',function(){{const form=picker.querySelector('form');if(form)form.reset();const radio=picker.querySelector('input[name=design]:checked');if(radio){{const img=document.getElementById('pick-design-image');if(img)img.src=radio.dataset.src;document.getElementById('pick-design-name').textContent=radio.dataset.name;}}}});picker.addEventListener('change',function(event){{const radio=event.target;if(radio.name!=='design')return;const img=document.getElementById('pick-design-image');if(img)img.src=radio.dataset.src;document.getElementById('pick-design-name').textContent=radio.dataset.name;}});}})();
</script>'''
