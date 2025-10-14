# booking/context_processors.py
def menu_context(request):
    if not request.user.is_authenticated:
        return {}

    is_admin = request.user.groups.filter(name='Admin').exists()
    is_approver = request.user.groups.filter(name='Approver').exists()

    current_page = request.resolver_match.url_name if request.resolver_match else ''

    menu_items = [
        {'id': 'dashboard', 'label': 'แดชบอร์ด', 'icon': 'bi-grid-1x2-fill', 'url_name': 'dashboard', 'show': True},
        {'id': 'history', 'label': 'ประวัติการจอง', 'icon': 'bi-clock-history', 'url_name': 'history', 'show': True},
        {'id': 'approvals', 'label': 'รออนุมัติ', 'icon': 'bi-check2-square', 'url_name': 'approvals', 'show': is_approver or is_admin},
        {'id': 'rooms', 'label': 'จัดการห้องประชุม', 'icon': 'bi-door-open-fill', 'url_name': 'rooms', 'show': is_admin},

        # --- [ใหม่] เพิ่มเมนูรายงานและสถิติ ---
        {'id': 'reports', 'label': 'รายงานและสถิติ', 'icon': 'bi-bar-chart-line-fill', 'url_name': 'reports', 'show': is_admin},
    ]

    for item in menu_items:
        item['active'] = (item['url_name'] == current_page)

    role_badge = {'label': 'ผู้ใช้งาน', 'class': 'bg-secondary'}
    if is_admin:
        role_badge = {'label': 'ผู้ดูแลระบบ', 'class': 'bg-danger'}
    elif is_approver:
        role_badge = {'label': 'ผู้อนุมัติ', 'class': 'bg-info'}

    return {'menu_items': menu_items, 'role_badge': role_badge}