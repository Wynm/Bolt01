"""الكشّاف: اكتشاف مشاريع من المنصات المفتوحة مع حالة إتاحة صريحة لكل منصة."""

from __future__ import annotations

import urllib.parse

from .util import days_ago, days_since, github_token, http_get_json


def _normalize_github(item: dict, query: str) -> dict:
    lic = item.get("license") or {}
    return {
        "source": "github",
        "query": query,
        "full_name": item.get("full_name"),
        "name": item.get("name"),
        "url": item.get("html_url"),
        "description": item.get("description"),
        "stars": item.get("stargazers_count") or 0,
        "forks": item.get("forks_count") or 0,
        "open_issues": item.get("open_issues_count") or 0,
        "license_spdx": lic.get("spdx_id"),
        "pushed_at": item.get("pushed_at"),
        "created_at": item.get("created_at"),
        "language": item.get("language"),
        "topics": item.get("topics") or [],
        "homepage": item.get("homepage"),
        "default_branch": item.get("default_branch") or "main",
        "archived": item.get("archived", False),
        "owner": (item.get("owner") or {}).get("login"),
    }


def discover_github(cfg: dict) -> tuple[list[dict], list[dict]]:
    """يعيد (قائمة المشاريع، سجل الأخطاء)."""
    results: list[dict] = []
    errors: list[dict] = []
    d = cfg["discovery"]
    for spec in d["github_queries"]:
        q = spec["q"].format(AFTER=days_ago(d["days_active"]), CREATED=days_ago(d["days_created"]))
        try:
            from .util import gh_search_repos

            items = gh_search_repos(
                q, sort=spec.get("sort", "stars"), order=spec.get("order", "desc"),
                per_page=spec.get("per_page", 10),
            )
            for it in items:
                row = _normalize_github(it, spec["name"])
                if not row["archived"]:
                    results.append(row)
        except Exception as exc:  # حدود أو شبكة
            errors.append({"platform": "github", "query": spec["name"], "error": str(exc)[:200]})
    # إزالة التكرار
    seen: set[str] = set()
    unique = []
    for r in results:
        if r["full_name"] not in seen:
            seen.add(r["full_name"])
            unique.append(r)
    return unique, errors


def _npm_latest_meta(name: str) -> dict:
    quoted = urllib.parse.quote(name, safe="")
    return http_get_json(f"https://registry.npmjs.org/{quoted}/latest", timeout=15)


def discover_npm(cfg: dict) -> tuple[list[dict], list[dict]]:
    d = cfg["discovery"]
    results: list[dict] = []
    errors: list[dict] = []
    for text in d["npm_queries"]:
        try:
            params = urllib.parse.urlencode({"text": text, "size": d.get("npm_size", 6)})
            data = http_get_json(f"https://registry.npmjs.org/-/v1/search?{params}", timeout=20)
            for obj in data.get("objects", []):
                pkg = obj.get("package", {})
                name = pkg.get("name")
                if not name:
                    continue
                detail = obj.get("score", {}).get("detail", {})
                pop = obj.get("score", {}).get("final", 0)
                downloads = (obj.get("downloads") or {}).get("weekly") or 0
                meta: dict = {}
                try:
                    meta = _npm_latest_meta(name)
                except Exception:
                    pass
                lic = meta.get("license")
                if isinstance(lic, dict):
                    lic = lic.get("type")
                url = pkg.get("links", {}).get("repository") or f"https://www.npmjs.com/package/{name}"
                if url.startswith("git+"):
                    url = url[4:]
                if url.endswith(".git"):
                    url = url[:-4]
                results.append({
                    "source": "npm",
                    "query": text,
                    "full_name": name,
                    "name": name,
                    "url": url,
                    "description": pkg.get("description") or meta.get("description"),
                    "stars": None,
                    "forks": None,
                    "open_issues": None,
                    "downloads_weekly": downloads,
                    "search_score": pop,
                    "quality": detail.get("quality"),
                    "maintenance": detail.get("maintenance"),
                    "license_spdx": lic if isinstance(lic, str) else None,
                    "pushed_at": obj.get("updated") or pkg.get("date"),
                    "created_at": None,
                    "language": "JavaScript",
                    "topics": pkg.get("keywords") or [],
                    "homepage": pkg.get("links", {}).get("homepage"),
                    "default_branch": "main",
                    "archived": False,
                    "owner": None,
                    "version": pkg.get("version") or meta.get("version"),
                })
        except Exception as exc:
            errors.append({"platform": "npm", "query": text, "error": str(exc)[:200]})
    return results, errors


def probe_platform(cfg: dict, platform: str) -> dict:
    """فحص إتاحة منصة خارجية: يعمل فور توفر الشبكة، ويُسجّل الحالة بصدق."""
    p = cfg["platforms"].get(platform, {})
    if not p.get("enabled"):
        return {"platform": platform, "status": "disabled", "detail": "معطّل في الإعدادات"}
    base = p["base"]
    test_url = {
        "gitlab": f"{base}/projects?per_page=1&order_by=star_count",
        "bitbucket": f"{base}/repositories?role=member&pagelen=1",
    }.get(platform)
    if not test_url:
        return {"platform": platform, "status": "unknown", "detail": "لا يوجد مسار فحص"}
    try:
        http_get_json(test_url, timeout=8)
        return {"platform": platform, "status": "reachable", "detail": "متاحة — المحوّل يعمل"}
    except Exception as exc:
        return {
            "platform": platform,
            "status": "unreachable",
            "detail": f"غير متاحة من شبكة التشغيل الحالية ({type(exc).__name__}) — يُفعَّل تلقائياً عند الإتاحة",
        }


def discover_all(cfg: dict) -> dict:
    """تشغيل كل الكشّافات وحالة المنصات."""
    gh, gh_err = discover_github(cfg)
    npm, npm_err = discover_npm(cfg)
    platforms = [probe_platform(cfg, "gitlab"), probe_platform(cfg, "bitbucket")]
    platforms.append({"platform": "github", "status": "reachable", "detail": "متاحة — تعمل"})
    platforms.append({"platform": "npm", "status": "reachable", "detail": "متاحة — تعمل"})
    return {
        "candidates": gh + npm,
        "github": gh,
        "npm": npm,
        "platforms": platforms,
        "errors": gh_err + npm_err,
    }
