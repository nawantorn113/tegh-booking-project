# from django.core.management.base import BaseCommand
# from django.contrib.auth.models import User
# from django.conf import settings
# # ต้องติดตั้ง ldap3 ก่อน (pip install ldap3)
# try:
#     from ldap3 import Server, Connection, ALL, NTLM
# except ImportError:
#     Server = None
#     Connection = None
#     ALL = None
#     NTLM = None

# class Command(BaseCommand):
#     help = 'Sync user status from Active Directory'

#     def handle(self, *args, **kwargs):
#         self.stdout.write("🔄 Starting AD Sync...")

#         # ⚠️ ถ้ายังไม่ได้ลง ldap3 ให้แจ้งเตือนและจบการทำงาน
#         if not Server:
#             self.stdout.write(self.style.ERROR("❌ Error: Library 'ldap3' not found. Please run 'pip install ldap3'"))
#             return

#         # 1. ตั้งค่าการเชื่อมต่อ AD (ต้องขอข้อมูลจาก IT)
#         # ตัวอย่าง: แก้ไขข้อมูลด้านล่างให้ตรงกับของบริษัท
#         AD_SERVER = 'ldap://192.168.1.x' 
#         AD_USER = 'TEGH\\Administrator'
#         AD_PASSWORD = 'password'        
#         SEARCH_BASE = 'dc=tegh,dc=com'  

#         try:
#             # 2. เชื่อมต่อ AD
#             server = Server(AD_SERVER, get_info=ALL)
#             conn = Connection(server, user=AD_USER, password=AD_PASSWORD, authentication=NTLM, auto_bind=True)
            
#             # 3. ดึง User ทั้งหมดใน Django (ยกเว้น Admin/Superuser)
#             django_users = User.objects.filter(is_superuser=False, is_active=True)

#             for user in django_users:
#                 # ค้นหา User นี้ใน AD ด้วย Username
#                 search_filter = f'(&(objectClass=user)(sAMAccountName={user.username}))'
#                 conn.search(SEARCH_BASE, search_filter, attributes=['userAccountControl'])

#                 if len(conn.entries) == 0:
#                     # A. ถ้าหาไม่เจอใน AD เลย (ลบไปแล้ว) -> ปิด User ใน Django
#                     user.is_active = False
#                     user.save()
#                     self.stdout.write(self.style.WARNING(f"❌ Disabled (Not found in AD): {user.username}"))
                
#                 else:
#                     # B. ถ้าเจอ แต่สถานะใน AD เป็น Disabled
#                     uac = conn.entries[0].userAccountControl.value
#                     if uac and (uac & 2): 
#                         user.is_active = False
#                         user.save()
#                         self.stdout.write(self.style.WARNING(f"⛔ Disabled (AD Flag): {user.username}"))

#             self.stdout.write(self.style.SUCCESS("✨ Sync Complete!"))

#         except Exception as e:
#             self.stdout.write(self.style.ERROR(f"Error connecting to AD: {e}"))