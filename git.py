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
    print(f"💡 Пояснение:\n{solution}\n")
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


# ===== HISTORY =====

def show_recent_commits():
    print("\n📜 Последние 10 коммитов:\n")
    ok, out = run_git("git log --oneline -10")
    if not ok or not out.strip():
        print("❌ Не удалось получить историю коммитов")
        wait_for_enter()

    commits = []
    for i, line in enumerate(out.strip().splitlines(), 1):
        print(f"{i}. {line}")
        commits.append(line.split()[0])

    return commits


# ===== FORCE PUSH =====

def offer_force_push(branch):
    confirm = input(
        f"\n⚠️ История ветки была изменена.\n"
        f"Разрешить git push --force-with-lease в ветку '{branch}'?\n"
        f"Введите YES для подтверждения: "
    )
    if confirm == "YES":
        ok, out = run_git(f"git push --force-with-lease origin {branch}")
        if ok:
            print("✅ Force-push выполнен успешно")
        else:
            print("❌ Ошибка force-push:\n", out)
    else:
        print("ℹ️ Force-push отменён")


# ===== ROLLBACK =====

def rollback_menu(commits, branch):
    mode = choose(
        "Профессиональный откат Git",
        "Ты собираешься откатить репозиторий к предыдущему состоянию.",
        (
            "1️⃣ reset --soft\n"
            "Коммиты будут отменены.\n"
            "Все изменения останутся ПОДГОТОВЛЕННЫМИ к коммиту.\n"
            "Используй, если нужно изменить сообщение коммита.\n\n"

            "2️⃣ reset --mixed (самый популярный вариант)\n"
            "Коммиты будут отменены.\n"
            "Изменения останутся в файлах, но НЕ будут добавлены.\n"
            "Используй, если нужно доработать код.\n\n"

            "3️⃣ reset --hard ⚠️ ОПАСНО\n"
            "Коммиты и все изменения в файлах будут УДАЛЕНЫ БЕЗВОЗВРАТНО.\n"
            "Используй только если уверен на 100%.\n\n"

            "4️⃣ revert (БЕЗОПАСНО)\n"
            "История НЕ переписывается.\n"
            "Создаётся новый коммит, отменяющий выбранный.\n"
            "Рекомендуется для GitHub и совместной работы."
        ),
        [
            "reset --soft",
            "reset --mixed",
            "reset --hard",
            "revert (безопасно)"
        ]
    )

    num = input("\nВведите номер строки коммита (1–10): ").strip()
    if not num.isdigit() or not (1 <= int(num) <= len(commits)):
        print("❌ Неверный номер")
        wait_for_enter()

    commit = commits[int(num) - 1]
    did_reset = False

    if mode == 1:
        run_git(f"git reset --soft {commit}")
        did_reset = True

    elif mode == 2:
        run_git(f"git reset --mixed {commit}")
        did_reset = True

    elif mode == 3:
        if input("Введите YES для подтверждения HARD RESET: ") != "YES":
            wait_for_enter()
        run_git(f"git reset --hard {commit}")
        did_reset = True

    elif mode == 4:
        run_git(f"git revert {commit}")
        wait_for_enter()

    if did_reset:
        offer_force_push(branch)

    wait_for_enter()


# ===== EDIT COMMIT MESSAGE =====

def edit_commit_message(commits):
    print(
        "\n⚠️ ВАЖНО:\n"
        "Изменять комментарий БЕЗОПАСНО можно ТОЛЬКО у ПОСЛЕДНЕГО (HEAD) коммита.\n"
        "Любые другие коммиты требуют интерактивный rebase.\n"
    )

    print(
        "Если выбран НЕ последний коммит:\n"
        "Git откроет редактор со списком коммитов.\n"
        "Ты сам управляешь историей.\n\n"

        "Основные команды rebase:\n"
        "pick    — оставить коммит как есть\n"
        "reword  — изменить сообщение коммита (или r)\n"
        "squash  — объединить с предыдущим (или s)\n"
        "drop    — удалить коммит\n\n"

        "ВАЖНО:\n"
        "Если что-то пошло не так — выполни:\n"
        "git rebase --abort\n"
        "и история вернётся в исходное состояние.\n"
    )

    num = input("Введите номер строки коммита (1–10): ").strip()
    if not num.isdigit() or not (1 <= int(num) <= len(commits)):
        wait_for_enter()

    if int(num) == 1:
        print("\n✏️ Изменение сообщения HEAD-коммита\n")
        run_git("git commit --amend")
        wait_for_enter()
    else:
        print(
            "\n🔧 Будет выполнен интерактивный rebase:\n"
            "git rebase -i HEAD~10\n\n"
            "Найди нужный коммит и замени 'pick' на 'reword'\n"
        )
        run_git("git rebase -i HEAD~10")
        wait_for_enter()


