"""المسبك: نسخ آمن للمشاريع المؤهّلة + فحص ساكن + بطاقة نموذج تجريبية.

سياسة الأمان: الفحص ساكن افتراضياً (أسماء ملفات وبيانات وصفية فقط).
لا يُشغَّل أي كود غير موثوق ضمن هذا الوحدة.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path

from .util import github_token, http_get_bytes

EXPERIMENTS_DIR = Path("experiments")

_MANIFESTS = {
    "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile", "poetry.lock"],
    "node": ["package.json"],
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "java": ["pom.xml", "build.gradle"],
    "ruby": ["Gemfile"],
    "php": ["composer.json"],
}


def _safe_extract(archive_path: Path, dest: Path) -> None:
    """استخراج آمن: يرفض المسارات المطلقة والخروج عن الوجهة."""
    dest_resolved = dest.resolve()
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            target = (dest / member.name).resolve()
            if not str(target).startswith(str(dest_resolved)):
                raise ValueError(f"unsafe path in archive: {member.name}")
            if member.issym() or member.islnk():
                continue  # تجاهل الروابط الرمزية تماماً
        tar.extractall(dest)


def _detect_language(root: Path) -> list[str]:
    counts: dict[str, int] = {}
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".go": "go",
        ".rs": "rust", ".java": "java", ".rb": "ruby", ".php": "php", ".c": "c",
        ".cpp": "cpp", ".cs": "csharp", ".swift": "swift", ".kt": "kotlin",
    }
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in ext_map and ".git/" not in str(p):
            counts[ext_map[p.suffix]] = counts.get(ext_map[p.suffix], 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:3]]


def probe(root: Path) -> dict:
    """فحص ساكن: ما يحتويه المشروع من إشارات جاهزية للتجربة."""
    files = [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]
    rel = [str(p.relative_to(root)) for p in files]

    manifests = []
    for lang, names in _MANIFESTS.items():
        if any(Path(r).name in names for r in rel):
            manifests.append(lang)

    has_tests = any(
        re.search(r"(^|/)(tests?|spec|__tests__)(/|$)", r) or
        re.search(r"(test_|_test\.|\.test\.|\.spec\.)", r)
        for r in rel
    )
    has_ci = any(r.startswith(".github/workflows/") for r in rel) or ".gitlab-ci.yml" in rel
    has_docker = any(Path(r).name.lower().startswith("dockerfile") or r.endswith("docker-compose.yml") for r in rel)
    readme = next((r for r in rel if Path(r).name.upper().startswith("README")), None)
    readme_size = (root / readme).stat().st_size if readme else 0
    has_license_file = any(Path(r).name.upper().startswith(("LICENSE", "LICENCE", "COPYING")) for r in rel)
    has_docs = any(r.startswith(("docs/", "doc/")) for r in rel) or "CHANGELOG.md" in rel
    has_contributing = any(Path(r).name.upper().startswith("CONTRIBUTING") for r in rel)

    return {
        "file_count": len(files),
        "languages": _detect_language(root),
        "manifests": manifests,
        "tests": has_tests,
        "ci": has_ci,
        "docker": has_docker,
        "readme_bytes": readme_size,
        "license_file": has_license_file,
        "docs": has_docs,
        "contributing": has_contributing,
    }


def _experiment_ideas(repo: dict, signals: dict) -> list[str]:
    ideas: list[str] = []
    if "python" in signals["manifests"]:
        ideas.append("ثبّت الحزمة في بيئة معزولة (`python -m venv`) وشغّل اختباراتها كخطوة تأسيس")
    if "node" in signals["manifests"]:
        ideas.append("جرّب الواجهة/الأداة من الطرفية ثم افحص إمكانية تغليفها كخدمة صغيرة")
    if "go" in signals["manifests"] or "rust" in signals["manifests"]:
        ideas.append("ابْنِ الثنائي وقِس الأداء كخط أساس للمقارنة مع بديلك")
    if signals["tests"]:
        ideas.append("شغّل حزمة الاختبارات كاملة وسجّل النتائج قبل أي تعديل (خط الأساس)")
    else:
        ideas.append("اكتب اختباراً واحداً تلقائياً للوظيفة الأساسية كأول مساهمة ممكنة upstream")
    if signals["docker"]:
        ideas.append("شغّل عبر Docker لتجربة معزولة سريعة دون تلوث البيئة")
    if signals["ci"]:
        ideas.append("فعّل نفس خط CI في فوركك لضمان بقاء تعديلاتك سليمة")
    ideas.append(
        f"اصنع فوركاً باسمك وأضف ميزة صغيرة واحدة (تحسين توثيق، خيار CLI، دعم عربي) ثم انشر نسختك"
    )
    ideas.append(
        "افتح issue أو PR في المستودع الأصلي بأي تحسين تجده — علاقة متبادلة تنمو مع الوقت"
    )
    ideas.append(
        "إذا كان المشروع سماحياً: أعد نشر نموذجك المعدَّل باسمنا مع الإسناد الكامل في README"
    )
    return ideas


def _prototype_card(repo: dict, signals: dict, gate_info: dict, sc: dict, ideas: list[str]) -> str:
    parts = sc.get("parts", {})
    warn = "\n> ⚠️ **رخصة مشروطة:** راجع بنود الإسناد/المشتق قبل أي نشر تجاري." if gate_info.get("warning") else ""
    langs = ", ".join(signals["languages"]) or "غير محدد"
    manifests = ", ".join(signals["manifests"]) or "—"
    ideas_md = "\n".join(f"{i+1}. {idea}" for i, idea in enumerate(ideas))
    return f"""# 🧪 بطاقة نموذج تجريبية — {repo['full_name']}

