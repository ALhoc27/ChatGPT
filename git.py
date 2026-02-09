import subprocess
from datetime import datetime
import os
import sys

LOG_FILE = "git.log"


def log(text):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


def wait_for_enter():
    input("\nНажмите ENTER для выхода...")
    sys.exit(0)


def run_git(cmd):
    log(f">>> {cmd}")
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    output = (result.stdout + result.stderr).strip()
    log(output)
    return result.returncode == 0, output


def choose(title, description, solution, options):
    print(f"\n❗ {title}")
    print(f"{description}\n")
    print(f"💡 Решение:\n{solution}\n")
    for i, opt in enumerate(options, 1):
        print(f"{i}. {opt}")
    while True:
        c = input("Выбери номер: ").strip()
        if c.isdigit() and 1 <= int(c) <= len(options):
            return int(c)
        print("Неверный выбор.")


def detect_branch():
    ok, out = run_git("git branch --show-current")
    if ok and out.strip():
        return out.strip()
    ok, out = run_git("git branch")
    if "main" in out:
        return "main"
    if "master" in out:
        return "master"
    return "main"


def main():
    print("\n🧠 Smart Git Helper — PROD\n")
    log("=== START ===")

    if not os.path.isdir(".git"):
        print("❌ Это не git-репозиторий (нет папки .git)")
        wait_for_enter()

    branch = detect_branch()
    log(f"Branch: {branch}")

    msg = input("Введите сообщение коммита: ").strip()
    if not msg:
        print("❌ Пустое сообщение коммита недопустимо")
        wait_for_enter()

    commit_msg = f"{msg} [{datetime.now().strftime('%Y-%m-%d %H:%M')}]"
    print(f"\n📝 Commit:\n{commit_msg}\n")

    run_git("git add .")

    ok, out = run_git(f'git commit -m "{commit_msg}"')
    if not ok and "nothing to commit" not in out.lower():
        print("❌ Ошибка коммита:\n", out)
        wait_for_enter()

    while True:
        ok, out = run_git(f"git push origin {branch}")
        if ok:
            print("✅ Push выполнен успешно")
            wait_for_enter()

        low = out.lower()
        print("\n❌ Ошибка git push:\n", out)

        # ===== ERROR HANDLERS =====

        if "would be overwritten by merge" in low:
            c = choose(
                "Локальные изменения мешают обновлению",
                "В рабочей директории есть изменения, которые Git боится перезаписать.",
                "Сохранить изменения во временное хранилище (stash) или отменить операцию.",
                ["git stash (рекомендуется)", "Отмена"]
            )
            if c == 1:
                run_git("git stash")
            else:
                wait_for_enter()

        elif "src refspec" in low or "bad revision 'head'" in low:
            c = choose(
                "Ветка не существует или нет коммитов",
                "Git не может отправить ветку, потому что она ещё не создана.",
                "Создать ветку и сделать push.",
                ["Создать ветку и push", "Отмена"]
            )
            if c == 1:
                run_git(f"git branch -M {branch}")
                run_git(f"git push -u origin {branch}")
                wait_for_enter()
            else:
                wait_for_enter()

        elif "repository not found" in low:
            choose(
                "Репозиторий не найден",
                "URL репозитория неверный или у тебя нет к нему доступа.",
                "Проверь адрес remote origin и права доступа.",
                ["Выйти"]
            )
            wait_for_enter()

        elif "authentication failed" in low or "password authentication was removed" in low:
            choose(
                "Ошибка авторизации GitHub",
                "GitHub больше не принимает логин/пароль.",
                "Используй Personal Access Token вместо пароля.",
                ["Открыть https://github.com/settings/tokens"]
            )
            wait_for_enter()

        elif "rejected" in low or "behind" in low:
            c = choose(
                "Удалённый репозиторий новее",
                "На GitHub есть коммиты, которых нет локально.",
                "Подтянуть изменения и повторить push.",
                ["git pull --rebase", "Отмена"]
            )
            if c == 1:
                ok, _ = run_git("git pull --rebase")
                if not ok:
                    print("⚠️ Конфликт. Исправь вручную.")
                    wait_for_enter()
            else:
                wait_for_enter()

        elif "refusing to merge unrelated histories" in low:
            choose(
                "Несвязанные истории",
                "Локальный и удалённый репозиторий не имеют общей истории.",
                "Обычно возникает при первом pull.",
                ["git pull --allow-unrelated-histories"]
            )
            wait_for_enter()

        elif "index.lock" in low:
            choose(
                "Git заблокирован",
                "Файл index.lock остался после сбоя.",
                "Закрой все git-процессы и удали .git/index.lock.",
                ["Выйти"]
            )
            wait_for_enter()

        elif "ssl certificate problem" in low:
            choose(
                "SSL ошибка",
                "Проблема сертификата (часто прокси или корпоративная сеть).",
                "Проверь сеть, VPN или прокси.",
                ["Выйти"]
            )
            wait_for_enter()

        elif "unable to access" in low or "could not resolve host" in low:
            choose(
                "Проблемы с сетью",
                "GitHub недоступен: интернет, DNS или VPN.",
                "Проверь соединение и повтори.",
                ["Выйти"]
            )
            wait_for_enter()

        elif "detached head" in low:
            choose(
                "Detached HEAD",
                "Ты не находишься на ветке.",
                "Переключись на main или master.",
                ["git checkout main/master"]
            )
            wait_for_enter()

        else:
            choose(
                "Неизвестная ошибка",
                "Git вернул ошибку, которую скрипт не распознал.",
                "См. лог-файл для деталей.",
                ["Выйти"]
            )
            wait_for_enter()


if __name__ == "__main__":
    main()
