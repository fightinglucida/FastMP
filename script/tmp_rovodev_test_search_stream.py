import argparse
import json
import sys
import time

import requests


def main():
    parser = argparse.ArgumentParser(description="Test /gzhaccount/search/stream NDJSON output")
    parser.add_argument("base_url", help="API base url, e.g. http://127.0.0.1:8000")
    parser.add_argument("email", help="Account email to login")
    parser.add_argument("password", help="Account password to login")
    parser.add_argument("name", help="WeChat account name to search")
    parser.add_argument("--max", dest="max_articles", type=int, default=20, help="Max articles to return in snapshots (default 20)")
    args = parser.parse_args()

    # 1) login to get token
    login_url = f"{args.base_url.rstrip('/')}/auth/login"
    login_payload = {"email": args.email, "password": args.password}
    print(f"POST {login_url} as {args.email}")
    lr = requests.post(login_url, json=login_payload)
    lr.raise_for_status()
    token = lr.json()["access_token"]

    # 2) stream search
    url = f"{args.base_url.rstrip('/')}/gzhaccount/search/stream"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/x-ndjson",
    }
    payload = {"name": args.name, "max_articles": args.max_articles}

    print(f"POST {url} name={args.name} max_articles={args.max_articles}")
    with requests.post(url, headers=headers, json=payload, stream=True) as r:
        r.raise_for_status()
        print("Connected. Streaming events (NDJSON). Press Ctrl+C to stop.\n")
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                print(f"! Non-JSON line: {line}")
                continue

            t = evt.get("type")
            if t == "account":
                acc = evt.get("account")
                print(f"[account] name={acc.get('name')} biz={acc.get('biz')} total_db={acc.get('article_account')}")
            elif t == "page":
                page = evt.get("page")
                new_added = evt.get("new_added")
                total_db = evt.get("total_db")
                has_more = evt.get("has_more")
                items = evt.get("items") or []
                latest = items[0]["title"] if items else "-"
                print(f"[page {page}] new_added={new_added} total_db={total_db} has_more={has_more} latest='{latest}' items={len(items)}")
            elif t == "done":
                total_db = evt.get("total_db")
                items = evt.get("items") or []
                latest = items[0]["title"] if items else "-"
                print(f"[done] total_db={total_db} final_items={len(items)} latest='{latest}'")
                break
            elif t == "error":
                print(f"[error] {evt.get('message')}")
                break
            else:
                print(f"[unknown] {evt}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
