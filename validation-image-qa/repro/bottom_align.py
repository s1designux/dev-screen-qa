# -*- coding: utf-8 -*-
"""하단(푸터) 자리 맞추기 재현 세트를 만든다.

같은 화면을 그리되 **개발 쪽 그림만 짧게** 만들어, 푸터가 '위에서 몇 px'이 아니라
'바닥에서 몇 px'에 놓이게 한다. 두 그림의 내용은 같으므로, 자리를 제대로 맞추면
잘라 온 두 조각이 거의 똑같아야 한다 — 그것으로 맞고 틀림을 가른다.

    python3 bottom_align.py        # 그림·핀 목록·검사판(harness) 다시 만들기

만들어지는 것
  bottom_*_design.png / bottom_*_dev.png   화면 짝 네 벌
  bottom_align.json                        핀 목록(개발 그림 기준 좌표)
  bottom_align.harness.html                브라우저에서 열어 보는 검사판
  bottom_align.before_after.png            눈으로 보는 고치기 전·후 한 장
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
KR = '/System/Library/Fonts/AppleSDGothicNeo.ttc'


def font(size, idx=2):
    try:
        return ImageFont.truetype(KR, size, index=idx)
    except OSError:
        return ImageFont.load_default()


W = 1200


def 그리기(height, foot_top, faint=False, rows=0):
    """화면 한 장. 내용은 위에 붙고 푸터만 foot_top에 놓는다."""
    im = Image.new('RGB', (W, height), 'white')
    g = ImageDraw.Draw(im)
    g.rectangle([0, 0, W, 88], fill='#1f3864')
    g.text((40, 30), '삼성 통근버스 운영 시스템', font=font(26), fill='white')
    g.text((980, 34), '로그아웃', font=font(18), fill='#dbe5f1')
    g.text((40, 140), '휴대전화번호 입력', font=font(30), fill='#111111')
    y = 210
    for label, ph in (('이름', '이름을 입력해 주세요.'), ('휴대전화번호', '휴대전화번호를 입력해 주세요.')):
        g.text((40, y), label, font=font(18), fill='#333333')
        g.rectangle([40, y + 28, 640, y + 78], outline='#c9ced6')
        g.text((56, y + 42), ph, font=font(18), fill='#9aa1ab')
        y += 110
    g.rectangle([40, y + 10, 640, y + 70], fill='#1d6ceb')
    g.text((280, y + 28), '인증요청', font=font(20), fill='white')
    y += 110
    for i in range(rows):   # 비슷하게 생긴 줄을 여러 개 — 아래쪽에서 헷갈리기 쉬운 화면
        g.rectangle([40, y, 1160, y + 44], outline='#e3e7ec')
        g.text((56, y + 12), '2026-09-%02d   버스 %d호차   정상 운행' % (i + 1, i + 1), font=font(16), fill='#55606e')
        y += 48
    ink = '#c8ccd2' if faint else '#8b929c'
    g.line([(0, foot_top - 24), (W, foot_top - 24)], fill='#e5e7eb')
    g.text((300, foot_top), '개인정보 처리방침', font=font(15), fill=ink)
    g.text((520, foot_top), '위치기반 서비스 이용약관', font=font(15), fill=ink)
    g.text((300, foot_top + 26), '(주)에스원  사업자등록번호 214-81-01488', font=font(13), fill=ink)
    g.text((300, foot_top + 48), 'COPYRIGHT S-1 CORPORATION. ALL RIGHTS RESERVED.', font=font(12), fill=ink)
    g.rectangle([1080, foot_top - 2, 1140, foot_top + 22], fill='#eef1f5')
    return im


# (이름, 설명, 시안 높이, 개발 높이, 옅은 푸터, 표 줄 수)
CASES = [
    ('same', '같은 높이 — 밀림 없음(회귀용)', 1400, 1400, False, 0),
    ('short', '개발 쪽이 300px 짧다 — 푸터는 바닥 기준', 1400, 1100, False, 0),
    ('faint', '거기에 푸터 글자가 옅다', 1400, 1100, True, 0),
    ('rows', '거기에 비슷한 표 줄이 여럿 — 헷갈리기 쉬운 화면', 1500, 1200, True, 9),
]


def 핀들(foot_top, rows, 밀림):
    """검사할 자리 — 개발 그림 좌표. 밀림 = 시안 y - 개발 y (정답)."""
    위 = [
        ('head', '상단바', [40, 24, 340, 40]),
        ('title', '제목', [40, 140, 320, 38]),
        ('field', '입력칸', [40, 238, 600, 50]),
        ('button', '버튼', [40, 430 + rows * 48, 600, 60]),
    ]
    아래 = [
        ('foot1', '푸터 · 개인정보 처리방침', [300, foot_top, 170, 22]),
        ('foot2', '푸터 · 위치기반 서비스 이용약관', [520, foot_top, 230, 22]),
        ('foot3', '푸터 · 사업자등록번호', [300, foot_top + 26, 420, 20]),
        ('foot4', '푸터 · 저작권 줄', [300, foot_top + 48, 520, 18]),
        ('footbox', '푸터 오른쪽 상자', [1080, foot_top - 2, 60, 24]),
    ]
    out = [{'id': i, 'why': w, 'box': b, 'shift': 0} for i, w, b in 위]
    out += [{'id': i, 'why': w, 'box': b, 'shift': 밀림} for i, w, b in 아래]
    return out


def main():
    세트 = []
    for name, 설명, dh, vh, faint, rows in CASES:
        d_foot, v_foot = dh - 120, vh - 120
        design = 그리기(dh, d_foot, faint, rows)
        dev = 그리기(vh, v_foot, faint, rows)
        design.save(os.path.join(HERE, 'bottom_%s_design.png' % name))
        dev.save(os.path.join(HERE, 'bottom_%s_dev.png' % name))
        세트.append({'name': name, 'why': 설명, 'design': 'bottom_%s_design.png' % name,
                    'dev': 'bottom_%s_dev.png' % name, 'dw': W, 'dh': dh, 'vw': W, 'vh': vh,
                    'pins': 핀들(v_foot, rows, dh - vh)})
    with open(os.path.join(HERE, 'bottom_align.json'), 'w', encoding='utf-8') as f:
        json.dump(세트, f, ensure_ascii=False, indent=1)
    sys.path.insert(0, os.path.join(HERE, '..', '..', 'mvp0'))
    import comparison_view
    html = HARNESS.replace('/*CSS*/', comparison_view.CSS).replace('/*JS*/', comparison_view.JS) \
                  .replace('/*DATA*/', json.dumps(세트, ensure_ascii=False))
    with open(os.path.join(HERE, 'bottom_align.harness.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    견줌그림(세트)
    print('만들었어요 — bottom_align.harness.html 을 브라우저로 열면 성적이 나옵니다.')


def 견줌그림(세트, 고를이름='rows'):
    """사람이 눈으로 판정할 한 장 — 푸터마다 [고치기 전 · 고친 뒤 · 개발]을 나란히."""
    c = {x['name']: x for x in 세트}[고를이름]
    D = Image.open(os.path.join(HERE, c['design'])).convert('RGB')
    V = Image.open(os.path.join(HERE, c['dev'])).convert('RGB')
    pins = [p for p in c['pins'] if p['shift']]
    CW, CH, PAD, LAB = 300, 86, 10, 200

    def 잘라(im, x, y, w, h):
        칸 = Image.new('RGB', (int(w), int(h)), 'white')
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(im.size[0], int(x + w)), min(im.size[1], int(y + h))
        if x1 > x0 and y1 > y0:
            칸.paste(im.crop((x0, y0, x1, y1)), (x0 - int(x), y0 - int(y)))
        return 칸.resize((CW, CH))

    s = Image.new('RGB', (LAB + 3 * (CW + PAD) + PAD, 78 + len(pins) * (CH + PAD) + PAD), 'white')
    g = ImageDraw.Draw(s)
    g.text((PAD, 12), '화면 아래쪽(푸터) — 시안에서 어디를 잘라 오나', font=font(17, 3), fill='#111827')
    g.text((PAD, 36), '개발 그림이 %dpx 짧아 푸터가 바닥에 붙은 화면' % (c['dh'] - c['vh']), font=font(13), fill='#6b7280')
    for i, t in enumerate(['고치기 전 (시안)', '고친 뒤 (시안)', '개발 — 이것과 같아야 맞음']):
        g.text((LAB + i * (CW + PAD), 56), t, font=font(13, 3), fill=['#b91c1c', '#15803d', '#374151'][i])
    y = 78
    for p in pins:
        x, py, w, h = p['box']
        x -= 20; py -= 20; w += 40; h += 40
        cx, cy = x + w / 2, py + h / 2
        hh = w * CH / CW
        칸들 = [잘라(D, cx - w / 2, cy - hh / 2, w, hh), 잘라(D, cx - w / 2, cy - hh / 2 + p['shift'], w, hh),
              잘라(V, cx - w / 2, cy - hh / 2, w, hh)]
        g.text((PAD, y + CH / 2 - 8), p['why'].replace('푸터 · ', ''), font=font(13), fill='#374151')
        for i, im in enumerate(칸들):
            s.paste(im, (LAB + i * (CW + PAD), y))
            g.rectangle([LAB + i * (CW + PAD), y, LAB + i * (CW + PAD) + CW, y + CH], outline='#cbd5e1')
        y += CH + PAD
    s.save(os.path.join(HERE, 'bottom_align.before_after.png'))


HARNESS = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>하단 자리 맞추기 검사판</title>
<style>/*CSS*/
body{font:14px system-ui,sans-serif;margin:0;padding:16px;color:#1f2937}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px;position:absolute;left:-99999px;top:0}
.pane .canvas{position:relative}.pane img{width:100%;display:block}
table{border-collapse:collapse;margin:10px 0 22px;font-size:13px}
th,td{border:1px solid #e5e7eb;padding:5px 9px;text-align:left}th{background:#f8fafc}
td.no{background:#fee2e2}td.ok{background:#dcfce7}
h2{font-size:15px;margin:18px 0 4px}.sum{font-weight:700;margin:6px 0 14px}
</style>
<h1 style="font-size:18px">하단(푸터) 자리 맞추기 — 검사판</h1>
<p>같은 화면을 시안·개발 두 벌로 그렸습니다. 내용이 같으니 <b>정답 자리를 정확히 알 수 있습니다</b> —
위쪽 내용은 그대로, 푸터는 두 그림의 높이 차이만큼 내려가 있어야 합니다.
<b>어긋남 6px 이하면 맞음</b>으로 셉니다.</p>
<div id="out">재는 중…</div>
<div class="cols"><section class="pane"><div class="canvas"><img id="dimg"></div></section>
<section class="pane"><div class="canvas"><img id="vimg"><svg class="auto-overlay" id="ov"></svg></div></section></div>
<script>
const 세트=/*DATA*/;
const dimg=document.getElementById('dimg'),vimg=document.getElementById('vimg'),ov=document.getElementById('ov');
function load(el,src){return new Promise(r=>{el.onload=()=>r();el.src=src;});}
function 어긋남(r,p){   // 잘라 온 시안 자리의 한가운데가 정답에서 몇 px 벗어났나
 if(!r)return null;const 정답=p.box[1]+p.box[3]/2+p.shift;
 if(!r.design)return Math.round(r.dev.y+r.dev.h/2-정답);   // 시안 자리를 못 구하면 개발 자리 그대로 쓴 셈
 return Math.round(r.design.y+r.design.h/2-정답);}
function 읽을수있나(){   // file:// 로 열면 그림 화소를 못 읽어(브라우저 보안) 엉뚱한 성적이 나온다
 try{const c=document.createElement('canvas');c.width=c.height=2;const g=c.getContext('2d');
  g.drawImage(dimg,0,0);g.getImageData(0,0,2,2);return true;}catch(e){return false;}}
async function 재기(){
 const out=document.getElementById('out');out.innerHTML='';let 총=0,맞음=0;
 await Promise.all([load(dimg,세트[0].design),load(vimg,세트[0].dev)]);
 if(!읽을수있나()){out.innerHTML='<p style="color:#b91c1c"><b>이 파일을 그냥 열면 잴 수 없어요.</b> '
  +'같은 폴더에서 <code>python3 -m http.server 8788</code> 을 켜고 '
  +'<code>http://localhost:8788/bottom_align.harness.html</code> 로 열어 주세요.</p>';return;}
 for(const c of 세트){
  ov.setAttribute('viewBox','0 0 '+c.vw+' '+c.vh);ov.innerHTML='';
  for(const p of c.pins){const r=document.createElementNS('http://www.w3.org/2000/svg','rect');
   r.id='box-'+p.id;r.setAttribute('x',p.box[0]);r.setAttribute('y',p.box[1]);r.setAttribute('width',p.box[2]);r.setAttribute('height',p.box[3]);ov.appendChild(r);}
  await Promise.all([load(dimg,c.design),load(vimg,c.dev)]);
  window.qaDesignBox={};window.qaAlign=null;window.qaDesignRef=null;
  const rows=[];
  for(const p of c.pins){
   const r=window.qaCompareIssue(p.id),e=어긋남(r,p),ok=e!==null&&Math.abs(e)<=6;
   총++;if(ok)맞음++;
   rows.push('<tr><td>'+p.why+'</td><td>'+p.box[1]+'</td><td>'+(p.box[1]+p.shift)+'</td><td class="'+(ok?'ok':'no')+'">'
    +(e===null?'못 구함':(e>0?'+':'')+e+'px')+'</td></tr>');}
  out.insertAdjacentHTML('beforeend','<h2>'+c.name+' — '+c.why+' (시안 '+c.dh+'px · 개발 '+c.vh+'px)</h2>'
   +'<table><tr><th>자리</th><th>개발 y</th><th>시안 정답 y</th><th>어긋남</th></tr>'+rows.join('')+'</table>');}
 out.insertAdjacentHTML('afterbegin','<p class="sum" id="총평">맞음 '+맞음+' / '+총+'</p>');
 document.querySelector('.cv-pop').hidden=true;}
addEventListener('load',()=>{setTimeout(재기,60);});
/*JS*/
</script></html>'''

if __name__ == '__main__':
    main()
