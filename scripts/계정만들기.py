"""포털 계정 한 개를 자료함에 직접 넣는다 (관리자 계정은 이 길로만 만든다).

river 확정 2026-09-28: 관리자 계정은 화면에서 만들지 않는다 — 자료함에만 둔다.
그래서 로그인 화면에는 '계정 만들기'가 없고, 첫 관리자는 이 도구로 넣는다.
그 뒤 그룹원은 관리자가 포털 '계정 관리' 화면에서 더한다.

비밀번호는 되돌릴 수 없게 굳혀서(pbkdf2-sha256) 넣는다 — 자료함에도 원문은 남지 않는다.
비밀번호를 명령 줄에 적지 않는다(화면 기록에 남는다). 물어보면 그때 친다.

    python3 scripts/계정만들기.py <아이디> <이름> [--관리자|--그룹원] [--바꾸게]

`--바꾸게` 를 주면 그 사람이 처음 들어올 때 비밀번호를 새로 정해야 한다.
"""
import argparse
import getpass
import sys
from pathlib import Path

뿌리 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(뿌리))
sys.path.insert(0, str(뿌리 / "mvp0"))

import 설정  # noqa: E402
import auth  # noqa: E402
import db as dbmod  # noqa: E402


def main():
    묻 = argparse.ArgumentParser(description="포털 계정 한 개 만들기")
    묻.add_argument("아이디")
    묻.add_argument("이름")
    묻.add_argument("--관리자", action="store_true", help="관리자 권한으로 만든다")
    묻.add_argument("--그룹원", action="store_true", help="그룹원 권한으로 만든다(기본)")
    묻.add_argument("--바꾸게", action="store_true",
                   help="처음 들어올 때 비밀번호를 새로 정하게 한다")
    것 = 묻.parse_args()

    자료함 = 설정.자리("포털.자료함")
    auth.설정하기(자료함)

    비번 = getpass.getpass("비밀번호: ")
    또 = getpass.getpass("비밀번호 다시: ")
    if 비번 != 또:
        print("두 번 친 비밀번호가 다릅니다. 만들지 않았습니다.")
        return 1

    conn = dbmod.connect(str(자료함))
    auth.표만들기(conn)
    권한 = auth.관리자 if 것.관리자 else auth.그룹원
    막힘 = auth.만들기(conn, 것.아이디, 것.이름, 비번, 권한,
                    actor="자료함에서 직접", 바꾸게=것.바꾸게)
    conn.close()
    if 막힘:
        print(막힘)
        return 1
    print(f"{것.이름}({것.아이디}) 님을 {auth.권한으로[권한]} 넣었습니다 → {자료함}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
