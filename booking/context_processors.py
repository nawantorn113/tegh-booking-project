# booking/context_processors.py
# [ฉบับสมบูรณ์ - เพิ่มเมนู Reports]

from .views import is_admin, is_approver_or_admin

def menu_context(request):
    # ดึงค่า is_admin และ is_approver จาก user ปัจจุบัน
    user_is_admin = is_admin(request.user)
    user_is_approver = is_approver_or_admin(request.user)

    # รายการเมนูทั้งหมด
    menu_items = [
        {
            'label': 'Dashboard',
            'url_name': 'dashboard',
            'icon': 'bi-grid-fill',
            'show': True # แสดงสำหรับทุกคน
        },
        {
            'label': 'ตารางเวลารวม',
            'url_name': 'master_calendar',
            'icon': 'bi-calendar3',
            'show': True # แสดงสำหรับทุกคน
        },
        {
            'label': 'ประวัติการจอง',
            'url_name': 'history',
            'icon': 'bi-clock-history',
            'show': True # แสดงสำหรับทุกคน
        },
        {
            'label': 'จัดการการอนุมัติ',
            'url_name': 'approvals',
            'icon': 'bi-check2-square',
            'show': user_is_approver # แสดงสำหรับ Approver และ Admin
        },
        # --- [ใหม่] เพิ่มเมนู "รายงาน" ที่นี่ ---
        {
            'label': 'รายงาน',
            'url_name': 'reports',
            'icon': 'bi-file-earmark-bar-graph-fill',
            'show': user_is_admin # แสดงสำหรับ Admin เท่านั้น
        }
    ]

    # ตรวจสอบว่าหน้าปัจจุบันคือหน้าไหน เพื่อใส่ class 'active'
    current_url_name = request.resolver_match.url_name if request.resolver_match else ''
    for item in menu_items:
        item['active'] = (item['url_name'] == current_url_name)

    # ส่งค่า is_admin ไปให้ template ทุกหน้าใช้งาน
    return {
        'menu_items': menu_items,
        'is_admin': user_is_admin
    }