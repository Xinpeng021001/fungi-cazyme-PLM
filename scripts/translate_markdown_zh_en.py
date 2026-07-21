#!/usr/bin/env python3
"""Translate Chinese Markdown to English while preserving Markdown structure."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
from pathlib import Path


ZH = re.compile(r"[\u3400-\u9fff]")
INLINE_CODE = re.compile(r"`[^`]*`")
PREFIX = re.compile(r"^(\s*(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+|[-*+]\s+\[[ xX]\]\s+))(.*)$")


def mask_inline_code(text: str) -> tuple[str, list[str]]:
    saved: list[str] = []

    def replace(match: re.Match[str]) -> str:
        token = f"ZXQCODE{len(saved)}QXZ"
        saved.append(match.group(0))
        return token

    return INLINE_CODE.sub(replace, text), saved


def restore_inline_code(text: str, saved: list[str]) -> str:
    for index, value in enumerate(saved):
        text = text.replace(f"ZXQCODE{index}QXZ", value)
        text = text.replace(f"ZXQ CODE {index} QXZ", value)
    return text


def google_translate(text: str) -> str:
    masked, saved = mask_inline_code(text)
    command = [
        "curl", "-L", "--get", "--silent", "--show-error", "--retry", "4",
        "--data-urlencode", "client=gtx", "--data-urlencode", "sl=zh-CN",
        "--data-urlencode", "tl=en", "--data-urlencode", "dt=t",
        "--data-urlencode", f"q={masked}",
        "https://translate.googleapis.com/translate_a/single",
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    translated = "".join(part[0] for part in payload[0] if part and part[0])
    return restore_inline_code(translated, saved)


def fragments_for_line(line: str, in_code: bool, code_language: str) -> list[str]:
    if not ZH.search(line):
        return []
    if in_code and code_language not in {"", "text", "markdown", "md"}:
        # Code is kept byte-for-byte to avoid corrupting executable examples.
        return []
    if line.lstrip().startswith("|") and line.rstrip().endswith("|"):
        return [cell.strip() for cell in line.split("|") if ZH.search(cell)]
    match = PREFIX.match(line)
    return [match.group(2) if match else line]


def translate_line(line: str, translations: dict[str, str], in_code: bool, code_language: str) -> str:
    if not ZH.search(line) or (in_code and code_language not in {"", "text", "markdown", "md"}):
        return line
    newline = "\n" if line.endswith("\n") else ""
    body = line[:-1] if newline else line
    if body.lstrip().startswith("|") and body.rstrip().endswith("|"):
        cells = body.split("|")
        for i, cell in enumerate(cells):
            stripped = cell.strip()
            if ZH.search(stripped):
                left = cell[: len(cell) - len(cell.lstrip())]
                right = cell[len(cell.rstrip()) :]
                cells[i] = left + translations[stripped] + right
        return "|".join(cells) + newline
    match = PREFIX.match(body)
    if match:
        return match.group(1) + translations[match.group(2)] + newline
    return translations[body] + newline


def translate_document(source: Path, destination: Path, workers: int) -> None:
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    fragments: list[str] = []
    states: list[tuple[bool, str]] = []
    in_code = False
    code_language = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_code:
                code_language = stripped[3:].strip().lower()
                states.append((False, ""))
                in_code = True
            else:
                states.append((False, ""))
                in_code = False
                code_language = ""
            continue
        states.append((in_code, code_language))
        fragments.extend(fragments_for_line(line, in_code, code_language))

    unique = list(dict.fromkeys(fragment for fragment in fragments if fragment.strip()))
    translations: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(google_translate, fragment): fragment for fragment in unique}
        for future in concurrent.futures.as_completed(future_map):
            fragment = future_map[future]
            translations[fragment] = future.result()

    output = [translate_line(line, translations, *state) for line, state in zip(lines, states)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(output), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()
    translate_document(args.source, args.destination, args.workers)


if __name__ == "__main__":
    main()
