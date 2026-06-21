from django.contrib.auth.models import User
from django.db import models
from django.db.models import F


class Show(models.Model):
    """演出剧目。"""

    GENRE_CHOICES = [
        ("concert", "演唱会"),
        ("drama", "话剧"),
        ("musical", "音乐剧"),
        ("opera", "戏曲"),
        ("other", "其他"),
    ]
    STATUS_CHOICES = [
        ("on_sale", "售票中"),
        ("upcoming", "待开票"),
        ("ended", "已结束"),
    ]

    title = models.CharField(max_length=128)
    troupe = models.CharField(max_length=128, blank=True, default="")
    genre = models.CharField(max_length=16, choices=GENRE_CHOICES, default="concert")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="upcoming")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "shows"


class Performance(models.Model):
    """场次。"""

    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name="performances")
    hall = models.CharField(max_length=64, default="")
    start_at = models.DateTimeField()
    total_seats = models.IntegerField(default=0)
    sold_seats = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    priority_start_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "performances"


class TicketOrder(models.Model):
    """购票订单。"""

    STATUS_CHOICES = [
        ("paid", "已支付"),
        ("cancelled", "已取消"),
        ("refunded", "已退票"),
    ]
    CHANNEL_CHOICES = [
        ("normal", "普通购买"),
        ("priority", "优先购"),
    ]

    performance = models.ForeignKey(Performance, on_delete=models.CASCADE, related_name="orders")
    member = models.ForeignKey("Member", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    customer_name = models.CharField(max_length=64)
    phone = models.CharField(max_length=32, blank=True, default="")
    quantity = models.IntegerField(default=1)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cash_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    point_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    points_used = models.IntegerField(default=0)
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES, default="normal")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="paid")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ticket_orders"


class MemberLevel(models.Model):
    """会员等级配置。"""

    name = models.CharField(max_length=32, unique=True)
    level = models.IntegerField(unique=True)
    min_growth = models.IntegerField(default=0)
    max_growth = models.IntegerField(default=0)
    discount_rate = models.DecimalField(max_digits=4, decimal_places=2, default=1.00)
    priority_hours = models.IntegerField(default=0)
    priority_quota = models.IntegerField(default=0)
    free_refund_count = models.IntegerField(default=0)
    birthday_gift = models.CharField(max_length=255, blank=True, default="")
    dedicated_support = models.BooleanField(default=False)
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "member_levels"
        ordering = ["level"]


class Member(models.Model):
    """会员账户。"""

    GENDER_CHOICES = [
        ("male", "男"),
        ("female", "女"),
        ("other", "其他"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="member", null=True, blank=True)
    name = models.CharField(max_length=64)
    phone = models.CharField(max_length=32, unique=True)
    gender = models.CharField(max_length=16, choices=GENDER_CHOICES, blank=True, default="")
    birthday = models.DateField(null=True, blank=True)
    level = models.ForeignKey(MemberLevel, on_delete=models.PROTECT, related_name="members")
    growth_value = models.IntegerField(default=0)
    period_growth = models.IntegerField(default=0)
    points_balance = models.IntegerField(default=0)
    total_points_earned = models.IntegerField(default=0)
    total_points_spent = models.IntegerField(default=0)
    free_refund_used = models.IntegerField(default=0)
    total_orders = models.IntegerField(default=0)
    total_attended = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_active_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "members"


class PointRule(models.Model):
    """积分获取规则。"""

    SOURCE_CHOICES = [
        ("purchase", "消费购票"),
        ("review", "演出评价"),
        ("checkin", "签到"),
        ("activity", "活动奖励"),
        ("birthday", "生日礼"),
        ("refund_return", "退票返还"),
        ("admin", "管理员调整"),
    ]

    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, unique=True)
    name = models.CharField(max_length=64)
    points = models.IntegerField(default=0)
    per_yuan = models.IntegerField(default=0)
    expire_days = models.IntegerField(default=365)
    daily_limit = models.IntegerField(default=0)
    enabled = models.BooleanField(default=True)
    description = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "point_rules"


class PointBatch(models.Model):
    """积分批次（分批次过期，先到期先扣）。"""

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="point_batches")
    source = models.CharField(max_length=32)
    source_ref = models.CharField(max_length=64, blank=True, default="")
    total_points = models.IntegerField(default=0)
    remaining_points = models.IntegerField(default=0)
    earned_at = models.DateTimeField()
    expire_at = models.DateTimeField()
    expired = models.BooleanField(default=False)

    class Meta:
        db_table = "point_batches"
        indexes = [
            models.Index(fields=["member", "expire_at"]),
            models.Index(fields=["expire_at", "expired"]),
        ]
        ordering = ["expire_at"]


