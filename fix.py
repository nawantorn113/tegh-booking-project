import json
from ftfy import fix_text

with open("room.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for item in data:
    for key, val in item["fields"].items():
        if isinstance(val, str):
            item["fields"][key] = fix_text(val)

with open("room_fixed.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("DONE: room_fixed.json")
