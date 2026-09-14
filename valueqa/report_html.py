"""후보를 눈으로 보는 한 장 — 판정용이 아니라 '보고 고르는' 화면이다.

포털이 생기기 전까지 결과를 눈으로 확인하는 용도다. 여기 나온 것은 전부 **후보**이고,
지적으로 올리는 것은 사람이 포털에서 한다(CLAUDE.md 2번-2).
"""
import html


def _칸(값, 색이냐):
    글 = html.escape(str(값))
    if 색이냐 and isinstance(값, str) and 값.startswith("rgb"):
        return ('<span class="sw" style="background:%s"></span>%s' % (html.escape(값), 글))
    return 글


def _다른줄(rows):
    trs = ""
    for r in rows:
        if r["j"] == "pass" or r.get("cascade") or r.get("deferred"):
            continue
        색 = bool(r.get("color"))
        단위 = r.get("unit", "") if isinstance(r["a"], (int, float)) else ""
        trs += ("<tr><td class=k>%s</td><td>%s%s</td><td class=dev>%s%s</td></tr>"
                % (html.escape(r["label"]), _칸(r["a"], 색), 단위, _칸(r["b"], 색), 단위))
    if not trs:
        return ""
    return ("<table><thead><tr><th>항목</th><th>시안</th><th>개발</th></tr></thead><tbody>%s</tbody></table>" % trs)


def 한장(결과, 제목="값 대조 — 후보"):
    셈 = 결과["셈"]
    시안meta = 결과["meta"]["시안"]
    개발meta = 결과["meta"]["개발"]
    css = """
body{font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif;color:#1f2937;margin:0;padding:28px;background:#fff;line-height:1.55}
.wrap{max-width:880px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}
.meta{color:#6b7280;font-size:13px;border-bottom:2px solid #111;padding-bottom:12px;margin-bottom:18px}
.sum{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:22px}
.chip{border:1px solid #e5e7eb;border-radius:10px;padding:9px 14px;min-width:74px;text-align:center}
.chip .n{font-size:22px;font-weight:800}.chip .t{font-size:11px;color:#6b7280}
h2{font-size:15px;margin:22px 0 10px;padding-bottom:6px;border-bottom:1px solid #e5e7eb}
.it{border:1px solid #e5e7eb;border-left:4px solid #dc2626;border-radius:8px;margin-bottom:9px;overflow:hidden}
.it.struct{border-left-color:#d97706}.it.warn{border-left-color:#d97706}
.hd{display:flex;align-items:center;gap:8px;padding:9px 13px;background:#fafafa}
.hd .no{background:#dc2626;color:#fff;width:21px;height:21px;border-radius:999px;font-size:11px;font-weight:800;display:inline-flex;align-items:center;justify-content:center;flex:none}
.hd.struct .no{background:#d97706}
.hd .nm{font-weight:700;font-family:ui-monospace,monospace;font-size:13px;flex:1;word-break:break-all}
.hd .cf{font-size:11px;color:#6b7280;border:1px solid #e5e7eb;border-radius:999px;padding:2px 9px;flex:none}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:6px 13px;border-top:1px solid #eee}
th{color:#6b7280;font-weight:600;background:#fcfcfc;font-size:12px}
td.k{color:#6b7280;width:120px}td.dev{background:#fef2f2}
.sw{display:inline-block;width:11px;height:11px;border-radius:3px;border:1px solid #0002;vertical-align:middle;margin-right:5px}
.note{padding:9px 13px;font-size:13px;color:#92400e}
.foot{margin-top:26px;color:#9ca3af;font-size:11px;text-align:center}
"""
    h = ['<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>%s</title><style>%s</style></head><body><div class="wrap">'
         % (html.escape(제목), css)]
    h.append("<h1>%s</h1>" % html.escape(제목))
    h.append('<div class="meta">시안 %s · %spx ↔ 개발 %s · %spx%s</div>'
             % (html.escape(str(시안meta.get("frameName") or "")), 시안meta.get("artboardWidth") or "",
                html.escape(str(개발meta.get("label") or "")), 개발meta.get("artboardWidth") or "",
                " · 폭이 서로 다름(크기 차이는 참고로 내림)" if 결과["폭다름"] else ""))
    h.append('<div class="sum">'
             '<div class="chip"><div class="n" style="color:#dc2626">%d</div><div class="t">후보</div></div>'
             '<div class="chip"><div class="n" style="color:#d97706">%d</div><div class="t">주의(미세)</div></div>'
             '<div class="chip"><div class="n" style="color:#6b7280">%d</div><div class="t">밀림 여파</div></div>'
             '<div class="chip"><div class="n" style="color:#16a34a">%d</div><div class="t">일치</div></div>'
             '<div class="chip"><div class="n">%d</div><div class="t">짝</div></div></div>'
             % (셈["후보"], 셈["주의"], 셈["밀림"], 셈["일치"], 셈["짝"]))

    h.append("<h2>사람이 볼 후보 (%d)</h2>" % 셈["후보"])
    for i, c in enumerate(결과["후보"], 1):
        구조 = c["갈래"] != "값다름"
        h.append('<div class="it%s"><div class="hd%s"><span class="no">%d</span>'
                 '<span class="nm">%s</span><span class="cf">믿음 %.2f</span></div>'
                 % (" struct" if 구조 else "", " struct" if 구조 else "", i,
                    html.escape(c["이름"]), c["신뢰도"]))
        if c["갈래"] == "더있음":
            h.append('<div class="note">시안에 없는 것이 개발에 있어요</div>')
        elif c["갈래"] == "빠짐":
            h.append('<div class="note">시안에 있는데 개발에서 못 찾았어요</div>')
        else:
            h.append(_다른줄(c["rows"]))
        h.append("</div>")
    if not 결과["후보"]:
        h.append('<div class="note" style="color:#16a34a">다른 곳이 안 보입니다</div>')

    if 결과["주의"]:
        h.append("<h2>주의 — 미세 차이 (%d)</h2>" % len(결과["주의"]))
        for c in 결과["주의"]:
            h.append('<div class="it warn"><div class="hd struct"><span class="no" style="background:#d97706">·</span>'
                     '<span class="nm">%s</span></div>%s</div>' % (html.escape(c["이름"]), _다른줄(c["rows"])))

    h.append('<div class="foot">값 대조 후보 — 지적이 아니라 후보입니다. 확정은 사람이 포털에서 합니다.<br>'
             '안쪽여백(padding)은 퍼블리싱 소관이라 후보로 올리지 않습니다. 위치(x·y)는 참고로만 둡니다.</div>')
    h.append("</div></body></html>")
    return "".join(h)
