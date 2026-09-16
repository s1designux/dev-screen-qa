"""'찍는 손'이 어디를 누르는지 **보이게** 하는 가상 마우스.

창을 보이게 찍을 때(webshot.숨어서찍나() 가 거짓일 때) 화면 위에 화살표 하나를 띄우고,
누를 것으로 스윽 옮긴 뒤 파문을 한 번 튀긴다. 사람이 옆에서 보며 "지금 저기를 누르는구나"
를 바로 알 수 있게 하는 것이 전부다 — 찍는 결과는 달라지지 않는다.

**사진·값에는 절대 들어가지 않는다.** 화살표는 동작을 하는 동안에만 문서에 붙어 있고,
값을 재거나 사진을 찍기 전에 `치우기()` 로 문서에서 통째로 뺀다.

끄고 싶으면 CAPTURE_CURSOR=0 (창을 숨겨 찍을 때는 저절로 꺼진다).
"""
import os
import time

옮기는초 = 0.38          # 화살표가 미끄러져 가는 시간 — 자바스크립트 쪽 transition 과 같아야 한다
누른뒤초 = 0.12          # 파문을 보여 주고 실제로 누르기까지의 틈
표시 = "data-capture-cursor"


def 켜졌나(보이나=None):
    값 = (os.environ.get("CAPTURE_CURSOR", "") or "").strip().lower()
    if 값 in ("0", "false", "n", "no", "off"):
        return False
    if 보이나 is None:
        import webshot
        보이나 = not webshot.숨어서찍나()
    return bool(보이나)


_그리기 = """
([x, y, 누름, 옮기는초]) => {
  const 표시 = 'data-capture-cursor';
  let 켜 = document.querySelector('style[' + 표시 + ']');
  if (!켜) {
    켜 = document.createElement('style');
    켜.setAttribute(표시, '1');
    켜.textContent = '@keyframes __촬영파문{from{opacity:.55;transform:translate(-50%,-50%) scale(.2)}' +
      'to{opacity:0;transform:translate(-50%,-50%) scale(1)}}';
    (document.head || document.documentElement).appendChild(켜);
  }
  let 것 = document.querySelector('div[' + 표시 + ']');
  if (!것) {
    것 = document.createElement('div');
    것.setAttribute(표시, '1');
    것.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:30px;z-index:2147483647;' +
      'pointer-events:none;filter:drop-shadow(0 2px 3px rgba(0,0,0,.45));' +
      'transform:translate(' + Math.round(innerWidth / 2) + 'px,' + (innerHeight - 40) + 'px);' +
      'transition:transform ' + 옮기는초 + 's cubic-bezier(.22,.61,.36,1);';
    것.innerHTML = '<svg width="22" height="30" viewBox="0 0 22 30" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M2 2 L2 21.5 L7.4 16.8 L10.8 25.6 L14.6 24 L11.2 15.6 L18.4 15.2 Z" ' +
      'fill="#ffffff" stroke="#111111" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    (document.body || document.documentElement).appendChild(것);
    void 것.offsetWidth;                    // 처음 놓은 자리에서 미끄러져 가게
  }
  것.style.transform = 'translate(' + (x - 2) + 'px,' + (y - 2) + 'px)';   // 화살표 끝이 그 자리에 오게
  if (누름) {
    const 파문 = document.createElement('div');
    파문.setAttribute(표시, '1');
    파문.style.cssText = 'position:fixed;left:' + x + 'px;top:' + y + 'px;width:46px;height:46px;' +
      'margin:0;border-radius:50%;background:#1a73e8;z-index:2147483646;pointer-events:none;' +
      'animation:__촬영파문 .45s ease-out forwards;';
    (document.body || document.documentElement).appendChild(파문);
    setTimeout(() => 파문.remove(), 600);
  }
  return true;
}
"""

_지우기 = """
() => { document.querySelectorAll('[data-capture-cursor]').forEach(e => e.remove()); return true; }
"""


def 자리로(쪽, x, y, 누름=True):
    """그 자리로 화살표를 옮기고(누름=참이면) 파문을 한 번 튀긴다. 무슨 일이 나도 찍기를 막지 않는다."""
    if not 켜졌나():
        return
    try:
        쪽.evaluate(_그리기, [x, y, False, 옮기는초])
        time.sleep(옮기는초)
        if 누름:
            쪽.evaluate(_그리기, [x, y, True, 옮기는초])
            time.sleep(누른뒤초)
    except Exception:
        pass


def 것으로(것, 누름=True):
    """누를 것(로케이터) 한가운데로 옮긴다. 자리를 모르면 조용히 넘어간다."""
    if not 켜졌나():
        return
    try:
        상자 = 것.bounding_box()
        if not 상자:
            return
        자리로(것.page, 상자["x"] + 상자["width"] / 2, 상자["y"] + 상자["height"] / 2, 누름)
    except Exception:
        pass


def 치우기(쪽):
    """문서에서 화살표를 통째로 뺀다 — 값을 재거나 사진을 찍기 전에 꼭 부른다."""
    try:
        쪽.evaluate(_지우기)
    except Exception:
        pass
