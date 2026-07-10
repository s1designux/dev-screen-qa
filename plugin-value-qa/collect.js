/* 생성 파일 — 직접 고치지 말고 collect-core.js 를 수정하세요 (build-tools.js가 생성) */
/* =====================================================================
   측정 코어 (단일 원본) — 태그 없이 화면의 '의미있는' 요소를 잼.
   globalThis.__qaMeasure() → 측정 결과 객체 반환 (다운로드는 안 함).
   collect.js(콘솔)·북마클릿·캡처 확장앱이 모두 이 파일에서 파생됨(build-tools.js).
   ===================================================================== */
(function () {
  if (typeof globalThis.__qaMeasure === 'function') return;
  globalThis.__qaMeasure = function () {
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
      if (!(isText || hasBg || hasBorder || hasImg || formish)) continue;

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
    return { meta:{ label:name, source:'web-all', url:location.href, title:document.title, viewportWidth:window.innerWidth, artboardWidth:r(W), artboardHeight:r(H), contentX:r(minX), contentY:r(minY), docW:r(Math.max(document.documentElement.scrollWidth, document.body?document.body.scrollWidth:0)), capturedAt:new Date().toISOString(), toolVersion:'core-1.1' }, elements: elements };
  };
})();

(function(){var res=globalThis.__qaMeasure();var nm=res.meta.label;var blob=new Blob([JSON.stringify(res,null,2)],{type:'application/json'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='measure-'+nm+'.json';document.body.appendChild(a);a.click();a.remove();alert('측정 완료: '+res.elements.length+'개 요소\n파일: measure-'+nm+'.json (다운로드됨)\n폭 '+res.meta.artboardWidth+'px');})();
