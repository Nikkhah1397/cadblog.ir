#!/usr/bin/env python3
"""سازنده‌ی سایت CADBLOG
اجرا:  python build.py      (خروجی در پوشه‌ی public ساخته می‌شود)
"""
import datetime
import html
import json
import re
import shutil
import sys
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent
OUT = ROOT / "public"
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
SITE = CFG["site"]
CATS = {c["slug"]: c for c in CFG["categories"]}
TAGS = {t["slug"]: t for t in CFG["tags"]}
LTYPES = {t["slug"]: t for t in CFG["library_types"]}
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
warnings = []


# ---------- تاریخ شمسی ----------
def to_jalali(d):
    gy, gm, gd = d.year, d.month, d.day
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def fa(s):
    return str(s).translate(FA_DIGITS)


def jdate(d):
    jy, jm, jd = to_jalali(d)
    return fa(f"{jd} {MONTHS[jm - 1]} {jy}")


# ---------- خواندن مطالب ----------
def split_front_matter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        raise ValueError("front matter (بخش بین دو خط ---) پیدا نشد")
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def reading_minutes(text):
    words = len(re.findall(r"\w+", text))
    return fa(max(1, round(words / 180)))


def load_posts():
    posts = []
    md = markdown.Markdown(extensions=["extra", "toc", "sane_lists", "admonition"],
                           extension_configs={"toc": {"permalink": False}})
    for f in sorted((ROOT / "content" / "posts").glob("*.md")):
        try:
            meta, body = split_front_matter(f.read_text(encoding="utf-8"))
        except Exception as e:
            warnings.append(f"{f.name}: {e}")
            continue
        if meta.get("draft"):
            continue
        md.reset()
        slug = meta.get("slug") or f.stem
        cat = meta.get("category")
        if cat not in CATS:
            warnings.append(f"{f.name}: دسته‌ی «{cat}» در config.yaml تعریف نشده")
            continue
        tags = []
        for t in meta.get("tags", []):
            if t not in TAGS:
                warnings.append(f"{f.name}: برچسب «{t}» در config.yaml تعریف نشده (نادیده گرفته شد)")
            else:
                tags.append(t)
        date = meta["date"] if isinstance(meta["date"], datetime.date) else datetime.date.fromisoformat(str(meta["date"]))
        content_html = md.convert(body)
        posts.append({
            "title": meta["title"], "slug": slug, "url": f"/posts/{slug}/",
            "date": date, "date_fa": jdate(date), "category": CATS[cat], "tags": [TAGS[t] for t in tags],
            "summary": meta.get("summary", ""), "html": content_html, "toc": md.toc if "[TOC]" in body or len(md.toc_tokens) > 2 else "",
            "minutes": reading_minutes(body), "plain": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", content_html)),
        })
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def load_library():
    items = yaml.safe_load((ROOT / "data" / "library.yaml").read_text(encoding="utf-8")) or []
    out = []
    for it in items:
        if it.get("type") not in LTYPES:
            warnings.append(f"کتابخانه: نوع «{it.get('type')}» برای «{it.get('title')}» تعریف نشده")
            continue
        if it.get("category") not in CATS:
            warnings.append(f"کتابخانه: دسته‌ی «{it.get('category')}» برای «{it.get('title')}» تعریف نشده")
            continue
        out.append({**it, "type_obj": LTYPES[it["type"]], "category_obj": CATS[it["category"]],
                    "tags_obj": [TAGS[t] for t in it.get("tags", []) if t in TAGS]})
    return out


