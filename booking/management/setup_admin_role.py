# booking/management/commands/setup_admin_role.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group

class Command(BaseCommand):
    help = 'Assigns Admin and Approver roles to a specified superuser.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username of the superuser to promote.')

    def handle(self, *args, **kwargs):
        username = kwargs['username']
        try:
            user = User.objects.get(username=username, is_superuser=True)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"ไม่พบ Superuser ที่ชื่อ '{username}'"))
            return

        admin_group, created = Group.objects.get_or_create(name='Admin')
        if created:
            self.stdout.write(self.style.SUCCESS("สร้าง Group 'Admin' เรียบร้อยแล้ว"))

        approver_group, created = Group.objects.get_or_create(name='Approver')
        if created:
            self.stdout.write(self.style.SUCCESS("สร้าง Group 'Approver' เรียบร้อยแล้ว"))

        user.groups.add(admin_group)
        user.groups.add(approver_group)

        self.stdout.write(self.style.SUCCESS(f"ติดยศ 'Admin' และ 'Approver' ให้กับ '{username}' เรียบร้อยแล้ว!"))