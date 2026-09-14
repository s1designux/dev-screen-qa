"""스플래시처럼 '지나가는 화면'을 연사로 찍고, 그중 한 장을 자동으로 고른다.

왜 필요한가
    스플래시가 머무는 시간은 폰 상태·앱 캐시·첫 실행 여부에 따라 매번 다르다.
    '0.1초 뒤에 찍기' 처럼 시간을 정해 두면 어떤 날은 홈 화면이, 어떤 날은
    다음 화면이 찍힌다. 그래서 시간을 맞추려 하지 않고, 앱을 켠 순간부터
    0.5초 동안 여러 장을 찍어 두고 그중 스플래시 한 장을 골라낸다.

어떻게 찍는가
    사진 한 장을 폰에서 PC로 가져오는 데 0.3초가 걸린다. 그래서 찍는 일은
    폰 안에서 하고(약 0.2초에 한 장), 그것도 네 줄기를 조금씩 어긋나게 동시에
    돌린다. 그러면 0.5초 안에 여덟 장 안팎이 남는다. 다 찍은 뒤에 한꺼번에
    가져온다.

어떻게 고르는가
    ① 앱을 켜기 직전 화면(직전 장)과 똑같은 장은 버린다 — 아직 안 뜬 것이다.
    ② 온통 한 색인 장(까맣게 넘어가는 순간)은 버린다.
    ③ 남은 장을 '앞 장과 같으면 한 덩어리'로 묶는다.
    ④ 0.15초 넘게 머문 첫 덩어리의 마지막 장을 고른다 — 로고가 다 그려지고
       화면이 멈춘 첫 순간이 스플래시다. (앱을 켤 때 잠깐 스치는 '앱 아이콘만
       있는 화면'은 머무는 시간이 짧아 여기서 걸러진다.)
    고르기가 틀릴 수 있으므로 찍은 장을 모두 남긴다(연사기록 폴더). 사람이
    다른 장으로 바꿔 넣으면 그만이다.

바깥 라이브러리를 쓰지 않는다(설치 묶음 배포 때 파이썬만 있으면 돌아가게).
사진은 폰에서 날것(raw)으로 받아 파이썬 표준 zlib으로 PNG를 만든다.
"""
import os
import re
import shutil
import struct
import subprocess
import zlib

폰폴더 = "/data/local/tmp/qa_burst"
같은화면임계 = 4.0      # 0~255. 이보다 작으면 '같은 화면'으로 본다
민무늬임계 = 12         # 밝기 폭이 이보다 좁으면 '온통 한 색'
머문시간임계 = 150      # 밀리초 — 이보다 짧게 머문 구간은 스플래시로 치지 않는다
기본창 = 0.5            # 초 — 앱을 켠 뒤 이만큼 찍는다
갈래 = 4                # 폰 안에서 동시에 도는 촬영 줄기 수


def adb():
    """어느 PC에서든 adb 를 찾아 쓴다."""
    찾은것 = shutil.which("adb")
    if 찾은것:
        return 찾은것
    자리 = os.path.expanduser("~/Library/Android/sdk/platform-tools/adb")
    return 자리 if os.path.exists(자리) else "adb"


def _adb실행(*args, timeout=90):
    return subprocess.run([adb(), *args], capture_output=True, text=True, timeout=timeout)


def _폰대본(앱주소, 창):
    """폰 안에서 돌 대본. 앱을 켜는 것과 찍는 것을 동시에 시작한다."""
    창ms = int(창 * 1000)
    어긋남 = [round(i * 0.22 / 갈래, 3) for i in range(갈래)]
    줄기 = " & ".join(
        (f"찍기 {i}" if t == 0 else f"(sleep {t}; 찍기 {i})") for i, t in enumerate(어긋남)
    )
    # 폰 셸이라 한글 함수 이름을 못 쓴다 — 여기서만 영문으로 적는다.
    줄기 = 줄기.replace("찍기", "cap")
    return f"""
app={앱주소}
dir={폰폴더}
rm -rf $dir; mkdir -p $dir
am force-stop $app
comp=$(cmd package resolve-activity --brief -c android.intent.category.LAUNCHER $app | tail -1)
screencap $dir/ref.raw
cap() {{
  j=$1; i=0
  end=$(( $(date +%s%3N) + {창ms} ))
  while [ $(date +%s%3N) -lt $end ]; do
    echo "$(date +%s%3N) ${{j}}_${{i}}"
    screencap $dir/${{j}}_${{i}}.raw
    i=$(( i + 1 ))
  done
}}
echo "T0 $(date +%s%3N)"
am start -n $comp > /dev/null 2>&1 &
{줄기}
wait
"""


