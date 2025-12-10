import json
import os
from ftfy import fix_text

# loop ทุกไฟล์ในโฟลเดอร์
for filename in os.listdir("."):
    if filename.endswith(".json") and "fixed" not in filename:
        print(f"Processing {filename} ...")

        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Error reading {filename}: {e}")
            continue

        # แก้ไขข้อความทุกฟิลด์
        for item in data:
            if "fields" in item:
                for key, val in item["fields"].items():
                    if isinstance(val, str):
                        item["fields"][key] = fix_text(val)

        # สร้างไฟล์ใหม่ เช่น booking_fixed.json
        output_name = filename.replace(".json", "_fixed.json")
        with open(output_name, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ DONE → {output_name}")

print("\n🎉 All JSON files processed!")
