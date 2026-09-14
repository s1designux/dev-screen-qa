"""이름표 한 장을 받아 화면을 차례로 찍고, 포털이 알아보는 이름으로 붙인다.

찍는 일 자체는 hands/ 안의 '손'이 한다(안드로이드는 android.sh).
여기서는 무엇을 찍을지 정하고, 이름을 붙이고, 찍은 목록을 남긴다.
"""
import json
import os
import re
import glob
import shutil
import subprocess
import sys
import time
from datetime import datetime

여기 = os.path.dirname(os.path.abspath(__file__))
뿌리 = os.path.dirname(여기)
sys.path.insert(0, 여기)

import account  # noqa: E402
import actions  # noqa: E402
import burst  # noqa: E402
import learn  # noqa: E402
import nametag  # noqa: E402
import places  # noqa: E402
import webshot  # noqa: E402

손 = {"android": "android.sh", "ios": "android.sh", "web": "web.sh"}


def 기기정보():
    """어느 폰으로 몇 픽셀에서 찍었는지 남긴다(나중에 겹쳐보기에 필요)."""
    def adb(*args):
        try:
            out = subprocess.run(
                [os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"), *args],
                capture_output=True, text=True, timeout=10)
            return out.stdout.strip()
        except Exception:
            return ""
    모델 = adb("shell", "getprop", "ro.product.model")
    크기 = adb("shell", "wm", "size").replace("Physical size:", "").strip()
    밀도 = adb("shell", "wm", "density").replace("Physical density:", "").strip()
    안드 = adb("shell", "getprop", "ro.build.version.release")
    return {"기기": 모델, "화면크기": 크기, "밀도": 밀도, "안드로이드": 안드}


def 사진찾기(임시폴더, 이름=None):
    """촬영 도구가 임시로 떨궈 놓은 사진을 찾는다(이름을 주면 그 사진만)."""
    무늬 = f"{이름}.png" if 이름 else "*.png"
    후보 = glob.glob(os.path.join(임시폴더, "**", "takeScreenshot", 무늬), recursive=True)
    return 후보[0] if 후보 else None


def _따옴표(v):
    """대본에 글자를 안전하게 넣는다."""
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def 묶기(화면들):
    """'이어서'가 예인 화면은 앞 화면과 한 묶음 — 앱을 껐다 켜지 않고 이어 찍는다."""
    묶음 = []
    for s in 화면들:
        if 묶음 and s.get("이어서", "아니오") == "예":
            묶음[-1].append(s)
        else:
            묶음.append([s])
    return 묶음


# 스플래시는 몇 백 밀리초 만에 지나간다 — 시간을 맞추지 않고 연사로 찍는다(burst.py).
스플래시인가 = burst.스플래시인가


def 연사로찍을묶음인가(plat, 한묶음):
    """앱을 켠 순간만 찍으면 되는 한 장짜리 스플래시 묶음인가.

    연사는 폰 안에서 도는 것이라 안드로이드에서만 된다. 상태 변형이 뒤에
    이어붙은 묶음(이어서=예)은 앱을 켜 둔 채로 계속 눌러야 하므로 예전 길로 간다.
    """
    return plat == "android" and len(한묶음) == 1 and 스플래시인가(한묶음[0])


def 기다림으로끝나나(동작):
    """동작이 '기다림 3' 으로 끝나면 뒤에 기다림을 또 붙이지 않는다(겹쳐서 느려진다)."""
    마디들 = actions.쪼개기(동작)
    return bool(마디들) and 마디들[-1].split(None, 1)[0] in ("기다림", "대기")


def 대본쓰기(tag, 한묶음, 사진이름들, 대본폴더, 순번, 계정=None, 자리=None):
    """한 묶음(같은 화면의 상태들)을 한 대본으로 적는다.

    동작에 적힌 <아이디>·<비번> 표식은 여기서 진짜 시험 계정으로 바뀐다.
    스플래시 화면은 앱이 뜨기를 기다리지 않고 곧바로 찍는다.
    기억해 둔 자리가 있으면 글자를 찾지 않고 그 자리를 바로 누른다(빠르다).
    """
    줄 = [f"appId: {tag.get('앱주소','')}", "---", "- stopApp", "- launchApp"]
    if not 스플래시인가(한묶음[0]):
        줄 += ["- waitForAnimationToEnd:", "    timeout: 5000"]
    첫장 = 한묶음[0]
    누를것 = 첫장.get("누를것", "-")
    if 누를것 not in ("-", "", "없음"):
        줄 += ["- scrollUntilVisible:", "    element:",
              f"      text: {_따옴표(누를것)}", "    direction: DOWN",
              "    timeout: 10000", f"- tapOn: {_따옴표(누를것)}",
              "- waitForAnimationToEnd:", "    timeout: 5000"]

    for s, 사진이름 in zip(한묶음, 사진이름들):
        동작 = s.get("동작", "")
        줄 += actions.옮기기(동작, 계정, account.실패화면(s.get("이름", "")), 자리)
        # 동작 뒤에는 화면이 가라앉기를 기다린다. 스플래시만은 기다리지 않는다 —
        # 기다리는 사이에 이미 다음 화면으로 넘어가 버리기 때문이다.
        # 동작이 '기다림'으로 끝났으면 방금 기다린 것이므로 또 기다리지 않는다.
        if (동작.strip() not in ("", "-", "없음") and not 스플래시인가(s)
                and not 기다림으로끝나나(동작)):
            줄 += ["- waitForAnimationToEnd:", "    timeout: 2000"]
        줄 += [f"- takeScreenshot: {사진이름[:-4]}"]

    경로 = os.path.join(대본폴더, f"{순번:03d}.yaml")
    with open(경로, "w", encoding="utf-8") as f:
        f.write("\n".join(줄) + "\n")
    return 경로


def 연사한장(tag, 화면, 결과폴더, 찍힌것, 실패):
    """스플래시 한 장을 연사로 찍고 고른 결과를 목록에 담는다.

    적어 둔 '기다림 …' 은 여기서 쓰지 않는다 — 기다릴 시간을 사람이 맞추지
    않아도 되게 하려고 연사로 바꾼 것이기 때문이다.
    """
    사진이름 = nametag.사진이름(tag, 화면)
    기록 = os.path.join(결과폴더, "연사기록", 사진이름[:-4])
    try:
        결과 = burst.찍기(tag.get("앱주소", ""), os.path.join(결과폴더, 사진이름), 기록)
    except Exception as e:
        까닭 = f"연사로 찍지 못했습니다 — {e}"
        print(f"  ✗ {화면['이름']} — {까닭}", flush=True)
        실패.append({"화면이름": 화면["이름"], "까닭": 까닭})
        return
    print(f"  ✓ {화면['이름']} → {사진이름}"
          f"  (연사 {결과['장수']}장 중 {결과['고른때']}밀리초 장 — {결과['까닭']})", flush=True)
    찍힌것.append({"파일": 사진이름, "화면번호": 화면["번호"], "화면이름": 화면["이름"],
                 "상태": 화면.get("상태", "default"),
                 "연사": {"장수": 결과["장수"], "고른때": 결과["고른때"],
                        "까닭": 결과["까닭"], "기록폴더": os.path.relpath(기록, 결과폴더)}})


def 자리기억켰나():
    """'자리기억' 이라고 뒤에 붙여 부르면 켜진다(기본은 꺼짐)."""
    return any(a.strip("-") == "자리기억" for a in sys.argv[1:])


def 묶음자리(한묶음, 자리사전):
    """이 묶음에서 쓸 '글자 → 자리' 만 추려 준다(화면마다 자리가 다르므로)."""
    추린것 = {}
    for s in 한묶음:
        for 글자 in actions.누를글자들(s.get("동작", "")):
            좌표 = 자리사전.get(places.열쇠(s["번호"], 글자))
            if 좌표:
                추린것[글자] = 좌표
    return 추린것


def 같은사진인가(가, 나):
    try:
        with open(가, "rb") as f1, open(나, "rb") as f2:
            return f1.read() == f2.read()
    except OSError:
        return False


def 다시찍기(tag, 묶음차례, 계정, 손파일, 결과폴더, 임시):
    """자리가 어긋나 앞 장과 똑같이 찍힌 묶음을, 글자로 찾는 예전 방식으로 다시 찍는다."""
    되돌릴것 = []
    for 한묶음, 사진이름들, 한묶음자리 in 묶음차례:
        if not 한묶음자리 or len(사진이름들) < 2:
            continue
        길 = [os.path.join(결과폴더, n) for n in 사진이름들]
        겹침 = any(같은사진인가(가, 나) for 가, 나 in zip(길, 길[1:]))
        if 겹침:
            되돌릴것.append((한묶음, 사진이름들))
    if not 되돌릴것:
        return

    앱주소 = tag.get("앱주소", "")
    for 한묶음, _ in 되돌릴것:
        places.지우기(앱주소, [places.열쇠(s["번호"], 글자) for s in 한묶음
                          for 글자 in actions.누를글자들(s.get("동작", ""))])
    print(f"기억해 둔 자리가 맞지 않는 묶음 {len(되돌릴것)}개를 글자로 다시 찍습니다.", flush=True)

    다시폴더 = os.path.join(임시, "다시대본")
    shutil.rmtree(다시폴더, ignore_errors=True)
    os.makedirs(다시폴더, exist_ok=True)
    for i, (한묶음, 사진이름들) in enumerate(되돌릴것, 1):
        대본쓰기(tag, 한묶음, 사진이름들, 다시폴더, i, 계정, None)
    다시임시 = os.path.join(임시, "다시")
    subprocess.run([손파일, 다시폴더, 앱주소, "-", "-", 다시임시],
                   capture_output=True, text=True)
    for _, 사진이름들 in 되돌릴것:
        for 사진이름 in 사진이름들:
            찍힌파일 = 사진찾기(다시임시, 사진이름[:-4])
            if 찍힌파일:
                shutil.move(찍힌파일, os.path.join(결과폴더, 사진이름))


def 한번에찍기(tag, 결과폴더):
    """화면 여러 장을 촬영 도구 한 번 띄워서 몰아 찍는다.

    예전에는 화면마다 촬영 도구를 새로 띄워서 한 장에 30초 가까이 걸렸다.
    대본을 미리 다 만들어 폴더째 넘기면 도구는 한 번만 뜬다.
    한 장이 실패해도 다음 장으로 넘어간다.
    """
    plat = tag["플랫폼"].strip().lower()
    손파일 = os.path.join(뿌리, "hands", 손.get(plat, ""))
    if not 손파일 or not os.path.exists(손파일):
        raise SystemExit(f"'{plat}' 을(를) 찍는 손이 아직 없습니다.")

    os.makedirs(결과폴더, exist_ok=True)
    임시 = os.path.join(결과폴더, ".찍는중")
    대본폴더 = os.path.join(임시, "대본")
    shutil.rmtree(임시, ignore_errors=True)
    os.makedirs(대본폴더, exist_ok=True)

    계정 = account.읽기(tag.get("앱이름", ""))
    빠짐 = [s["이름"] for s in tag["화면"] if account.표식있나(s.get("동작", ""))
          and not (계정["아이디"] and 계정["비밀번호"])]
    if 빠짐:
        print("시험 계정(아이디·비밀번호)이 비어 있습니다 — 촬영 준비 사이트 ②의 "
              "'앱 정보'에 적어 주세요. 그 전까지 아래 화면은 로그인이 되지 않습니다:\n    "
              + "\n    ".join(빠짐) + "\n", flush=True)

    묶음들 = 묶기(tag["화면"])
    찍힌것, 실패 = [], []

    # 스플래시는 촬영 도구에 맡기지 않고 먼저 연사로 찍는다(시간을 맞출 수 없으므로).
    연사묶음 = {id(묶) for 묶 in 묶음들 if 연사로찍을묶음인가(plat, 묶)}
    for 한묶음 in 묶음들:
        if id(한묶음) in 연사묶음:
            연사한장(tag, 한묶음[0], 결과폴더, 찍힌것, 실패)

    # 자리 기억 — 글자를 찾지 않고 좌표를 바로 누르면 빠르지만, 서버 응답에 따라
    # 단추가 오르내리는 화면에서는 헛손질이 된다(통근버스 로그인에서 두 장이 잘못 찍혔다).
    # 그래서 기본은 꺼 둔다. 화면이 늘 같은 자리인 앱에서만 켜서 쓴다:
    #     ./run.sh apps/이름표.yaml 자리기억
    자리기억 = 자리기억켰나()
    찍을묶음 = [묶 for 묶 in 묶음들 if id(묶) not in 연사묶음]
    if plat == "android" and 자리기억:
        try:
            learn.익히기(tag, 찍을묶음, 계정, 손파일, 결과폴더,
                      스플래시인가, account.실패화면)
        except Exception as e:
            print(f"자리를 익히지 못했습니다 — 예전처럼 글자로 찾아 찍습니다({e}).\n", flush=True)
    자리 = places.읽기(tag.get("앱주소", "")) if (plat == "android" and 자리기억) else {}

    이름들 = []
    묶음차례 = []
    순번 = 0
    for 한묶음 in 찍을묶음:
        순번 += 1
        사진이름들 = [nametag.사진이름(tag, s) for s in 한묶음]
        한묶음자리 = 묶음자리(한묶음, 자리)
        대본쓰기(tag, 한묶음, 사진이름들, 대본폴더, 순번, 계정, 한묶음자리)
        이름들 += list(zip(한묶음, 사진이름들))
        묶음차례.append((한묶음, 사진이름들, 한묶음자리))

    if not 이름들:
        shutil.rmtree(임시, ignore_errors=True)
        return 목록쓰기(tag, plat, 결과폴더, 찍힌것, 실패)

    print(f"촬영 도구를 한 번만 띄워 {len(이름들)}장을 찍습니다"
          f"({순번}묶음). 잠시 기다려 주세요.\n", flush=True)
    r = subprocess.run([손파일, 대본폴더, tag.get("앱주소", ""), "-", "-", 임시],
                       capture_output=True, text=True)

    if r.returncode != 0:
        꼬리 = [l for l in (r.stdout + r.stderr).strip().splitlines()
              if l.strip() and not l.strip().startswith(("│", "╭", "╰", "="))][-6:]
        print("촬영 도구가 알려 온 말:\n    " + "\n    ".join(꼬리) + "\n", flush=True)
    for s, 사진이름 in 이름들:
        찍힌파일 = 사진찾기(임시, 사진이름[:-4])
        if 찍힌파일:
            shutil.move(찍힌파일, os.path.join(결과폴더, 사진이름))

    # 기억해 둔 자리가 어긋나면 아무 일도 일어나지 않아 앞 장과 똑같은 사진이 찍힌다.
    # 그런 묶음은 자리 기억을 지우고 예전처럼 글자로 찾아 한 번 더 찍는다.
    다시찍기(tag, 묶음차례, 계정, 손파일, 결과폴더, 임시)

    for s, 사진이름 in 이름들:
        if os.path.exists(os.path.join(결과폴더, 사진이름)):
            print(f"  ✓ {s['이름']} → {사진이름}", flush=True)
            찍힌것.append({"파일": 사진이름, "화면번호": s["번호"], "화면이름": s["이름"],
                         "상태": s.get("상태", "default")})
        else:
            까닭 = ("눌러 들어갈 메뉴를 화면에서 찾지 못했습니다"
                  if s.get("누를것", "-") not in ("-", "", "없음")
                  else ("적어 둔 동작이 화면에서 되지 않았습니다"
                        if s.get("동작", "-") not in ("-", "", "없음") else "찍히지 않았습니다"))
            print(f"  ✗ {s['이름']} — {까닭}", flush=True)
            실패.append({"화면이름": s["이름"], "까닭": 까닭})

    shutil.rmtree(임시, ignore_errors=True)
    찍힌것.sort(key=lambda x: x["화면번호"])
    return 목록쓰기(tag, plat, 결과폴더, 찍힌것, 실패)


def 목록쓰기(tag, plat, 결과폴더, 찍힌것, 실패):
    목록 = {
        "앱이름": tag["앱이름"],
        "플랫폼": tag["플랫폼"],
        "찍은때": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **(기기정보() if plat == "android" else {}),
        "찍힌것": 찍힌것,
        "못찍은것": 실패,
    }
    with open(os.path.join(결과폴더, "찍은목록.json"), "w", encoding="utf-8") as f:
        json.dump(목록, f, ensure_ascii=False, indent=2)
    return 목록


def 찍기(tag, 결과폴더):
    plat = tag["플랫폼"].strip().lower()
    손파일 = os.path.join(뿌리, "hands", 손.get(plat, ""))
    if not 손파일 or not os.path.exists(손파일):
        raise SystemExit(f"'{plat}' 을(를) 찍는 손이 아직 없습니다.")

    os.makedirs(결과폴더, exist_ok=True)
    찍힌것, 실패 = [], []

    for i, s in enumerate(tag["화면"], 1):
        이름 = nametag.사진이름(tag, s)
        if 연사로찍을묶음인가(plat, [s]):
            print(f"[{i}/{len(tag['화면'])}] {s['이름']} → {이름}", flush=True)
            연사한장(tag, s, 결과폴더, 찍힌것, 실패)
            continue
        누를것 = s.get("누를것", "-")
        대본 = "shoot-home.yaml" if 누를것 in ("-", "", "없음") else "shoot-menu.yaml"
        대본경로 = os.path.join(뿌리, "flows", "android", 대본)
        임시 = os.path.join(결과폴더, ".찍는중")
        shutil.rmtree(임시, ignore_errors=True)

        print(f"[{i}/{len(tag['화면'])}] {s['이름']} → {이름}", flush=True)
        r = subprocess.run([손파일, 대본경로, tag.get("앱주소", ""), 누를것, 이름[:-4], 임시],
                           capture_output=True, text=True)
        찍힌파일 = 사진찾기(임시)
        if r.returncode == 0 and 찍힌파일:
            shutil.move(찍힌파일, os.path.join(결과폴더, 이름))
            shutil.rmtree(임시, ignore_errors=True)
            찍힌것.append({"파일": 이름, "화면번호": s["번호"], "화면이름": s["이름"],
                         "상태": s.get("상태", "default")})
        else:
            shutil.rmtree(임시, ignore_errors=True)
            꼬리 = [l for l in (r.stdout + r.stderr).strip().splitlines()
                  if l.strip() and not l.strip().startswith(("│", "╭", "╰", "="))][-3:]
            실패.append({"화면이름": s["이름"], "까닭": " / ".join(꼬리)})
            print(f"    ✗ 못 찍음: {' / '.join(꼬리)}", flush=True)

    목록 = {
        "앱이름": tag["앱이름"],
        "플랫폼": tag["플랫폼"],
        "찍은때": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **(기기정보() if plat == "android" else {}),
        "찍힌것": 찍힌것,
        "못찍은것": 실패,
    }
    with open(os.path.join(결과폴더, "찍은목록.json"), "w", encoding="utf-8") as f:
        json.dump(목록, f, ensure_ascii=False, indent=2)
    return 목록


def main():
    붙임말 = [a for a in sys.argv[1:] if a.strip("-") != "자리기억"]
    if not 붙임말:
        raise SystemExit("쓰는 법: ./run.sh apps/이름표.yaml")
    이름표경로 = 붙임말[0]
    tag = nametag.읽기(이름표경로)

    폴더이름 = time.strftime("%Y%m%d-%H%M") + "-" + tag["서비스코드"]
    결과폴더 = 붙임말[1] if len(붙임말) > 1 else os.path.join(뿌리, "shots", 폴더이름)

    print(f"■ {tag['앱이름']} — 화면 {len(tag['화면'])}개 찍습니다\n")
    if tag["플랫폼"].strip().lower() == "web":
        # 웹은 폰을 꽂지 않는다 — 브라우저만 열면 되므로 윈도우 PC에서 그대로 돈다.
        목록 = webshot.찍기(tag, 결과폴더)
        with open(os.path.join(결과폴더, "찍은목록.json"), "w", encoding="utf-8") as f:
            json.dump(목록, f, ensure_ascii=False, indent=2)
    else:
        한장씩 = os.environ.get("한장씩") == "1"      # 예전 방식(느림)으로 돌리고 싶을 때
        목록 = 찍기(tag, 결과폴더) if 한장씩 else 한번에찍기(tag, 결과폴더)

    print(f"\n■ 끝. 찍힌 것 {len(목록['찍힌것'])}장 / 못 찍은 것 {len(목록['못찍은것'])}장")
    print(f"   폴더: {결과폴더}")
    if 목록["못찍은것"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
