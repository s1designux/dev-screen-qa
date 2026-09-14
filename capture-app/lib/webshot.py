"""'찍는 손' — PC 웹. 주소를 열어 **값을 긁고** 화면도 한 장 통짜로 찍는다.

PC 웹 검수는 그림 대조가 아니라 **값 대조**다(색·글꼴·크기·자리). 그래서 한 번 열 때
값(JSON)을 먼저 긁고, 사람이 좌우로 볼 그림(PNG)도 함께 남긴다.
그림 대조는 모바일 앱·설치형 소프트웨어 쪽 이야기다.

앱(안드로이드)은 폰을 꽂아야 하지만 웹은 그럴 것이 없다. 그래서 윈도우 PC에서
그대로 돌아간다. 브라우저는 **이미 깔려 있는 크롬·엣지**를 빌려 쓴다(따로 내려받지 않는다).

쓰는 말은 앱 쪽(lib/actions.py)과 같다: 탭 · 있으면탭 · 입력 · 기다림 · 스크롤 · 뒤로 · 지우기.
"""
import os
import re
import time
from datetime import datetime

import account
import actions
import nametag
import webvalue

기본폭 = 1440
기본기다림 = 1.5          # 화면이 가라앉기를 기다리는 초
브라우저차례 = ("chrome", "msedge", None)   # 깔려 있는 것부터 빌려 쓰고, 없으면 딸려온 것


class 웹오류(Exception):
    pass


def 연장가져오기():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise 웹오류(
            "웹을 찍는 연장(Playwright)이 아직 없습니다.\n"
            "  윈도우 명령창에서:  py -m pip install playwright\n"
            "  (자세한 것은 capture-app/설치/윈도우.md)")
    return sync_playwright


def 브라우저켜기(연장):
    """깔려 있는 크롬 → 엣지 → 딸려온 것 차례로 열어 본다."""
    마지막탈 = None
    for 이름 in 브라우저차례:
        try:
            if 이름:
                return 연장.chromium.launch(channel=이름), 이름
            return 연장.chromium.launch(), "딸려온 크로미움"
        except Exception as e:          # 안 깔려 있으면 다음 차례로
            마지막탈 = e
    raise 웹오류(f"브라우저를 열지 못했습니다 — {마지막탈}")


def 주소만들기(tag, 화면):
    주소 = (화면.get("주소") or "").strip()
    바탕 = (tag.get("기본주소") or "").strip().rstrip("/")
    if not 주소:
        if not 바탕:
            raise 웹오류(f"{화면['이름']}: 주소가 없습니다")
        return 바탕
    if re.match(r"^https?://", 주소):
        return 주소
    if not 바탕:
        raise 웹오류(f"{화면['이름']}: '기본주소' 가 없어 '{주소}' 만으로는 열 수 없습니다")
    return 바탕 + "/" + 주소.lstrip("/")


def _칸찾기(쪽, 글자):
    """이름·안내글·라벨 어느 것으로 적어도 그 칸을 찾아 준다."""
    for 찾기 in (lambda: 쪽.get_by_label(글자, exact=False),
               lambda: 쪽.get_by_placeholder(글자, exact=False),
               lambda: 쪽.locator(f'[name="{글자}"], #{글자}')):
        try:
            것 = 찾기().first
            것.wait_for(state="visible", timeout=2000)
            return 것
        except Exception:
            continue
    raise 웹오류(f"'{글자}' 칸을 화면에서 찾지 못했습니다")


def _누를것찾기(쪽, 글자):
    for 찾기 in (lambda: 쪽.get_by_role("button", name=글자, exact=False),
               lambda: 쪽.get_by_role("link", name=글자, exact=False),
               lambda: 쪽.get_by_text(글자, exact=False)):
        try:
            것 = 찾기().first
            것.wait_for(state="visible", timeout=2000)
            return 것
        except Exception:
            continue
    return None


