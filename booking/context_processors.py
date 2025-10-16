# booking/context_processors.py
def menu_context(request):
    current_path = request.path
    is_admin = request.user.is_authenticated and request.user.groups.filter(name='Admin').exists()
    is_approver = request.user.is_authenticated and request.user.groups.filter(name='Approver').exists()

    menu_items = [
        {'label': 'Dashboard', 'icon': 'bi bi-grid-fill', 'url_name': 'dashboard', 'path': '/', 'show': True},
        {'label': 'ประวัติการจอง', 'icon': 'bi bi-clock-history', 'url_name': 'history', 'path': '/history/', 'show': True},
        {'label': 'รออนุมัติ', 'icon': 'bi bi-hourglass-split', 'url_name': 'approvals', 'path': '/approvals/', 'show': is_admin or is_approver},
        {'label': 'รายงาน', 'icon': 'bi bi-bar-chart-line-fill', 'url_name': 'reports', 'path': '/reports/', 'show': is_admin},
        {'label': 'จัดการห้องประชุม', 'icon': 'bi bi-door-closed-fill', 'url_name': 'rooms', 'path': '/management/rooms/', 'show': is_admin},
        # --- [ใหม่] เพิ่มเมนูจัดการผู้ใช้ ---
        {'label': 'จัดการผู้ใช้', 'icon': 'bi bi-people-fill', 'url_name': 'user_management', 'path': '/management/users/', 'show': is_admin},
    ]

    for item in menu_items:
        item['active'] = current_path == item['path']

    role_badge = {'label': 'User', 'class': 'bg-secondary'}
    if is_admin:
        role_badge = {'label': 'Admin', 'class': 'bg-danger'}
    elif is_approver:
        role_badge = {'label': 'Approver', 'class': 'bg-info text-dark'}

    return {'menu_items': menu_items, 'role_badge': role_badge}