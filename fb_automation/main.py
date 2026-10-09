"""Facebook multi-Page automation: pages | post | autoreply | report."""
import argparse
import csv
import datetime as dt
import json
import pathlib
import re
import sys

import fb_client as fb

ROOT = pathlib.Path(__file__).resolve().parent.parent
POSTS_CSV = ROOT / "content" / "posts.csv"
RULES_JSON = ROOT / "content" / "replies.json"
REPORT_DIR = ROOT / "reports"
FIELDS = ["page", "message", "link", "image_url", "scheduled_time", "status"]


def targets(pages, spec):
    """spec: 'all' or ';'-separated page ids / names."""
    spec = (spec or "all").strip()
    if spec.lower() == "all":
        return list(pages.items())
    wanted = {s.strip().lower() for s in spec.split(";") if s.strip()}
    return [(i, p) for i, p in pages.items() if i in wanted or p["name"].lower() in wanted]


def cmd_pages(args):
    for pid, p in fb.load_pages().items():
        print(pid, p["name"])


def cmd_post(args):
    """Process rows of content/posts.csv whose status is empty.

    scheduled_time empty or in the past -> publish now.
    scheduled_time 10 min..30 days ahead -> schedule on Facebook.
    Further ahead -> left pending until it is in range.
    """
    pages = fb.load_pages()
    with open(POSTS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    now = dt.datetime.now(dt.timezone.utc)
    for row in rows:
        if row.get("status"):
            continue
        when = None
        if row.get("scheduled_time"):
            when = dt.datetime.fromisoformat(row["scheduled_time"].strip())
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt.timezone.utc)
        delta = (when - now).total_seconds() if when else 0
        if delta > 30 * 86400:
            continue
        ts = when.timestamp() if delta >= 600 else None  # <10 min: publish now
        chosen = targets(pages, row["page"])
        if not chosen:
            row["status"] = "error: no matching page"
            continue
        results = []
        for pid, p in chosen:
            try:
                if args.dry_run:
                    print(f"[dry-run] {p['name']}: {row['message'][:50]!r} at {when}")
                    continue
                fb.publish(pid, p["token"], row["message"], row.get("link") or None,
                           row.get("image_url") or None, ts)
                results.append("ok")
            except fb.FBError as e:
                results.append(f"error: {e}")
                print(f"{p['name']}: {e}", file=sys.stderr)
        if not args.dry_run:
            bad = [r for r in results if r != "ok"]
            row["status"] = ("scheduled" if ts else "posted") if not bad else bad[0]
    if not args.dry_run:
        with open(POSTS_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows({k: r.get(k, "") for k in FIELDS} for r in rows)


def cmd_autoreply(args):
    rules = json.loads(RULES_JSON.read_text(encoding="utf-8"))
    for pid, p in fb.load_pages().items():
        for c in fb.recent_comments(pid, p["token"], args.posts):
            if c.get("from", {}).get("id") == pid:
                continue  # our own comment
            replied = any(r.get("from", {}).get("id") == pid
                          for r in c.get("comments", {}).get("data", []))
            if replied:
                continue
            text = c.get("message", "")
            for rule in rules["rules"]:
                if any(re.search(k, text, re.I) for k in rule["keywords"]):
                    answer = rule["reply"]
                    break
            else:
                answer = rules.get("default")
            if not answer:
                continue
            if args.dry_run:
                print(f"[dry-run] {p['name']}: {text[:40]!r} -> {answer[:40]!r}")
            else:
                fb.reply(c["id"], p["token"], answer)
                print(f"{p['name']}: replied to {c['id']}")


def cmd_report(args):
    REPORT_DIR.mkdir(exist_ok=True)
    stamp = dt.date.today().isoformat()
    out = REPORT_DIR / f"report-{stamp}.csv"
    rows = []
    for pid, p in fb.load_pages().items():
        info, posts = fb.page_summary(pid, p["token"], args.posts)
        react = sum(x.get("reactions", {}).get("summary", {}).get("total_count", 0) for x in posts)
        comm = sum(x.get("comments", {}).get("summary", {}).get("total_count", 0) for x in posts)
        shares = sum(x.get("shares", {}).get("count", 0) for x in posts)
        rows.append({"date": stamp, "page": info["name"], "page_id": pid,
                     "fans": info.get("fan_count", ""), "followers": info.get("followers_count", ""),
                     "posts_sampled": len(posts), "reactions": react, "comments": comm, "shares": shares})
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["date"])
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)
    print("saved", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pages").set_defaults(fn=cmd_pages)
    for name, fn in (("post", cmd_post), ("autoreply", cmd_autoreply)):
        s = sub.add_parser(name)
        s.add_argument("--dry-run", action="store_true")
        s.add_argument("--posts", type=int, default=10)
        s.set_defaults(fn=fn)
    s = sub.add_parser("report")
    s.add_argument("--posts", type=int, default=25)
    s.set_defaults(fn=cmd_report)
    args = ap.parse_args()
    try:
        args.fn(args)
    except fb.FBError as e:
        sys.exit(f"Facebook error: {e}")


if __name__ == "__main__":
    main()
