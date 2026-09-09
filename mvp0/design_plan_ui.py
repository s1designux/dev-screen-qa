"""Design-led pages, reusing the portal detail renderer."""
import json
from pathlib import Path
from intake_ui import e, hidden, form, page
from design_plan import Plans,LABEL


def listing(store,plan,notice=''):
    p,rows=Plans(store).get(plan);body=''
    for r in rows:
        href=f'/design/{plan}/case/{r["id"]}'
        remove=form(href+'/exclude',hidden('revision',r['revision'])+'<button>목록에서 제외</button>')
        body+=f'<tr><td>{r["seq"]}</td><td><img class="thumb" src="/uploads/{e(r["design_file"])}" alt="{e(r["name"])}"></td><td><a class="section-link" href="{href}"><b>{e(r["name"])}</b></a><small style="display:block">{e(r["expected"])}</small></td><td><span class="badge">{LABEL[r["status"]]}</span></td><td>{e(r["capture_name"] or "대응 캡처 없음")}</td><td><a class="button" href="{href}">TC·대조</a>{remove}</td></tr>'
    return page('디자인 기준 검수 페이지',f'<a class="section-link" href="/">← 화면 목록</a><h1>{e(p["name"])}</h1><p>디자인 원본 {len(rows)}개 → TC → 개발 촬영 → 매칭 확인</p><p class="muted">{e(p["source_note"])}</p><a class="button" href="/design/{plan}/manage">디자인 추가·복원</a> <a class="button primary" href="/design/{plan}/queue">추가 촬영 대기 {sum(r["status"]=="required" for r in rows)}건</a> <a class="button" href="/intake/{p["batch_id"]}">기존 촬영 원본·연결 이력</a><section class="card"><table><thead><tr><th>순서</th><th>원본</th><th>디자인 기준 페이지</th><th>촬영·매칭</th><th>개발 캡처</th><th></th></tr></thead><tbody>{body}</tbody></table></section>',notice)


