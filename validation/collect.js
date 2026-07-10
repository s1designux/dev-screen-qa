/* =====================================================================
   개발화면 측정 수집기 (웹용) — v0.1  ⚠️[구버전]
   ※ 이건 data-qa 태그가 '필요한' 옛 버전입니다. 현재 플러그인은 태그 없이 재는
     plugin-value-qa/collect.js 를 씁니다. 이 파일은 초기 증명용으로만 보관.
   사용법: 검사할 화면을 브라우저에서 연 뒤, F12 → Console 탭에
           이 파일 내용을 통째로 붙여넣고 Enter.
           → 측정 결과 JSON 파일이 자동으로 다운로드됩니다.
   특징: 색·크기·위치·폰트·간격 같은 '스타일 값'만 모읍니다.
         글자 내용(샘플 텍스트)은 모으지 않으므로 검수에서 자동 제외됩니다.
   ===================================================================== */
(function () {
  // 측정 기준점(정답과 개발을 같은 좌표계로 맞추기 위한 앵커)
  var root = document.querySelector('[data-qa-root]') || document.body;
  var rootRect = root.getBoundingClientRect();
  var label = (root.getAttribute && root.getAttribute('data-qa-label')) || 'dev';

  // 소수점 1자리 반올림
  function r(n) { return Math.round(n * 10) / 10; }
  // "12px" -> 12 (숫자만)
  function num(v) { var f = parseFloat(v); return isNaN(f) ? 0 : r(f); }
  // 첫 번째 폰트 이름만 (따옴표 제거)
  function firstFont(v) { return (v || '').split(',')[0].replace(/["']/g, '').trim(); }

  var nodes = document.querySelectorAll('[data-qa]');
  var elements = [];

  nodes.forEach(function (el) {
    var qa = el.getAttribute('data-qa');
    var rect = el.getBoundingClientRect();
    var cs = getComputedStyle(el);

    elements.push({
      qa: qa,
      role: el.tagName,
      box: {
        x: r(rect.left - rootRect.left),
        y: r(rect.top - rootRect.top),
        w: r(rect.width),
        h: r(rect.height)
      },
      style: {
        color:           cs.color,
        backgroundColor: cs.backgroundColor,
        fontSize:        num(cs.fontSize),
        fontWeight:      num(cs.fontWeight),
        fontFamily:      firstFont(cs.fontFamily),
        lineHeight:      num(cs.lineHeight),
        borderRadius:    num(cs.borderTopLeftRadius),
        borderWidth:     num(cs.borderTopWidth),
        borderColor:     cs.borderTopColor,
        paddingTop:      num(cs.paddingTop),
        paddingRight:    num(cs.paddingRight),
        paddingBottom:   num(cs.paddingBottom),
        paddingLeft:     num(cs.paddingLeft),
        textAlign:       cs.textAlign,
        opacity:         num(cs.opacity)
      },
      // qa 이름이 content/ 로 시작하면 '샘플 콘텐츠 영역' → 위치·크기만 검사
      contentZone: qa.indexOf('content/') === 0,
      // 글자 요소(내용 길이에 따라 너비가 달라짐) → 너비·높이는 비교 제외, 위치·스타일만
      isText: el.hasAttribute('data-qa-text')
    });
  });

  var result = {
    meta: {
      label: label,
      source: 'web',
      url: location.href,
      viewportWidth: window.innerWidth,
      artboardWidth: r(rootRect.width),
      capturedAt: new Date().toISOString(),
      toolVersion: '0.1'
    },
    elements: elements
  };

  // 파일로 다운로드
  var json = JSON.stringify(result, null, 2);
  var blob = new Blob([json], { type: 'application/json' });
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'measure-' + label + '.json';
  document.body.appendChild(a);
  a.click();
  a.remove();

  console.log('%c✅ 측정 완료: ' + elements.length + '개 요소 → measure-' + label + '.json 다운로드됨',
    'color:#16A34A;font-weight:bold;');
})();
