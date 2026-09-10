"""이름표 한 장을 받아 화면을 차례로 찍고, 포털이 알아보는 이름으로 붙인다.

찍는 일 자체는 hands/ 안의 '손'이 한다(안드로이드는 android.sh).
여기서는 무엇을 찍을지 정하고, 이름을 붙이고, 찍은 목록을 남긴다.
"""
import json
import os
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
import nametag  # noqa: E402

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


def 대본쓰기(tag, 한묶음, 사진이름들, 대본폴더, 순번, 계정=None):
    """한 묶음(같은 화면의 상태들)을 한 대본으로 적는다.

    동작에 적힌 <아이디>·<비번> 표식은 여기서 진짜 시험 계정으로 바뀐다.
    """
    줄 = [f"appId: {tag.get('앱주소','')}", "---", "- stopApp", "- launchApp",
         "- waitForAnimationToEnd:", "    timeout: 5000"]
    첫장 = 한묶음[0]
    누를것 = 첫장.get("누를것", "-")
    if 누를것 not in ("-", "", "없음"):
        줄 += ["- scrollUntilVisible:", "    element:",
              f"      text: {_따옴표(누를것)}", "    direction: DOWN",
              "    timeout: 10000", f"- tapOn: {_따옴표(누를것)}",
              "- waitForAnimationToEnd:", "    timeout: 5000"]

    for s, 사진이름 in zip(한묶음, 사진이름들):
        줄 += actions.옮기기(s.get("동작", ""), 계정)
        if s.get("동작", "").strip() not in ("", "-", "없음"):
            줄 += ["- waitForAnimationToEnd:", "    timeout: 3000"]
        줄 += [f"- takeScreenshot: {사진이름[:-4]}"]

    경로 = os.path.join(대본폴더, f"{순번:03d}.yaml")
    with open(경로, "w", encoding="utf-8") as f:
        f.write("\n".join(줄) + "\n")
    return 경로


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
    이름들 = []
    for i, 한묶음 in enumerate(묶음들, 1):
        사진이름들 = [nametag.사진이름(tag, s) for s in 한묶음]
        대본쓰기(tag, 한묶음, 사진이름들, 대본폴더, i, 계정)
        이름들 += list(zip(한묶음, 사진이름들))

    print(f"촬영 도구를 한 번만 띄워 {len(이름들)}장을 찍습니다"
          f"({len(묶음들)}묶음). 잠시 기다려 주세요.\n", flush=True)
    r = subprocess.run([손파일, 대본폴더, tag.get("앱주소", ""), "-", "-", 임시],
                       capture_output=True, text=True)

    찍힌것, 실패 = [], []
    if r.returncode != 0:
        꼬리 = [l for l in (r.stdout + r.stderr).strip().splitlines()
              if l.strip() and not l.strip().startswith(("│", "╭", "╰", "="))][-6:]
        print("촬영 도구가 알려 온 말:\n    " + "\n    ".join(꼬리) + "\n", flush=True)
    for s, 사진이름 in 이름들:
        찍힌파일 = 사진찾기(임시, 사진이름[:-4])
        if 찍힌파일:
            shutil.move(찍힌파일, os.path.join(결과폴더, 사진이름))
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
    if len(sys.argv) < 2:
        raise SystemExit("쓰는 법: ./run.sh apps/이름표.yaml")
    이름표경로 = sys.argv[1]
    tag = nametag.읽기(이름표경로)

    폴더이름 = time.strftime("%Y%m%d-%H%M") + "-" + tag["서비스코드"]
    결과폴더 = sys.argv[2] if len(sys.argv) > 2 else os.path.join(뿌리, "shots", 폴더이름)

    print(f"■ {tag['앱이름']} — 화면 {len(tag['화면'])}개 찍습니다\n")
    한장씩 = os.environ.get("한장씩") == "1"      # 예전 방식(느림)으로 돌리고 싶을 때
    목록 = 찍기(tag, 결과폴더) if 한장씩 else 한번에찍기(tag, 결과폴더)

    print(f"\n■ 끝. 찍힌 것 {len(목록['찍힌것'])}장 / 못 찍은 것 {len(목록['못찍은것'])}장")
    print(f"   폴더: {결과폴더}")
    if 목록["못찍은것"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
