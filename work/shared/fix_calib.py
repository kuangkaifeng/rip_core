p = r"D:\work\RIP核心分析\src\core\rip_engine.cpp"
t = open(p, encoding="utf-8").read()
t = t.replace("    QVector<uint8_t> calibGray;   // 4*256: C,M,Y,K 的 v_icc -> v_oracle",
              "    QByteArray calibGray;   // 4*256: C,M,Y,K 的 v_icc -> v_oracle")
t = t.replace("                        dst[ci] = static_cast<uint8_t>(calibGray[ci * 256 + dst[ci]]);",
              "                        dst[ci] = static_cast<uint8_t>(static_cast<unsigned char>(calibGray.at(ci * 256 + dst[ci])));")
open(p, "w", encoding="utf-8", newline="").write(t)
print("fixed")
