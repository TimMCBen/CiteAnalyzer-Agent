import os
import json
from collections import defaultdict

input_dir = "arxiv_papers"
output_path = "arxiv_papers_merged_幻觉.json"

merged = {
    "metadata": {
        "last_updated": None,
        "total_papers": 0,
        "matched_keywords_stats": defaultdict(int),
    },
    "papers": []
}

def merge_datetime(old, new):
    if new is None:
        return old
    if old is None:
        return new
    try:
        return max(old, new)
    except:
        return old

for fname in os.listdir(input_dir):
    if not fname.endswith(".json"):
        continue

    path = os.path.join(input_dir, fname)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"⚠️ 跳过无法解析文件: {fname}，错误：{e}")
        continue

    # 🚨 data 不是 dict → 跳过
    if not isinstance(data, dict):
        print(f"⚠️ 跳过文件（不是对象结构）: {fname}，实际类型: {type(data).__name__}")
        continue

    print(f"✅ 已合并文件: {fname}")

    meta = data.get("metadata", {})

    merged["metadata"]["last_updated"] = merge_datetime(
        merged["metadata"]["last_updated"],
        meta.get("last_updated")
    )

    merged["metadata"]["total_papers"] += meta.get("total_papers", 0)

    for k, v in meta.get("matched_keywords_stats", {}).items():
        merged["metadata"]["matched_keywords_stats"][k] += v

    merged["papers"].extend(data.get("papers", []))

merged["metadata"]["matched_keywords_stats"] = dict(merged["metadata"]["matched_keywords_stats"])

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(merged, f, indent=2, ensure_ascii=False)

print("\n🎉 合并完成")
print(f"📄 共合并论文数: {len(merged['papers'])}")
print(f"📁 输出文件: {output_path}")
