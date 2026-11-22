"""مولّد التقارير: Markdown عربي + لوحة HTML RTL من بيانات خط الأنابيب."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path("reports")

_STATUS_BADGE = {
    "allow": ("🟢", "سماحية"),
    "conditional": ("🟡", "مشروطة"),
    "deny": ("🔴", "ممنوعة"),
    "unknown": ("⚪", "مجهولة"),
}


def _fmt_stars(c: dict) -> str:
    if c.get("source") == "npm":
        w = c.get("downloads_weekly") or 0
        return f"{w:,}/أسبوع"
    s = c.get("stars") or 0
    return f"{s:,}"


def _age(c: dict) -> str:
    from .util import days_since

    d = days_since(c.get("pushed_at"))
    if d is None:
        return "—"
    if d == 0:
        return "اليوم"
    if d == 1:
        return "أمس"
    if d < 30:
        return f"قبل {d} يوم"
    if d < 365:
        return f"قبل {d // 30} شهر"
    return f"قبل {d // 365} سنة"


def build_markdown(data: dict) -> str:
    now = data.get("generated_at") or datetime.utcnow().isoformat()
    cands = data.get("ranked", [])
    gate_stats = data.get("gate_stats", {})
    platforms = data.get("platforms", [])
    forged = data.get("forged", [])

    lines = [
        f"# 📊 تقرير OpenForge التشغيلي",
        f"> تاريخ التوليد: {now} · مرشّحون مفحوصون: **{len(cands)}** · مسبوك فعلياً: **{len(forged)}**",
        "",
        "## 1. حالة المنصات",
        "",
        "| المنصة | الحالة | التفصيل |",
        "|--------|--------|---------|",
    ]
    for p in platforms:
        icon = {"reachable": "✅", "unreachable": "⚠️", "disabled": "⏸️"}.get(p.get("status"), "❓")
        lines.append(f"| {p.get('platform')} | {icon} {p.get('status')} | {p.get('detail', '')} |")

    lines += [
        "",
        "## 2. بوابة الرخص (نتيجة الفرز)",
        "",
        "| التصنيف | العدد |",
        "|---------|-------|",
        f"| 🟢 رخصة سماحية (مؤهّل) | {gate_stats.get('allow', 0)} |",
        f"| 🟡 رخصة مشروطة (مؤهّل مع تنبيه) | {gate_stats.get('conditional', 0)} |",
        f"| 🔴 ممنوعة | {gate_stats.get('deny', 0)} |",
        f"| ⚪ مجهولة (مستبعدة) | {gate_stats.get('unknown', 0)} |",
        "",
        "## 3. أفضل المرشحات (مرتبة بالدرجة)",
        "",
        "| # | المشروع | المصدر | النجوم/التنزيلات | الرخصة | آخر نشاط | الدرجة | القرار |",
        "|---|---------|--------|------------------|--------|----------|--------|--------|",
    ]
    for i, c in enumerate(cands[:15], 1):
        g = c.get("gate", {})
        s = c.get("score", {})
        badge, label = _STATUS_BADGE.get(g.get("status"), ("❓", "—"))
        spdx = g.get("spdx") or "—"
        lines.append(
            f"| {i} | [{c.get('full_name')}]({c.get('url')}) | {c.get('source')} | "
            f"{_fmt_stars(c)} | {badge} `{spdx}` ({label}) | {_age(c)} | **{s.get('total', '—')}** | {g.get('decision', '—')} |"
        )

    if forged:
        lines += ["", "## 4. النماذج المُختبَرة فعلياً (المسبك)", ""]
        for f in forged:
            if f.get("status") == "forged":
                sig = f.get("signals", {})
                lines += [
                    f"### 🧪 {f.get('full_name')}",
                    f"- المسار: `{f.get('path')}`",
                    f"- بطاقة النموذج: `{f.get('card')}`",
                    f"- إشارات: اختبارات={'✅' if sig.get('tests') else '❌'} · "
                    f"CI={'✅' if sig.get('ci') else '❌'} · Docker={'✅' if sig.get('docker') else '❌'} · "
                    f"ملفات={sig.get('file_count')}",
                    f"- أفكار تجربة مولّدة: {f.get('ideas')}",
                    "",
                ]
            else:
                lines.append(f"- ⏭️ {f.get('full_name')}: {f.get('reason') or f.get('status')}")

    lines += [
        "",
        "## 5. التوصيات",
        "",
        "1. ابدأ بالمرشحات الخضراء الأعلى درجة — بوابة الرخص تسمح بالتجربة الفورية.",
        "2. لكل نموذج: شغّل اختباراته أولاً، ثم عدّل صغيراً، ثم انشر باسمك مع الإسناد.",
        "3. أضف منصات جديدة بمحوّل واحد في `discover.py` عند توفر الشبكة (GitLab/Bitbucket جاهزان).",
        "4. راجع `experiments/*/PROTOTYPE.md` — كل بطاقة تحتوي أوامر وأفكار جاهزة.",
        "",
        "## 6. السجل الكامل",
        "",
        "| # | المشروع | المصدر | الدرجة | الرخصة |",
        "|---|---------|--------|--------|--------|",
    ]
    for i, c in enumerate(cands, 1):
        g = c.get("gate", {})
        s = c.get("score", {})
        lines.append(
            f"| {i} | {c.get('full_name')} | {c.get('source')} | {s.get('total', '—')} | {g.get('spdx') or '—'} |"
        )
    if data.get("errors"):
        lines += ["", "## 7. أخطاء الاستكشاف", ""]
        for e in data["errors"]:
            lines.append(f"- `{e.get('platform')}/{e.get('query')}`: {e.get('error')}")
    lines.append("")
    return "\n".join(lines)


def build_html(data: dict) -> str:
    now = data.get("generated_at", "")
    cands = data.get("ranked", [])[:15]
    gate_stats = data.get("gate_stats", {})
    platforms = data.get("platforms", [])
    forged = [f for f in data.get("forged", []) if f.get("status") == "forged"]

    def esc(x) -> str:
        return html.escape(str(x if x is not None else ""))

    rows = ""
    for i, c in enumerate(cands, 1):
        g = c.get("gate", {})
        s = c.get("score", {})
        cls = {"allow": "ok", "conditional": "warn", "deny": "bad", "unknown": "muted"}.get(g.get("status"), "muted")
        rows += f"""<tr>
