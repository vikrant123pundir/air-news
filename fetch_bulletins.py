#!/usr/bin/env python3
"""Fetch the latest AIR English bulletins and keep the newest few of each
in data/<kind>.json (newest first). Only changes the files when a new bulletin appears.
Standard library only."""
import json, os, re, sys, time, urllib.request

KINDS = ["morning-news", "evening-news"]
KEEP = 7
PAGE = "https://newsonair.gov.in/bulletins-detail-category/{}/"
OUT_DIR = os.environ.get("OUT_DIR", "data")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
DATE_RE = re.compile(r"(%s)\s+(\d{1,2}),\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*([AP]M)" % "|".join(MONTHS))
URL_RE = re.compile(r"https://newsonair\.gov\.in/bulletins-detail/[^\"'<>\s]+")


def get(url, tries=3):
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (n + 1))
    raise RuntimeError("could not fetch %s: %s" % (url, last))


def entry_content(html):
    """Inner HTML of the first <div class="entry-content ...">, nested divs balanced."""
    m = re.search(r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>', html)
    if not m:
        return None
    start, depth = m.end(), 0
    for t in re.finditer(r"<(/?)div\b", html[start:]):
        if t.group(1) == "":
            depth += 1
        elif depth == 0:
            return html[start:start + t.start()].strip()
        else:
            depth -= 1
    return None


def published(html):
    i = html.find("blogCategory")
    m = DATE_RE.search(html, max(i, 0)) or DATE_RE.search(html)
    if not m:
        return None
    mon, day, year, hh, mm, ap = m.groups()
    h = int(hh) % 12 + (12 if ap == "PM" else 0)
    return "%s-%02d-%02dT%02d:%s" % (year, MONTHS.index(mon) + 1, int(day), h, mm)  # IST


def fetch_kind(kind):
    html = get(PAGE.format(kind))
    body = entry_content(html)
    pub = published(html)
    if not body or not pub or "HEADLINES" not in body.upper():
        raise RuntimeError("%s: page structure not recognised (content=%s, date=%s)" % (kind, bool(body), pub))
    m = URL_RE.search(html)
    return {"published": pub, "url": m.group(0) if m else PAGE.format(kind), "html": body}


def update(kind):
    path = os.path.join(OUT_DIR, kind + ".json")
    old = {"kind": kind, "items": []}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
    new = fetch_kind(kind)
    if any(i["published"] == new["published"] for i in old["items"]):
        print("%s: nothing new (latest %s)" % (kind, new["published"]))
        return
    items = ([new] + old["items"])[:KEEP]
    items.sort(key=lambda i: i["published"], reverse=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"kind": kind, "items": items}, f, ensure_ascii=False, indent=1)
    print("%s: added %s (%d stored)" % (kind, new["published"], len(items)))


if __name__ == "__main__":
    failed = 0
    for k in KINDS:
        try:
            update(k)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print("ERROR", e, file=sys.stderr)
    sys.exit(1 if failed else 0)
