import json
import sqlite3

conn = sqlite3.connect("db.sqlite3")
cur = conn.cursor()
rows = cur.execute("SELECT * FROM django_content_type").fetchall()

data = []
for id, app_label, model in rows:
    data.append({
        "model": "contenttypes.contenttype",
        "pk": id,
        "fields": {
            "app_label": app_label,
            "model": model
        }
    })

with open("contenttype_fixed.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("DONE: contenttype_fixed.json")
