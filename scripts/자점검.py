# -*- coding: utf-8 -*-
"""자(尺) 점검 — 좌표가 어긋난 화면을 사람이 눈으로 찾기 전에 짚는다.

보는 것 둘:
1. 자 자체가 제 일을 하는지 (`자.py` 의 자체검사)
2. 접수된 화면마다 **시안과 개발이 같은 자 위에 있는지** — 짝이 맞은 요소들의 크기 비를 되짚어
   1.0 에서 벗어나면 짚는다. 어긋나면 그 화면은 자리·크기 견주기를 믿을 수 없다.

돌리기: python3 scripts/자점검.py
"""
import glob
import json
import os
import sys

뿌리 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, 뿌리)

import 설정                                          # noqa: E402
import 자 as 자모듈                                   # noqa: E402
from valueqa.__main__ import 시안읽기                  # noqa: E402
from valueqa.match import 짝맞추기                     # noqa: E402

문턱 = 0.02                                          # 2% 넘게 벗어나면 짚는다


def 가운뎃값(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def 한화면(시안길, 개발길):
    시안 = 시안읽기(시안길)
    with open(개발길, encoding='utf-8') as f:
        개발 = json.load(f)
    M = 짝맞추기(시안, 개발)
    fig, 화면상자, 짝 = M['fig'], M['화면상자'], M['pairs']
    비, 가로벌 = [], []
    for p in 짝:
        f, b = fig[p['fi']], 화면상자[p['di']]
        if f['box']['w'] > 20 and b['w'] > 20:
            비.append(f['box']['w'] / b['w'])
        if f['box']['h'] > 20 and b['h'] > 20:
            비.append(f['box']['h'] / b['h'])
        가로벌.append(abs(f['box']['x'] - b['x']))
    ㅈ = M['자']
    # 세로는 시안 목업 높이 탓에 밀릴 수 있지만, 가로는 같은 자면 겹쳐야 한다.
    return ㅈ, len(짝), 가운뎃값(비), 가운뎃값(가로벌)


def 회차자():
    """후보를 잰 촬영본과 지금 쓰는 좌표 기준이 **비를 지키는지**.

    가로·세로 배율이 갈리면 그림이 찌그러진 것이고, 그런 자리는 핀이 요소에서 벗어난다.
    """
    import sqlite3
    길 = os.path.join(뿌리, 설정.자리('포털.자료함'))
    if not os.path.exists(길):
        return []
    c = sqlite3.connect(길)
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute("""SELECT r.capture_w cw, r.capture_h ch, ir.coord_ref_w rw, ir.coord_ref_h rh, COUNT(*) n
                            FROM auto_run r JOIN inspection_run ir ON ir.uuid=r.run_id
                            WHERE r.capture_w AND ir.coord_ref_w GROUP BY 1,2,3,4""").fetchall()
    except sqlite3.OperationalError:
        return []                                   # 옛 자료함
    finally:
        c.close()
    말 = []
    for r in rows:
        가로 = r['rw'] / r['cw']
        세로 = (r['rh'] / r['ch']) if (r['rh'] and r['ch']) else 가로
        if abs(가로 - 세로) > 문턱:
            말.append('촬영본 %sx%s ↔ 좌표 기준 %sx%s — 가로 %.3f 배 · 세로 %.3f 배로 갈립니다 (회차 %d개)'
                      % (r['cw'], r['ch'], r['rw'], r['rh'], 가로, 세로, r['n']))
    return 말


def main():
    문제 = 자모듈.점검()
    for x in 문제:
        print('✗ 자 자체검사 —', x)
    for x in 회차자():
        print('✗ 회차 자 —', x)
        문제.append(x)
    보관 = os.path.join(뿌리, 설정.자리('포털.그림보관'))
    짚은것 = 0
    본것 = 0
    for 개발길 in sorted(glob.glob(os.path.join(보관, '*_dev값.json'))):
        시안길 = 개발길.replace('_dev값.json', '_design.json')
        if not os.path.exists(시안길):
            continue
        이름 = os.path.basename(개발길)[:8]
        try:
            ㅈ, 짝수, 비, 가로벌 = 한화면(시안길, 개발길)
        except Exception as e:
            print('✗ %s — 읽지 못했습니다 (%s)' % (이름, e))
            짚은것 += 1
            continue
        본것 += 1
        if 비 is None:
            print('· %s — 짝이 적어 재지 못했습니다(짝 %d)' % (이름, 짝수))
            continue
        if abs(비 - 1.0) > 문턱:
            print('✗ %s — 시안과 개발의 자가 %.3f 배 어긋납니다 (짝 %d · 시안폭 %g · 화면폭 %g)'
                  % (이름, 비, 짝수, ㅈ.시안폭, ㅈ.화면폭))
            짚은것 += 1
        elif 가로벌 is not None and 가로벌 > ㅈ.시안폭 * 문턱:
            print('✗ %s — 가로가 %.0fpx 밀려 있습니다 (짝 %d · 시안폭 %g)' % (이름, 가로벌, 짝수, ㅈ.시안폭))
            짚은것 += 1
    if 문제:
        짚은것 += len(문제)
    print('— 화면 %d개 봄 · 짚은 것 %d개' % (본것, 짚은것))
    return 1 if 짚은것 else 0


if __name__ == '__main__':
    raise SystemExit(main())
