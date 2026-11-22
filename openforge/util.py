"""أدوات مشتركة: HTTP، GitHub API عبر gh، تواريخ ديناميكية."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

UA = "openforge/0.1 (project-experimentation pipeline)"


def http_get_json(url: str, *, token: str | None = None, timeout: int = 20):
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_bytes(url: str, *, token: str | None = None, timeout: int = 30, cap_bytes: int | None = None):
    """تنزيل ثنائي بسقف حجم اختياري (للحماية من الانزلاقات الضخمة)."""
    headers = {"User-Agent": UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    chunks: list[bytes] = []
    total = 0
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if cap_bytes is not None and total > cap_bytes:
                raise ValueError(f"archive exceeds cap of {cap_bytes} bytes")
            chunks.append(chunk)
    return b"".join(chunks)


def github_token() -> str | None:
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok
    try:
        tok = subprocess.check_output(
            ["gh", "auth", "token"], text=True, timeout=10, stderr=subprocess.DEVNULL
        ).strip()
        return tok or None
    except Exception:
        return None


def gh_search_repos(q: str, *, sort: str = "stars", order: str = "desc", per_page: int = 10) -> list[dict]:
    params = urllib.parse.urlencode(
        {"q": q, "sort": sort, "order": order, "per_page": per_page}
    )
    data = http_get_json(
        f"https://api.github.com/search/repositories?{params}",
        token=github_token(),
        timeout=25,
    )
    return data.get("items", [])


def gh_repo_license(full_name: str) -> dict | None:
    """جلب ملف LICENSE الفعلي حين تكون الحقل SPDX مجهولاً."""
    try:
        data = http_get_json(
            f"https://api.github.com/repos/{full_name}/license",
            token=github_token(),
            timeout=15,
        )
        return data
    except Exception:
        return None


def days_ago(n: int) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=n)).strftime("%Y-%m-%d")


def parse_iso(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def days_since(s: str | None) -> int | None:
    d = parse_iso(s)
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return max(0, (dt.datetime.now(dt.timezone.utc) - d).days)
