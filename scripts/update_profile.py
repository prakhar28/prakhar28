"""Refresh the live-feed section of the profile README.

Fills the block between <!--LIVE:START--> and <!--LIVE:END--> with:
  * my most recently pushed public repos (GitHub API)
  * today's top AI stories from Hacker News
"""
import datetime as dt
import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

USER = os.environ.get("GH_USER", "prakhar28")
README = Path(__file__).resolve().parent.parent / "README.md"
AI = re.compile(
    r"\b(ai|llms?|gpt[- ]?\d*|openai|anthropic|claude|gemini|llama|mistral|deepseek|agents?|agentic|"
    r"rag|transformers?|machine learning|deep learning|inference|fine[- ]?tun\w*|embeddings?|mcp|evals?)\b",
    re.I,
)


def get(url: str, token: str | None = None):
    headers = {"User-Agent": f"{USER}-profile", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        return json.load(r)


def ago(iso: str, now: dt.datetime) -> str:
    days = (now - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    return "today" if days == 0 else "yesterday" if days == 1 else f"{days} days ago"


def recent_repos(now: dt.datetime) -> list[str]:
    repos = get(
        f"https://api.github.com/users/{USER}/repos?sort=pushed&per_page=30&type=owner",
        os.environ.get("GITHUB_TOKEN"),
    )
    rows = []
    for r in repos:
        if r["fork"] or r["archived"] or r["name"].lower() == USER.lower():
            continue
        desc = (r["description"] or "").replace("|", "\\|")
        lang = r["language"] or "—"
        rows.append(f"| [{r['name']}]({r['html_url']}) | {desc} | {lang} | {ago(r['pushed_at'], now)} |")
        if len(rows) == 5:
            break
    return rows


def ai_headlines() -> list[str]:
    hn = "https://hacker-news.firebaseio.com/v0"
    ids = get(f"{hn}/topstories.json")[:120]

    def item(i):
        try:
            return get(f"{hn}/item/{i}.json")
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=16) as pool:
        items = [it for it in pool.map(item, ids) if it and it.get("type") == "story" and it.get("title")]
    picks = sorted([it for it in items if AI.search(it["title"])], key=lambda it: -it.get("score", 0))[:5]
    out = []
    for it in picks:
        url = it.get("url") or f"https://news.ycombinator.com/item?id={it['id']}"
        title = it["title"].replace("[", "(").replace("]", ")")
        out.append(f"- [{title}]({url}) · ▲ {it.get('score', 0)}")
    return out


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc)
    repos = recent_repos(now)
    news = ai_headlines()

    parts = ["<!--LIVE:START-->"]
    if repos:
        parts += ["**🛠️ Recently shipped**\n", "| Repo | What it is | Lang | Last push |", "|---|---|---|---|", *repos, ""]
    if news:
        parts += ["**🤖 What I'm reading today** (top AI stories on Hacker News)\n", *news, ""]
    parts += [f"<sub>Auto-updated by GitHub Actions · last refresh {now:%b %d, %Y}</sub>", "<!--LIVE:END-->"]

    text = README.read_text(encoding="utf-8")
    new = re.sub(r"<!--LIVE:START-->.*?<!--LIVE:END-->", "\n".join(parts), text, flags=re.S)
    README.write_text(new, encoding="utf-8")
    print("README live section refreshed" if new != text else "no change")


if __name__ == "__main__":
    main()
