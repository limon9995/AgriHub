"""Thin Facebook Graph API wrapper that handles every Page you manage."""
import os
import requests

GRAPH = "https://graph.facebook.com/v21.0"


class FBError(RuntimeError):
    pass


def _call(method, path, token, **params):
    params["access_token"] = token
    r = requests.request(method, f"{GRAPH}/{path}", params=params if method == "GET" else None,
                         data=params if method != "GET" else None, timeout=60)
    data = r.json()
    if "error" in data:
        raise FBError(f"{path}: {data['error'].get('message')}")
    return data


def load_pages():
    """Return {page_id: {"name", "token"}} for all Pages the user token manages.

    Set FB_PAGE_IDS (comma separated) to limit to specific Pages.
    """
    user_token = os.environ.get("FB_USER_TOKEN")
    if not user_token:
        raise FBError("FB_USER_TOKEN is not set")
    wanted = {p.strip() for p in os.environ.get("FB_PAGE_IDS", "").split(",") if p.strip()}
    pages, url = {}, "me/accounts"
    after = None
    while True:
        extra = {"fields": "id,name,access_token", "limit": 100}
        if after:
            extra["after"] = after
        data = _call("GET", url, user_token, **extra)
        for p in data.get("data", []):
            if not wanted or p["id"] in wanted:
                pages[p["id"]] = {"name": p["name"], "token": p["access_token"]}
        after = data.get("paging", {}).get("cursors", {}).get("after")
        if not data.get("paging", {}).get("next"):
            break
    return pages


def publish(page_id, token, message="", link=None, image_url=None, scheduled_ts=None):
    """Publish now, or schedule if scheduled_ts (unix seconds) is given."""
    params = {}
    if scheduled_ts:
        params.update(published="false", scheduled_publish_time=int(scheduled_ts))
    if image_url:
        params.update(url=image_url, caption=message)
        return _call("POST", f"{page_id}/photos", token, **params)
    params["message"] = message
    if link:
        params["link"] = link
    return _call("POST", f"{page_id}/feed", token, **params)


def recent_comments(page_id, token, posts=10):
    """Comments on the Page's latest posts, with existing replies so we never double-reply."""
    data = _call("GET", f"{page_id}/posts", token, limit=posts,
                 fields="id,comments.limit(50){id,message,from,comments.limit(25){from}}")
    for post in data.get("data", []):
        for c in post.get("comments", {}).get("data", []):
            yield c


def reply(comment_id, token, message):
    return _call("POST", f"{comment_id}/comments", token, message=message)


def page_summary(page_id, token, posts=25):
    info = _call("GET", page_id, token, fields="name,fan_count,followers_count")
    feed = _call("GET", f"{page_id}/posts", token, limit=posts,
                 fields="id,created_time,message,shares,"
                        "reactions.summary(true).limit(0),comments.summary(true).limit(0)")
    return info, feed.get("data", [])
