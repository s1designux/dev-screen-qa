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
    function 픽셀(v){ var f=parseFloat(v); return (v && /px/.test(v) && !isNaN(f)) ? r(f) : null; }

    // 개발·퍼블리싱이 "어디를 고치면 되는지" 알아볼 수 있게, 그 요소를 가리키는 CSS 선택자를 만든다.
    // 디자인 레이어 이름은 디자이너가 임의로 붙인 것이라 개발 쪽에서 못 알아본다.
    function cssEsc(s){ return String(s).replace(/[^a-zA-Z0-9_ -￿-]/g, '\\$&'); }
    function classSel(el){
      var cn = (el.className && el.className.toString) ? el.className.toString().trim() : '';
      if (!cn) return '';
      return cn.split(/\s+/).slice(0,3).map(function(c){ return '.' + cssEsc(c); }).join('');
    }
    function nthOf(el){
      var p = el.parentElement; if (!p) return '';
      var same = 0, idx = 0;
      for (var i=0;i<p.children.length;i++){ var ch=p.children[i]; if (ch.tagName===el.tagName){ same++; if (ch===el) idx=same; } }
      return same > 1 ? (':nth-of-type(' + idx + ')') : '';
    }
    function selectorOf(el){
      if (el.id) return '#' + cssEsc(el.id);
      var parts = [], cur = el, depth = 0;
      while (cur && cur.nodeType === 1 && cur !== document.body && depth < 5){
        if (cur.id) { parts.unshift('#' + cssEsc(cur.id)); break; }
        var 조각 = cur.tagName.toLowerCase() + classSel(cur);
        if (조각 === cur.tagName.toLowerCase()) 조각 += nthOf(cur);
        parts.unshift(조각);
        // 클래스가 붙은 조상까지 왔으면 거기서 멈춘다 — 너무 긴 선택자는 쓸모가 없다.
        if (classSel(cur) && parts.length > 1) break;
        cur = cur.parentElement; depth++;
      }
      return parts.join(' > ');
    }


    // ── 가상요소(::before·::after) 도 잰다 ────────────────────────────────
    // 구분선·밑줄·말머리표는 태그 없이 CSS 로만 그리는 일이 많다. 태그가 없으니 위 훑기에
    // 잡히지 않아 "디자인엔 있는데 개발엔 없다"는 헛지적이 되곤 했다.
    // 가상요소는 상자를 직접 물어볼 수 없어서, 부모의 상자와 CSS 값으로 자리를 셈한다.
    function 가상요소(el, rect, cs, 자리이름){
      var s = getComputedStyle(el, 자리이름);
      if (!s) return null;
      var c = s.content;
      if (!c || c === 'none' || c === 'normal') return null;
      if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return null;

      var w = 픽셀(s.width), h = 픽셀(s.height);
      if (w === null || h === null || w < 1 || h < 1) return null;   // 크기를 못 읽으면 견줄 수 없다

      var 칠 = !transparent(s.backgroundColor);
      var 테 = num(s.borderTopWidth)>0 || num(s.borderBottomWidth)>0 || num(s.borderLeftWidth)>0 || num(s.borderRightWidth)>0;
      var 그림 = s.backgroundImage && s.backgroundImage !== 'none';
      if (!(칠 || 테 || 그림)) return null;                          // 보이는 칠이 없으면 잴 것이 없다

      // 부모의 테두리·안쪽여백을 걷어낸 '속 상자'
      var bt=num(cs.borderTopWidth), bl=num(cs.borderLeftWidth), bR=num(cs.borderRightWidth), bb=num(cs.borderBottomWidth);
      var pt=num(cs.paddingTop), pl=num(cs.paddingLeft), pr=num(cs.paddingRight), pb=num(cs.paddingBottom);
      var cx = rect.left + bl + pl, cy = rect.top + bt + pt;
      var cw = rect.width - bl - bR - pl - pr, ch = rect.height - bt - bb - pt - pb;
      var mt=num(s.marginTop), mr=num(s.marginRight), mb=num(s.marginBottom), ml=num(s.marginLeft);
      var 앞 = (자리이름 === '::before');
      var x, y;

      if (s.position === 'absolute' || s.position === 'fixed') {
        var ax = rect.left + bl, ay = rect.top + bt;                 // 안쪽여백 상자
        var aw = rect.width - bl - bR, ah = rect.height - bt - bb;
        var L = 픽셀(s.left), R = 픽셀(s.right), T = 픽셀(s.top), B = 픽셀(s.bottom);
        x = (L !== null) ? ax + L : (R !== null ? ax + aw - R - w : ax);
        y = (T !== null) ? ay + T : (B !== null ? ay + ah - B - h : ay);
      } else {
        var 가로줄 = /flex|grid/.test(cs.display) && !/column/.test(cs.flexDirection || '');
        if (가로줄) {
          x = 앞 ? (cx + ml) : (cx + cw - mr - w);
          var ai = cs.alignItems || '';
          y = /center/.test(ai) ? cy + (ch - h)/2 : (/end/.test(ai) ? cy + ch - h - mb : cy + mt);
        } else if (s.display === 'block' || s.display === 'flex' || s.display === 'grid') {
          x = cx + ml;                                               // 블록이면 부모 폭에 걸쳐 눕는다
          y = 앞 ? (cy + mt) : (cy + ch - mb - h);
        } else {
          x = 앞 ? (cx + ml) : (cx + cw - mr - w);                   // 인라인이면 글자 앞·뒤
          y = cy + (ch - h)/2;
        }
      }

      return {
        tag: el.tagName, cls: (el.className&&el.className.toString?el.className.toString():'').slice(0,40),
        domId: '', sel: (selectorOf(el) + 자리이름).slice(0,120),
        text: '', isText: false,
        rect: { left:x, top:y, width:w, height:h, right:x+w, bottom:y+h },
        style: {
          color: s.color, backgroundColor: s.backgroundColor,
          fontSize: num(s.fontSize), fontWeight: num(s.fontWeight), fontFamily: firstFont(s.fontFamily),
          lineHeight: 0, borderRadius: num(s.borderTopLeftRadius), borderWidth: num(s.borderTopWidth),
          borderColor: s.borderTopColor, paddingTop: num(s.paddingTop), paddingRight: num(s.paddingRight),
          paddingBottom: num(s.paddingBottom), paddingLeft: num(s.paddingLeft),
          textAlign: s.textAlign, opacity: num(s.opacity)
        }
      };
    }

    var all = document.body.getElementsByTagName('*');
    var SKIP = { SCRIPT:1, STYLE:1, META:1, LINK:1, HEAD:1, NOSCRIPT:1, BR:1, HR:1 };
    var raw = [];
    for (var i=0;i<all.length;i++){
      var el = all[i];
      if (SKIP[el.tagName]) continue;
      var rect = el.getBoundingClientRect();
      // 1px 짜리 구분선·밑줄도 디자인 요소다 — 3px 그물에 걸려 사라지던 것을 살린다.
      // 보이는 칠이 없는 것은 아래 '의미있는가' 그물에서 어차피 빠진다.
      if (rect.width < 1 || rect.height < 1) continue;
      var cs = getComputedStyle(el);
      if (cs.display==='none' || cs.visibility==='hidden' || parseFloat(cs.opacity)===0) continue;

      // 부모가 아래 그물에서 빠지더라도 가상요소는 따로 담는다
      // (구분선을 단 li 는 제 칠도 글자도 없어 빠지지만, 그 ::after 는 엄연한 선이다).
      var 앞뒤 = [가상요소(el, rect, cs, '::before'), 가상요소(el, rect, cs, '::after')];
      for (var g=0; g<2; g++){ if (앞뒤[g]) raw.push(앞뒤[g]); }

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
        domId: el.id || '', sel: selectorOf(el).slice(0,120),
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
        id: 'dev-'+idx, role: o.tag, cls: o.cls, domId: o.domId, sel: o.sel, text: o.text, isText: o.isText,
        box: { x:r(o.rect.left-minX), y:r(o.rect.top-minY), w:r(o.rect.width), h:r(o.rect.height) },
        style: o.style, contentZone: false
      };
    });
    return { meta:{ label:name, source:'web-all', url:location.href, title:document.title, viewportWidth:window.innerWidth, artboardWidth:r(W), artboardHeight:r(H), contentX:r(minX), contentY:r(minY), docW:r(Math.max(document.documentElement.scrollWidth, document.body?document.body.scrollWidth:0)), capturedAt:new Date().toISOString(), toolVersion:'core-1.3' }, elements: elements };
  };
})();

(function(){var res=globalThis.__qaMeasure();var nm=res.meta.label;var blob=new Blob([JSON.stringify(res,null,2)],{type:'application/json'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='measure-'+nm+'.json';document.body.appendChild(a);a.click();a.remove();alert('측정 완료: '+res.elements.length+'개 요소\n파일: measure-'+nm+'.json (다운로드됨)\n폭 '+res.meta.artboardWidth+'px');})();
