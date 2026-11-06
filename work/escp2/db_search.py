# -*- coding: utf-8 -*-
import sqlite3, sys, re, io
db = r"D:\work\usb协议\tmp\pdfs\escp2ref_translation.sqlite3"
con = sqlite3.connect(db)
con.text_factory = bytes
cur = con.cursor()

def dec(b):
    for enc in ('utf-8', 'gbk', 'gb18030', 'latin1'):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode('latin1', 'replace')

pages = {}
for t in ('pages',):
    for pno, sha, tr in cur.execute('select page_no, source_sha, translation from "%s"' % t):
        pages[int(pno)] = dec(tr)

kw = sys.argv[1:] or ['ESC ( c', 'ESC ( D', 'ESC ( $', 'ESC ( v', 'ESC i', 'color']
for k in kw:
    print("=" * 100)
    print("KEYWORD:", k)
    for pno in sorted(pages):
        tx = pages[pno]
        if k.lower() in tx.lower():
            print("--- page", pno, "hit count", tx.lower().count(k.lower()))
            # print surrounding lines
            lines = tx.splitlines()
            for i, ln in enumerate(lines):
                if k.lower() in ln.lower():
                    lo = max(0, i - 1); hi = min(len(lines), i + 12)
                    print("\n".join("    " + x for x in lines[lo:hi]))
                    print("    ....")
                    break