def detail(store,plan,case,notice='',sel_round=None):
    import portal
    plans=Plans(store);p,r=plans.case(plan,case)
    if r['excluded']:return page('제외한 디자인',f'<h1>{e(r["name"])}</h1><p>목록에서 제외했습니다. 원본과 검수 이력은 보존되어 있습니다.</p><a href="/design/{plan}/manage">디자인 복원</a>')
    b,_,_=store.batch(p['batch_id']);b=dict(b)
    synthetic={'id':case,'batch_id':p['batch_id'],'state_name':r['name'],'screen_name':p['name'],'design_file':r['design_file'],'design_id':r['design_id'],'design_name':r['name'],'filename':r['capture_file'],'width':r['width'],'height':r['height'],'source_url':r['source_url'],'fetched_at':r['fetched_at'],'status':'confirmed' if r['status']=='confirmed' else 'pending','revision':r['revision'],'page_id':r['page_id'],'error':''}
    controls=hidden('revision',r['revision'])
    selection_controls=controls+(hidden('keep_request','1') if r['status']=='required' else '')
    base=f'/design/{plan}/case/{case}'
    top=f'<div class="connection-controls"><span class="chip">{LABEL[r["status"]]}</span><span>{e(r["match_note"] if r["status"]!="required" else r["request_reason"])}</span>'
    if r['status']=='pending':top+=form(base+'/confirm',controls+'<button>TC와 같은 상태 · 짝 확인</button>')
    top+=f'<a href="/design/{plan}/queue">추가 촬영 대기</a></div>'
    tc=f'<section class="issue"><b>TC · 촬영 절차</b><p style="white-space:pre-wrap">{e(r["tc"])}</p><b>기대 모습</b><p>{e(r["expected"])}</p><p class="muted">{e(r["prerequisite"])}</p><details><summary>TC 수정</summary>'+form(base+'/tc',controls+f'<label>촬영 절차<textarea name="tc" required>{e(r["tc"])}</textarea></label><label>기대 모습<textarea name="expected" required>{e(r["expected"])}</textarea></label><label>준비 조건<textarea name="prerequisite">{e(r["prerequisite"])}</textarea></label><button>TC 저장</button>')+'</details>'
    if not r['page_id']:
        tc+='<details><summary>TC에 맞지 않음 · 추가 촬영 요청</summary>'+form(base+'/request',controls+'<label>추가 촬영 사유<textarea name="reason" required>디자인과 같은 입력·포커스·언어·오류 상태로 다시 촬영해 주세요.</textarea></label><button>촬영 대기에 추가</button>')+'</details>'
        tc+=f'<details {"open" if r["status"]=="required" else ""}><summary>추가 촬영본 등록</summary><form method="post" enctype="multipart/form-data" action="{base}/upload">{controls}<label>TC대로 촬영한 PNG<input type="file" name="capture" accept="image/png" required></label><button>촬영본 가져와 대조</button></form></details>'
    if r['status']=='pending':tc+=form(base+'/confirm',controls+'<button>이 캡처로 검수 시작</button>')
    tc+='</section>'
    caps=plans.captures(plan);options=''
    for cap in sorted(caps,key=lambda x:(x['id']!=r['capture_id'],x['case_id']!=case,x['name'])):
        options+=f'<label class="cap-option"><input type="radio" name="capture" value="{cap["id"]}" data-src="/uploads/{e(cap["filename"])}" data-name="{e(cap["name"])}" {"checked" if cap["id"]==r["capture_id"] else ""}><span class="rank">비교 중</span><span>{e(cap["name"])}</span></label>'
    pic=f'<img id="plan-capture-preview" src="/uploads/{e(r["capture_file"])}" alt="선택한 개발 캡처">' if r['capture_file'] else '<img id="plan-capture-preview" alt="아래에서 개발 캡처를 선택하세요.">'
    dialog=f'''<dialog id="capture-picker"><div class="dialog-head"><h2>디자인에 맞는 개발 캡처</h2><button type="button" onclick="document.getElementById('capture-picker').close()">닫기</button></div><p class="recommendation-status" role="status">유사한 개발 캡처를 찾고 있습니다…</p><div class="capture-pair"><section><h3>디자인 원본</h3><img class="design-original" src="/uploads/{e(r['design_file'])}" alt="디자인 원본"></section><section><h3>개발 캡처</h3>{pic}</section></div>{form(base+'/select',selection_controls+f'<div class="capture-options">{options}</div><div class="capture-footer"><button {"disabled" if not caps else ""}>이 개발 화면으로 변경</button></div>')}</dialog><script>{Path(__file__).with_name('capture_recommendation.js').read_text()}</script>'''
    _,active=plans.get(plan)
    position=next(i for i,item in enumerate(active) if item['id']==case)
    def step_link(offset,label):
        target=position+offset
        if not 0<=target<len(active):return f'<span class="page-step disabled" aria-disabled="true">{label}</span>'
        item=active[target]
        return f'<a class="page-step" href="/design/{plan}/case/{item["id"]}" title="{e(item["name"])}">{label}</a>'
    navigation=f'<nav class="page-navigation" aria-label="검수 페이지 이동">{step_link(-1,"← 이전")}<span>{position+1} / {len(active)}</span>{step_link(1,"다음 →")}</nav>'
    workflow={'navigation':navigation,'row':synthetic,'controls':top,'dialog':dialog,'sidebar':tc,'parent':f'/design/{plan}','base':base}
    return portal.render_page(r['page_id'] or case,sel_round=sel_round,notice=notice,store=store,draft=None if r['page_id'] else (b,synthetic),workflow=workflow)


