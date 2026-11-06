#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert the MainTop SDK HTML doc into readable text for analysis.

Strips <style>/<script>/<svg>, converts block tags to newlines, table cells to
' | ', keeps <pre>/<code> content verbatim and <h1>-<h6> as '#' headings.
Usage: python html2txt.py <input.html> <output.txt>
"""
import sys
import re
import html as htmllib


def _strip_tag(text: str, tag: str) -> str:
    return re.sub(rf"<{tag}\b.*?</{tag}>", "", text, flags=re.S | re.I)


def convert(src: str) -> str:
    t = src
    for tag in ("style", "script", "svg", "head"):
        t = _strip_tag(t, tag)
    # protect pre blocks
    blocks = []

    def _keep(m):
        inner = m.group(2)
        inner = re.sub(r"<[^>]+>", "", inner)
        inner = htmllib.unescape(inner)
        blocks.append(inner)
        return f"\n\n\uf000{len(blocks)-1}\uf000\n\n"

    t = re.sub(r"<pre\b(.*?)>(.*?)</pre>", lambda m: _keep(m), t, flags=re.S | re.I)
    # markdown-ish tables: <table> ... rows ... cells
    t = re.sub(r"<h([1-6])\b[^>]*>(.*?)</h\1>",
               lambda m: "\n\n" + "#" * int(m.group(1)) + " " + re.sub(r"<[^>]+>", "", m.group(2)).strip() + "\n",
               t, flags=re.S | re.I)
    t = re.sub(r"<(td|th)\b[^>]*>", " | ", t, flags=re.I)
    t = re.sub(r"</(tr|table|thead|tbody|div|p|li|ul|ol|dl|dt|dd|blockquote|section|article)>", "\n", t, flags=re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</?(tr|td|th|table|thead|tbody|colgroup|col|span|a|b|i|u|strong|em|code|li|div|p)\b[^>]*>", "", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = htmllib.unescape(t)
    # restore pre blocks
    t = re.sub(r"\uf000(\d+)\uf000", lambda m: "\n<<<PRE " + str(int(m.group(1))) + ">>>\n" + blocks[int(m.group(1))] + "\n<<<END PRE>>>\n", t)
    # collapse blank lines
    lines = [ln.rstrip() for ln in t.splitlines()]
    out = []
    blank = 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank <= 1:
                out.append("")
            continue
        blank = 0
        out.append(ln)
    return "\n".join(out)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    with open(sys.argv[1], "r", encoding="utf-8", errors="replace") as f:
        src = f.read()
    txt = convert(src)
    with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    print(f"wrote {sys.argv[2]}: {len(txt)} chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
