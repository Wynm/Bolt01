"""ميزان التقييم: درجة 0–100 موزونة حسب الإعدادات."""

from __future__ import annotations

import math

from .licenses import classify
from .util import days_since


def _activity_points(pushed_at: str | None) -> float:
    d = days_since(pushed_at)
    if d is None:
        return 20
    if d <= 7:
        return 100.0
    if d <= 30:
        return 80.0
    if d <= 90:
        return 60.0
    if d <= 180:
        return 40.0
    return 20.0


def _log_scale(value: float | None, ceiling: float) -> float:
    if not value or value <= 0:
        return 0.0
    return min(100.0, math.log10(value + 1) / math.log10(ceiling + 1) * 100.0)


def _community_points(repo: dict) -> float:
    if repo.get("source") == "npm":
        weekly = repo.get("downloads_weekly") or 0
        final = repo.get("search_score") or 0
        # دفاع: بعض سجلات npm تعيد final خارج [0,1] (مرآة/مقياس مئة)
        if final > 1:
            final = min(1.0, final / 100.0)
        return min(100.0, _log_scale(weekly, 500_000) * 0.6 + final * 100 * 0.4)
    stars = _log_scale(repo.get("stars"), 5000)
    forks = _log_scale(repo.get("forks"), 2000)
    return 0.75 * stars + 0.25 * forks


def _docs_points(repo: dict) -> float:
    pts = 0.0
    if repo.get("description"):
        pts += 30
    topics = repo.get("topics") or []
    if len(topics) >= 3:
        pts += 30
    elif topics:
        pts += 15
    if repo.get("homepage"):
        pts += 20
    if repo.get("license_spdx") and repo["license_spdx"] not in ("NOASSERTION", "OTHER"):
        pts += 20
    elif repo.get("source") == "npm" and repo.get("license_spdx"):
        pts += 20
    return min(100.0, pts)


def _health_points(repo: dict) -> float:
    if repo.get("source") == "npm":
        q = repo.get("quality")
        if q is not None:
            return float(q) * 100
        return 50.0
    stars = repo.get("stars") or 0
    if stars <= 0:
        return 30.0
    fr = (repo.get("forks") or 0) / stars
    ir = (repo.get("open_issues") or 0) / stars
    fork_pts = 100.0 if 0.03 <= fr <= 0.8 else (70.0 if fr < 0.03 else 80.0)
    if ir <= 0.05:
        issue_pts = 100.0
    elif ir <= 0.15:
        issue_pts = 85.0
    elif ir <= 0.4:
        issue_pts = 65.0
    else:
        issue_pts = 45.0
    return 0.5 * fork_pts + 0.5 * issue_pts


def _license_points(spdx: str | None, cfg: dict) -> float:
    status = classify(spdx, cfg)
    return {"allow": 100.0, "conditional": 70.0, "deny": 0.0, "unknown": 0.0}[status]


def score(repo: dict, cfg: dict, gate_info: dict) -> dict:
    w = cfg["scoring"]["weights"]
    parts = {
        "license": _license_points(gate_info.get("spdx") or repo.get("license_spdx"), cfg),
        "activity": _activity_points(repo.get("pushed_at")),
        "community": _community_points(repo),
        "docs": _docs_points(repo),
        "health": _health_points(repo),
    }
    total = sum(parts[k] * w[k] for k in w)
    return {"total": round(total, 2), "parts": {k: round(v, 1) for k, v in parts.items()}}
