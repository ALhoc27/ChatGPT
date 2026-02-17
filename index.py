import subprocess
import time
import os
import sys
import hashlib
import requests
import re
from urllib.parse import urlparse
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import pyperclip
import shutil


# ================= НАСТРОЙКИ =================
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_PROFILE = r"C:\chrome-debug"
WAIT_CHROME = 3

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))  # ChatGPT/
MD_DIR = ROOT_DIR

ASSETS_ROOT = os.path.join(MD_DIR, "ChatGPT_0x", "Cach")

# runtime
CURRENT_CHAT_SLUG = None
CURRENT_CACHE_DIR = None
DOWNLOADED_FILES = []
# ============================================


def get_chat_url():
    url = pyperclip.paste().strip()
    if not url.startswith("https://chatgpt.com/"):
        raise RuntimeError("❌ В буфере нет ссылки ChatGPT")
    return url


def get_chat_title(page):
    title = page.title().replace(" - ChatGPT", "").strip()
    return title or "ChatGPT Chat"


def scroll_to_top(page):
    last = None
    while True:
        h = page.evaluate("document.body.scrollHeight")
        if h == last:
            break
        last = h
        page.evaluate("window.scrollTo(0,0)")
        time.sleep(1)


# ================= ИЗМЕНЕНО ТОЛЬКО ЭТО =================
def download_image(src, page):
    global CURRENT_CACHE_DIR, DOWNLOADED_FILES, CURRENT_CHAT_SLUG

    if CURRENT_CACHE_DIR is None:
        return src

    if not src or src.startswith("data:"):
        return src

    os.makedirs(CURRENT_CACHE_DIR, exist_ok=True)

    ext = os.path.splitext(urlparse(src).path)[1] or ".png"
    name = hashlib.md5(src.encode()).hexdigest()[:12] + ext
    path = os.path.join(CURRENT_CACHE_DIR, name)

    if os.path.exists(path):
        DOWNLOADED_FILES.append(name)
        return f"ChatGPT_0x/Cach/{CURRENT_CHAT_SLUG}/{name}"

    try:
        response = page.context.request.get(
            src,
            headers={
                "referer": page.url,
                "origin": "https://chatgpt.com"
            }
        )

        if not response.ok:
            print("❌ HTTP:", response.status, src)
            return src

        with open(path, "wb") as f:
            f.write(response.body())

        DOWNLOADED_FILES.append(name)
        return f"ChatGPT_0x/Cach/{CURRENT_CHAT_SLUG}/{name}"

    except Exception as e:
        print("Ошибка загрузки:", e)
        return src
# =======================================================


def render_inline(el):
    from bs4 import NavigableString, Tag

    if isinstance(el, NavigableString):
        return str(el)

    if not isinstance(el, Tag):
        return ""

    name = el.name

    if name in ["strong", "b"]:
        return f"**{''.join(render_inline(c) for c in el.children)}**"

    if name in ["em", "i"]:
        return f"*{''.join(render_inline(c) for c in el.children)}*"

    if name == "del":
        return f"~~{''.join(render_inline(c) for c in el.children)}~~"

    if name == "code":
        return f"`{el.get_text(strip=True)}`"

    if name == "a":
        text = ''.join(render_inline(c) for c in el.children)
        href = el.get("href", "")
        return f"[{text}]({href})" if href else text

    return ''.join(render_inline(c) for c in el.children)


