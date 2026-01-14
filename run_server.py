from waitress import serve
# เช็คชื่อโฟลเดอร์ให้ชัวร์นะครับ จาก settings.py ก่อนหน้า คุณใช้ชื่อ 'mysite'
from mysite.wsgi import application 

import socket

# หา IP เครื่องตัวเองอัตโนมัติ เพื่อโชว์ให้ดู
hostname = socket.gethostname()
ip_address = socket.gethostbyname(hostname)

print(f"========================================")
print(f" Server Started Successfully! (Waitress)")
print(f"----------------------------------------")
print(f" Access URL (Local):  http://127.0.0.1:8080")
print(f" Access URL (LAN):    http://{ip_address}:8080")
print(f"========================================")
print(f" Press Ctrl+C to stop the server.")

# รัน Server
serve(application, host='0.0.0.0', port=8080, threads=6)