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
CHROME_USER_DATA = r"C:\Users\alex7\Documents\chrome-debug"
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
    global CURRENT_CACHE_DIR, DOWNLOADED_FILES, CURRENT_CHAT_SLUG, PLAYWRIGHT_CONTEXT

    if CURRENT_CACHE_DIR is None:
        return src

    os.makedirs(CURRENT_CACHE_DIR, exist_ok=True)

    ext = os.path.splitext(urlparse(src).path)[1] or ".png"
    name = hashlib.md5(src.encode()).hexdigest()[:12] + ext
    path = os.path.join(CURRENT_CACHE_DIR, name)

    if not os.path.exists(path):
        try:
            # 🔥 скачиваем через авторизованный браузер
            response = PLAYWRIGHT_CONTEXT.request.get(src, timeout=30000)
            if not response.ok:
                print("❌ image download failed:", response.status)
                return src

            with open(path, "wb") as f:
                f.write(response.body())

        except Exception as e:
            print("❌ image download exception:", e)
            return src

    DOWNLOADED_FILES.append(name)
    return f"./ChatGPT_0x/Cach/{CURRENT_CHAT_SLUG}/{name}"



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

    # устойчивый селектор turn
    for article in soup.select("article[data-testid^='conversation-turn']"):
        role = article.get("data-turn")
        if role not in ["user", "assistant"]:
            role = "assistant"

        blocks = []

        # контейнер с реальным содержимым
        container = article.find(attrs={"data-message-author-role": role})
        if not container:
            continue

        for el in container.find_all([
            "h1", "h2", "h3", "h4",
            "p", "pre", "ul", "ol",
            "hr", "blockquote",
            "table", "div", "button"
        ]):

            # -------- USER RAW PRE BLOCK --------
            if el.name == "div" and "whitespace-pre-wrap" in el.get("class", []):
                raw_text = el.get_text()

                # нормализуем Windows переносы
                raw_text = raw_text.replace("\r\n", "\n")

                # убираем только один возможный лишний перевод строки в конце
                if raw_text.endswith("\n"):
                    raw_text = raw_text[:-1]

                blocks.append(f"```\n{raw_text}\n```")
                continue

            # -------- ЗАГОЛОВКИ --------
            if el.name in ["h1", "h2", "h3", "h4"]:
                level = int(el.name[1])
                text = render_inline(el).strip()
                blocks.append(f"{'#' * level} {text}")
                continue

            # -------- HR --------
            if el.name == "hr":
                blocks.append("---")
                continue

            # -------- CODE BLOCK --------
            if el.name == "pre":
                code_tag = el.find("code")
                if not code_tag:
                    continue

                # язык
                lang = ""
                for c in code_tag.get("class", []):
                    if c.startswith("language-"):
                        lang = c.replace("language-", "").lower()

                code = code_tag.get_text("", strip=False).rstrip("\n")
                clean = code.strip()

                # 🔥 Фильтр технических мусорных шаблонов ChatGPT
                if re.fullmatch(r"(\\n)?\{[a-zA-Z_]+\}(\\n)?", clean):
                    continue

                # Дополнительный фильтр конкретных служебных паттернов
                if clean in (
                        r"\n{raw_text}\n",
                        r"{lang}\n{code}\n",
                        r"{code}\n",
                        r"{lang}\n{code}"
                ):
                    continue

                blocks.append(f"```{lang}\n{code}\n```")
                continue

            # -------- IMAGE --------
            # if el.name == "img" and el.get("src"):
            #     blocks.append(f"![]({download_image(el['src'])})")
            #     continue

            # -------- TABLE --------
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

            # -------- BLOCKQUOTE --------
            if el.name == "blockquote":
                text = render_inline(el).strip()
                blocks.append(f"> {text}")
                continue

            # -------- LISTS --------
            if el.name in ("ul", "ol"):
                is_ordered = el.name == "ol"
                for i, li in enumerate(el.find_all("li", recursive=False), start=1):
                    text = render_inline(li).strip()
                    if text:
                        prefix = f"{i}." if is_ordered else "-"
                        blocks.append(f"{prefix} {text}")
                continue

            # -------- PARAGRAPH --------
            if el.name == "p":
                if el.find_parent(["li", "blockquote"]):
                    continue
                text = render_inline(el).strip()
                if text:
                    blocks.append(text)
                continue

        # ===== ДОБАВЛЯЕМ ВСЕ ИЗОБРАЖЕНИЯ (И ТВОИ И МОИ) =====
        images = page.eval_on_selector_all(
            "article[data-testid^='conversation-turn'] img",
            "imgs => imgs.map(img => img.currentSrc || img.src)"
        )

        # убираем дубликаты
        images = list(dict.fromkeys(images))

        for src in images:
            if src and src.startswith("http"):
                blocks.append(f"![[{download_image(src)}]]")

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


