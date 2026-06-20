"""
End-to-end test for the data-analyst agentic chat workflow.

Usage:
    python test_agentic_chat.py
    python test_agentic_chat.py https://api.example.com

Requires:
    - BE running on http://localhost:8000
    - A registered test user (use /auth/register)
"""
import json
import sys
import time
from typing import Optional

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
EMAIL = f"agentic_{int(time.time())}@example.com"
PASSWORD = "TestPass@12345"


def H(p): return f"\033[{p}m"
GREEN = H(92); RED = H(91); CYAN = H(96); BOLD = H(1); END = H(0)


def banner(t):
    print(f"\n{BOLD}{CYAN}{'=' * 60}\n  {t}\n{'=' * 60}{END}")


def ok(msg): print(f"  {GREEN}PASS{END}  {msg}")
def fail(msg, detail=""):
    print(f"  {RED}FAIL{END}  {msg}")
    if detail:
        for line in detail.splitlines()[:5]:
            print(f"         {line}")


def truncate(s, n=240):
    s = str(s)
    return s if len(s) <= n else s[:n] + f"... [+{len(s)-n}]"


def main():
    print(f"{BOLD}Data Analyst Agentic Chat - end-to-end test{END}")
    print(f"Target: {CYAN}{BASE_URL}{END}")
    with httpx.Client(timeout=120.0) as c:
        # Register + login
        banner("0. Auth bootstrap")
        r = c.post(f"{BASE_URL}/api/v1/auth/register", json={
            "username": f"agentic_{int(time.time())}",
            "email": EMAIL,
            "password": PASSWORD,
            "confirm_password": PASSWORD,
            "full_name": "Agentic Test User",
        })
        if r.status_code not in (201, 409):
            fail("register failed", r.text)
            return
        r = c.post(f"{BASE_URL}/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if r.status_code != 200:
            fail("login failed", r.text)
            return
        token = r.json()["access_token"]
        H_AUTH = {"Authorization": f"Bearer {token}"}
        ok("Authenticated.")

        # 1. Plain chat (no code)
        banner("1. Plain chat (no code needed)")
        r = c.post(f"{BASE_URL}/api/v1/chat",
                   headers=H_AUTH,
                   json={"message": "Có bao nhiêu game trong database?"})
        if r.status_code == 200:
            body = r.json()
            print(f"     status={body['status']} retries={body['retries_used']} files={body['new_files']}")
            print(f"     reply: {truncate(body['user_response'])}")
            if body["status"] == "success":
                ok(f"Plain chat OK (session_id={body['session_id'][:30]}...)")
            else:
                fail(f"Chat returned status={body['status']}")
        else:
            fail("chat failed", r.text)

        # 2. Stats / aggregation (requires code)
        banner("2. Stats query (will run Python in E2B)")
        r = c.post(f"{BASE_URL}/api/v1/chat",
                   headers=H_AUTH,
                   json={"message": "Tính trung bình playtime_forever của tất cả reviews. Trả lời ngắn gọn bằng 1-2 câu."})
        if r.status_code == 200:
            body = r.json()
            print(f"     status={body['status']} retries={body['retries_used']} files={body['new_files']}")
            print(f"     reply: {truncate(body['user_response'])}")
            if body["code"]:
                print(f"     code preview: {truncate(body['code'])}")
            if body["status"] == "success":
                ok("Stats query OK")
            else:
                fail(f"Stats query returned status={body['status']}")
        else:
            fail("stats query failed", r.text)

        # 3. Sessions list
        banner("3. Sessions list")
        r = c.get(f"{BASE_URL}/api/v1/chat/sessions", headers=H_AUTH)
        if r.status_code == 200:
            sessions = r.json()
            ok(f"Found {len(sessions)} session(s)")
            for s in sessions[:3]:
                print(f"     - {s['session_id'][:30]}... turns={s['turn_count']}")
        else:
            fail("sessions list failed", r.text)

        # 4. Files list
        banner("4. Generated files list")
        r = c.get(f"{BASE_URL}/api/v1/chat/files", headers=H_AUTH)
        if r.status_code == 200:
            files = r.json()["files"]
            ok(f"Found {len(files)} file(s) in temp_data/")
            for f in files[:5]:
                print(f"     - {f['name']} ({f['size']} bytes)")
        else:
            fail("files list failed", r.text)

    print(f"\n{BOLD}{CYAN}{'=' * 60}\n  Done.\n{'=' * 60}{END}")


if __name__ == "__main__":
    main()
