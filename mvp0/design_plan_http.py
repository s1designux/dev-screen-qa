import io,json,re,zipfile
from pathlib import Path
from urllib.parse import parse_qs
import intake_http
import design_plan_ui as ui
from design_plan import Plans


def get(handler,store,path):
    plans=Plans(store);parts=path.strip('/').split('/')
    try:
        if path=='/design/new':handler._html(ui.new_plan(store));return
        plan=parts[1];plans.get(plan)
        if len(parts)==2:handler._html(ui.listing(store,plan))
        elif len(parts)==4 and parts[2]=='case':handler._html(ui.detail(store,plan,parts[3]))
        elif len(parts)==3 and parts[2]=='manage':handler._html(ui.manage(store,plan))
        elif len(parts)==3 and parts[2]=='queue':handler._html(ui.queue_page(store,plan))
        elif len(parts)==3 and parts[2]=='bundle':
            q=plans.queue(plan);buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('촬영요청.json',json.dumps(q,ensure_ascii=False,indent=2));z.write(Path(__file__).with_name('capture_tc.py'),'capture_tc.py')
                z.writestr('사용안내.txt','디자인별 TC 촬영 요청\n1. 촬영요청.json과 디자인 폴더에서 목표 모습을 확인합니다.\n2. Android 기기를 연결하고 잠금을 해제합니다. adb가 설치된 PC에서 python3 capture_tc.py 를 실행합니다.\n3. TC대로 직접 조작한 뒤 Enter를 누릅니다. 도우미는 화면 촬영만 하며 입력·로그인·계정 잠금은 자동 실행하지 않습니다. 준비 조건이 충족되지 않으면 s로 건너뜁니다.\n4. shots 폴더의 PNG와 찍은목록.json을 포털의 촬영 결과 가져오기로 등록합니다.\n5. 포털에서 시안과 맞는지 확인합니다. 오류는 자동 확정하지 않습니다.\niOS는 TC대로 수동 촬영한 PNG를 각 페이지에 등록하세요.\n')
                _,cases=plans.get(plan)
                for r in cases:
                    if r['status']=='required':z.write(store.uploads/r['design_file'],f'디자인/{r["seq"]:02d}-{r["id"]}.png')
            data=buf.getvalue();handler.send_response(200);handler.send_header('Content-Type','application/zip');handler.send_header('Content-Disposition','attachment; filename="design-capture-tc.zip"');handler.send_header('Content-Length',str(len(data)));handler.end_headers();handler.wfile.write(data)
        else:raise ValueError('페이지를 찾을 수 없습니다.')
    except (ValueError,IndexError) as ex:handler._html(ui.page('확인',str(ex)),404)


