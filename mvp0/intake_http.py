"""Intake request handling, multipart parsing and same-origin write protection."""
from email import policy
from email.parser import BytesParser
from urllib.parse import parse_qs, urlparse, urlencode
import secrets
import re
import figma_reader
import intake_ui as ui

CSRF = secrets.token_urlsafe(32)
MAX_BODY = 100 * 1024 * 1024


def multipart(body, content_type):
    message=BytesParser(policy=policy.default).parsebytes(b'Content-Type: '+content_type.encode()+b'\r\nMIME-Version: 1.0\r\n\r\n'+body)
    fields,files={},[]
    if not message.is_multipart():
        raise ValueError('선택한 파일을 읽지 못했습니다.')
    for part in message.iter_parts():
        name=part.get_param('name',header='content-disposition')
        filename=part.get_filename()
        data=part.get_payload(decode=True) or b''
        if filename:
            files.append((filename,data))
        elif name:
            fields[name]=data.decode('utf-8')
    return fields,files


def protect(handler,fields):
    if not secrets.compare_digest(fields.get('csrf',''),CSRF):
        raise ValueError('페이지를 새로고침한 뒤 다시 시도해 주세요.')
    origin=handler.headers.get('Origin')
    expected=f'http://{handler.headers.get("Host","")}'
    if origin and origin != expected:
        raise ValueError('포털 화면에서 다시 시도해 주세요.')


def decorate(body):
    return re.sub(r'(<form\b[^>]*method=["\']post["\'][^>]*>)',lambda m:m.group(1)+ui.hidden('csrf',CSRF),body,flags=re.I)


def redirect(handler,path):
    handler.send_response(303)
    handler.send_header('Location',path)
    handler.end_headers()


def get(handler,store,path,q):
    if path=='/intake':
        handler._html(ui.inbox(store))
    elif path=='/intake/new':
        handler._html(ui.new(store))
    elif re.fullmatch(r'/intake/[a-f0-9]{32}(/connect|/pages|/screen/[a-f0-9]{32})?',path):
        batch=path.split('/')[2]
        try:
            if '/screen/' in path:
                body=ui.page_list(store,batch,path.rsplit('/',1)[1])
            elif path.endswith('/pages'):
                body=ui.page_list(store,batch)
            elif path.endswith('/connect'):
                from design_plan import Plans
                planned=next((p for p in Plans(store).plans() if p['batch_id']==batch),None)
                if planned:
                    redirect(handler,'/design/'+planned['id'])
                    return
                item=q.get('item',[''])[0]
                if item:
                    _, items, _=store.batch(batch)
                    if not any(r['id']==item for r in items):
                        raise ValueError('이 화면의 검수 페이지를 선택해 주세요.')
                    destination=store.page_destination(item)
                    if destination.startswith('/screen/'):
                        redirect(handler,destination)
                        return
                body=ui.connect_page(store,batch,item)
            else:
                body=ui.batch_page(store,batch)
            handler._html(body)
        except ValueError as ex:
            handler._html(ui.page('접수 확인','<a class="button" href="/intake">접수함으로</a>',str(ex),True),404)
    else:
        handler._html(ui.page('접수함','<a href="/intake">접수함으로</a>','페이지를 찾을 수 없습니다.',True),404)


def post(handler,store,path):
    batch=path.split('/')[2] if len(path.split('/'))>2 else ''
    fields={}
    try:
        length=int(handler.headers.get('Content-Length','0'))
        if not 0<length<=MAX_BODY:
            raise ValueError('파일 크기를 확인해 주세요. 전체 최대 100MB입니다.')
        body=handler.rfile.read(length)
        ct=handler.headers.get('Content-Type','')
        if ct.startswith('multipart/form-data'):
            fields,files=multipart(body,ct)
        else:
            fields={k:v[0] for k,v in parse_qs(body.decode('utf-8'),keep_blank_values=True).items()}
            files=[]
        protect(handler,fields)
        if path=='/intake/import':
            batch,duplicate=store.import_files(files,fields.get('project_id',''),fields.get('project_name',''),fields.get('platform','android'))
            if duplicate:
                handler._html(ui.batch_page(store,batch,'같은 자료가 이미 접수되어 있습니다. 기존 접수 기록을 열었습니다.'))
            else:
                redirect(handler,'/')
            return
        if not re.fullmatch(r'/intake/[a-f0-9]{32}/(edit|select|confirm|start|fetch|token)',path):
            raise ValueError('작업 주소를 확인해 주세요.')
        action=path.rsplit('/',1)[1]
        from design_plan import Plans
        if action in ('select','confirm','start') and any(p['batch_id']==batch for p in Plans(store).plans()):
            raise ValueError('이 자료는 디자인 기준 목록으로 전환되었습니다. 화면 목록에서 TC 기준으로 연결하세요.')
        b,items,_=store.batch(batch)
        item=fields.get('item','')
        if (action!='start' or item) and item not in {r['id'] for r in items}:
            raise ValueError('이 접수함의 촬영본을 다시 선택해 주세요.')
        if action=='edit':
            store.edit_item(item,fields.get('revision','-1'),fields.get('screen',''),fields.get('state',''),fields.get('status',''),fields.get('reason',''))
            redirect(handler,'/intake/'+batch)
        elif action=='select':
            store.select_design(item,fields.get('revision','-1'),fields.get('design',''))
            redirect(handler,f'/intake/{batch}/connect?item={item}')
        elif action=='confirm':
            store.confirm(item,fields.get('revision','-1'))
            store.start(batch)
            redirect(handler,store.page_destination(item))
        elif action=='start':
            destination=store.start(batch)
            redirect(handler,store.page_destination(item) if item else destination)
        elif action=='fetch':
            added,failed=figma_reader.fetch(store,fields.get('link',''))
            connection_result(handler,store,batch,item,f'디자인 {len(added)}개를 가져왔습니다.'+(f' {failed}개는 이미지 가져오기에 실패했습니다.' if failed else ''))
        elif action=='token':
            token=fields.get('token','').strip()
            if not token or len(token)>500 or any(ord(ch)<33 or ord(ch)>126 for ch in token):
                raise ValueError('연결 키 형식을 확인해 주세요.')
            figma_reader.TOKEN=token
            connection_result(handler,store,batch,item,'연결 키를 이 실행에만 보관했습니다. 링크로 디자인을 불러오면 읽기 권한을 확인합니다.')
    except (ValueError,UnicodeError) as ex:
        if re.fullmatch(r'[a-f0-9]{32}',batch):
            try:
                render=ui.batch_page(store,batch,str(ex),True) if path.endswith('/edit') else ui.connect_page(store,batch,fields.get('item',''),str(ex),True)
            except ValueError:
                render=ui.page('접수 확인','<a href="/intake">접수함으로</a>',str(ex),True)
        else:
            render=ui.new(store,str(ex),True)
        handler._html(render,400)


def connection_result(handler,store,batch,item,message):
    destination=store.page_destination(item)
    if destination.startswith('/screen/'):
        redirect(handler,destination+'?'+urlencode({'designs':'1','notice':message}))
    else:
        handler._html(ui.connect_page(store,batch,item,message))
