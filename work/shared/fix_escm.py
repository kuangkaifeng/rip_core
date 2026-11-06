p = r"D:\work\RIP核心分析\src\core\encode\escp2_writer.cpp"
t = open(p, encoding="utf-8").read()
old = "    static const uint8_t mCmd[6] = {0x1B, 0x28, 0x6D, 0x01, 0x00, 0x40};"
new = "    static const uint8_t mCmd[6] = {0x1B, 0x28, 0x6D, 0x01, 0x00, 0x41};"
assert old in t
t = t.replace(old, new)
open(p, "w", encoding="utf-8", newline="").write(t)
print("ESC(m) fixed to 0x41")
