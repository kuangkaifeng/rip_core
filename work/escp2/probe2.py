import sys, struct, collections, json

def hexdump(b, off=0, n=400):
    out=[]
    for i in range(0, min(n, len(b)), 16):
        chunk = b[off+i:off+i+16]
        hx = ' '.join('%02x'%c for c in chunk)
        asc = ''.join(chr(c) if 32<=c<127 else '.' for c in chunk)
        out.append('%08x  %-47s  %s' % (off+i, hx, asc))
    return '\n'.join(out)

def scan(path, maxrec=2000, dumpfirst=0, head=0x200):
    d = open(path,'rb').read()
    print("="*100)
    print("FILE", path, "size", len(d))
    print(hexdump(d,0,head))
    i = 0
    cmds = []
    n = len(d)
    while i < n:
        off = i
        c = d[i]
        if c == 0x1b:
            c2 = d[i+1] if i+1<n else -1
            if c2 == 0x28 and i+3 < n:
                letter = d[i+2]
                ln = d[i+3] | (d[i+4]<<8)
                data = d[i+5:i+5+ln]
                cmds.append(('esc(', letter, off, ln, data))
                i = i+5+ln
                # special: ESC ( $ followed by ESC i record; the ESC i data length unknown -> we handle below
                if letter == 0x24:
                    # next should be ESC i
                    if d[i] == 0x1b and d[i+1] == 0x69:
                        pass
                continue
            elif c2 == 0x69:
                color, comp, bit = d[i+2], d[i+3], d[i+4]
                nl = d[i+5] | (d[i+6]<<8); m = d[i+7] | (d[i+8]<<8)
                cmds.append(('esci', color, off, 9, bytes([color,comp,bit]), nl, m))
                # cannot skip data without RLE decode -> decode here
                i = i+9
                target = nl*m
                out = 0
                while out < target and i < n:
                    cc = d[i]; i += 1
                    if cc <= 127:
                        i += cc+1
                        out += cc+1
                    else:
                        i += 1
                        out += 257-cc
                # expect 0x0d
                if i < n and d[i] == 0x0d:
                    cmds[-1] = cmds[-1] + ('term0d',)
                    i += 1
                else:
                    cmds[-1] = cmds[-1] + ('NOTERM:%02x'%d[i],)
                continue
            elif c2 == 0x55:
                cmds.append(('escU', d[i+2], off, 3, None)); i += 3; continue
            elif c2 == 0x40:
                cmds.append(('esc@', None, off, 2, None)); i += 2; continue
            elif c2 == 0x00:
                cmds.append(('esc_exit_remote', None, off, 4, None)); i += 4; continue
            elif c2 == 0x0c:
                cmds.append(('escFF?', None, off, 2, None)); i += 2; continue
            else:
                cmds.append(('ESC?', c2, off, 2, None)); i += 2; continue
        elif c == 0x0c:
            cmds.append(('FF', None, off, 1, None)); i += 1; continue
        elif c == 0x0d:
            cmds.append(('CR', None, off, 1, None)); i += 1; continue
        else:
            cmds.append(('BYTE', c, off, 1, None)); i += 1; continue
    print("total cmds:", len(cmds))
    cnt = collections.Counter((c[0], c[1] if not isinstance(c[1], bytes) else None) for c in cmds)
    print("cmd counts:", cnt.most_common(30))
    # first 60 commands
    print("--- first 90 commands ---")
    for c in cmds[:90]:
        s = str(c[:5])
        print('  %08x %s' % (c[2], s))
    # ESC ( v values in order
    vs = [struct.unpack('<I', c[4][0:4])[0] for c in cmds if c[0]=='esc(' and c[1]==0x76]
    ds = [struct.unpack('<I', c[4][0:4])[0] for c in cmds if c[0]=='esc(' and c[1]==0x24]
    es = [c for c in cmds if c[0]=='esc(' and c[1]==0x65]
    print("ESC(v) count", len(vs), "values:", vs[:60], "..." if len(vs)>60 else "")
    print("ESC(v) all distinct:", collections.Counter(vs).most_common())
    print("ESC($) count", len(ds), "distinct:", collections.Counter(ds).most_common())
    # record sequence: group by advancing
    recs = [c for c in cmds if c[0]=='esci']
    print("records:", len(recs))
    print("colors order:", collections.Counter(r[1] for r in recs))
    print("n values:", collections.Counter(r[5] for r in recs))
    print("m values:", collections.Counter(r[6] for r in recs))
    print("bit/comp:", collections.Counter((r[4][1], r[4][2]) for r in recs))
    # terminal stats
    term = collections.Counter(r[-1] for r in recs)
    print("record terminators:", term)
    # non esc commands after prologue
    other = [(c[0],c[1],c[2]) for c in cmds if c[0] not in ('esc(','esci','CR')]
    print("other cmds:", collections.Counter((o[0], o[1] if not isinstance(o[1], bytes) else None) for o in other).most_common(20))
    return cmds, d

if __name__ == '__main__':
    for p in sys.argv[1:]:
        scan(p)
