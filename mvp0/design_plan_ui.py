"""Design-led pages, reusing the portal detail renderer."""
import json
from pathlib import Path
from intake_ui import e, hidden, form, page
from design_plan import Plans,LABEL
import s1


def listing(store,plan,notice=''):
    p,rows=Plans(store).get(plan);body=''
    for r in rows:
        href=f'/design/{plan}/case/{r["id"]}'
        remove=form(href+'/exclude',hidden('revision',r['revision'])+s1.단추('목록에서 제외',종류='submit'))
        body+=s1.줄([str(r["seq"]),
                     f'<img class="thumb" src="/uploads/{e(r["design_file"])}" alt="{e(r["name"])}">',
                     f'<a class="section-link" href="{href}"><b>{e(r["name"])}</b></a>'
                     f'<small style="display:block">{e(r["expected"])}</small>',
                     s1.이름표(LABEL[r["status"]]),
                     e(r["capture_name"] or "대응 캡처 없음"),
                     s1.단추링크('TC·대조',href)+remove])
    단추줄 = (s1.단추링크('디자인 추가·복원', '/design/%s/manage' % plan) + ' '
            + s1.단추링크('추가 촬영 대기 %d건' % sum(x["status"] == "required" for x in rows),
                       '/design/%s/queue' % plan, 'primary') + ' '
            + s1.단추링크('기존 촬영 원본·연결 이력', '/intake/%s' % p["batch_id"]))
    표 = (s1.표머리(['순서', '원본', '디자인 기준 페이지', '촬영·매칭', '개발 캡처', ''])
         + body + s1.표꼬리())
    return page('디자인 기준 검수 페이지',f'<a class="section-link" href="/">← 화면 목록</a><h1>{e(p["name"])}</h1><p>디자인 원본 {len(rows)}개 → TC → 개발 촬영 → 매칭 확인</p><p class="muted">{e(p["source_note"])}</p>{단추줄}<section class="card">{표}</section>',notice)


