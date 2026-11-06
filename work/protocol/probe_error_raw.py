import urllib.request, json, binascii
url="http://127.0.0.1:8089/mtrip/v1/jobs"
obj={"command":"rip","doc":{"name":"D:/nonexistent_zzz.png"},"prs":"./A3-DTF-1390.prs","modeId":0,
     "output":{"mode":"file","file":{"name":"D:/work/x.prn"}}}
body=json.dumps(obj).encode()
req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json;charset=utf-8"},method="POST")
raw=urllib.request.urlopen(req,timeout=30).read()
print("RAW BYTES:", binascii.hexlify(raw).decode())
print("UTF8 :", raw.decode("utf-8","replace"))
print("GBK  :", raw.decode("gbk","replace"))