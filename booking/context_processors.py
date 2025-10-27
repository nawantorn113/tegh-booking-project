# booking/context_processors.py
from .views import is_admin, is_approver_or_admin
from .models import Booking # 1. 🟢 เพิ่ม Import Booking 🟢

def menu_context(request):
    user = request.user
    if not user.is_authenticated:
        return {}

    is_admin_user = is_admin(user)
    is_approver_user = is_approver_or_admin(user)
    
    # --- 2. 🟢 START: แก้ไข Logic การนับ 🟢 ---
    pending_count = 0
    pending_notifications = [] # (สร้าง List ว่างไว้ก่อน)
    
    if is_approver_user: # (นับ/ดึงข้อมูล เฉพาะเมื่อ User เป็น Admin/Approver)
        # ดึงรายการที่รออนุมัติ โดยเรียงตาม ID ล่าสุด
        pending_bookings_query = Booking.objects.filter(status='PENDING').select_related('room').order_by('-created_at')
        
        pending_count = pending_bookings_query.count()
        # (ดึงมาแค่ 5 รายการล่าสุดสำหรับแสดงใน Dropdown)
        pending_notifications = pending_bookings_query[:5] 
    # --- 🟢 END: แก้ไข Logic การนับ 🟢 ---
    
    current_path = request.path_info
    
    menu_items = [
        {'label': 'หน้าหลัก', 'icon': 'bi bi-house-door-fill', 'url_name': 'dashboard', 'show': True},
        {'label': 'ประวัติการจอง', 'icon': 'bi bi-clock-history', 'url_name': 'history', 'show': True},
        {'label': 'รออนุมัติ', 'icon': 'bi bi-calendar2-check-fill', 'url_name': 'approvals', 'show': is_approver_user},
        {'label': 'จัดการห้องประชุม', 'icon': 'bi bi-building-fill-gear', 'url_name': 'rooms', 'show': is_admin_user},
        {'label': 'จัดการผู้ใช้งาน', 'icon': 'bi bi-people-fill', 'url_name': 'user_management', 'show': is_admin_user},
        {'label': 'รายงานและสถิติ', 'icon': 'bi bi-bar-chart-line-fill', 'url_name': 'reports', 'show': is_admin_user},
    ]

    for item in menu_items:
        item['active'] = current_path.startswith(f"/{item['url_name']}".replace("//", "/")) if item['url_name'] != 'dashboard' else (current_path == '/')
    
    if current_path != '/':
        dashboard_item = next((item for item in menu_items if item['url_name'] == 'dashboard'), None)
        if dashboard_item:
            dashboard_item['active'] = False

    return {
        'menu_items': menu_items,
        'is_admin_user': is_admin_user,
        'pending_count': pending_count, # <-- 3. 🟢 ส่งค่า Count
        'pending_notifications': pending_notifications, # <-- 4. 🟢 ส่งค่า List (5 รายการ)
    }