#!/usr/bin/env python3
"""
Инкрементальная выгрузка НПА РК с adilet.zan.kz.

Принципы:
  * НЕ краулим /rus/search/ — этот раздел закрыт в robots.txt.
  * Работаем только по явному списку doc_id (seed/docids.txt) —
    список составляется вручную/полуавтоматически из поиска на сайте.
  * Новые документы приходят через RSS (scripts/watch_rss.py).
  * 1 запрос в 2 секунды, один поток, честный User-Agent.
"""
import hashlib
import json
import pathlib
import sys
import time

import httpx
from selectolax.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
MANIFEST = ROOT / "manifest.json"
SEED = ROOT / "seed" / "docids.txt"

BASE = "https://adilet.zan.kz"
# /compare отдаёт русский и казахский тексты в одном документе
URL_TMPL = BASE + "/rus/docs/{doc_id}/compare"

DELAY = 2.0
HEADERS = {
    # Укажите реальный контакт — это норма хорошего тона и снижает риск бана
    "User-Agent": "lsc-corpus-bot/1.0 (+mailto:legal@thesequence.tech)",
    "Accept-Language": "ru,kk;q=0.8",
}


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"documents": {}}


def text_hash(html: str) -> str:
    """Хэш по тексту, а не по HTML: баннеры и счётчики не должны
    порождать ложные изменения редакции."""
    tree = HTMLParser(html)
    for tag in tree.css("script, style, nav, header, footer"):
        tag.decompose()
    body = tree.body.text(separator=" ", strip=True) if tree.body else ""
    normalized = " ".join(body.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def main() -> int:
    if not SEED.exists():
        print(f"нет файла {SEED}", file=sys.stderr)
        return 1

    doc_ids = [
        line.split("#")[0].strip()
        for line in SEED.read_text(encoding="utf-8").splitlines()
    ]
    doc_ids = [d for d in doc_ids if d]

    RAW.mkdir(exist_ok=True)
    manifest = load_manifest()
    changed, unchanged, failed = [], 0, []

    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        for i, doc_id in enumerate(doc_ids, 1):
            url = URL_TMPL.format(doc_id=doc_id)
            try:
                r = client.get(url)
                r.raise_for_status()
            except Exception as exc:                      # noqa: BLE001
                failed.append((doc_id, str(exc)))
                print(f"[{i}/{len(doc_ids)}] FAIL {doc_id}: {exc}")
                time.sleep(DELAY)
                continue

            digest = text_hash(r.text)
            prev = manifest["documents"].get(doc_id, {})

            if prev.get("sha256") == digest:
                unchanged += 1
                print(f"[{i}/{len(doc_ids)}] = {doc_id}")
            else:
                (RAW / f"{doc_id}.html").write_text(r.text, encoding="utf-8")
                manifest["documents"][doc_id] = {
                    "url": url,
                    "sha256": digest,
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    # история версий — критично для citation-anchored ответов
                    "revisions": prev.get("revisions", [])
                    + [{"sha256": digest, "seen": time.strftime("%Y-%m-%d")}],
                }
                changed.append(doc_id)
                print(f"[{i}/{len(doc_ids)}] ~ {doc_id} ИЗМЕНЁН")

            time.sleep(DELAY)

    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"\nизменено: {len(changed)}, без изменений: {unchanged}, ошибок: {len(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
