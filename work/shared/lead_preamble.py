# -*- coding: utf-8 -*-
"""Lead: ESC/P2 preamble (job header + command region) dumper.
用法: python lead_preamble.py <prn>
"""
import sys, struct

def main(path):
    buf = open(path, 'rb').read()
    print("file=%s size=%d" % (path, len(buf)))
    i = 0
    # 1) 找到 ENTER D4 / EJL 头
    print("head:", buf[:24])
    # 2) 打印 remote 模式字段
    p = buf.find(b'@EJL')
    print("EJL at", p, "ctx:", buf[p:p+40])
    # 3) 打印前 512 字节的可读 hexdump + 结构
    end = min(len(buf), 700)
    print("---- hexdump first %d bytes ----" % end)
    for off in range(0, end, 16):
        chunk = buf[off:off+16]
        hx = ' '.join('%02X' % b for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print("%08X  %-47s  %s" % (off, hx, asc))

    # 4) 解析 remote 记录: 在 1B 00 00 00 之前的部分
    print("---- remote records ----")
    q = buf.find(b'\x1b\x00\x00\x00')
    print("first 1B 00 00 00 at", q)
    if q < 0:
        return
    # 从第一个 @EJL 行后面开始找 2 字节命令
    start = buf.find(b'REMOTE1')
    if start < 0:
        return
    pos = start + 7
    while pos + 4 <= q:
        cmd = buf[pos:pos+2]
        ln = buf[pos+2] | (buf[pos+3] << 8)
        data = buf[pos+4:pos+4+ln]
        print("  %s len=%d data=%s hex=%s" % (cmd.decode('latin1'), ln, data, data.hex()))
        pos += 4 + ln
        if pos > q:
            break

    # 5) 解析命令区（从 1B 00 00 00 之后到第一个 ESC ( $ 之前）
    print("---- command region ----")
    pos = q + 4
    stop = buf.find(b'\x1b\x28\x24', pos)
    print("first ESC ( $ at", stop)
    while pos < stop and pos + 2 <= len(buf):
        if buf[pos] != 0x1B:
            print("  unexpected byte %02X at %#x" % (buf[pos], pos))
            pos += 1
            continue
        b1 = buf[pos+1]
        if b1 == 0x28:  # ESC ( cmd len
            cmd = buf[pos+2]
            ln = buf[pos+3] | (buf[pos+4] << 8)
            data = buf[pos+5:pos+5+ln]
            val = None
            if ln == 3:
                val = struct.unpack('<H', data[:2])[0] if False else data
            elif ln == 4:
                val = 'LE32=%d' % struct.unpack('<I', data[:4])[0]
            elif ln == 8:
                val = 'LE32=%d,LE32=%d' % struct.unpack('<II', data[:8])
            elif ln == 5:
                val = data.hex()
            print("  %#06x ESC ( %s len=%d data=%s %s" % (pos, chr(cmd), ln, data.hex(), val or ''))
            pos += 5 + ln
        elif b1 == 0x40:
            print("  %#06x ESC @" % pos)
            pos += 2
        elif b1 == 0x55:
            print("  %#06x ESC U %02X" % (pos, buf[pos+2]))
            pos += 3
        else:
            print("  %#06x ESC %02X" % (pos, b1))
            pos += 2

    # 6) 第一块的记录头
    print("---- first block ----")
    pos = stop
    block = 1
    while pos < len(buf):
        if buf[pos:pos+3] == b'\x1b\x28\x24':
            ln = buf[pos+3] | (buf[pos+4] << 8)
            data = buf[pos+5:pos+5+ln]
            print("  ESC ( $ len=%d param=%d" % (ln, struct.unpack('<I', data[:4])[0] if ln >= 4 else -1))
            pos += 5 + ln
        elif buf[pos:pos+3] == b'\x1b\x28\x76':
            ln = buf[pos+3] | (buf[pos+4] << 8)
            data = buf[pos+5:pos+5+ln]
            print("  ESC ( v len=%d param=%d  (block %d)" % (ln, struct.unpack('<I', data[:4])[0] if ln >= 4 else -1, block))
            pos += 5 + ln
            block += 1
        elif buf[pos:pos+2] == b'\x1b\x69':
            color = buf[pos+2]; comp = buf[pos+3]; depth = buf[pos+4]
            nl, nh, ml, mh = buf[pos+5], buf[pos+6], buf[pos+7], buf[pos+8]
            n = nl | (nh << 8); m = ml | (mh << 8)
            print("  ESC i color=%#04x comp=%d depth=%d n=%d m=%d" % (color, comp, depth, n, m))
            # 跳过 RLE
            j = pos + 9
            dec = 0
            need = n * m
            while j < len(buf) and dec < need:
                c = buf[j]
                if c <= 127:
                    dec += c + 1; j += 1 + c + 1
                else:
                    dec += 257 - c; j += 2
            pos = j
        else:
            pos += 1
        if block > 3:
            break

if __name__ == '__main__':
    main(sys.argv[1])