def render_block(container):
    blocks = []

    for el in container.children:
        if getattr(el, "name", None) is None:
            continue

        # CODE BLOCK
        if el.name == "pre":
            code_tag = el.find("code")
            if code_tag:
                lang = ""
                for c in code_tag.get("class", []):
                    if c.startswith("language-"):
                        lang = c.replace("language-", "")

                code = code_tag.get_text("\n", strip=False).rstrip()
                blocks.append(f"```{lang}\n{code}\n```")
            continue

        # IMAGE
        if el.name == "img" and el.get("src"):
            src = el.get("src", "").strip()
            if src.startswith("http"):
                blocks.append(f"![]({download_image(src)})")
            continue

        # LIST
        if el.name in ("ul", "ol"):
            is_ordered = el.name == "ol"
            for i, li in enumerate(el.find_all("li", recursive=False), 1):
                text = render_inline(li).strip()
                if text:
                    prefix = f"{i}." if is_ordered else "-"
                    blocks.append(f"{prefix} {text}")
            continue

        # TABLE
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

        # BLOCKQUOTE
        if el.name == "blockquote":
            text = render_inline(el).strip()
            blocks.append(f"> {text}")
            continue

        # HEADINGS
        if el.name in ["h1", "h2", "h3", "h4"]:
            level = int(el.name[1])
            text = render_inline(el).strip()
            blocks.append(f"{'#' * level} {text}")
            continue

        # PARAGRAPH / DIV (универсально)
        if el.name in ["p", "div"]:
            text = render_inline(el).strip()
            if text:
                blocks.append(text)
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

def scroll_for_images(page):
    last_height = 0

    while True:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break

        last_height = new_height


def main():
    print("🚀 Запускаем Chrome с удаленной отладкой...")

    chrome_process = subprocess.Popen([
        CHROME_PATH,
        "--remote-debugging-port=9222",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={CHROME_USER_DATA}",
        "--window-position=-32000,-32000",
        "--window-size=1920,1080",
        "--start-maximized"
    ])

    print(f"⏳ Ждем {WAIT_CHROME} секунд на запуск Chrome...")
    time.sleep(WAIT_CHROME)

    exit_code = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            page = context.new_page()

            global PLAYWRIGHT_CONTEXT
            PLAYWRIGHT_CONTEXT = context

            chat_url = get_chat_url()
            print("🌐 Открываем чат...")
            page.goto(chat_url, wait_until="domcontentloaded")
            time.sleep(3)  # даём React догрузиться

            scroll_to_top(page)
            scroll_for_images(page)
            # ждём реальной загрузки изображений
            # page.wait_for_function("""
            #                        () => {
            #                            const imgs = Array.from(document.querySelectorAll("article img"));
            #                            return imgs.length > 0 && imgs.every(img => img.src && img.src.startsWith("http"));
            #                        }
            #                        """, timeout=15000)

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
                root_assets = os.path.join(MD_DIR, "ChatGPT_0x")
                if os.path.exists(root_assets):
                    shutil.rmtree(root_assets)

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
