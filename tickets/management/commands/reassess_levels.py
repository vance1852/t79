"""批量重评会员等级命令。"""
from django.core.management.base import BaseCommand

from tickets.services import LevelService


class Command(BaseCommand):
    help = "批量重评所有会员等级（滚动周期）"

    def handle(self, *args, **options):
        changed = LevelService.batch_reassess_all()
        self.stdout.write(f"已重新评定，共有 {changed} 个会员等级发生变化")
