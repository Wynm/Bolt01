"""بوابة الرخص — تطبيق حرف لجدول التصنيف (أخضر/أصفر/أحمر).

القاعدة: المؤهّل للتجربة = رخصة في قائمة السماحية (أو مشروطة مع تنبيه).
المجهولة أو الممنوعة → استبعاد قبل أي نسخ أو تشغيل.
"""

from __future__ import annotations

import base64
import re

from .util import gh_repo_license

# أنماط النصوص لاستخراج SPDX حين يغيب حقل الرخصة
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"GNU AFFERO GENERAL PUBLIC LICENSE", re.I), "AGPL-3.0"),
    (re.compile(r"GNU LESSER GENERAL PUBLIC LICENSE", re.I), "LGPL-3.0"),
    (re.compile(r"GNU GENERAL PUBLIC LICENSE\s*Version 3", re.I), "GPL-3.0"),
    (re.compile(r"GNU GENERAL PUBLIC LICENSE\s*Version 2", re.I), "GPL-2.0"),
    (re.compile(r"Apache License", re.I), "Apache-2.0"),
    (re.compile(r"Mozilla Public License", re.I), "MPL-2.0"),
    (re.compile(r"Permission is hereby granted, free of charge", re.I), "MIT"),
    (re.compile(r"ISC License", re.I), "ISC"),
    (re.compile(r"Redistribution and use in source and binary forms", re.I), "BSD-3-Clause"),
    (re.compile(r"unencumbered software released into the public domain", re.I), "Unlicense"),
]


def classify(spdx: str | None, cfg: dict) -> str:
    """يعيد: allow | conditional | deny | unknown"""
    if not spdx or spdx in ("NOASSERTION", "OTHER"):
        return "unknown"
    gate = cfg["gate"]
    spdx_norm = spdx.strip()
    if spdx_norm in gate["allow"]:
        return "allow"
    if spdx_norm in gate["conditional"]:
        return "conditional"
    if spdx_norm in gate["deny"]:
        return "deny"
    # معرفات غير متوقعة: ابحث في قوائم البداية
    for item in gate["allow"]:
        if spdx_norm.startswith(item):
            return "allow"
    for item in gate["conditional"]:
        if spdx_norm.startswith(item):
            return "conditional"
    return "deny"


def spdx_from_text(text: str) -> str | None:
    for pat, spdx in _PATTERNS:
        if pat.search(text):
            # تحقق من رقم الإصدار لـ BSD/LGPL البسيط
            if spdx == "LGPL-3.0" and re.search(r"version 2\.1", text, re.I):
                return "LGPL-2.1"
            if spdx == "BSD-3-Clause" and not re.search(
                r"Neither the name|names of its contributors|name of the copyright holder",
                text,
                re.I,
            ):
                return "BSD-2-Clause"
            return spdx
    return None


def resolve_license(repo: dict, cfg: dict) -> tuple[str | None, str]:
    """يعيد (spdx, source) — source: api | npm | file | none"""
    if repo.get("source") == "npm":
        spdx = repo.get("license_spdx")
        if spdx and spdx not in ("NOASSERTION", "OTHER"):
            return spdx, "npm"
        return None, "none"
    spdx = repo.get("license_spdx")
    if spdx and spdx not in ("NOASSERTION", "OTHER"):
        return spdx, "api"
    lic = repo.get("license") or {}
    spdx = lic.get("spdx_id")
    if spdx and spdx not in ("NOASSERTION", "OTHER"):
        return spdx, "api"
    # محاولة قراءة ملف LICENSE الفعلي
    data = gh_repo_license(repo["full_name"])
    if data:
        content_b64 = (data.get("content") or "").replace("\n", "")
        try:
            text = base64.b64decode(content_b64).decode("utf-8", errors="replace")
        except Exception:
            text = ""
        spdx = spdx_from_text(text) or data.get("license", {}).get("name")
        if spdx:
            return spdx, "file"
    return None, "none"


def gate(repo: dict, cfg: dict) -> dict:
    """تقييم بوابة الرخص لمستودع واحد."""
    spdx, source = resolve_license(repo, cfg)
    status = classify(spdx, cfg)
    decision = {
        "allow": "مؤهّل",
        "conditional": "مؤهّل مشروط",
        "deny": "مستبعد",
        "unknown": "مستبعد (رخصة مجهولة)",
    }[status]
    return {
        "spdx": spdx,
        "source": source,
        "status": status,
        "decision": decision,
        "eligible": status in ("allow", "conditional"),
        "warning": status == "conditional",
        "attribution_required": status in ("allow", "conditional"),
    }
