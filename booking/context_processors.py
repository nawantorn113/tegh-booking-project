# booking/context_processors.py
# [ฉบับสมบูรณ์]

def menu_context(request):
    is_admin = False
    is_approver = False
    if request.user.is_authenticated:
        is_admin = request.user.groups.filter(name='Admin').exists()
        is_approver = request.user.groups.filter(name='Approver').exists()

    current_url_name = request.resolver_match.url_name if request.resolver_match else ''

    menu_items = [
        {'label': 'หน้าหลัก', 'url_name': 'dashboard', 'icon': 'bi-grid-1x2-fill', 'show': True},
        {'label': 'ประวัติการจอง', 'url_name': 'history', 'icon': 'bi-clock-history', 'show': True},
        {'label': 'รออนุมัติ', 'url_name': 'approvals', 'icon': 'bi-check2-square', 'show': is_approver or is_admin},
        {'label': 'จัดการห้องประชุม', 'url_name': 'rooms', 'icon': 'bi-door-open-fill', 'show': is_admin},
        {'label': 'จัดการผู้ใช้งาน', 'url_name': 'user_management', 'icon': 'bi-people-fill', 'show': is_admin},
        {'label': 'รายงานและสถิติ', 'url_name': 'reports', 'icon': 'bi-bar-chart-line-fill', 'show': is_admin},
        # {'label': 'ตั้งค่าระบบ', 'url_name': 'settings', 'icon': 'bi-gear-fill', 'show': is_admin},
        # {'label': 'ประวัติการใช้งาน', 'url_name': 'audit_log', 'icon': 'bi-file-text-fill', 'show': is_admin},
    ]

    for item in menu_items:
        item['active'] = (item['url_name'] == current_url_name)

    return {'menu_items': menu_items}