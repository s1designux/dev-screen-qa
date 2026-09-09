"""Server-rendered intake screens: browser holds no authoritative state."""
import html
import json
from urllib.parse import quote
import figma_reader


def e(v):
    return html.escape(str(v if v is not None else ''))


STATUS={'unlinked':'디자인 미연결','pending':'짝 확인 대기','confirmed':'짝 확인됨','held':'보류','excluded':'이번 연결 제외'}
CSS='''
*{box-sizing:border-box}body{margin:0;background:#f6f7f9;color:#1d2738;font:14px -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif}a{color:inherit;text-decoration:none}header{background:white;border-bottom:1px solid #e4e7ec;padding:18px 30px;display:flex;align-items:center;gap:24px}header strong{font-size:18px}nav{margin-left:auto;display:flex;gap:20px;color:#586478}main{max-width:1320px;margin:auto;padding:28px 30px 70px}h1{font-size:25px;margin:0 0 10px}h2{font-size:17px;margin:0 0 16px}h3{font-size:14px;margin:0 0 12px}p{line-height:1.6}.muted,small{color:#657085}.sub{margin:0 0 24px;color:#657085}.card{background:white;border:1px solid #e1e6ed;border-radius:12px;padding:22px;margin:18px 0}.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.spread{justify-content:space-between}.button,button{display:inline-block;border:1px solid #ced5df;border-radius:8px;background:white;padding:10px 16px;font:inherit;cursor:pointer;white-space:nowrap}.primary{background:#245be5;border-color:#245be5;color:white}button:disabled{opacity:.45;cursor:not-allowed}.badge{display:inline-block;font-size:12px;border-radius:6px;background:#edf0f5;padding:4px 8px;color:#586478}.confirmed{background:#e8f6ed;color:#1a7146}.pending{background:#eaf0ff;color:#245be5}.held,.error{background:#fff3e5;color:#965219}.notice{padding:14px 18px;border-radius:8px;background:#eaf0ff;margin:14px 0;line-height:1.6}.notice.error{background:#fff1ed;color:#a12d19}label{display:block;font-size:13px;color:#586478;margin:8px 0}input:not([type=checkbox]),select,textarea{border:1px solid #ccd4df;border-radius:7px;background:white;font:inherit;padding:9px 11px;max-width:100%;width:100%;color:#1d2738}input[type=file]{padding:16px;background:#f9fafc}input:focus,select:focus,textarea:focus{outline:2px solid #8cabfa}textarea{min-height:65px}.field{flex:1;min-width:180px}.drop{border:1px dashed #a8b7cd;padding:22px;border-radius:10px;background:#fafcff;margin:18px 0}.steps{display:flex;gap:20px;margin:0 0 25px;color:#68748a;font-size:13px}.steps b{color:#245be5}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #edf0f4}th{font-size:12px;color:#647084}.thumb{width:42px;height:82px;object-fit:contain;background:#eef1f5;border-radius:4px}.intake-item{display:grid;grid-template-columns:60px 1fr 1fr 1fr 190px;gap:16px;align-items:start;border-top:1px solid #e8ecf1;padding:18px 0}.intake-item input{font-size:13px}.intake-item small{display:block;margin-top:8px;overflow-wrap:anywhere}.workspace{display:grid;grid-template-columns:225px minmax(0,1fr);gap:22px}.states{background:white;border:1px solid #e1e6ed;border-radius:10px;padding:8px;align-self:start}.state{display:block;padding:13px;border-radius:7px;border:1px solid transparent;margin-bottom:5px}.state.active{border-color:#b5c9fc;background:#eef3ff}.state small{display:block;margin-top:6px}.compare{display:grid;grid-template-columns:1fr 1fr;gap:18px}.pane{background:white;border:1px solid #e1e6ed;border-radius:10px;overflow:hidden}.pane h3{padding:14px 18px;margin:0;border-bottom:1px solid #edf0f4}.canvas{height:540px;background:#edf0f5;padding:16px;display:flex;align-items:center;justify-content:center}.canvas img{width:100%;height:100%;object-fit:contain}.canvas .empty{max-width:230px;text-align:center;color:#758098;line-height:1.7}.caption{font-size:12px;padding:10px 16px;color:#657085;overflow-wrap:anywhere}.designs{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}.designs form{border:1px solid #e1e6ed;border-radius:8px;padding:10px}.designs img{width:100%;height:170px;object-fit:contain;background:#f4f6f9}.designs p{font-size:12px;min-height:36px}.designs button{width:100%;font-size:12px}.actions{position:sticky;bottom:0;background:rgba(246,247,249,.96);padding:16px 0;margin-top:12px;z-index:2}.section-link{color:#245be5}.count{font-size:30px;font-weight:650}details{margin:16px 0}summary{cursor:pointer;color:#56657a}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:#586478}.history{font-size:12px}.history li{padding:8px 0;line-height:1.7}.spacer{flex:1}@media(max-width:850px){main{padding:20px 16px}.workspace{grid-template-columns:1fr}.states{display:flex;overflow:auto}.state{min-width:155px}.intake-item{grid-template-columns:45px 1fr}.intake-item>*:last-child{grid-column:2}.canvas{height:420px}.row{align-items:stretch}header{padding:15px}nav{gap:10px;font-size:12px}}@media(max-width:520px){.compare{grid-template-columns:1fr}.steps{gap:10px;font-size:11px}}
'''


