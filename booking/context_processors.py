# booking/context_processors.py
# [ฉบับแก้ไขสมบูรณ์ - ควบคุม Sidebar ตามสิทธิ์]

from django.urls import reverse, NoReverseMatch
# ดึงฟังก์ชันตรวจสอบสิทธิ์มาจาก views.py
try:
    from .views import is_admin, is_approver_or_admin
except ImportError:
    # Fallback เผื่อกรณี import วน
    def is_admin(user): return False
    def is_approver_or_admin(user): return False


def menu_context(request):
    """
    สร้างเมนู Sidebar แบบไดนามิกตามสิทธิ์ของผู้ใช้
    จะถูกเรียกใช้ในทุกหน้า
    """
    
    # ถ้ายังไม่ login ไม่ต้องแสดงเมนู
    if not request.user.is_authenticated:
        return {'menu_items': []}

    # ตรวจสอบสิทธิ์
    is_admin_user = is_admin(request.user)
    is_approver_user = is_approver_or_admin(request.user)
    current_path = request.path_info

    # --- นี่คือเมนูทั้งหมดที่มีในระบบ ---
    all_menu_items = [
        {
            'label': 'หน้าหลัก',
            'url_name': 'dashboard',
            'icon': 'bi bi-house-door-fill',
            # Requirement: ผู้ใช้ทั่วไป และ Admin เห็น
            'show': True 
        },
        {
            'label': 'ประวัติการจอง',
            'url_name': 'history',
            'icon': 'bi bi-clock-history',
            # Requirement: ผู้ใช้ทั่วไป และ Admin เห็น
            'show': True 
        },
        {
            'label': 'รออนุมัติ',
            'url_name': 'approvals',
            'icon': 'bi bi-calendar2-check-fill',
            # Requirement: เฉพาะ Approver และ Admin
            'show': is_approver_user 
        },
        {
            'label': 'แดชบอร์ดผู้ดูแล',
            'url_name': 'admin_dashboard',
            'icon': 'bi bi-speedometer2',
            # Requirement: เฉพาะ Admin
            'show': is_admin_user 
        },
        {
            'label': 'จัดการห้องประชุม',
            'url_name': 'rooms',
            'icon': 'bi bi-building-fill-gear',
            # Requirement: เฉพาะ Admin
            'show': is_admin_user 
        },
        {
            'label': 'จัดการผู้ใช้งาน',
            'url_name': 'user_management',
            'icon': 'bi bi-people-fill',
            # Requirement: เฉพาะ Admin
            'show': is_admin_user 
        },
        {
            'label': 'รายงานและสถิติ',
            'url_name': 'reports',
            'icon': 'bi bi-bar-chart-line-fill',
            # Requirement: เฉพาะ Admin
            'show': is_admin_user 
        },
    ]

    # --- ประมวลผลเมนู ---
    processed_items = []
    active_item_found = False
    
    for item in all_menu_items:
        try:
            item_url = reverse(item['url_name'])
        except NoReverseMatch:
            continue # ข้ามเมนูนี้ไปเลยถ้าหา URL ไม่เจอ

        # ตรวจสอบว่าเมนูนี้คือหน้าที่กำลังเปิดอยู่หรือไม่
        if not active_item_found and current_path.startswith(item_url) and item_url != '/':
            item['active'] = True
            active_item_found = True
        else:
            item['active'] = False
            
        processed_items.append(item)

    # กรณีพิเศษ: ถ้าวนลูปแล้วยังไม่เจอ (เช่น อยู่หน้า Dashboard '/')
    if not active_item_found and current_path == reverse('dashboard'):
        for item in processed_items:
            if item['url_name'] == 'dashboard':
                item['active'] = True
                break

    return {'menu_items': processed_items}