def detail(store,plan,case,notice='',sel_round=None):
    import portal
    plans=Plans(store);p,r=plans.case(plan,case)
    if r['excluded']:return page('제외한 디자인',f'<h1>{e(r["name"])}</h1><p>목록에서 제외했습니다. 원본과 검수 이력은 보존되어 있습니다.</p><a href="/design/{plan}/manage">디자인 복원</a>')
    b,_,_=store.batch(p['batch_id']);b=dict(b)
    synthetic={'id':case,'batch_id':p['batch_id'],'state_name':r['name'],'screen_name':p['name'],'design_file':r['design_file'],'design_id':r['design_id'],'design_name':r['name'],'filename':r['capture_file'],'width':r['width'],'height':r['height'],'source_url':r['source_url'],'fetched_at':r['fetched_at'],'status':'confirmed' if r['status']=='confirmed' else 'pending','revision':r['revision'],'page_id':r['page_id'],'error':''}
    controls=hidden('revision',r['revision'])
    selection_controls=controls+(hidden('keep_request','1') if r['status']=='required' else '')
    base=f'/design/{plan}/case/{case}'
    top=f'<div class="connection-controls">{s1.이름표(LABEL[r["status"]])}<span>{e(r["match_note"] if r["status"]!="required" else r["request_reason"])}</span>'
    if r['status']=='pending':top+=form(base+'/confirm',controls+s1.단추('시안과 같은 상태 · 짝 확인',종류='submit'))
    top+=f'<a href="/design/{plan}/queue">추가 촬영 대기</a></div>'
    tc='<section class="issue">' if not r['page_id'] else ''
    if not r['page_id']:
        tc+=('<details><summary>시안과 다름 · 추가 촬영 요청</summary>'
             +form(base+'/request',controls+'<label for="plan-reason">추가 촬영 사유</label>'
                   +s1.여러줄('reason','디자인과 같은 입력·포커스·언어·오류 상태로 다시 촬영해 주세요.',
                            칸id='plan-reason',required=True)
                   +s1.단추('촬영 대기에 추가',종류='submit'))+'</details>')
        # DESIGN_SYSTEM_GAP: 정본에 '파일 고르기' 부품이 없다 — 브라우저 기본 칸을 쓴다.
        tc+=(f'<details {"open" if r["status"]=="required" else ""}><summary>추가 촬영본 등록</summary>'
             f'<form method="post" enctype="multipart/form-data" action="{base}/upload">{controls}'
             '<label for="plan-capture">디자인 시안과 같은 상태의 PNG</label>'
             '<input class="filepick" id="plan-capture" type="file" name="capture" accept="image/png" required>'
             +s1.단추('촬영본 가져와 대조',종류='submit')+'</form></details>')
    if r['status']=='pending':tc+=form(base+'/confirm',controls+s1.단추('이 캡처로 검수 시작',종류='submit'))
    if not r['page_id']:tc+='</section>'
    caps=plans.captures(plan);options=''
    for cap in sorted(caps,key=lambda x:(x['id']!=r['capture_id'],x['case_id']!=case,x['name'])):
        options+=('<div class="cap-option"><span class="rank">비교 중</span>'
                  +s1.라디오('capture','cap-%s'%cap["id"],cap["name"],
                           켬=cap["id"]==r["capture_id"],값=cap["id"],
                           **{'data-src':'/uploads/'+cap["filename"],'data-name':cap["name"]})
                  +'</div>')
    pic=f'<img id="plan-capture-preview" src="/uploads/{e(r["capture_file"])}" alt="선택한 개발 캡처">' if r['capture_file'] else '<img id="plan-capture-preview" alt="아래에서 개발 캡처를 선택하세요.">'
    comparison=f'<div class="capture-layout"><div class="capture-pair"><section><h3>디자인 원본</h3><div class="capture-image"><img class="design-original" src="/uploads/{e(r["design_file"])}" alt="디자인 원본"></div></section><section><h3>개발 화면</h3><div class="capture-image">{pic}</div></section></div><aside class="capture-list"><b>다른 개발 화면 둘러보기</b><div class="capture-options">{options}</div></aside></div>'
    속=('<p class="recommendation-status" role="status">유사한 개발 캡처를 찾고 있습니다…</p>'
       +form(base+'/select',selection_controls+comparison
             +'<div class="capture-footer">'
             +s1.단추('이 개발 화면으로 변경','primary',종류='submit',disabled=(not caps) or None)
             +'</div>'))
    dialog=(s1.대화창('capture-picker','디자인·개발 대조',속)
            +'<script>'+Path(__file__).with_name('capture_recommendation.js').read_text()+'</script>')
    _,active=plans.get(plan)
    position=next(i for i,item in enumerate(active) if item['id']==case)
    def step_link(offset,label):
        target=position+offset
        if not 0<=target<len(active):return s1.단추(label,disabled=True)
        item=active[target]
        return s1.단추링크(label,f'/design/{plan}/case/{item["id"]}',title=e(item["name"]))
    navigation=f'<nav class="page-navigation" aria-label="검수 페이지 이동">{step_link(-1,"← 이전")}<span>{position+1} / {len(active)}</span>{step_link(1,"다음 →")}</nav>'
    workflow={'navigation':navigation,'row':synthetic,'controls':top,'dialog':dialog,'sidebar':tc,'parent':f'/design/{plan}','base':base}
    return portal.render_page(r['page_id'] or case,sel_round=sel_round,notice=notice,store=store,draft=None if r['page_id'] else (b,synthetic),workflow=workflow)


def queue_page(store,plan):
    q=Plans(store).queue(plan);cards=''
    for r in q['cases']:
        시안단추 = s1.단추링크('시안 보기·촬영 결과 등록', '/design/%s/case/%s' % (plan, r["case_id"]))
        cards+=f'<section class="card"><h2>{r["seq"]}. {e(r["design_name"])}</h2><p><b>추가 촬영 사유:</b> {e(r["reason"])}</p><p style="white-space:pre-wrap">{e(r["steps"])}</p><p><b>기대 모습:</b> {e(r["expected"])}</p><p class="muted">{e(r["prerequisite"])}</p>{시안단추}</section>'
    묶음단추 = s1.단추링크('TC·디자인·촬영 도우미 내려받기', '/design/%s/bundle' % plan, 'primary')
    가져오기단추 = s1.단추('TC별로 가져오기', 종류='submit')
    return page('추가 촬영 대기',f'<a href="/design/{plan}">← 디자인 기준 목록</a><h1>추가 촬영 대기 · {len(q["cases"])}건</h1><p>TC대로 상태를 만든 뒤 촬영합니다. 결과를 등록해도 작업자가 짝을 확인할 때까지 대기 상태입니다.</p>{묶음단추}<form method="post" enctype="multipart/form-data" action="/design/{plan}/import"><label for="plan-import">촬영 결과 가져오기 · PNG와 찍은목록.json</label><input class="filepick" id="plan-import" type="file" name="files" multiple required accept="image/png,.json">{가져오기단추}</form><p class="muted">도우미는 사람이 TC대로 조작한 뒤 현재 Android 화면을 촬영합니다. 입력이나 로그인 실패를 자동으로 실행하지 않습니다. 파일 묶음의 사용안내를 확인하세요.</p>{cards or "<p>추가 촬영 대기가 없습니다.</p>"}')