class PointTransaction(models.Model):
    """积分变动流水。"""

    TYPE_CHOICES = [
        ("earn", "获取"),
        ("spend", "消耗"),
        ("expire", "过期"),
        ("refund", "退还"),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="point_transactions")
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    points = models.IntegerField(default=0)
    balance_after = models.IntegerField(default=0)
    source = models.CharField(max_length=32, blank=True, default="")
    source_ref = models.CharField(max_length=64, blank=True, default="")
    batch = models.ForeignKey(PointBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    remark = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "point_transactions"
        ordering = ["-id"]


class GrowthRecord(models.Model):
    """成长值获取记录。"""

    SOURCE_CHOICES = [
        ("purchase", "消费购票"),
        ("attend", "观演完成"),
        ("activity", "活动奖励"),
        ("admin", "管理员调整"),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="growth_records")
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    growth = models.IntegerField(default=0)
    source_ref = models.CharField(max_length=64, blank=True, default="")
    remark = models.CharField(max_length=255, blank=True, default="")
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "growth_records"
        ordering = ["-id"]


class LevelChangeLog(models.Model):
    """等级升降记录。"""

    DIRECTION_CHOICES = [
        ("upgrade", "升级"),
        ("downgrade", "降级"),
        ("initial", "初始"),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="level_changes")
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES)
    from_level = models.ForeignKey(MemberLevel, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    to_level = models.ForeignKey(MemberLevel, on_delete=models.PROTECT, related_name="+")
    growth_before = models.IntegerField(default=0)
    growth_after = models.IntegerField(default=0)
    notified = models.BooleanField(default=False)
    remark = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "level_change_logs"
        ordering = ["-id"]


class PerformancePriorityQuota(models.Model):
    """场次优先购配额（按等级）。"""

    performance = models.ForeignKey(Performance, on_delete=models.CASCADE, related_name="priority_quotas")
    level = models.ForeignKey(MemberLevel, on_delete=models.CASCADE, related_name="priority_quotas")
    total_quota = models.IntegerField(default=0)
    used_quota = models.IntegerField(default=0)

    class Meta:
        db_table = "performance_priority_quotas"
        unique_together = [("performance", "level")]


class MallProduct(models.Model):
    """权益商城商品。"""

    TYPE_CHOICES = [
        ("coupon", "优惠券"),
        ("perk", "权益"),
        ("merch", "周边实物"),
        ("ticket", "赠票"),
    ]

    name = models.CharField(max_length=128)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    description = models.TextField(blank=True, default="")
    point_price = models.IntegerField(default=0)
    stock = models.IntegerField(default=0)
    min_level = models.ForeignKey(MemberLevel, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    limit_per_member = models.IntegerField(default=0)
    coupon_discount = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    coupon_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    coupon_valid_days = models.IntegerField(default=0)
    enabled = models.BooleanField(default=True)
    image_url = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mall_products"
        ordering = ["-id"]


class MallOrder(models.Model):
    """商城兑换订单。"""

    STATUS_CHOICES = [
        ("completed", "已完成"),
        ("cancelled", "已取消"),
        ("delivered", "已发货"),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="mall_orders")
    product = models.ForeignKey(MallProduct, on_delete=models.PROTECT, related_name="orders")
    quantity = models.IntegerField(default=1)
    point_price = models.IntegerField(default=0)
    total_points = models.IntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="completed")
    coupon_code = models.CharField(max_length=64, blank=True, default="")
    coupon_expire_at = models.DateTimeField(null=True, blank=True)
    tracking_no = models.CharField(max_length=64, blank=True, default="")
    remark = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mall_orders"
        ordering = ["-id"]


class MemberCoupon(models.Model):
    """会员优惠券。"""

    STATUS_CHOICES = [
        ("unused", "未使用"),
        ("used", "已使用"),
        ("expired", "已过期"),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="coupons")
    product = models.ForeignKey(MallProduct, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    code = models.CharField(max_length=64, unique=True)
    discount = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="unused")
    expire_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    used_order = models.ForeignKey(TicketOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    mall_order = models.ForeignKey(MallOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "member_coupons"
        ordering = ["-id"]
