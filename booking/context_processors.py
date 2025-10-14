# booking/context_processors.py
def menu_context(request):
    if not request.user.is_authenticated:
        return {}

    is_admin = request.user.groups.filter(name='Admin').exists()
    is_approver = request.user.groups.filter(name='Approver').exists()

    current_page = request.resolver_match.url_name if request.resolver_match else ''

    menu_items = [
        { 'id': 'dashboard', 'label': 'แดชบอร์ด', 'icon': 'bi-grid-1x2-fill', 'url_name': 'dashboard', 'show': True },
        { 'id': 'history', 'label': 'ประวัติการจอง', 'icon': 'bi-clock-history', 'url_name': 'history', 'show': True },
        { 'id': 'approvals', 'label': 'รออนุมัติ', 'icon': 'bi-check2-square', 'url_name': 'approvals', 'show': is_approver or is_admin },
        { 'id': 'rooms', 'label': 'จัดการห้องประชุม', 'icon': 'bi-door-open-fill', 'url_name': 'rooms', 'show': is_admin },
        # เพิ่มเมนูอื่นๆ ที่นี่ในอนาคต
    ]

    for item in menu_items:
        item['active'] = (item['url_name'] == current_page)

    return {
        'menu_items': menu_items,
        'is_admin': is_admin,
        'is_approver': is_approver
    }