# Facebook multi-Page automation

Commands (run from repo root, `pip install -r fb_automation/requirements.txt`):

    export FB_USER_TOKEN=<long-lived user token>
    python fb_automation/main.py pages              # list all Pages you manage
    python fb_automation/main.py post --dry-run     # posts/schedules from content/posts.csv
    python fb_automation/main.py autoreply --dry-run
    python fb_automation/main.py report

## Setup
1. developers.facebook.com -> create a Business app.
2. Permissions: pages_show_list, pages_manage_posts, pages_read_engagement,
   pages_manage_engagement. (Dev mode works for Pages you admin.)
3. Graph API Explorer -> generate a user token, exchange it for a long-lived one
   (`/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=SECRET&fb_exchange_token=TOKEN`).
4. Add it as GitHub repo secret `FB_USER_TOKEN`. Optional env `FB_PAGE_IDS=id1,id2` limits Pages.

## posts.csv
`page` = `all`, or `;`-separated Page IDs/names. `scheduled_time` = ISO (e.g. `2026-10-12T09:00:00+06:00`),
empty = post now. Rows with a `status` are skipped; the workflow fills it in.
Facebook only accepts schedules 10 min - 30 days ahead; later rows wait until in range.

## Auto-reply
Edit `content/replies.json` (regex keywords -> reply, plus `default`). Each comment is replied to once.
