"""End-to-end test script for the Steam Game Data API.

Tests the full flow: login -> dashboard -> chat (intro) -> chat (chart) ->
download chart -> evaluate. Saves artefacts to scripts/output/.

Usage:
    pip install requests
    python scripts/test_e2e.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

import requests

API = "http://localhost:8000/api/v1"
EMAIL = "vercel@gmail.com"
PASSWORD = "Thinh@28082002"
OUTPUT_DIR = Path(__file__).parent / "output"
TIMEOUT = 120


def hr(title: str) -> None:
    print("\n" + "=" * 70 + "\n" + title + "\n" + "=" * 70)


def safe_get(d, *path, default="<n/a>"):
    cur = d
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur


def truncate(text: str, n: int = 400) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[:n] + "..."


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    s = requests.Session()

    # 1. health
    hr("1. Health check")
    try:
        r = s.get("http://localhost:8000/health", timeout=10)
        print(f"GET /health -> {r.status_code}")
        print(json.dumps(r.json(), indent=2))
    except Exception as e:
        print(f"Cannot reach backend: {e}")
        print("Start it with: cd back_end && uvicorn app.main:app --port 8000")
        return 1

    # 2. login
    hr("2. Login")
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    print(f"POST /auth/login -> {r.status_code}")
    if r.status_code != 200:
        print("Login failed. Update EMAIL/PASSWORD at the top of this file.")
        print(r.text[:500])
        return 1
    body = r.json()
    access = body.get("access_token")
    refresh = body.get("refresh_token")
    print(f"access_token: {access[:24]}...")
    print(f"expires_in:   {body.get('expires_in')}s")
    auth = {"Authorization": f"Bearer {access}"}

    # 3. me
    hr("3. /auth/me")
    r = s.get(f"{API}/auth/me", headers=auth, timeout=10)
    me = r.json()
    print(f"User: {me.get('email')}  roles={me.get('roles')}")

    # 4. dashboard stats
    hr("4. /dashboard/overview")
    r = s.get(f"{API}/dashboard/overview", headers=auth, timeout=10)
    print(f"GET /dashboard/overview -> {r.status_code}")
    print(json.dumps(r.json(), indent=2))

    # 5. games list
    hr("5. /games (first 3)")
    r = s.get(f"{API}/games", params={"page": 1, "page_size": 3}, headers=auth, timeout=15)
    games = r.json().get("items", [])
    print(f"items returned: {len(games)}")
    for g in games[:3]:
        print(f"  - appid={g.get('steam_appid'):>6}  {g.get('name')!r}  free={g.get('is_free')}")

    # 6. chat: introduction
    hr("6. /ai/chat  Q1: Giới thieu nen tang")
    t0 = time.time()
    r = s.post(
        f"{API}/ai/chat",
        json={"message": "Hay gioi thieu ve nen tang Steam Game Data Demo.", "session_id": "test-intro"},
        headers=auth,
        timeout=TIMEOUT,
    )
    dt = time.time() - t0
    print(f"POST /ai/chat -> {r.status_code}  ({dt:.1f}s)")
    if r.status_code == 200:
        body = r.json()
        reply = body.get("reply") or safe_get(body, "user_response")
        print("\nReply (first 600 chars):")
        print(truncate(reply, 600))
        print(f"\nStatus: {body.get('status')}")
        print(f"Charts: {len(body.get('charts') or [])}")
        print(f"Sandbox files: {body.get('sandbox_files') or body.get('new_files') or []}")
    else:
        print(r.text[:500])

    # 7. chat: chart request
    hr("7. /ai/chat  Q2: Top 10 genres by game count")
    t0 = time.time()
    r = s.post(
        f"{API}/ai/chat",
        json={
            "message": "Tao bieu do so luong game o moi genres trong top 10 genres co nhieu game nhat.",
            "session_id": "test-genre-chart",
        },
        headers=auth,
        timeout=TIMEOUT,
    )
    dt = time.time() - t0
    print(f"POST /ai/chat -> {r.status_code}  ({dt:.1f}s)")
    chart_body: Dict[str, Any] = {}
    if r.status_code == 200:
        chart_body = r.json()
        reply = chart_body.get("reply") or safe_get(chart_body, "user_response")
        print("\nReply (first 800 chars):")
        print(truncate(reply, 800))
        charts = chart_body.get("charts") or []
        print(f"\nCharts attached: {len(charts)}")
        for c in charts:
            print(f"  - type={c.get('chart_type')}  title={c.get('chart_title')!r}  x={c.get('x_axis_label')!r}")
        files = chart_body.get("sandbox_files") or chart_body.get("new_files") or []
        print(f"Sandbox files: {files}")
        (OUTPUT_DIR / "chat_chart_response.json").write_text(
            json.dumps(chart_body, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"Saved -> {OUTPUT_DIR / 'chat_chart_response.json'}")
    else:
        print(r.text[:500])

    # 8. download chart
    hr("8. /chat/files  +  download chart")
    r = s.get(f"{API}/chat/files", headers=auth, timeout=10)
    print(f"GET /chat/files -> {r.status_code}")
    if r.status_code == 200:
        files = r.json().get("files", [])
        print(f"Total files in temp_data/: {len(files)}")
        for f in files[:5]:
            print(f"  - {f.get('name')!r}  size={f.get('size') or f.get('size_bytes')}")
        # download the first HTML/PNG file we find
        for f in files:
            name = f.get("name", "")
            ext = Path(name).suffix.lower()
            if ext in {".html", ".png", ".svg"}:
                host = API.replace("/api/v1", "")
                target = host + (f.get("url") or f"/api/v1/chat/files/{name}")
                print(f"\nDownloading: {target}")
                rr = s.get(target, headers=auth, timeout=30)
                print(f"GET -> {rr.status_code}  ({len(rr.content)} bytes)")
                if rr.status_code == 200:
                    out = OUTPUT_DIR / name
                    out.write_bytes(rr.content)
                    print(f"Saved -> {out}")
                break

    # 9. logout
    hr("9. /auth/logout")
    r = s.post(f"{API}/auth/logout", json={"refresh_token": refresh}, headers=auth, timeout=10)
    print(f"POST /auth/logout -> {r.status_code}")

    # 10. quick evaluation
    hr("10. Quick evaluation")
    reply = chart_body.get("reply") or ""
    charts = chart_body.get("charts") or []
    files = chart_body.get("sandbox_files") or chart_body.get("new_files") or []
    print(f"- AI reply length: {len(reply)} chars")
    print(f"- Reply mentions 'genre': {'genre' in reply.lower()}")
    print(f"- Reply mentions a number: {any(ch.isdigit() for ch in reply)}")
    print(f"- Charts attached: {len(charts)}")
    if charts:
        c = charts[0]
        labels = c.get("config", {}).get("labels", [])
        data = [d.get("data") for d in c.get("config", {}).get("datasets", [])]
        print(f"  - Genre labels ({len(labels)}): {labels}")
        print(f"  - Counts: {data}")
        print(f"  - Chart type: {c.get('chart_type')}")
        print(f"  - Title: {c.get('chart_title')!r}")
    print(f"- Sandbox files: {len(files)}")
    print(f"  - HTML interactive: {any(Path(f).suffix == '.html' for f in files)}")
    print(f"  - PNG image: {any(Path(f).suffix == '.png' for f in files)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Network failure: {e}", file=sys.stderr)
        sys.exit(2)
