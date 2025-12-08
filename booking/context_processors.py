from django.db.models import Q
from .views import is_admin, is_approver_or_admin
from .models import Booking

def menu_context(request):
    user = request.user
    
    # ถ้ายังไม่ได้ Login ให้ส่งค่าว่างกลับไป
    if not user.is_authenticated:
        return {}

    is_admin_user = is_admin(user)
    is_approver_user = is_approver_or_admin(user)
    
    # --- ส่วนการแจ้งเตือน (Notification Logic) ---
    pending_count = 0
    pending_notifications = [] 
    
    if is_approver_user:
        # สร้างเงื่อนไข (Query) ตามสิทธิ์
        # ถ้าเป็น Admin: เห็นของตัวเอง + ห้องส่วนกลาง (ที่ไม่มีคนคุม)
        # ถ้าเป็น Approver: เห็นเฉพาะห้องที่ตัวเองเป็นคนคุม (approver=user)
        if is_admin_user:
            query = Q(room__approver=user) | Q(room__approver__isnull=True)
        else:
            query = Q(room__approver=user)

        # ดึงข้อมูลครั้งเดียว (QuerySet)
        pending_qs = Booking.objects.filter(query, status='PENDING').select_related('room', 'user').order_by('-created_at')
        
        # นับจำนวนทั้งหมด
        pending_count = pending_qs.count()
        
        # ดึงมาแสดงผลแค่ 5 รายการล่าสุด (เพื่อไม่ให้ Navbar โหลดหนัก)
        pending_notifications = pending_qs[:5]

    # --- ส่วนเมนู (Menu Active Logic) ---
    current_path = request.path_info
    
    menu_items = [
        {'label': 'หน้าหลัก', 'icon': 'bi bi-house-door-fill', 'url_name': 'dashboard', 'show': True},
        {'label': 'ปฏิทินรวม', 'icon': 'bi bi-calendar3', 'url_name': 'master_calendar', 'show': True},
        {'label': 'ประวัติการจอง', 'icon': 'bi bi-clock-history', 'url_name': 'history', 'show': True},
        {'label': 'รออนุมัติ', 'icon': 'bi bi-calendar2-check-fill', 'url_name': 'approvals', 'show': is_approver_user},
        # เมนู Admin
        {'label': 'จัดการห้องประชุม', 'icon': 'bi bi-building-fill-gear', 'url_name': 'rooms', 'show': is_admin_user},
        {'label': 'จัดการอุปกรณ์', 'icon': 'bi bi-tools', 'url_name': 'equipments', 'show': is_admin_user},
        {'label': 'จัดการผู้ใช้งาน', 'icon': 'bi bi-people-fill', 'url_name': 'user_management', 'show': is_admin_user},
        {'label': 'รายงานและสถิติ', 'icon': 'bi bi-bar-chart-line-fill', 'url_name': 'reports', 'show': is_admin_user},
        {'label': 'Log การใช้งาน', 'icon': 'bi bi-file-earmark-text', 'url_name': 'audit_log', 'show': is_admin_user},
    ]

    # วนลูปเช็คว่าอยู่หน้าไหน เพื่อใส่ class active
    for item in menu_items:
        if item['show']:
            if item['url_name'] == 'dashboard':
                item['active'] = (current_path == '/') or (current_path == '/dashboard/') # ปรับตาม URL จริงของคุณ
            else:
                # เช็คว่า URL ปัจจุบัน ขึ้นต้นด้วย url_name ของเมนูนั้นไหม
                item['active'] = current_path.startswith(f"/{item['url_name']}".replace("//", "/"))

    # คืนค่าตัวแปรทั้งหมดไปที่ Template
    return {
        'menu_items': menu_items,
        'is_admin_user': is_admin_user,
        'pending_count': pending_count,             # ส่งตัวเลข
        'pending_notifications': pending_notifications, # ส่งรายการข้อมูล (List)
    }