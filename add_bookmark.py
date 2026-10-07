import json, os, time

target_url = "http://zhimian.ai:5000"
target_name = "智面AI"
bookmarks = []

# Chrome
chrome_path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Bookmarks")
# Edge
edge_path = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Bookmarks")

for name, path in [("Chrome", chrome_path), ("Edge", edge_path)]:
    if not os.path.exists(path):
        print(f"⚠️ {name} 未安装或 Bookmarks 文件不存在")
        continue
    try:
        # 备份
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        bak = path + f".bak_{int(time.time())}"
        with open(bak, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ {name} 书签已备份")

        # 找书签栏 roots.bookmark_bar.children
        bar = data["roots"]["bookmark_bar"]["children"]
        # 检查是否已存在
        exists = any(c.get("url") == target_url for c in bar if c.get("type") == "url")
        if exists:
            print(f"ℹ️ {name} 已有该书签")
        else:
            bar.append({
                "date_added": str(int(time.time() * 1000000) + 11644473600000000),
                "date_last_used": "0",
                "guid": f"zhimian-{int(time.time())}",
                "id": str(len(bar) + 100),
                "name": target_name,
                "type": "url",
                "url": target_url
            })
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✅ {name} 书签已添加: [{target_name}] → {target_url}")
        bookmarks.append(name)
    except Exception as e:
        print(f"❌ {name} 书签修改失败: {e}")

print(f"\n{'='*50}")
print(f"完成！现在关掉 Chrome/Edge 再打开，")
print(f"地址栏输入「智面」→ 自动补全 → 回车！")