def extract_chat(page):
    soup = BeautifulSoup(page.content(), "html.parser")

    messages = []
    last_role = None
    buffer = []

    for article in soup.select("article[data-testid^='conversation-turn']"):

        role = article.get("data-turn")
        if role not in ["user", "assistant"]:
            role = "assistant"

        blocks = []

        container = article.find(attrs={"data-message-author-role": role})
        if not container:
            continue

        for el in container.find_all([
            "h1", "h2", "h3", "h4",
            "p", "pre", "ul", "ol",
            "img", "hr", "blockquote",
            "table", "div"
        ]):

            if el.name == "img" and el.get("src"):
                src = el.get("src")
                if not src.startswith("data:"):
                    blocks.append(f"![]({download_image(src, page)})")
                continue

            if el.name in ["h1", "h2", "h3", "h4"]:
                level = int(el.name[1])
                text = render_inline(el).strip()
                blocks.append(f"{'#' * level} {text}")
                continue

            if el.name == "hr":
                blocks.append("---")
                continue

            if el.name == "pre":
                code_tag = el.find("code")
                if not code_tag:
                    continue

                lang = ""
                for c in code_tag.get("class", []):
                    if c.startswith("language-"):
                        lang = c.replace("language-", "").lower()

                code = code_tag.get_text("\n", strip=False).rstrip()
                blocks.append(f"```{lang}\n{code}\n```")
                continue

            if el.name == "table":
                rows = []
                for tr in el.find_all("tr"):
                    cells = [
                        render_inline(td).strip()
                        for td in tr.find_all(["th", "td"])
                    ]
                    rows.append(cells)

                if rows:
                    header = rows[0]
                    separator = ["---"] * len(header)
                    table_md = []

                    table_md.append("| " + " | ".join(header) + " |")
                    table_md.append("| " + " | ".join(separator) + " |")

                    for row in rows[1:]:
                        table_md.append("| " + " | ".join(row) + " |")

                    blocks.append("\n".join(table_md))
                continue

            if el.name == "blockquote":
                text = render_inline(el).strip()
                blocks.append(f"> {text}")
                continue

            if el.name in ("ul", "ol"):
                is_ordered = el.name == "ol"
                for i, li in enumerate(el.find_all("li", recursive=False), start=1):
                    text = render_inline(li).strip()
                    if text:
                        prefix = f"{i}." if is_ordered else "-"
                        blocks.append(f"{prefix} {text}")
                continue

            if el.name == "p":
                if el.find_parent(["li", "blockquote"]):
                    continue
                text = render_inline(el).strip()
                if text:
                    blocks.append(text)
                continue

        for img in container.find_all("img"):
            src = img.get("src")
            if not src or src.startswith("data:"):
                continue
            blocks.append(f"![]({download_image(src, page)})")

        if not blocks:
            continue

        text = "\n\n".join(blocks)

        if role == last_role:
            buffer.append(text)
        else:
            if buffer:
                messages.append((last_role, "\n\n".join(buffer)))
            buffer = [text]
            last_role = role

    if buffer:
        messages.append((last_role, "\n\n".join(buffer)))

    return messages


def render_block(container, page):
    blocks = []

    for el in container.children:

        if getattr(el, "name", None) is None:
            continue

        if el.name == "img" and el.get("src"):
            blocks.append(f"![]({download_image(el['src'], page)})")
            continue

    return blocks


def format_md(messages, title, source_url):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    out = [
        "---",
        "tags: [chatgpt, export]",
        f"source: {source_url}",
        f"date: {now}",
        "---",
        "",
        f"# {title}",
        ""
    ]

    for role, text in messages:
        out.append("## 🧑 You" if role == "user" else "## 🤖 ChatGPT")
        out.append("")
        out.append(text.strip())
        out.append("")

    return "\n".join(out).strip()


def main():
    print("🚀 Запускаем Chrome с удаленной отладкой...")
    chrome_process = subprocess.Popen([
        CHROME_PATH,
        "--remote-debugging-port=9222",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={CHROME_PROFILE}"
    ])

    print(f"⏳ Ждем {WAIT_CHROME} секунд на запуск Chrome...")
    time.sleep(WAIT_CHROME)

    exit_code = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.new_page()

            chat_url = get_chat_url()
            print("🌐 Открываем чат...")
            page.goto(chat_url, wait_until="networkidle")

            scroll_to_top(page)

            print("📥 Экспортируем...")
            title = get_chat_title(page)

            global CURRENT_CHAT_SLUG, CURRENT_CACHE_DIR, DOWNLOADED_FILES
            DOWNLOADED_FILES = []

            ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
            safe_title = re.sub(r"[\\/:*?\"<>|]", "", title)
            CURRENT_CHAT_SLUG = f"{safe_title}_{ts}"
            CURRENT_CACHE_DIR = os.path.join(ASSETS_ROOT, CURRENT_CHAT_SLUG)

            messages = extract_chat(page)

            md_path = os.path.join(MD_DIR, f"{CURRENT_CHAT_SLUG}.md")
            md_text = format_md(messages, title, chat_url)

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_text)

            if not DOWNLOADED_FILES:
                if os.path.exists(os.path.join(MD_DIR, "ChatGPT_0x")):
                    shutil.rmtree(os.path.join(MD_DIR, "ChatGPT_0x"))

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        exit_code = 1

    finally:
        print("🛑 Закрываем Chrome...")
        if chrome_process.poll() is None:
            chrome_process.terminate()
            try:
                chrome_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome_process.kill()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
