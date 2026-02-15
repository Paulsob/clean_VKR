import os
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGET_FILE = PROJECT_ROOT / "code_report_full.txt"


EMOJI_REGEX = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE
)


def remove_emoji_from_print(line: str) -> str:
    if "print(" not in line:
        return line

    return EMOJI_REGEX.sub("", line)


def clean_file(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    cleaned_lines = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.lstrip()

            if stripped.startswith("#"):
                continue

            line = remove_emoji_from_print(line)
            cleaned_lines.append(line)

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(cleaned_lines)


def main():
    print(f"Обработка файла: {TARGET_FILE}")
    clean_file(TARGET_FILE)
    print("Готово. Комментарии и эмодзи в print удалены.")


if __name__ == "__main__":
    main()
