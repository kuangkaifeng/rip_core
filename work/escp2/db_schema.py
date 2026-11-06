# -*- coding: utf-8 -*-
import sqlite3, sys, re
db = r"D:\work\usb协议\tmp\pdfs\escp2ref_translation.sqlite3"
con = sqlite3.connect(db)
cur = con.cursor()
tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table'")]
print("tables:", tables)
for t in tables:
    print("---", t, cur.execute('select count(*) from "%s"' % t).fetchone())
    cols = [r[1] for r in cur.execute('pragma table_info("%s")' % t)]
    print("    cols:", cols)
    for r in cur.execute('select * from "%s" limit 2' % t):
        print("    sample:", [str(x)[:120] for x in r])