# ---------- ساخت ----------
def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT, dirs_exist_ok=True)

    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    env.filters["fa"] = fa
    posts, library = load_posts(), load_library()
    cat_counts = {s: sum(1 for p in posts if p["category"]["slug"] == s) for s in CATS}
    tag_counts = {s: sum(1 for p in posts for t in p["tags"] if t["slug"] == s) for s in TAGS}
    base = dict(site=SITE, cats=CFG["categories"], cat_counts=cat_counts, year=fa(to_jalali(datetime.date.today())[0]),
                build_id=datetime.date.today().strftime("%Y%m%d"))

    def write(url, template, **ctx):
        path = OUT / url.strip("/") / "index.html" if url != "/" else OUT / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        ctx.update(base)
        ctx["canonical"] = SITE["url"] + url
        path.write_text(env.get_template(template).render(**ctx), encoding="utf-8")

    write("/", "home.html", posts=posts[:6], page_title=None, library_count=fa(len(library)),
          post_count=fa(len(posts)), tag_cloud=[(TAGS[s], tag_counts[s]) for s in TAGS if tag_counts[s]][:20])
    write("/posts/", "list.html", heading="همه‌ی مطالب", posts=posts, page_title="همه‌ی مطالب", intro="")
    for p in posts:
        related = [q for q in posts if q is not p and (q["category"] == p["category"] or {t["slug"] for t in q["tags"]} & {t["slug"] for t in p["tags"]})][:3]
        write(p["url"], "post.html", post=p, page_title=p["title"], related=related, description=p["summary"])
    for c in CFG["categories"]:
        write(f"/category/{c['slug']}/", "list.html", heading=f"{c['icon']} {c['name']}", intro=c["desc"],
              posts=[p for p in posts if p["category"]["slug"] == c["slug"]], page_title=c["name"])
    for t in CFG["tags"]:
        if tag_counts[t["slug"]]:
            write(f"/tag/{t['slug']}/", "list.html", heading=f"برچسب: {t['name']}", intro="",
                  posts=[p for p in posts if any(x["slug"] == t["slug"] for x in p["tags"])], page_title=f"برچسب {t['name']}")
    write("/tags/", "tags.html", page_title="همه‌ی برچسب‌ها",
          tag_list=[(t, tag_counts[t["slug"]]) for t in CFG["tags"]])
    write("/library/", "library.html", page_title="کتابخانه", items=library, ltypes=CFG["library_types"])
    write("/search/", "search.html", page_title="جستجو")
    write("/about/", "about.html", page_title="درباره‌ی ما")
    (OUT / "404.html").write_text(env.get_template("404.html").render(**base, canonical=SITE["url"], page_title="صفحه پیدا نشد"), encoding="utf-8")

    # شاخص جستجو
    index = [{"t": p["title"], "u": p["url"], "c": p["category"]["name"], "d": p["summary"],
              "g": " ".join(t["name"] for t in p["tags"]), "x": p["plain"][:3000]} for p in posts]
    index += [{"t": i["title"], "u": "/library/", "c": "کتابخانه · " + i["type_obj"]["name"], "d": i.get("desc", ""), "g": "", "x": ""} for i in library]
    (OUT / "search-index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    # sitemap / robots / rss / CNAME
    urls = ["/", "/posts/", "/library/", "/tags/", "/about/"] + [p["url"] for p in posts] + \
           [f"/category/{s}/" for s in CATS] + [f"/tag/{s}/" for s in TAGS if tag_counts[s]]
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                                     "\n".join(f"<url><loc>{SITE['url']}{u}</loc></url>" for u in urls) + "\n</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE['url']}/sitemap.xml\n", encoding="utf-8")
    (OUT / "CNAME").write_text(SITE["url"].replace("https://", "") + "\n", encoding="utf-8")
    items = "".join(
        f"<item><title>{html.escape(p['title'])}</title><link>{SITE['url']}{p['url']}</link><guid>{SITE['url']}{p['url']}</guid>"
        f"<pubDate>{p['date'].strftime('%a, %d %b %Y')} 00:00:00 +0000</pubDate><description>{html.escape(p['summary'])}</description></item>"
        for p in posts[:20])
    (OUT / "feed.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{SITE["title"]}</title>'
                                  f'<link>{SITE["url"]}</link><description>{html.escape(SITE["description"])}</description><language>fa</language>{items}</channel></rss>', encoding="utf-8")

    print(f"✔ سایت ساخته شد: {len(posts)} مطلب، {len(library)} منبع کتابخانه ← پوشه‌ی public")
    for w in warnings:
        print("⚠ ", w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
