"""Read-only Figma REST adapter. Credential is process-local, never persisted."""
import html
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

TOKEN = os.environ.get('FIGMA_ACCESS_TOKEN', '')


def parse_link(link):
    p = urlparse(html.unescape(link.strip()))
    parts = p.path.strip('/').split('/')
    if p.scheme != 'https' or p.hostname not in ('figma.com','www.figma.com') or len(parts)<2 or parts[0] not in ('design','file'):
        raise ValueError('Figma 디자인의 원본 링크를 붙여 넣어 주세요.')
    key = parts[3] if len(parts)>3 and parts[2]=='branch' else parts[1]
    node = parse_qs(p.query).get('node-id',[''])[0].replace('-',':')
    if not re.fullmatch(r'[A-Za-z0-9]+',key) or not re.fullmatch(r'\d+:\d+',node):
        raise ValueError('프레임 또는 페이지를 선택한 뒤 링크를 복사해 주세요.')
    return key,node


def link_for(key,node):
    return f'https://www.figma.com/design/{key}/?node-id={node.replace(":","-")}'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def api(path):
    if not TOKEN:
        raise ValueError('Figma 읽기 연결이 필요합니다. 아래 연결 설정을 열어 주세요.')
    try:
        req=Request('https://api.figma.com/v1/'+path,headers={'X-Figma-Token':TOKEN})
        with build_opener(NoRedirect()).open(req,timeout=20) as r:
            data=r.read(15*1024*1024+1)
        if len(data)>15*1024*1024:
            raise ValueError('선택 범위가 너무 큽니다. 로그인 프레임 링크로 좁혀 주세요.')
        result=json.loads(data)
        if not isinstance(result,dict) or result.get('err'):
            raise ValueError('Figma 응답을 읽지 못했습니다. 잠시 후 다시 시도해 주세요.')
        return result
    except HTTPError as e:
        raise ValueError({401:'Figma 연결 키를 확인해 주세요.',403:'Figma 읽기 권한 또는 연결 키 만료를 확인해 주세요.',404:'링크 대상이 없거나 접근할 수 없습니다.',429:'Figma 요청이 많습니다. 잠시 후 다시 시도해 주세요.'}.get(e.code,'Figma에서 이미지를 가져오지 못했습니다. 다시 시도해 주세요.')) from None
    except (URLError,TimeoutError,OSError,json.JSONDecodeError):
        raise ValueError('Figma에 연결하지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.') from None


def image_bytes(url):
    # API-issued signed image URL only; no user-supplied image URL accepted.
    p=urlparse(url)
    host=p.hostname or ''
    allowed=host.endswith('.amazonaws.com') or host.endswith('.figma.com') or host.endswith('.figmausercontent.com')
    if p.scheme!='https' or not allowed:
        raise ValueError('Figma 이미지 주소를 확인하지 못했습니다.')
    try:
        with build_opener(NoRedirect()).open(Request(url),timeout=25) as r:
            data=r.read(25*1024*1024+1)
        return data
    except (URLError,TimeoutError,OSError):
        raise ValueError('디자인 이미지를 가져오지 못했습니다. 다시 시도해 주세요.') from None


SHARED_NS='devScreenQa'  # 검수기 플러그인이 사람이 정한 설정을 두는 공유 칸(legacy/plugin-image-qa/code.js SHARED_NS와 같아야 함)


def qa_settings(node):
    """디자인 프레임·캡처 노드에 검수기가 남긴 사람의 설정(화면 종류·글자 가변 여부·검수 범위·겹쳐보기 위치).
    검수 결과가 아니라 설정만 읽는다. 없으면 {}."""
    raw=(node.get('sharedPluginData') or {}).get(SHARED_NS) or {}
    out={}
    if raw.get('imageQaPolicy'):
        try:
            p=json.loads(raw['imageQaPolicy'])
            if isinstance(p,dict):
                out['policy']=p
        except json.JSONDecodeError:
            pass
    for src,dst in (('imageQaTopTrim','top_trim'),('imageQaBottomTrim','bottom_trim')):
        v=raw.get(src)
        if v not in (None,''):
            try:
                out[dst]=max(0,int(float(v)))
            except ValueError:
                pass
    if raw.get('imageQaOverlayFix'):
        try:
            f=json.loads(raw['imageQaOverlayFix'])
            if isinstance(f,dict) and all(isinstance(f.get(k),(int,float)) for k in ('dx','dy')):
                out['overlay_fix']={'dx':int(f['dx']),'dy':int(f['dy'])}
        except json.JSONDecodeError:
            pass
    return out


def fetch(store,link):
    key,node=parse_link(link)
    data=api('files/'+key+'/nodes?'+urlencode({'ids':node,'depth':2,'plugin_data':'shared'}))
    item=data.get('nodes',{}).get(node)
    if not item or not item.get('document'):
        raise ValueError('링크 대상을 찾지 못했습니다. 프레임 링크를 확인해 주세요.')
    root=item['document']
    if root.get('type') in ('FRAME','COMPONENT','INSTANCE'):
        candidates=[root]
    else:
        candidates=[]
        def walk(n):
            for child in n.get('children',[]):
                if child.get('type') in ('FRAME','COMPONENT','INSTANCE'):
                    candidates.append(child)
                elif child.get('type') in ('SECTION','GROUP','CANVAS'):
                    walk(child)
        walk(root)
    candidates=[n for n in candidates if n.get('visible',True)]
    if not candidates:
        raise ValueError('불러올 프레임이 없습니다. 개별 프레임 링크를 선택해 주세요.')
    if len(candidates)>24:
        raise ValueError('범위에 프레임이 24개보다 많습니다. 로그인 프레임이나 작은 섹션의 링크로 좁혀 주세요.')
    version=data.get('version')
    query={'ids':','.join(n['id'] for n in candidates),'format':'png','scale':1}
    if version:
        query['version']=version
    images=api('images/'+key+'?'+urlencode(query)).get('images',{})
    added,failed=[],0
    for n in candidates:
        url=images.get(n['id'])
        if not url:
            failed+=1
            continue
        try:
            raw=image_bytes(url)
            added.append(store.add_design(key,n['id'],n.get('name','디자인'),link_for(key,n['id']),node,raw,version,qa_settings=qa_settings(n)))
        except ValueError:
            failed+=1
    if not added:
        raise ValueError('디자인 이미지를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.')
    return added,failed
