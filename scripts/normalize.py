#!/usr/bin/env python3
"""
raw/*.html -> corpus/*.md с YAML-метаданными.

Каждый файл получает шапку, которую потом цитирует RAG:
doc_id, название, URL, дата редакции (по сноскам), хэш, дата выгрузки.
"""
import json
import pathlib
import re

from selectolax.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
CORPUS = ROOT / "corpus"
MANIFEST = ROOT / "manifest.json"

# "Закон Республики Казахстан от 15 апреля 2013 года № 88-V"
RE_ACT = re.compile(
    r"(Закон|Кодекс|Указ|Постановление|Приказ)[^\n]{0,200}?"
    r"от\s+\d{1,2}\s+\w+\s+\d{4}\s+года[^\n]{0,60}"
)
# последняя дата в сносках "Сноска. ... от 25.06.2020 № 347-VI"
RE_AMEND = re.compile(r"от\s+(\d{2}\.\d{2}\.\d{4})\s+№")


def to_markdown(html: str) -> str:
    tree = HTMLParser(html)
    for tag in tree.css("script, style, nav, header, footer, .noprint"):
        tag.decompose()

    out = []
    for node in tree.css("h1, h2, h3, h4, p, li, td"):
        text = " ".join(node.text(strip=True).split())
        if not text:
            continue
        tag = node.tag
        if tag in ("h1", "h2", "h3", "h4"):
            out.append(f"\n{'#' * int(tag[1])} {text}\n")
        elif tag == "li":
            out.append(f"- {text}")
        else:
            out.append(text)
    return "\n\n".join(out)


def main() -> int:
    CORPUS.mkdir(exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    for path in sorted(RAW.glob("*.html")):
        doc_id = path.stem
        html = path.read_text(encoding="utf-8")
        body = to_markdown(html)

        m = RE_ACT.search(body)
        title = m.group(0).strip() if m else doc_id
        amendments = RE_AMEND.findall(body)
        last_amended = max(
            amendments, key=lambda d: (d[6:], d[3:5], d[:2]), default=""
        )
        meta = manifest["documents"].get(doc_id, {})

        header = (
            "---\n"
            f'doc_id: "{doc_id}"\n'
            f'title: "{title.replace(chr(34), chr(39))}"\n'
            f'source_url: "{meta.get("url", "")}"\n'
            f'last_amended: "{last_amended}"\n'
            f'sha256: "{meta.get("sha256", "")}"\n'
            f'fetched_at: "{meta.get("fetched_at", "")}"\n'
            'jurisdiction: "KZ"\n'
            "---\n\n"
        )
        (CORPUS / f"{doc_id}.md").write_text(header + body, encoding="utf-8")
        print(f"{doc_id}: {len(body):>8} симв., ред. {last_amended or '—'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