def 동작하기(쪽, 동작, 계정, 실패, 기다림):
    """사람이 적은 동작 한 줄을 그대로 해 본다(앱 쪽과 같은 말)."""
    for 마디 in actions.쪼개기(동작):
        낱말 = 마디.split(None, 1)
        앞 = 낱말[0]
        뒤 = 낱말[1].strip() if len(낱말) > 1 else ""

        if 앞 in ("탭", "누르기", "클릭"):
            것 = _누를것찾기(쪽, 뒤)
            if 것 is None:
                raise 웹오류(f"'{뒤}' 를 화면에서 찾지 못했습니다")
            것.click()
        elif 앞 in ("있으면탭", "있으면누르기"):
            것 = _누를것찾기(쪽, 뒤)
            if 것 is not None:
                것.click()
        elif 앞 in ("입력", "적기"):
            if "=" not in 뒤:
                raise 웹오류("어느 칸에 무엇을 적을지 = 로 이어 주세요 — 예: 입력 아이디=test01")
            칸, 값 = 뒤.split("=", 1)
            _칸찾기(쪽, 칸.strip()).fill(account.채우기(값.strip(), 계정, 실패))
        elif 앞 in ("기다림", "대기"):
            try:
                time.sleep(float(뒤))
            except ValueError:
                raise 웹오류(f"몇 초 기다릴지 숫자로 적어 주세요 — {마디}")
            continue
        elif 앞 == "스크롤":
            쪽.mouse.wheel(0, 800)
        elif 앞 == "뒤로":
            쪽.go_back()
        elif 앞 == "지우기":
            쪽.keyboard.press("Control+A")
            쪽.keyboard.press("Delete")
        else:
            raise 웹오류(f"모르는 말입니다 — {마디}")
        쪽.wait_for_timeout(int(기다림 * 1000))


def 값이름(사진이름):
    """같은 화면의 값 파일 이름 — TS-WEB-001@default.png → TS-WEB-001@default.값.json"""
    return 사진이름[:-4] + ".값.json"


def 숫자(tag, 이름, 기본):
    try:
        return float(str(tag.get(이름, "")).strip())
    except (TypeError, ValueError):
        return 기본


def 찍기(tag, 결과폴더, 이름짓기=None):
    """이름표에 적힌 웹 화면을 차례로 재고 찍어, 앱 쪽과 같은 모양의 목록을 남긴다.

    이름짓기: 사진 이름을 다르게 붙이고 싶을 때(디자인 TC 기준 촬영 등) 넘긴다.
    """
    이름짓기 = 이름짓기 or (lambda t, s: nametag.사진이름(t, s))
    sync_playwright = 연장가져오기()
    os.makedirs(결과폴더, exist_ok=True)
    폭 = int(숫자(tag, "화면폭", 기본폭))
    기다림 = 숫자(tag, "기다림", 기본기다림)
    계정 = tag.get("로그인")
    찍힌것, 실패 = [], []

    with sync_playwright() as 연장:
        브라우저, 어느것 = 브라우저켜기(연장)
        print(f"  브라우저: {어느것} · 폭 {폭}px", flush=True)
        칸 = 브라우저.new_context(viewport={"width": 폭, "height": 900})
        쪽 = 칸.new_page()
        try:
            for i, 화면 in enumerate(tag["화면"], 1):
                이름 = 이름짓기(tag, 화면)
                print(f"[{i}/{len(tag['화면'])}] {화면['이름']} → {이름}", flush=True)
                try:
                    쪽.goto(주소만들기(tag, 화면), wait_until="load", timeout=30000)
                    쪽.wait_for_timeout(int(기다림 * 1000))
                    동작 = 화면.get("동작", "-")
                    if 동작 not in ("-", "", "없음"):
                        동작하기(쪽, 동작, 계정, account.실패화면(화면.get("이름", "")), 기다림)
                    값 = webvalue.긁기(쪽, 화면.get("이름", ""))
                    webvalue.쓰기(os.path.join(결과폴더, 값이름(이름)), 값)
                    쪽.screenshot(path=os.path.join(결과폴더, 이름), full_page=True)
                except Exception as e:
                    까닭 = str(e).strip().splitlines()[0]
                    print(f"    ✗ 못 찍음: {까닭}", flush=True)
                    실패.append({"화면이름": 화면["이름"], "까닭": 까닭})
                    continue
                한줄 = {"파일": 이름, "값파일": 값이름(이름), "화면번호": 화면["번호"],
                      "화면이름": 화면["이름"], "상태": 화면.get("상태", "default"),
                      "잰것": len(값.get("elements", []))}
                if 화면.get("case_id"):
                    한줄["case_id"] = 화면["case_id"]
                if 화면.get("디자인이름"):
                    한줄["디자인이름"] = 화면["디자인이름"]
                찍힌것.append(한줄)
        finally:
            브라우저.close()

    찍힌것.sort(key=lambda x: x["화면번호"])
    return {"앱이름": tag["앱이름"], "플랫폼": tag["플랫폼"],
            "찍은때": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "화면폭": 폭, "찍힌것": 찍힌것, "못찍은것": 실패}
