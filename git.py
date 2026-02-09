import subprocess
from datetime import datetime
import os

LOG_FILE = "git_smart_push.log"


def log(text):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


def run_git(cmd):
    log(f">>> {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True
    )
    output = (result.stdout + result.stderr).strip()
    log(output)
    return result.returncode == 0, output


def choose(title, description, options):
    print(f"\n❗ {title}")
    print(description)
    for i, opt in enumerate(options, 1):
        print(f"{i}. {opt}")
    while True:
        c = input("Выбери номер: ").strip()
        if c.isdigit() and 1 <= int(c) <= len(options):
            return int(c)
        print("Неверный выбор.")


def detect_branch():
    ok, out = run_git("git branch --show-current")
    if ok and out:
        return out.strip()

    ok, out = run_git("git branch")
    if "main" in out:
        return "main"
    if "master" in out:
        return "master"
    return "main"


def main():
    print("\n🧠 Smart Git Helper (ultimate)\n")
    log("=== START ===")

    if not os.path.isdir(".git"):
        print("❌ Это не git-репозиторий (нет папки .git)")
        log("Not a git repository")
        return

    branch = detect_branch()
    log(f"Using branch: {branch}")

    user_msg = input("Введите сообщение коммита: ").strip()
    if not user_msg:
        print("❌ Сообщение не может быть пустым")
        return

    commit_msg = f"{user_msg} [{datetime.now().strftime('%Y-%m-%d %H:%M')}]"
    print(f"\n📝 Commit:\n{commit_msg}\n")

    run_git("git add .")

    ok, out = run_git(f'git commit -m "{commit_msg}"')
    if not ok and "nothing to commit" not in out.lower():
        print("❌ Ошибка коммита:\n", out)
        return

    while True:
        ok, out = run_git(f"git push origin {branch}")
        if ok:
            print("✅ Успешно отправлено")
            log("SUCCESS")
            return

        low = out.lower()
        print("\n❌ Ошибка push:\n", out)

        # === ERROR HANDLERS ===

        if "would be overwritten by merge" in low:
            c = choose(
                "Локальные изменения мешают pull",
                "Git не может обновиться, потому что файлы будут перезаписаны.",
                ["Сохранить изменения (git stash)", "Отменить операцию"]
            )
            if c == 1:
                run_git("git stash")
            else:
                return

        elif "src refspec" in low:
            c = choose(
                "Ветка не существует",
                "Git не нашёл ветку для push.",
                ["Создать ветку и запушить", "Выйти"]
            )
            if c == 1:
                run_git(f"git branch -M {branch}")
                run_git(f"git push -u origin {branch}")
            else:
                return

        elif "authentication failed" in low or "password authentication was removed" in low:
            choose(
                "Ошибка авторизации",
                "GitHub больше не принимает пароли. Нужен Personal Access Token.",
                ["Открыть https://github.com/settings/tokens", "Выйти"]
            )
            return

        elif "rejected" in low or "behind" in low:
            c = choose(
                "Удалённый репозиторий новее",
                "На GitHub есть изменения, которых нет локально.",
                ["git pull --rebase", "Выйти"]
            )
            if c == 1:
                ok, _ = run_git("git pull --rebase")
                if not ok:
                    print("⚠️ Конфликт. Реши вручную.")
                    return
            else:
                return

        elif "detached head" in low:
            choose(
                "Detached HEAD",
                "Ты не находишься на ветке.",
                ["git checkout main/master", "Выйти"]
            )
            return

        elif "index.lock" in low:
            choose(
                "Файл блокировки Git",
                "Git думает, что другая операция всё ещё идёт.",
                ["Удалить .git/index.lock вручную", "Выйти"]
            )
            return

        elif "ssl certificate problem" in low:
            choose(
                "SSL ошибка",
                "Проблема с сертификатом (часто прокси / корпоративная сеть).",
                ["Проверить сеть / VPN", "Выйти"]
            )
            return

        elif "unable to access" in low:
            choose(
                "GitHub недоступен",
                "Проблемы с сетью, VPN или DNS.",
                ["Проверить интернет и повторить", "Выйти"]
            )
            return

        elif "permission denied" in low:
            choose(
                "Нет прав на репозиторий",
                "У тебя нет прав push в этот репозиторий.",
                ["Проверить URL репозитория", "Выйти"]
            )
            return

        else:
            c = choose(
                "Неизвестная ошибка",
                "Git вернул ошибку, которую скрипт не распознал.",
                ["Попробовать ещё раз", "Выйти"]
            )
            if c == 2:
                return


if __name__ == "__main__":
    main()