<td>{i}</td>
<td><a href="{esc(c.get('url'))}" target="_blank" rel="noopener">{esc(c.get('full_name'))}</a>
<div class="desc">{esc(c.get('description') or '')[:140]}</div></td>
<td><span class="tag src">{esc(c.get('source'))}</span></td>
<td>{esc(_fmt_stars(c))}</td>
<td><span class="badge {cls}">{esc(g.get('spdx') or 'مجهولة')}</span></td>
<td>{esc(_age(c))}</td>
<td><span class="score">{esc(s.get('total', '—'))}</span></td>
<td>{esc(g.get('decision', '—'))}</td>
</tr>"""

    plat_rows = "".join(
        f"<tr><td>{esc(p.get('platform'))}</td><td>{'✅' if p.get('status')=='reachable' else '⚠️' if p.get('status')=='unreachable' else '⏸️'} {esc(p.get('status'))}</td><td>{esc(p.get('detail'))}</td></tr>"
        for p in platforms
    )
    forge_cards = "".join(
        f"""<div class="card"><h3>🧪 {esc(f.get('full_name'))}</h3>
<p>المسار: <code>{esc(f.get('path'))}</code></p>
<p>الاختبارات {'✅' if f.get('signals',{}).get('tests') else '❌'} · CI {'✅' if f.get('signals',{}).get('ci') else '❌'} · Docker {'✅' if f.get('signals',{}).get('docker') else '❌'} · أفكار: {f.get('ideas')}</p></div>"""
        for f in forged
    ) or "<p class='muted'>لم يُسبَك شيء في هذه الدورة (شغّل مع --forge).</p>"

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenForge — تقرير تشغيلي</title>
<style>
:root {{ --bg:#0b1020; --card:#131a30; --line:#243052; --txt:#e8ecf8; --muted:#93a0c2;
 --green:#22c55e; --yellow:#f59e0b; --red:#ef4444; --accent:#6366f1; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:linear-gradient(160deg,#0b1020,#101736 60%); color:var(--txt);
 font-family:"Segoe UI",Tahoma,system-ui,sans-serif; line-height:1.7; }}
.wrap {{ max-width:1100px; margin:0 auto; padding:32px 20px 60px; }}
header {{ background:linear-gradient(120deg,var(--accent),#8b5cf6); border-radius:18px;
 padding:28px 30px; margin-bottom:26px; box-shadow:0 10px 40px rgba(99,102,241,.25); }}
header h1 {{ margin:0 0 6px; font-size:1.7rem; }}
header p {{ margin:0; opacity:.92; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:14px; margin:22px 0; }}
.stat {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px; }}
.stat b {{ display:block; font-size:1.6rem; color:#a5b4fc; }}
.stat span {{ color:var(--muted); font-size:.85rem; }}
section {{ background:var(--card); border:1px solid var(--line); border-radius:16px;
 padding:22px 24px; margin-bottom:22px; }}
h2 {{ margin-top:0; font-size:1.15rem; border-inline-start:4px solid var(--accent); padding-inline-start:10px; }}
table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
th,td {{ padding:10px 8px; border-bottom:1px solid var(--line); text-align:right; vertical-align:top; }}
th {{ color:var(--muted); font-weight:600; }}
a {{ color:#a5b4fc; text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.desc {{ color:var(--muted); font-size:.8rem; margin-top:3px; }}
.badge {{ padding:3px 9px; border-radius:999px; font-size:.78rem; font-weight:600; }}
.badge.ok {{ background:rgba(34,197,94,.15); color:#4ade80; }}
.badge.warn {{ background:rgba(245,158,11,.15); color:#fbbf24; }}
.badge.bad {{ background:rgba(239,68,68,.15); color:#f87171; }}
.badge.muted {{ background:rgba(147,160,194,.15); color:var(--muted); }}
.tag {{ background:#1e293b; padding:2px 8px; border-radius:6px; font-size:.75rem; color:#cbd5e1; }}
.score {{ background:var(--accent); color:#fff; padding:4px 10px; border-radius:10px; font-weight:700; }}
.card {{ background:#0f1530; border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin:10px 0; }}
.card h3 {{ margin:0 0 8px; font-size:1rem; }}
code {{ background:#0b1020; padding:2px 6px; border-radius:6px; font-size:.82rem; }}
.muted {{ color:var(--muted); }}
footer {{ color:var(--muted); text-align:center; font-size:.82rem; margin-top:26px; }}
@media (max-width:700px) {{ table {{ font-size:.78rem; }} }}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1>🔥 OpenForge — المسبك</h1>
<p>تقرير تشغيلي · {esc(now)} · اكتشاف، بوابة رخص، تقييم، وتجربة مؤتمتة</p>
</header>
<div class="stats">
<div class="stat"><b>{len(data.get('ranked', []))}</b><span>مرشّحاً مفحوصاً</span></div>
<div class="stat"><b>{gate_stats.get('allow', 0)}</b><span>رخصة سماحية 🟢</span></div>
<div class="stat"><b>{gate_stats.get('conditional', 0)}</b><span>رخصة مشروطة 🟡</span></div>
<div class="stat"><b>{len(forged)}</b><span>نماذج مُسبوكة 🧪</span></div>
</div>
<section>
<h2>حالة المنصات</h2>
<table><tr><th>المنصة</th><th>الحالة</th><th>التفصيل</th></tr>{plat_rows}</table>
</section>
<section>
<h2>أفضل المرشحات</h2>
<table>
<tr><th>#</th><th>المشروع</th><th>المصدر</th><th>النجوم</th><th>الرخصة</th><th>آخر نشاط</th><th>الدرجة</th><th>القرار</th></tr>
{rows}
</table>
</section>
<section>
<h2>النماذج المُختبَرة</h2>
{forge_cards}
</section>
<footer>وُلّد بواسطة OpenForge — الفحص ساكن؛ لا تشغيل للكود غير الموثوق. راجع docs/REPORT-ar.md للإطار القانوني.</footer>
</div>
</body>
</html>"""


def write_reports(data: dict) -> list[Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    md_path = REPORTS_DIR / f"openforge-{stamp}.md"
    html_path = REPORTS_DIR / f"openforge-{stamp}.html"
    latest_md = REPORTS_DIR / "latest.md"
    latest_html = REPORTS_DIR / "latest.html"
    latest_json = REPORTS_DIR / "latest.json"

    md = build_markdown(data)
    page = build_html(data)
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(page, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    latest_html.write_text(page, encoding="utf-8")
    latest_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return [md_path, html_path, latest_md, latest_html, latest_json]