def post(handler,store,path):
    plans=Plans(store);parts=path.strip('/').split('/');fields={}
    try:
        length=int(handler.headers.get('Content-Length','0'))
        if not 0<length<=intake_http.MAX_BODY:raise ValueError('전체 파일 크기를 확인하세요.')
        data=handler.rfile.read(length);ct=handler.headers.get('Content-Type','')
        if ct.startswith('multipart/form-data'):fields,files=intake_http.multipart(data,ct)
        else:fields={k:v[0] for k,v in parse_qs(data.decode(),keep_blank_values=True).items()};files=[]
        intake_http.protect(handler,fields)
        if path=='/design/create':
            chosen=[]
            for d in store.designs():
                rank=fields.get('order_'+d['id'],'').strip()
                if rank:
                    rank=int(rank)
                    if rank<1:raise ValueError('순서는 1 이상으로 입력하세요.')
                    chosen.append((rank,d))
            if not chosen:raise ValueError('등록할 시안의 순서를 입력하세요.')
            if len({n for n,d in chosen})!=len(chosen):raise ValueError('시안 순서가 중복됐습니다.')
            ordered=[{'design_id':d['id'],'tc':'1. 디자인에 표시된 상태로 이동합니다.\n2. 입력·언어·버튼 상태를 시안과 맞춥니다.\n3. 개발 화면을 촬영합니다.','expected':d['name']+'와 같은 상태','prerequisite':'촬영 전에 구체적인 조작 절차와 입력 조건을 TC에 보완하세요.'} for _,d in sorted(chosen,key=lambda v:v[0])]
            plan=plans.create_empty(fields.get('project',''),fields.get('name',''),fields.get('platform','android'),ordered)
            intake_http.redirect(handler,'/design/'+plan);return
        plan=parts[1]
        if len(parts)==3 and parts[2]=='upload-design':
            plans.get(plan)
            name=fields.get('name','').strip()
            if not name or len(name)>120:raise ValueError('디자인 화면 이름을 입력하세요.')
            if len(files)!=1:raise ValueError('디자인 원본 PNG 한 장을 선택하세요.')
            from intake_store import uid
            design=store.add_design('local-design',uid(),name,'','',files[0][1],provider='작업자 원본 PNG 등록')
            plans.add(plan,design)
            intake_http.redirect(handler,'/design/'+plan);return
        if len(parts)==3 and parts[2]=='add':
            plans.add(plan,fields.get('design',''))
            intake_http.redirect(handler,'/design/'+plan);return
        if len(parts)==3 and parts[2]=='import':
            results=[(n,b) for n,b in files if n=='찍은목록.json']
            if len(results)!=1:raise ValueError('찍은목록.json 한 개와 PNG를 함께 선택하세요.')
            manifest=json.loads(results[0][1])
            if not isinstance(manifest,dict):raise ValueError('촬영 목록 형식을 확인하세요.')
            entries=manifest.get('찍힌것',[])
            if not isinstance(entries,list) or any(not isinstance(x,dict) or not isinstance(x.get('case_id'),str) or not isinstance(x.get('파일'),str) for x in entries):raise ValueError('TC와 파일명이 있는 촬영 목록이 필요합니다.')
            if manifest.get('format')!='design-capture-results-v1' or manifest.get('plan_id')!=plan:raise ValueError('이 디자인 목록의 촬영 결과가 아닙니다.')
            byname={n:b for n,b in files}
            if len(byname)!=len(files):raise ValueError('파일명이 중복됐습니다.')
            if not entries or len(entries)>100:raise ValueError('촬영 결과는 1~100장씩 등록하세요.')
            from intake_store import png_size
            seen=set()
            for x in entries:
                if x['case_id'] in seen:raise ValueError('같은 TC가 중복됐습니다.')
                seen.add(x['case_id']);_,r=plans.case(plan,x['case_id'])
                if r['page_id']:raise ValueError('검수 시작된 TC는 새 차수로 등록해야 합니다.')
                if x['파일'] not in byname:raise ValueError('누락된 촬영 파일: '+x['파일'])
                png_size(byname[x['파일']])
            with store.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                for x in entries:
                    r=c.execute('SELECT revision FROM design_case WHERE id=?',(x['case_id'],)).fetchone()
                    plans.upload(plan,x['case_id'],r['revision'],x['파일'],byname[x['파일']],conn=c)
            intake_http.redirect(handler,'/design/'+plan);return
        if len(parts)!=5 or parts[2]!='case':raise ValueError('작업 주소를 확인하세요.')
        case,action=parts[3:];plans.case(plan,case)
        if not str(fields.get('revision','')).isdigit():raise ValueError('페이지를 새로고침한 뒤 다시 시도하세요.')
        if action=='upload':
            if len(files)!=1:raise ValueError('PNG 한 장을 선택하세요.')
            plans.upload(plan,case,fields.get('revision'),files[0][0],files[0][1])
        else:plans.update(plan,case,fields.get('revision'),action,fields)
        intake_http.redirect(handler,f'/design/{plan}' if action in ('exclude','restore') else f'/design/{plan}/case/{case}')
    except (ValueError,KeyError,IndexError,UnicodeError) as ex:
        handler._html(ui.page('촬영 계획 확인','<a href="/">화면 목록</a>',str(ex),True),400)
