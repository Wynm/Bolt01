"""واجهة الأوامر: python3 -m openforge [run|discover|report|forge]"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .discover import discover_all
from .forge import forge_top
from .licenses import gate as gate_repo
from .report import write_reports
from .score import score

CONFIG_PATH = Path("openforge/config.json")


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(candidates: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    """بوابة الرخص + التقييم + الترتيب."""
    stats = {"allow": 0, "conditional": 0, "deny": 0, "unknown": 0}
    evaluated = []
    for c in candidates:
        g = gate_repo(c, cfg)
        sc = score(c, cfg, g)
        stats[g["status"]] = stats.get(g["status"], 0) + 1
        evaluated.append({**c, "gate": g, "score": sc})
    evaluated.sort(key=lambda x: -(x["score"]["total"]))
    # فصل: المؤهّلون أعلى (الدرجة الحقيقية أولاً ثم الرخصة)
    eligible = [e for e in evaluated if e["gate"]["eligible"]]
    rest = [e for e in evaluated if not e["gate"]["eligible"]]
    eligible.sort(key=lambda x: -(x["score"]["total"]))
    rest.sort(key=lambda x: -(x["score"]["total"]))
    return eligible + rest, stats


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config) if args.config else CONFIG_PATH)
    print("[1/4] الاكتشاف عبر المنصات ...")
    disc = discover_all(cfg)
    print(f"      → {len(disc['candidates'])} مرشّحاً ({len(disc['github'])} GitHub، {len(disc['npm'])} npm)")
    for p in disc["platforms"]:
        print(f"      · {p['platform']}: {p['status']}")

    print("[2/4] بوابة الرخص + التقييم ...")
    ranked, stats = evaluate(disc["candidates"], cfg)
    print(f"      → {stats}")

    forged = []
    top_n = args.top if args.top is not None else cfg["forge"].get("top_n", 3)
    if args.forge:
        print(f"[3/4] المسبك: نسخ وفحص أعلى {top_n} مؤهّل ...")
        forged = forge_top(ranked, cfg, top_n)
        for f in forged:
            mark = "✅" if f["status"] == "forged" else ("⏭️" if f["status"] == "skipped" else "❌")
            print(f"      {mark} {f['full_name']} — {f.get('reason') or f.get('path', '')}")
    else:
        print("[3/4] تخطّي المسبك (أضف --forge لتشغيله)")

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ranked": ranked,
        "gate_stats": stats,
        "platforms": disc["platforms"],
        "errors": disc["errors"],
        "forged": forged,
    }
    print("[4/4] توليد التقارير ...")
    paths = write_reports(data)
    for p in paths:
        print(f"      → {p}")
    min_score = cfg["scoring"].get("min_score", 60)
    top = [c for c in ranked if c["gate"]["eligible"] and c["score"]["total"] >= min_score][:5]
    print("\nأفضل المرشحات المؤهّلة:")
    for c in top:
        print(f"  • {c['full_name']} — {c['score']['total']} — {c['gate']['spdx']}")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config) if args.config else CONFIG_PATH)
    disc = discover_all(cfg)
    ranked, stats = evaluate(disc["candidates"], cfg)
    print(json.dumps({"platforms": disc["platforms"], "gate_stats": stats,
                      "top": [{k: c[k] for k in ("full_name", "source", "url")} | {"score": c["score"]["total"], "license": c["gate"]["spdx"]}
                              for c in ranked[:10]]},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from .report import REPORTS_DIR

    latest = REPORTS_DIR / "latest.json"
    if not latest.exists():
        print("لا توجد بيانات سابقة — شغّل `run` أولاً", file=sys.stderr)
        return 1
    data = json.loads(latest.read_text(encoding="utf-8"))
    for p in write_reports(data):
        print(p)
    return 0


def cmd_forge(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config) if args.config else CONFIG_PATH)
    latest = Path("reports/latest.json")
    if not latest.exists():
        print("لا توجد بيانات — شغّل `run` أولاً", file=sys.stderr)
        return 1
    data = json.loads(latest.read_text(encoding="utf-8"))
    top_n = args.top if args.top is not None else cfg["forge"].get("top_n", 3)
    forged = forge_top(data.get("ranked", []), cfg, top_n)
    data["forged"] = forged
    for f in forged:
        print(f"{'✅' if f['status']=='forged' else '⏭️' if f['status']=='skipped' else '❌'} {f['full_name']} — {f.get('reason') or f.get('path','')}")
    for p in write_reports(data):
        print(p)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openforge",
        description="OpenForge — اكتشاف مشاريع مفتوحة، بوابة رخص، تقييم، وتجربة مؤتمتة",
    )
    parser.add_argument("--config", default=None, help="مسار ملف الإعدادات")
    sub = parser.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="خط الأنابيب الكامل")
    p_run.add_argument("--forge", action="store_true", help="نسخ وفحص أعلى المرشحات")
    p_run.add_argument("--top", type=int, default=None, help="عدد المشاريع للمسبك")
    p_run.set_defaults(func=cmd_run)

    p_disc = sub.add_parser("discover", help="الاكتشاف والتقييم فقط")
    p_disc.set_defaults(func=cmd_discover)

    p_rep = sub.add_parser("report", help="إعادة توليد التقرير من آخر بيانات")
    p_rep.set_defaults(func=cmd_report)

    p_forge = sub.add_parser("forge", help="المسبك من آخر بيانات")
    p_forge.add_argument("--top", type=int, default=None)
    p_forge.set_defaults(func=cmd_forge)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        args = parser.parse_args((argv or sys.argv[1:]) + ["run"])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
