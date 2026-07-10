// 화면 측정 + 픽셀-정확 캡처 — 확장앱 아이콘 클릭 시 실행
// 1) 페이지에 측정 코어(collect-core.js) 주입 → __qaMeasure() 로 값 수집
// 2) chrome.debugger 로 전체페이지 실픽셀 캡처(Page.captureScreenshot)
// 3) 값 JSON + 화면 PNG 둘 다 다운로드
chrome.action.onClicked.addListener(async function (tab) {
  if (!tab || !tab.id) return;
  var tabId = tab.id;
  try {
    // 1) 값 수집 (측정 코어는 collect-core.js 단일 원본 — build-tools가 동기화)
    await chrome.scripting.executeScript({ target: { tabId: tabId }, files: ['collect-core.js'] });
    var res = await chrome.scripting.executeScript({ target: { tabId: tabId }, func: function () { return globalThis.__qaMeasure(); } });
    var measure = res && res[0] && res[0].result;
    if (!measure || !measure.elements) throw new Error('측정 실패 (페이지에서 값 못 읽음)');
    var name = (measure.meta && measure.meta.label) || 'dev';

    // 2) 픽셀-정확 전체페이지 캡처
    var png = await captureFullPage(tabId);

    // 3) 다운로드 (서비스워커엔 createObjectURL 없음 → data URL 사용)
    downloadText('measure-' + name + '.json', JSON.stringify(measure, null, 2), 'application/json');
    if (png) chrome.downloads.download({ url: png, filename: 'screen-' + name + '.png', saveAs: false });

    toast(tabId, '✅ 측정 ' + measure.elements.length + '개 + 화면 캡처 완료 → 다운로드 (폭 ' + measure.meta.artboardWidth + 'px)');
  } catch (e) {
    console.error(e);
    toast(tabId, '⚠️ 실패: ' + (e && e.message ? e.message : e));
  }
});

async function captureFullPage(tabId) {
  var target = { tabId: tabId };
  try {
    await chrome.debugger.attach(target, '1.3');
    await chrome.debugger.sendCommand(target, 'Page.enable');
    var metrics = await chrome.debugger.sendCommand(target, 'Page.getLayoutMetrics');
    var cs = metrics.cssContentSize || metrics.contentSize || (metrics.cssLayoutViewport ? { width: metrics.cssLayoutViewport.clientWidth, height: metrics.cssLayoutViewport.clientHeight } : { width: 1280, height: 800 });
    var width = Math.min(16384, Math.ceil(cs.width)), height = Math.min(16384, Math.ceil(cs.height));
    var shot = await chrome.debugger.sendCommand(target, 'Page.captureScreenshot', {
      format: 'png', captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: width, height: height, scale: 1 }
    });
    return 'data:image/png;base64,' + shot.data;
  } catch (e) {
    console.error('capture 실패', e);
    return null;
  } finally {
    try { await chrome.debugger.detach(target); } catch (e) {}
  }
}

function downloadText(filename, text, mime) {
  var url = 'data:' + mime + ';charset=utf-8,' + encodeURIComponent(text);
  chrome.downloads.download({ url: url, filename: filename, saveAs: false });
}

function toast(tabId, msg) {
  chrome.scripting.executeScript({
    target: { tabId: tabId },
    func: function (m) {
      var d = document.createElement('div');
      d.textContent = m;
      d.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:2147483647;background:#111;color:#fff;font:14px/1.4 -apple-system,system-ui,sans-serif;padding:10px 16px;border-radius:8px;box-shadow:0 4px 16px #0005;max-width:80vw';
      document.body.appendChild(d);
      setTimeout(function () { d.remove(); }, 4000);
    },
    args: [msg]
  }).catch(function () {});
}