# ===== MAIN =====

def main():
    print("\n🧠 Smart Git Helper — PROD\n")
    log("=== START ===")

    if not os.path.isdir(".git"):
        print("❌ Это не git-репозиторий (нет папки .git)")
        wait_for_enter()

    branch = detect_branch()
    commits = show_recent_commits()

    print("\nENTER — продолжить обычную работу")
    print("0     — профессиональный откат")
    print("9     — изменить комментарий коммита\n")

    action = input("Выбор: ").strip()

    if action == "0":
        rollback_menu(commits, branch)

    if action == "9":
        edit_commit_message(commits)

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
                """👉 GitHub говорит тебе:
            В твоей ветке на сервере есть коммиты, которых у тебя локально нет.
            Я не дам тебе просто так их перезаписать.

            То есть:
            удалённый репозиторий новее
            твоя локальная ветка отстаёт
            обычный git push запрещён (чтобы ты случайно не потерял чужие коммиты)

            С высокой вероятностью ты раньше делал одно из этих действий:
            git reset --hard
            git rebase
            локальная история ≠ история на GitHub
            Git видит разные цепочки коммитов
            ТИПО 👉 «Сначала подтяни изменения с сервера, потом пушь»

            ДВА правильных варианта (выбирай осознанно)
            ✅ Вариант 1. Сохранить коммиты на GitHub (безопасно)
            Если ты не хочешь удалять то, что уже есть на GitHub:
            git pull --rebase
            git push
            Что будет:
            - коммиты с GitHub подтянутся
            - твои изменения «переиграются» поверх них
            - история станет линейной
            👉 Рекомендуется, если ты не уверен.

            ⚠️ Вариант 2. Перезаписать GitHub своим состоянием
            Если ты точно знаешь, что:
            - репозиторий твой
            - коммиты на GitHub больше не нужны
            git push --force
            Что будет:
            - GitHub станет точной копией твоего локального состояния
            - коммиты, которых нет локально, исчезнут

            Как понять, что именно расходится
            git log --oneline --graph --decorate --all -5
            Ты увидишь:
            - где твоя main
            - где origin/main
            - кто «впереди», кто «позади»""",
                [
                    "git log --oneline --graph --decorate --all -5",
                    "git push --force",
                    "git pull --rebase\ngit push",
                    "git reset --hard\ngit rebase"
                ]
            )

        # Обработка выбора пользователя
        if c == 1:
            print("📜 Показываем последние коммиты (лог графа)...")
            run_git("git log --oneline --graph --decorate --all -5")
            wait_for_enter()
        elif c == 2:
            print("⚠️ Перезаписываем GitHub своим состоянием...")
            ok, _ = run_git("git push --force")
            if ok:
                print("✅ GitHub теперь точно копия локального репозитория.")
            else:
                print("❌ Ошибка при push --force!")
            wait_for_enter()
        elif c == 3:
            print("🔄 Подтягиваем изменения с GitHub и пушим...")
            ok, _ = run_git("git pull --rebase")
            if not ok:
                print("⚠️ Конфликт. Исправь вручную.")
            else:
                run_git("git push")
                print("✅ Изменения успешно синхронизированы с GitHub.")
            wait_for_enter()
        elif c == 4:
            print("💥 Применяем жёсткий сброс и rebase...")
            ok, _ = run_git("git reset --hard")
            if ok:
                run_git("git rebase")
                print("✅ Локальная история обновлена и выровнена.")
            else:
                print("❌ Ошибка при reset --hard!")
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
