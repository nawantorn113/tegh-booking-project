import os
import django

# โหลด settings ของ Django (ของคุณชื่อ mysite)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.core import serializers
from django.apps import apps

print("Starting export...")

for model in apps.get_models():
    name = model.__name__.lower()
    qs = model.objects.all()
    if qs.exists():
        filename = f"{name}.json"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(serializers.serialize("json", qs, indent=4))
        print("exported:", filename)

print("All done!")