def new_plan(store):
    프로젝트보기=[(x["uuid"],x["name"]) for x in store.projects()]
    자리보기=[('android','Android'),('ios','iOS'),('web','PC 웹'),('mobile-web','모바일 웹')]
    rows=''
    for d in store.designs():
        rows+=s1.줄([f'<img class="thumb" src="/uploads/{e(d["filename"])}" alt="{e(d["name"])}">',
                     e(d["name"]),
                     s1.입력('order_%s'%d["id"],'',종류='number',min='1',자리글='빈 칸은 제외',
                            **{'aria-label':'%s 순서'%e(d["name"])})])
    속=('<section class="card"><label>프로젝트</label>'
       +s1.고르개('project',프로젝트보기,프로젝트보기[0][0] if 프로젝트보기 else '')
       +'<label for="plan-name">화면 이름</label>'
       +s1.입력('name','',칸id='plan-name',required=True,maxlength='120')
       +'<label>플랫폼</label>'+s1.고르개('platform',자리보기,'android')
       +s1.표머리(['원본','시안','순서'])+rows+s1.표꼬리()
       +s1.단추('디자인 순서대로 TC 준비','primary',종류='submit')+'</section>')
    return page('디자인부터 검수 준비', '<h1>디자인부터 검수 준비</h1><p>촬영본이 없어도 시작할 수 있습니다. 가져온 시안 중 등록할 시안의 순서를 입력하세요.</p>'+form('/design/create',속))


def manage(store,plan):
    p,rows=Plans(store).get(plan,include_excluded=True)
    registered={r['design_id'] for r in rows}
    available=''
    for d in store.designs():
        if d['id'] in registered:continue
        available+=f'<section class="card"><img class="thumb" src="/uploads/{e(d["filename"])}" alt="{e(d["name"])}"><b>{e(d["name"])}</b>'+form(f'/design/{plan}/add',hidden('design',d['id'])+s1.단추('이 디자인 추가',종류='submit'))+'</section>'
    removed=''
    for r in rows:
        if not r['excluded']:continue
        removed+=f'<section class="card"><img class="thumb" src="/uploads/{e(r["design_file"])}" alt="{e(r["name"])}"><b>{e(r["name"])}</b>'+form(f'/design/{plan}/case/{r["id"]}/restore',hidden('revision',r['revision'])+s1.단추('목록으로 복원',종류='submit'))+'</section>'
    이름칸 = s1.입력('name', '', 칸id='dsg-name', required=True, maxlength='120')
    추가단추 = s1.단추('새 디자인 추가', 종류='submit')
    return page('디자인 추가·복원',f'<a href="/design/{plan}">← 디자인 기준 목록</a><h1>디자인 추가·복원</h1><p>추가한 디자인은 목록 마지막에 놓입니다. 제외해도 원본·촬영본·검수 이력은 그대로 남습니다.</p><h2>제외한 디자인</h2>{removed or "<p>제외한 디자인이 없습니다.</p>"}<h2>새 디자인 원본 추가</h2><form method="post" enctype="multipart/form-data" action="/design/{plan}/upload-design"><label for="dsg-name">디자인 화면 이름</label>{이름칸}<label for="dsg-file">디자인 원본 PNG</label><input class="filepick" id="dsg-file" type="file" name="design" accept="image/png" required>{추가단추}</form><h2>가져온 디자인에서 추가</h2>{available or "<p>가져온 디자인이 모두 등록되어 있습니다.</p>"}')