def _연사(앱주소, 받을폴더, 창):
    """폰에서 연사하고 찍힌 것을 통째로 가져온다. [(밀리초, 파일경로)] 를 돌려준다."""
    r = _adb실행("shell", _폰대본(앱주소, 창))
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])

    t0, 차례 = None, []
    for 줄 in r.stdout.splitlines():
        낱말 = 줄.split()
        if len(낱말) == 2 and 낱말[0] == "T0" and 낱말[1].isdigit():
            t0 = int(낱말[1])
        elif len(낱말) == 2 and 낱말[0].isdigit():
            차례.append((int(낱말[0]), 낱말[1]))
    if t0 is None or not 차례:
        raise RuntimeError("폰이 사진을 한 장도 찍지 못했습니다.")

    os.makedirs(받을폴더, exist_ok=True)
    _adb실행("pull", "-a", 폰폴더, 받을폴더, timeout=180)
    _adb실행("shell", f"rm -rf {폰폴더}")
    안 = os.path.join(받을폴더, os.path.basename(폰폴더))
    if os.path.isdir(안):                      # adb 버전에 따라 한 겹 더 들어간다
        for f in os.listdir(안):
            shutil.move(os.path.join(안, f), os.path.join(받을폴더, f))
        os.rmdir(안)

    차례.sort()
    프레임 = [(밀리 - t0, os.path.join(받을폴더, f"{이름}.raw")) for 밀리, 이름 in 차례]
    프레임 = [(ms, p) for ms, p in 프레임 if os.path.exists(p)]
    if not 프레임:
        raise RuntimeError("폰에서 사진을 가져오지 못했습니다 — 케이블과 화면 잠금을 확인해 주세요")
    return 프레임, os.path.join(받을폴더, "ref.raw")


def _읽기(경로):
    """폰이 준 날것 사진 → (가로, 세로, 원본바이트)."""
    with open(경로, "rb") as f:
        머리 = f.read(16)
        w, h, _꼴, _색 = struct.unpack("<IIII", 머리)
        본문 = f.read()
    if len(본문) < w * h * 4:                   # 옛 안드로이드는 머리가 12바이트
        with open(경로, "rb") as f:
            w, h, _꼴 = struct.unpack("<III", f.read(12))
            본문 = f.read()
    return w, h, 본문


