#!/usr/bin/env python3
"""
Проверка ID из seed/docids.txt без полной выгрузки.

Для каждого ID запрашивает страницу и достаёт заголовок <title>.
Печатает таблицу: ID -> реальное название документа на сайте.
Если название не совпало с комментарием в списке — ID неверный,
правьте строку в seed/docids.txt.

Запуск: python scripts/check_ids.py
"""
import pathlib
import time

import httpx
from selectolax.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEED = ROOT / "seed" / "docids.txt"

URL_TMPL = "https://adilet.zan.kz/rus/docs/{doc_id}"
DELAY = 2.0
HEADERS = {
    "User-Agent": "lsc-corpus-bot/1.0 (+mailto:legal@thesequence.tech)",
    "Accept-Language": "ru,kk;q=0.8",
}


def parse_seed():
    rows = []
    for line in SEED.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        doc_id, _, comment = line.partition("#")
        rows.append((doc_id.strip(), comment.strip()))
    return rows


def main() -> int:
    rows = parse_seed()
    bad = []

    print(f"Проверяю {len(rows)} ID\n")
    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        for doc_id, comment in rows:
            try:
                r = client.get(URL_TMPL.format(doc_id=doc_id))
                status = r.status_code
                title = ""
                if status == 200:
                    node = HTMLParser(r.text).css_first("title")
                    title = " ".join(node.text().split()) if node else ""
                    # страница-заглушка «не найдено» тоже отдаёт 200
                    if not title or "не найден" in title.lower():
                        status = 404
            except Exception as exc:                       # noqa: BLE001
                status, title = 0, str(exc)[:60]

            mark = "OK  " if status == 200 else "БИТЫЙ"
            if status != 200:
                bad.append((doc_id, comment))
            print(f"{mark} {doc_id:<14} {title[:70]}")
            print(f"     ожидалось: {comment}\n")
            time.sleep(DELAY)

    if bad:
        print(f"\nНЕ ОТКРЫЛИСЬ ({len(bad)}) — найдите документ на adilet "
              f"и замените ID на хвост из адресной строки:")
        for doc_id, comment in bad:
            print(f"  {doc_id}  <- {comment}")
        return 1

    print("\nВсе ID рабочие. Можно запускать fetch.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
