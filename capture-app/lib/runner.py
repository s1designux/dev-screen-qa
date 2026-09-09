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


def 사진찾기(임시폴더):
    """촬영 도구가 임시로 떨궈 놓은 사진 한 장을 찾는다."""
    후보 = glob.glob(os.path.join(임시폴더, "**", "takeScreenshot", "*.png"), recursive=True)
    return 후보[0] if 후보 else None


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
    목록 = 찍기(tag, 결과폴더)

    print(f"\n■ 끝. 찍힌 것 {len(목록['찍힌것'])}장 / 못 찍은 것 {len(목록['못찍은것'])}장")
    print(f"   폴더: {결과폴더}")
    if 목록["못찍은것"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
