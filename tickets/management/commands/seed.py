"""初始化内置管理员与种子业务数据（幂等）。"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from tickets.models import (
    GrowthRecord,
    LevelChangeLog,
    MallProduct,
    Member,
    MemberLevel,
    Performance,
    PerformancePriorityQuota,
    PointBatch,
    PointRule,
    PointTransaction,
    Show,
    TicketOrder,
)


class Command(BaseCommand):
    help = "初始化管理员与演出票务种子数据"

    def handle(self, *args, **options):
        username = settings.DEFAULT_ADMIN_USERNAME
        password = settings.DEFAULT_ADMIN_PASSWORD
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, password=password, first_name="平台管理员")
            self.stdout.write("已创建管理员账号")

        self._seed_member_levels()
        self._seed_point_rules()
        self._seed_shows_if_needed()
        self._ensure_performances_priority()
        self._seed_members()
        self._seed_mall_products()
        self._seed_member_points_history()
        self._seed_priority_quotas()
        self.stdout.write("种子数据初始化完成")

    def _seed_member_levels(self):
        if MemberLevel.objects.exists():
            self.stdout.write("会员等级已存在，跳过")
            return
        levels = [
            MemberLevel.objects.create(
                name="普通会员", level=1, min_growth=0, max_growth=999,
                discount_rate=Decimal("1.00"), priority_hours=0, priority_quota=0,
                free_refund_count=0, birthday_gift="", dedicated_support=False,
                description="注册即享",
            ),
            MemberLevel.objects.create(
                name="银卡会员", level=2, min_growth=1000, max_growth=4999,
                discount_rate=Decimal("0.98"), priority_hours=2, priority_quota=2,
                free_refund_count=1, birthday_gift="50积分", dedicated_support=False,
                description="累计消费1000成长值",
            ),
            MemberLevel.objects.create(
                name="金卡会员", level=3, min_growth=5000, max_growth=19999,
                discount_rate=Decimal("0.95"), priority_hours=6, priority_quota=4,
                free_refund_count=3, birthday_gift="200积分+专属礼券", dedicated_support=False,
                description="累计消费5000成长值",
            ),
            MemberLevel.objects.create(
                name="钻石会员", level=4, min_growth=20000, max_growth=99999999,
                discount_rate=Decimal("0.90"), priority_hours=24, priority_quota=10,
                free_refund_count=10, birthday_gift="1000积分+限定周边", dedicated_support=True,
                description="累计消费20000成长值",
            ),
        ]
        self.stdout.write(f"已创建 {len(levels)} 个会员等级")

    def _seed_point_rules(self):
        if PointRule.objects.exists():
            self.stdout.write("积分规则已存在，跳过")
            return
        rules_data = [
            dict(source="purchase", name="购票消费", points=0, per_yuan=1,
                 expire_days=365, daily_limit=0, enabled=True,
                 description="每消费1元得1积分"),
            dict(source="review", name="演出评价", points=20, per_yuan=0,
                 expire_days=180, daily_limit=5, enabled=True,
                 description="每次评价得20积分，每日上限5次"),
            dict(source="checkin", name="每日签到", points=5, per_yuan=0,
                 expire_days=90, daily_limit=1, enabled=True,
                 description="每日签到得5积分"),
            dict(source="activity", name="活动奖励", points=0, per_yuan=0,
                 expire_days=365, daily_limit=0, enabled=True,
                 description="参与活动获得积分"),
            dict(source="birthday", name="生日礼", points=100, per_yuan=0,
                 expire_days=365, daily_limit=0, enabled=True,
                 description="生日当天领取生日礼积分"),
            dict(source="refund_return", name="退票返还", points=0, per_yuan=0,
                 expire_days=365, daily_limit=0, enabled=True,
                 description="退票时返还已使用的积分"),
            dict(source="admin", name="管理员调整", points=0, per_yuan=0,
                 expire_days=365, daily_limit=0, enabled=True,
                 description="管理员手动调整积分"),
        ]
        for rd in rules_data:
            PointRule.objects.create(**rd)
        self.stdout.write(f"已创建 {len(rules_data)} 条积分规则")

    def _seed_shows_if_needed(self):
        if Show.objects.exists():
            self.stdout.write("演出数据已存在，跳过")
            return

        shows = [
            Show.objects.create(title="星河巡回演唱会", troupe="星河乐团", genre="concert", status="on_sale"),
            Show.objects.create(title="金陵往事话剧", troupe="城南剧社", genre="drama", status="on_sale"),
            Show.objects.create(title="敦煌音乐剧", troupe="丝路艺术团", genre="musical", status="upcoming"),
            Show.objects.create(title="经典戏曲专场", troupe="梨园名家", genre="opera", status="ended"),
        ]

        now = datetime.now().replace(microsecond=0)
        perfs = [
            Performance.objects.create(
                show=shows[0], hall="一号厅", start_at=now + timedelta(days=3),
                total_seats=1200, sold_seats=860, price=380,
                priority_start_at=now + timedelta(days=1),
            ),
            Performance.objects.create(
                show=shows[0], hall="一号厅", start_at=now + timedelta(days=4),
                total_seats=1200, sold_seats=300, price=380,
                priority_start_at=now + timedelta(days=2),
            ),
            Performance.objects.create(
                show=shows[1], hall="小剧场", start_at=now + timedelta(days=2),
                total_seats=300, sold_seats=290, price=180,
                priority_start_at=now,
            ),
            Performance.objects.create(
                show=shows[2], hall="大剧院", start_at=now + timedelta(days=20),
                total_seats=900, sold_seats=0, price=280,
                priority_start_at=now + timedelta(days=15),
            ),
        ]

        TicketOrder.objects.create(
            performance=perfs[0], customer_name="陈静", phone="13900001111",
            quantity=2, amount=760, cash_amount=760, status="paid", channel="normal",
        )
        TicketOrder.objects.create(
            performance=perfs[2], customer_name="刘洋", phone="13900002222",
            quantity=4, amount=720, cash_amount=720, status="paid", channel="normal",
        )
        TicketOrder.objects.create(
            performance=perfs[0], customer_name="孙琳", phone="13900003333",
            quantity=1, amount=380, cash_amount=380, status="cancelled", channel="normal",
        )
        self.stdout.write("演出票务种子数据初始化完成")

    def _ensure_performances_priority(self):
        now = datetime.now().replace(microsecond=0)
        updated = Performance.objects.filter(
            priority_start_at__isnull=True
        ).update(priority_start_at=now)
        if updated > 0:
            self.stdout.write(f"已为 {updated} 个场次补充优先购开始时间")

    def _seed_members(self):
        if Member.objects.exists():
            self.stdout.write("会员数据已存在，跳过")
            return
        now = datetime.now().replace(microsecond=0)
        levels_qs = MemberLevel.objects.all()
        levels = {lv.level: lv for lv in levels_qs}

        members_data = [
            {
                "name": "张晓峰", "phone": "13800001001", "gender": "male",
                "birthday": "1990-05-15", "level": levels.get(4), "growth": 35000,
                "period_growth": 28000, "points": 12500,
            },
            {
                "name": "李雨晴", "phone": "13800001002", "gender": "female",
                "birthday": "1995-08-22", "level": levels.get(3), "growth": 8500,
                "period_growth": 6200, "points": 4800,
            },
            {
                "name": "王浩然", "phone": "13800001003", "gender": "male",
                "birthday": "1988-11-30", "level": levels.get(2), "growth": 2500,
                "period_growth": 1800, "points": 1200,
            },
            {
                "name": "陈思琪", "phone": "13800001004", "gender": "female",
                "birthday": "1998-03-10", "level": levels.get(1), "growth": 500,
                "period_growth": 500, "points": 300,
            },
            {
                "name": "刘子轩", "phone": "13800001005", "gender": "male",
                "birthday": "", "level": levels.get(2), "growth": 3200,
                "period_growth": 2100, "points": 800,
            },
        ]

        today = datetime.now().date()
        period_start = today - timedelta(days=179)
        start_dt = datetime(period_start.year, period_start.month, period_start.day)
        default_level = levels.get(1) or levels_qs.order_by("level").first()

        for md in members_data:
            bday = None
            if md["birthday"]:
                try:
                    bday = datetime.strptime(md["birthday"], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    bday = None
            member_level = md["level"] or default_level
            if not member_level:
                self.stdout.write(self.style.WARNING("没有可用的会员等级，跳过会员创建"))
                return
            member = Member.objects.create(
                name=md["name"], phone=md["phone"], gender=md.get("gender", ""),
                birthday=bday, level=member_level,
                growth_value=md["growth"], period_growth=md["period_growth"],
                points_balance=md["points"],
                total_points_earned=md["points"] + 500,
                total_points_spent=500,
                total_orders=md["growth"] // 200 if md["growth"] > 200 else 2,
                total_attended=max(1, md["growth"] // 500),
                total_amount=Decimal(md["growth"]),
                last_active_at=now - timedelta(days=2),
                joined_at=now - timedelta(days=365),
            )
            LevelChangeLog.objects.create(
                member=member, direction="initial", to_level=member_level,
                growth_before=0, growth_after=md["growth"], remark="初始入会",
            )
            if md["period_growth"] > 0:
                GrowthRecord.objects.create(
                    member=member, source="purchase",
                    growth=md["period_growth"], source_ref="seed",
                    period_start=period_start, period_end=today,
                    remark="种子数据-累计消费成长值",
                    created_at=start_dt,
                )
        self.stdout.write(f"已创建 {len(members_data)} 个会员")

    def _seed_member_points_history(self):
        if PointBatch.objects.exists() or PointTransaction.objects.exists():
            self.stdout.write("积分流水已存在，跳过")
            return
        now = datetime.now().replace(microsecond=0)
        members = Member.objects.all()
        batch_count = 0
        tx_count = 0
        for member in members:
            earn_points = member.total_points_earned
            spend_points = member.total_points_spent
            batch = None
            if earn_points > 0:
                batch = PointBatch.objects.create(
                    member=member, source="purchase", source_ref="seed",
                    total_points=earn_points, remaining_points=member.points_balance,
                    earned_at=now - timedelta(days=100),
                    expire_at=now + timedelta(days=265),
                )
                PointTransaction.objects.create(
                    member=member, type="earn", points=earn_points,
                    balance_after=member.points_balance + spend_points,
                    source="purchase", source_ref="seed", batch=batch,
                    remark="种子数据-购票累计积分",
                    created_at=now - timedelta(days=100),
                )
                batch_count += 1
                tx_count += 1
            if spend_points > 0:
                PointTransaction.objects.create(
                    member=member, type="spend", points=-spend_points,
                    balance_after=member.points_balance,
                    source="mall_exchange", source_ref="seed", batch=batch,
                    remark="种子数据-商城兑换消耗积分",
                    created_at=now - timedelta(days=30),
                )
                tx_count += 1
        self.stdout.write(f"已创建 {batch_count} 个积分批次，{tx_count} 条积分流水")

    def _seed_mall_products(self):
        if MallProduct.objects.exists():
            self.stdout.write("商城商品已存在，跳过")
            return
        levels_qs = MemberLevel.objects.all()
        levels = {lv.level: lv for lv in levels_qs}
        products_data = [
            dict(
                name="满300减50优惠券", type="coupon",
                description="全场通用满300减50优惠券，有效期30天",
                point_price=500, stock=100, min_level=None,
                limit_per_member=3, coupon_discount=None,
                coupon_amount=Decimal("50.00"), coupon_valid_days=30,
                enabled=True,
            ),
            dict(
                name="9折优惠券", type="coupon",
                description="全场9折优惠券，最高减200元，有效期30天",
                point_price=800, stock=50, min_level=levels.get(2),
                limit_per_member=2, coupon_discount=Decimal("0.90"),
                coupon_amount=None, coupon_valid_days=30, enabled=True,
            ),
            dict(
                name="限定周边T恤", type="merch",
                description="星河演唱会限定周边T恤，尺码随机",
                point_price=3000, stock=30, min_level=levels.get(2),
                limit_per_member=1, enabled=True,
            ),
            dict(
                name="VIP专属会员卡套", type="perk",
                description="金卡及以上会员专享，定制会员卡套",
                point_price=1500, stock=100, min_level=levels.get(3),
                limit_per_member=1, enabled=True,
            ),
            dict(
                name="生日礼券包", type="coupon",
                description="含2张50元优惠券+1张8折券，钻石会员专享",
                point_price=2000, stock=20, min_level=levels.get(4),
                limit_per_member=1, coupon_amount=Decimal("100.00"),
                coupon_valid_days=90, enabled=True,
            ),
            dict(
                name="签名海报", type="merch",
                description="演出明星亲笔签名海报",
                point_price=5000, stock=10, min_level=levels.get(2),
                limit_per_member=1, enabled=True,
            ),
        ]
        for pd in products_data:
            MallProduct.objects.create(**pd)
        self.stdout.write(f"已创建 {len(products_data)} 件商城商品")

    def _seed_priority_quotas(self):
        perfs = Performance.objects.all()
        levels = MemberLevel.objects.filter(priority_hours__gt=0)
        if not perfs.exists() or not levels.exists():
            self.stdout.write("优先购配额无需创建（缺少场次或等级配置）")
            return
        count = 0
        for perf in perfs:
            for lv in levels:
                _, created = PerformancePriorityQuota.objects.get_or_create(
                    performance=perf, level=lv,
                    defaults={"total_quota": lv.priority_quota, "used_quota": 0},
                )
                if created:
                    count += 1
        self.stdout.write(f"已创建 {count} 条优先购配额")
