from django.db.models import Q
from django.utils import timezone 
from .views import is_admin, is_approver_or_admin
from .models import Booking

def menu_context(request):
    user = request.user
    
    if not user.is_authenticated:
        return {}

    is_admin_user = is_admin(user)
    is_approver_user = is_approver_or_admin(user)
    
    # --- ส่วนการแจ้งเตือน ---
    pending_count = 0
    pending_notifications = [] 
    
    # เงื่อนไข: ถ้าเป็น Admin หรือ ผู้อนุมัติ
    if user.is_superuser or is_approver_user:
        
        # 1. เลือก Query (ใครเห็นอะไรบ้าง)
        if user.is_superuser:
            base_qs = Booking.objects.all() # Superuser เห็นหมด
        elif is_admin_user:
            query = Q(room__approver=user) | Q(room__approver__isnull=True)
            base_qs = Booking.objects.filter(query)
        else:
            base_qs = Booking.objects.filter(room__approver=user)

        # 2. นับเลข Badge สีแดง (นับเฉพาะงานค้าง "รออนุมัติ")
        pending_count = base_qs.filter(
            status='PENDING',
            start_time__gte=timezone.now()
        ).count()
        
        # 3. รายการในกล่องแจ้งเตือน (Timeline)
        # [จุดที่แก้ไข] ดึงมาทุกสถานะ (ไม่กรอง PENDING แล้ว) เรียงตามเวลาแก้ไขล่าสุด
        # รายการ "ยกเลิก" จะโผล่มาตรงนี้ครับ
        pending_notifications = base_qs.select_related('room', 'user').order_by('-updated_at')[:7]

    # --- ส่วนเมนู (ไม่ต้องแก้ ใช้ของเดิมได้เลย) ---
    current_path = request.path_info
    menu_items = [
        {'label': 'หน้าหลัก', 'icon': 'bi bi-house-door-fill', 'url_name': 'dashboard', 'show': True},
        {'label': 'ปฏิทินรวม', 'icon': 'bi bi-calendar3', 'url_name': 'master_calendar', 'show': True},
        {'label': 'ประวัติการจอง', 'icon': 'bi bi-clock-history', 'url_name': 'history', 'show': True},
        {'label': 'รออนุมัติ', 'icon': 'bi bi-calendar2-check-fill', 'url_name': 'approvals', 'show': is_approver_user},
        {'label': 'จัดการห้องประชุม', 'icon': 'bi bi-building-fill-gear', 'url_name': 'rooms', 'show': is_admin_user},
        {'label': 'จัดการอุปกรณ์', 'icon': 'bi bi-tools', 'url_name': 'equipments', 'show': is_admin_user},
        {'label': 'จัดการผู้ใช้งาน', 'icon': 'bi bi-people-fill', 'url_name': 'user_management', 'show': is_admin_user},
        {'label': 'รายงานและสถิติ', 'icon': 'bi bi-bar-chart-line-fill', 'url_name': 'reports', 'show': is_admin_user},
        {'label': 'Log การใช้งาน', 'icon': 'bi bi-file-earmark-text', 'url_name': 'audit_log', 'show': is_admin_user},
    ]

    for item in menu_items:
        if item['show']:
            if item['url_name'] == 'dashboard':
                item['active'] = (current_path == '/') or (current_path == '/dashboard/')
            else:
                check_url = f"/{item['url_name']}"
                item['active'] = current_path.startswith(check_url)

    return {
        'menu_items': menu_items,
        'is_admin_user': is_admin_user,
        'pending_count': pending_count,
        'pending_notifications': pending_notifications,
    }