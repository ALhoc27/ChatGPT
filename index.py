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


def download_image(src):
    global CURRENT_CACHE_DIR, DOWNLOADED_FILES, CURRENT_CHAT_SLUG

    if CURRENT_CACHE_DIR is None:
        return src

    # гарантируем существование папок ТОЛЬКО при реальной загрузке
    os.makedirs(CURRENT_CACHE_DIR, exist_ok=True)

    ext = os.path.splitext(urlparse(src).path)[1] or ".png"
    name = hashlib.md5(src.encode()).hexdigest()[:12] + ext
    path = os.path.join(CURRENT_CACHE_DIR, name)

    if not os.path.exists(path):
        r = requests.get(src, timeout=20)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)

    DOWNLOADED_FILES.append(name)

    return f"ChatGPT_0x/Cach/{CURRENT_CHAT_SLUG}/{name}"


def extract_chat(page):
    soup = BeautifulSoup(page.content(), "html.parser")

    messages = []
    last_role = None
    buffer = []

    for article in soup.select("article"):
        role = "assistant"
        if article.find("h5") and "You" in article.get_text():
            role = "user"

        blocks = []

        for el in article.find_all(["p", "pre", "img", "ul", "ol"], recursive=True):

            if el.name == "img" and el.get("src"):
                blocks.append(f"![]({download_image(el['src'])})")

            elif el.name == "pre":
                code = el.get_text("\n", strip=False)
                lang = ""
                for c in el.get("class", []):
                    if c.startswith("language-"):
                        lang = c.replace("language-", "")
                blocks.append(f"```{lang}\n{code.rstrip()}\n```")

            elif el.name in ("ul", "ol"):
                for li in el.find_all("li"):
                    blocks.append(f"- {li.get_text(strip=True)}")

            elif el.name == "p":
                text = el.get_text(strip=True)
                if text:
                    blocks.append(text)

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

            # ⬇️ КРИТИЧНО: инициализация ДО парсинга
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

            # если ассетов нет — чистим всё дерево
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