def page(title,body,notice='',error=False):
    banner=f'<div class="notice {"error" if error else ""}" role="status">{e(notice)}</div>' if notice else ''
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} · 검수 포털</title><style>{CSS}</style></head><body><header><strong>검수 포털</strong><nav><a href="/">화면 목록</a><a href="/intake">가져온 기록</a><a href="/intake/new">촬영본 가져오기</a></nav></header><main>{banner}{body}</main></body></html>'''


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
    return page('검수 페이지 목록',f'''<div class="row"><a class="section-link" href="/">← 화면 목록</a><h1 style="font-size:18px;margin:0">{e(selected['screen_name'])}</h1><span class="muted">공식 번호 미정 · {e(b['platform'])}</span></div><section class="card" style="max-width:1040px;margin:24px auto"><div class="row spread"><h2>검수 페이지 · {len(active)}개</h2><a class="button" href="/intake/{batch}">촬영본 이름·대상 관리</a></div><p class="muted">같은 화면의 상태·단계를 선택하세요. 재검수 차수는 각 페이지 안에서 확인합니다.</p><table><thead><tr><th>순번</th><th>검수 페이지</th><th>디자인 연결</th><th>Pass/Fail</th><th>미해결 / 전체</th><th></th></tr></thead><tbody>{rows}</tbody></table>{extra}</section>''',notice,error)


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
#design-picker{{width:96vw;max-width:1500px;height:92vh;max-height:92vh;box-sizing:border-box;padding:18px;overflow:auto;background:#f6f7f9}}
#design-picker .dialog-head{{display:flex;align-items:center;justify-content:space-between;gap:12px}}#design-picker h2{{margin:0;font-size:17px}}
#design-picker .pick-layout{{display:grid;grid-template-columns:minmax(0,1fr) 235px;gap:16px;height:60vh;min-height:300px}}
#design-picker .pick-pair{{display:grid;grid-template-columns:1fr 1fr;gap:12px;min-height:0;min-width:0}}
#design-picker .pick-pair section{{display:flex;flex-direction:column;min-height:0;min-width:0;background:white;border:1px solid #e1e6ed;border-radius:10px;overflow:hidden}}
#design-picker .pick-pair h3,#design-picker .pick-pair p{{padding:8px 12px;margin:0;font-size:12px;flex:none}}
#design-picker .pick-image{{flex:1;min-height:0;display:flex;justify-content:center;background:#f0f2f5}}
#design-picker .pick-image img{{width:100%;height:100%;object-fit:contain}}
#design-picker .pick-list{{overflow-y:auto;min-height:0;font-size:12px}}#design-picker .pick-list p{{color:#657085}}
#design-picker label.pick-option{{display:flex;align-items:center;gap:8px;padding:10px;background:white;border:1px solid #e1e6ed;border-radius:8px;margin:7px 0;cursor:pointer}}
#design-picker .pick-option:has(input:checked){{border-color:#2563eb;background:#eff6ff}}#design-picker input[type=radio]{{width:auto;flex:none}}
#design-picker .pick-footer{{position:sticky;bottom:-18px;background:#f6f7f9;padding:10px 0;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px;font-size:12px}}
#design-picker .pick-footer button{{background:#111827;color:white}}#design-picker .pick-note{{font-size:12px;color:#657085;margin:10px 0}}
@media(max-width:900px){{#design-picker .pick-layout{{grid-template-columns:1fr;height:auto}}#design-picker .pick-pair{{height:50vh}}#design-picker .pick-list{{max-height:110px}}}}
</style><div class="dialog-head"><h2>디자인·개발 대조</h2><button type="button" onclick="document.getElementById('design-picker').close()">닫기</button></div><p class="pick-note">{"초기 추천 이유: "+e(reason) if reason else "디자인을 바꿔도 개발 촬영본은 고정됩니다."}</p>{form(f'/intake/{batch}/select',body)}<details><summary>목록에 없는 Figma 시안 가져오기</summary>{linkform}<details><summary>Figma 읽기 연결 설정</summary>{setting}</details></details></dialog><script>
(function(){{const picker=document.getElementById('design-picker');picker.addEventListener('close',function(){{const form=picker.querySelector('form');if(form)form.reset();const radio=picker.querySelector('input[name=design]:checked');if(radio){{const img=document.getElementById('pick-design-image');if(img)img.src=radio.dataset.src;document.getElementById('pick-design-name').textContent=radio.dataset.name;}}}});picker.addEventListener('change',function(event){{const radio=event.target;if(radio.name!=='design')return;const img=document.getElementById('pick-design-image');if(img)img.src=radio.dataset.src;document.getElementById('pick-design-name').textContent=radio.dataset.name;}});}})();
</script>'''
