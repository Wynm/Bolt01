# 🔥 OpenForge — المسبك

نظام **مؤتمت** لاكتشاف المشاريع المفتوحة عبر المنصات (GitHub، npm، GitLab، Bitbucket...)، وفرزها عبر **بوابة قانونية صارمة للرخص**، وتقييمها بنتيجة رقمية، ونسخ المرشحات المؤهّلة إلى **مختبر تجريبي معزول** مع توليد **بطاقة نموذج أولي جاهزة** — وتقرير عربي كامل، أسبوعياً وآلياً.

> «السرقة التي تصنع المال ليست سرقة — هي إعادة تركيب مُصرَّح بها.»
> الإطار القانوني الكامل: [`docs/REPORT-ar.md`](docs/REPORT-ar.md)

## التشغيل

```bash
# خط الأنابيب الكامل (اكتشاف + بوابة + تقييم + تقرير)
python3 -m openforge run

# مع المسبك: نسخ وفحص أعلى 3 مؤهّلين وتوليد بطاقات النماذج
python3 -m openforge run --forge --top 3

# أوامر فردية
python3 -m openforge discover
python3 -m openforge report
python3 -m openforge forge --top 3
```

المخرجات:
- `reports/latest.html` — لوحة تفاعلية RTL
- `reports/latest.md` — تقرير Markdown
- `experiments/<المشروع>/PROTOTYPE.md` — بطاقة النموذج التجريبي (أفكار + أوامر + قائمة امتثال)

## المكوّنات

| الوحدة | المهمة |
|--------|--------|
| `openforge/discover.py` | كشّاف GitHub + npm + مفحوصات إتاحة GitLab/Bitbucket |
| `openforge/licenses.py` | بوابة الرخص (سماحية/مشروطة/ممنوعة/مجهولة) |
| `openforge/score.py` | درجة 0–100 موزونة |
| `openforge/forge.py` | نسخ آمن (سقف حجم + حماية مسارات) + فحص ساكن + بطاقة نموذج |
| `openforge/report.py` | تقارير MD + HTML عربي |
| `.github/workflows/openforge.yml` | جدولة أسبوعية آلياً |

## الأتمتة

يعمل أسبوعياً عبر GitHub Actions (الاثنين 06:00 UTC) أو يدوياً من تبويب Actions → **OpenForge weekly** → Run workflow.

## الأمان

- الفحص **ساكن** افتراضياً — لا تشغيل لأي كود غير موثوق.
- بوابة الرخص **قبل** أي نسخ.
- سقف حجم وحماية من path traversal في الاستخراج.

---
MIT © OpenForge
