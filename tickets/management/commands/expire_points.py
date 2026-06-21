"""积分过期批处理命令。"""
from django.core.management.base import BaseCommand

from tickets.services import PointService


class Command(BaseCommand):
    help = "批量处理过期积分"

    def handle(self, *args, **options):
        count = PointService.expire_points()
        self.stdout.write(f"已处理 {count} 个过期积分批次")