def _간추리기(경로, 칸=48, 잔=4):
    """사진을 아주 작은 밝기 표로 줄인다(비교만 할 것이라 이 정도면 넉넉하다).

    한 칸의 밝기를 점 하나로 뽑지 말고 그 칸 안 여러 점의 평균으로 낸다.
    점 하나로 뽑으면 글자 획에 걸릴 때마다 값이 크게 튀어, 상태바가 사라지는
    정도의 작은 변화가 '다른 화면'으로 잘못 읽힌다.
    """
    w, h, 본문 = _읽기(경로)
    칸너비 = max(1, w // 칸)
    칸높이 = max(1, h // (칸 * 2))
    가로걸음 = max(1, 칸너비 // 잔)
    세로걸음 = max(1, 칸높이 // 잔)
    표 = []
    for 칸y in range(0, h - 칸높이 + 1, 칸높이):
        for 칸x in range(0, w - 칸너비 + 1, 칸너비):
            합 = 수 = 0
            for dy in range(0, 칸높이, 세로걸음):
                바닥 = (칸y + dy) * w * 4
                for dx in range(0, 칸너비, 가로걸음):
                    i = 바닥 + (칸x + dx) * 4
                    합 += 본문[i] * 3 + 본문[i + 1] * 6 + 본문[i + 2]
                    수 += 10
            표.append(합 // 수 if 수 else 0)
    return 표


def _차이(a, b):
    if not a or not b or len(a) != len(b):
        return 255.0
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def _민무늬(표):
    return bool(표) and (max(표) - min(표)) < 민무늬임계


def 고르기(간추린것, 직전):
    """[(밀리초, 표)] 중 스플래시 한 장의 자리와 고른 까닭을 돌려준다."""
    쓸것 = [(i, ms, 표) for i, (ms, 표) in enumerate(간추린것)
          if not (직전 and _차이(표, 직전) < 같은화면임계) and not _민무늬(표)]
    if not 쓸것:
        남은것 = [(i, ms, 표) for i, (ms, 표) in enumerate(간추린것) if not _민무늬(표)]
        if not 남은것:
            return len(간추린것) // 2, "쓸 만한 장이 없어 가운데 장을 골랐습니다"
        return 남은것[-1][0], "앱이 뜨기 전 화면만 찍혀 마지막 장을 골랐습니다"

    덩어리, 이번 = [], [쓸것[0]]
    for 앞, 뒤 in zip(쓸것, 쓸것[1:]):
        if _차이(앞[2], 뒤[2]) < 같은화면임계:
            이번.append(뒤)
        else:
            덩어리.append(이번)
            이번 = [뒤]
    덩어리.append(이번)

    # 안드로이드는 앱을 켜면 앱 아이콘만 있는 화면을 잠깐 보여 준다. 이것도 '멈춰
    # 있는 구간'이라 자칫 스플래시로 잘못 집는다. 그래서 오래 머문 구간만 인정한다.
    for 한덩어리 in 덩어리:
        머문시간 = 한덩어리[-1][1] - 한덩어리[0][1]
        if len(한덩어리) >= 2 and 머문시간 >= 머문시간임계:
            return 한덩어리[-1][0], (f"{머문시간}밀리초 동안 멈춰 있던 첫 구간"
                                 f"({len(한덩어리)}장)의 마지막 장")
    for 한덩어리 in 덩어리:                      # 아주 짧은 스플래시면 이쪽으로
        if len(한덩어리) >= 2:
            return 한덩어리[-1][0], f"잠깐({한덩어리[-1][1] - 한덩어리[0][1]}밀리초) 멈춘 첫 구간의 마지막 장"
    return 쓸것[-1][0], "화면이 계속 바뀌어 마지막 장을 골랐습니다"


def png쓰기(raw경로, 저장경로):
    """폰이 준 날것 사진을 PNG 한 장으로 만든다(표준 zlib만 쓴다)."""
    w, h, 본문 = _읽기(raw경로)
    줄들 = bytearray()
    for y in range(h):
        바닥 = y * w * 4
        줄들.append(0)                          # 필터 없음
        줄들 += 본문[바닥:바닥 + w * 4]

    def 토막(이름, 속):
        return (struct.pack(">I", len(속)) + 이름 + 속
                + struct.pack(">I", zlib.crc32(이름 + 속) & 0xFFFFFFFF))

    머리 = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)   # 8비트 RGBA
    with open(저장경로, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(토막(b"IHDR", 머리))
        f.write(토막(b"IDAT", zlib.compress(bytes(줄들), 6)))
        f.write(토막(b"IEND", b""))


def 찍기(앱주소, 저장경로, 기록폴더, 창=기본창):
    """앱을 켜자마자 연사하고, 고른 한 장을 저장경로에 PNG로 남긴다.

    찍은 장은 모두 기록폴더에 PNG로 함께 남긴다(고르기가 틀렸을 때 바꿔 넣으라고).
    """
    임시 = 기록폴더 + ".받는중"
    shutil.rmtree(임시, ignore_errors=True)
    shutil.rmtree(기록폴더, ignore_errors=True)
    try:
        try:
            프레임, 직전경로 = _연사(앱주소, 임시, 창)
        except RuntimeError:                    # USB가 한 번 끊기는 일이 있다 — 한 번만 다시
            shutil.rmtree(임시, ignore_errors=True)
            프레임, 직전경로 = _연사(앱주소, 임시, 창)
        간추린것 = [(ms, _간추리기(p)) for ms, p in 프레임]
        직전 = _간추리기(직전경로) if os.path.exists(직전경로) else None
        자리, 까닭 = 고르기(간추린것, 직전)

        os.makedirs(기록폴더, exist_ok=True)
        for i, (ms, p) in enumerate(프레임):
            표 = "★" if i == 자리 else "-"
            png쓰기(p, os.path.join(기록폴더, f"{i:02d}_{max(ms,0):04d}ms{표}.png"))
        png쓰기(프레임[자리][1], 저장경로)
        return {"장수": len(프레임), "고른때": max(프레임[자리][0], 0), "까닭": 까닭,
                "기록폴더": 기록폴더}
    finally:
        shutil.rmtree(임시, ignore_errors=True)


_스플래시 = re.compile(r"splash|스플래시|스플레시", re.I)


def 스플래시인가(화면):
    return bool(_스플래시.search(화면.get("이름", "") or ""))