def queue_page(store,plan):
    q=Plans(store).queue(plan);cards=''
    for r in q['cases']:
        cards+=f'<section class="card"><h2>{r["seq"]}. {e(r["design_name"])}</h2><p><b>추가 촬영 사유:</b> {e(r["reason"])}</p><p style="white-space:pre-wrap">{e(r["steps"])}</p><p><b>기대 모습:</b> {e(r["expected"])}</p><p class="muted">{e(r["prerequisite"])}</p><a class="button" href="/design/{plan}/case/{r["case_id"]}">시안 보기·촬영 결과 등록</a></section>'
    return page('추가 촬영 대기',f'<a href="/design/{plan}">← 디자인 기준 목록</a><h1>추가 촬영 대기 · {len(q["cases"])}건</h1><p>TC대로 상태를 만든 뒤 촬영합니다. 결과를 등록해도 작업자가 짝을 확인할 때까지 대기 상태입니다.</p><a class="button primary" href="/design/{plan}/bundle">TC·디자인·촬영 도우미 내려받기</a><form method="post" enctype="multipart/form-data" action="/design/{plan}/import"><label>촬영 결과 가져오기 · PNG와 찍은목록.json<input type="file" name="files" multiple required accept="image/png,.json"></label><button>TC별로 가져오기</button></form><p class="muted">도우미는 사람이 TC대로 조작한 뒤 현재 Android 화면을 촬영합니다. 입력이나 로그인 실패를 자동으로 실행하지 않습니다. 파일 묶음의 사용안내를 확인하세요.</p>{cards or "<p>추가 촬영 대기가 없습니다.</p>"}')


def new_plan(store):
    options=''.join(f'<option value="{e(p["uuid"])}">{e(p["name"])}</option>' for p in store.projects())
    rows=''
    for d in store.designs():
        rows+=f'<tr><td><img class="thumb" src="/uploads/{e(d["filename"])}" alt="{e(d["name"])}"></td><td>{e(d["name"])}</td><td><input type="number" min="1" name="order_{d["id"]}" aria-label="{e(d["name"])} 순서" placeholder="빈 칸은 제외"></td></tr>'
    return page('디자인부터 검수 준비', '<h1>디자인부터 검수 준비</h1><p>촬영본이 없어도 시작할 수 있습니다. 가져온 시안 중 등록할 시안의 순서를 입력하세요.</p>'+form('/design/create',f'<section class="card"><label>프로젝트<select name="project">{options}</select></label><label>화면 이름<input name="name" required maxlength="120"></label><label>플랫폼<select name="platform"><option value="android">Android</option><option value="ios">iOS</option><option value="web">PC 웹</option><option value="mobile-web">모바일 웹</option></select></label><table><thead><tr><th>원본</th><th>시안</th><th>순서</th></tr></thead><tbody>{rows}</tbody></table><button class="primary">디자인 순서대로 TC 준비</button></section>'))


def manage(store,plan):
    p,rows=Plans(store).get(plan,include_excluded=True)
    registered={r['design_id'] for r in rows}
    available=''
    for d in store.designs():
        if d['id'] in registered:continue
        available+=f'<section class="card"><img class="thumb" src="/uploads/{e(d["filename"])}" alt="{e(d["name"])}"><b>{e(d["name"])}</b>'+form(f'/design/{plan}/add',hidden('design',d['id'])+'<button>이 디자인 추가</button>')+'</section>'
    removed=''
    for r in rows:
        if not r['excluded']:continue
        removed+=f'<section class="card"><img class="thumb" src="/uploads/{e(r["design_file"])}" alt="{e(r["name"])}"><b>{e(r["name"])}</b>'+form(f'/design/{plan}/case/{r["id"]}/restore',hidden('revision',r['revision'])+'<button>목록으로 복원</button>')+'</section>'
    return page('디자인 추가·복원',f'<a href="/design/{plan}">← 디자인 기준 목록</a><h1>디자인 추가·복원</h1><p>추가한 디자인은 목록 마지막에 놓이고 TC 초안이 만들어집니다. 제외해도 원본·촬영본·검수 이력은 보존됩니다.</p><h2>제외한 디자인</h2>{removed or "<p>제외한 디자인이 없습니다.</p>"}<h2>새 디자인 원본 추가</h2><form method="post" enctype="multipart/form-data" action="/design/{plan}/upload-design"><label>디자인 화면 이름<input name="name" required maxlength="120"></label><label>디자인 원본 PNG<input type="file" name="design" accept="image/png" required></label><button>새 디자인 추가</button></form><h2>가져온 디자인에서 추가</h2>{available or "<p>가져온 디자인이 모두 등록되어 있습니다.</p>"}')