**المصدر:** {repo.get('source')} · {repo.get('url')}
**الرخصة:** `{gate_info.get('spdx') or 'مجهولة'}` — {gate_info.get('decision')}{warn}
**الدرجة الكلية:** {sc.get('total')} / 100
**اللغات:** {langs} · **الحزم:** {manifests}
**تاريخ آخر نشاط:** {repo.get('pushed_at')}

## تفصيل الدرجة
| المحور | الدرجة |
|--------|--------|
| الرخصة | {parts.get('license', '—')} |
| النشاط | {parts.get('activity', '—')} |
| المجتمع | {parts.get('community', '—')} |
| التوثيق | {parts.get('docs', '—')} |
| الصحة | {parts.get('health', '—')} |

## إشارات الفحص الساكن
- عدد الملفات: {signals['file_count']}
- اختبارات: {'✅' if signals['tests'] else '❌'} · CI: {'✅' if signals['ci'] else '❌'} · Docker: {'✅' if signals['docker'] else '❌'}
- README: {'✅ (' + str(signals['readme_bytes']) + ' بايت)' if signals['readme_bytes'] else '❌'} · ملف رخصة: {'✅' if signals['license_file'] else '❌'}
- توثيق إضافي: {'✅' if signals['docs'] else '❌'} · CONTRIBUTING: {'✅' if signals['contributing'] else '❌'}

## أفكار التجربة المقترحة
{ideas_md}

## قائمة الامتثال قبل النشر
- [ ] الإسناد الكامل لـ `{repo['full_name']}` في README و NOTICE
- [ ] التحقق من بنود الرخصة ({gate_info.get('spdx')}) عند النشر
- [ ] عدم استخدام اسم/شعار المشروع الأصلي كعلامة لمشروعنا
- [ ] فصل واضح: تجربة داخلية ← مشتق منشور باسمنا

---
*وُلّدت تلقائياً بواسطة OpenForge — لا تشغيل للكود ضمن هذه البطاقة.*
"""


def forge_repo(repo: dict, cfg: dict, gate_info: dict, sc: dict) -> dict:
    """تنزيل المشروع إلى experiments/ وتوليد بطاقة النموذج. يعيد سجل النتيجة."""
    if not gate_info.get("eligible"):
        return {"full_name": repo["full_name"], "status": "skipped", "reason": gate_info.get("decision")}
    name = repo["full_name"].replace("/", "__")
    dest = EXPERIMENTS_DIR / name
    max_bytes = int(cfg["forge"].get("max_archive_mb", 150)) * 1024 * 1024
    branch = repo.get("default_branch") or "main"
    url = f"https://codeload.github.com/{repo['full_name']}/tar.gz/refs/heads/{branch}"
    tmp = Path(tempfile.mkdtemp(prefix="openforge-"))
    try:
        blob = http_get_bytes(url, token=github_token(), timeout=60, cap_bytes=max_bytes)
        archive = tmp / "src.tar.gz"
        archive.write_bytes(blob)
        staging = tmp / "stage"
        staging.mkdir()
        _safe_extract(archive, staging)
        # إزالة المجلد الجذري الوحيد
        children = list(staging.iterdir())
        root = children[0] if len(children) == 1 and children[0].is_dir() else staging
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(root), str(dest))
        signals = probe(dest)
        ideas = _experiment_ideas(repo, signals)
        (dest / "PROTOTYPE.md").write_text(
            _prototype_card(repo, signals, gate_info, sc, ideas), encoding="utf-8"
        )
        return {
            "full_name": repo["full_name"],
            "status": "forged",
            "path": str(dest),
            "signals": signals,
            "ideas": len(ideas),
            "card": str(dest / "PROTOTYPE.md"),
        }
    except Exception as exc:
        return {"full_name": repo["full_name"], "status": "failed", "reason": str(exc)[:300]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def forge_top(candidates: list[dict], cfg: dict, top_n: int) -> list[dict]:
    """فورك أعلى N مرشّحاً مؤهّلاً حسب الدرجة."""
    eligible = [c for c in candidates if c.get("gate", {}).get("eligible")]
    eligible.sort(key=lambda c: -(c.get("score", {}).get("total") or 0))
    results = []
    for c in eligible[:top_n]:
        results.append(forge_repo(c, cfg, c["gate"], c["score"]))
    return results
