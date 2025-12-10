from waitress import serve
from mysite.wsgi import application  # แก้ mysite เป็นชื่อโฟลเดอร์โปรเจกต์คุณ
import socket

# หา IP ของเครื่องนี้อัตโนมัติ
hostname = socket.gethostname()
ip_address = socket.gethostbyname(hostname)

print(f"========================================")
print(f" Server Started on Production Mode")
print(f" Access URL: http://{ip_address}:8000")
print(f"========================================")

# รัน Server ที่ Port 8000
serve(application, host='0.0.0.0', port=8000)