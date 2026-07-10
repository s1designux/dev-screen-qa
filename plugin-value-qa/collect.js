/* =====================================================================
   개발화면 측정 수집기 (태그 불필요 버전) — v2
   사용법: 검사할 개발화면을 브라우저에서 연 뒤, F12 → Console 탭에
           이 파일 내용을 통째로 붙여넣고 Enter.
           → 측정 결과 JSON 파일이 자동으로 다운로드됩니다.
   특징: data-qa 이름표가 없어도, 화면의 '의미있는' 요소를 전부 잽니다.
         (색·크기·위치·글자) 짝맞춤은 플러그인이 자동으로 합니다.
   ===================================================================== */
(function () {
  function r(n){ return Math.round(n*10)/10; }
  function num(v){ var f=parseFloat(v); return isNaN(f)?0:r(f); }
  function firstFont(v){ return (v||'').split(',')[0].replace(/["']/g,'').trim(); }
  function transparent(c){ return !c || c==='transparent' || c==='rgba(0, 0, 0, 0)'; }

  var all = document.body.getElementsByTagName('*');
  var SKIP = { SCRIPT:1, STYLE:1, META:1, LINK:1, HEAD:1, NOSCRIPT:1, BR:1, HR:1 };
  var raw = [];
  for (var i=0;i<all.length;i++){
    var el = all[i];
    if (SKIP[el.tagName]) continue;
    var rect = el.getBoundingClientRect();
    if (rect.width < 3 || rect.height < 3) continue;
    var cs = getComputedStyle(el);
    if (cs.display==='none' || cs.visibility==='hidden' || parseFloat(cs.opacity)===0) continue;

    var ownText = '';
    for (var k=0;k<el.childNodes.length;k++){ var nd=el.childNodes[k]; if(nd.nodeType===3){ ownText += nd.textContent; } }
    ownText = ownText.replace(/\s+/g,' ').trim();

    var hasBg = !transparent(cs.backgroundColor);
    var hasBorder = num(cs.borderTopWidth)>0 || num(cs.borderBottomWidth)>0 || num(cs.borderLeftWidth)>0 || num(cs.borderRightWidth)>0;
    var hasImg = cs.backgroundImage && cs.backgroundImage!=='none';
    var formish = /^(IMG|INPUT|BUTTON|SELECT|TEXTAREA|SVG)$/.test(el.tagName);
    var isText = ownText.length>0 && !hasBg && !hasBorder && !formish;
    var meaningful = isText || hasBg || hasBorder || hasImg || formish;
    if (!meaningful) continue;

    raw.push({
      tag: el.tagName, cls: (el.className&&el.className.toString?el.className.toString():'').slice(0,40),
      text: (el.innerText||'').replace(/\s+/g,' ').trim().slice(0,50),
      isText: isText, rect: rect,
      style: {
        color: cs.color, backgroundColor: cs.backgroundColor,
        fontSize: num(cs.fontSize), fontWeight: num(cs.fontWeight), fontFamily: firstFont(cs.fontFamily),
        lineHeight: 0, borderRadius: num(cs.borderTopLeftRadius), borderWidth: num(cs.borderTopWidth),
        borderColor: cs.borderTopColor, paddingTop: num(cs.paddingTop), paddingRight: num(cs.paddingRight),
        paddingBottom: num(cs.paddingBottom), paddingLeft: num(cs.paddingLeft),
        textAlign: cs.textAlign, opacity: num(cs.opacity)
      }
    });
  }

  var minX=Infinity, minY=Infinity, maxX=-Infinity, maxY=-Infinity;
  raw.forEach(function(o){ minX=Math.min(minX,o.rect.left); minY=Math.min(minY,o.rect.top); maxX=Math.max(maxX,o.rect.right); maxY=Math.max(maxY,o.rect.bottom); });
  var W = maxX-minX, H = maxY-minY;
  var name = (document.title||location.pathname||'dev').replace(/[^a-z0-9가-힣]+/gi,'-').replace(/^-+|-+$/g,'').slice(0,40) || 'dev';

  var elements = raw.map(function(o, idx){
    return {
      id: 'dev-'+idx, role: o.tag, cls: o.cls, text: o.text, isText: o.isText,
      box: { x:r(o.rect.left-minX), y:r(o.rect.top-minY), w:r(o.rect.width), h:r(o.rect.height) },
      style: o.style, contentZone: false
    };
  });
  var result = { meta:{ label:name, source:'web-all', url:location.href, title:document.title, viewportWidth:window.innerWidth, artboardWidth:r(W), artboardHeight:r(H), capturedAt:new Date().toISOString(), toolVersion:'all-2.0' }, elements: elements };

  var blob = new Blob([JSON.stringify(result, null, 2)], { type:'application/json' });
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'measure-'+name+'.json';
  document.body.appendChild(a); a.click(); a.remove();
  alert('측정 완료: '+elements.length+'개 요소\n파일: measure-'+name+'.json (다운로드됨)\n폭 '+r(W)+'px');
})();
