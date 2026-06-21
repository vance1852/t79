from rest_framework import serializers

from .models import (
    GrowthRecord,
    LevelChangeLog,
    MallOrder,
    MallProduct,
    Member,
    MemberCoupon,
    MemberLevel,
    Performance,
    PerformancePriorityQuota,
    PointBatch,
    PointRule,
    PointTransaction,
    Show,
    TicketOrder,
)


class ShowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Show
        fields = ["id", "title", "troupe", "genre", "status", "created_at"]
        read_only_fields = ["id", "created_at"]


class PerformanceSerializer(serializers.ModelSerializer):
    show_title = serializers.CharField(source="show.title", read_only=True)
    remaining_seats = serializers.SerializerMethodField()

    class Meta:
        model = Performance
        fields = [
            "id", "show", "show_title", "hall", "start_at",
            "total_seats", "sold_seats", "remaining_seats", "price",
            "priority_start_at", "created_at",
        ]
        read_only_fields = ["id", "sold_seats", "created_at"]

    def get_remaining_seats(self, obj):
        return obj.total_seats - obj.sold_seats


class OrderSerializer(serializers.ModelSerializer):
    show_title = serializers.CharField(source="performance.show.title", read_only=True)
    member_name = serializers.CharField(source="member.name", read_only=True, default="")

    class Meta:
        model = TicketOrder
        fields = [
            "id", "performance", "show_title", "member", "member_name",
            "customer_name", "phone", "quantity", "amount", "cash_amount",
            "point_amount", "points_used", "channel", "status", "created_at",
        ]
        read_only_fields = [
            "id", "amount", "cash_amount", "point_amount",
            "points_used", "channel", "status", "created_at",
        ]


class OrderCreateSerializer(serializers.Serializer):
    performance = serializers.IntegerField()
    member = serializers.IntegerField(required=False, default=None)
    customer_name = serializers.CharField(max_length=64)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    quantity = serializers.IntegerField(min_value=1, max_value=10)
    use_points = serializers.BooleanField(required=False, default=True)
    is_priority = serializers.BooleanField(required=False, default=False)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class MemberLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberLevel
        fields = [
            "id", "name", "level", "min_growth", "max_growth",
            "discount_rate", "priority_hours", "priority_quota",
            "free_refund_count", "birthday_gift", "dedicated_support",
            "description", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MemberSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    level_detail = MemberLevelSerializer(source="level", read_only=True)

    class Meta:
        model = Member
        fields = [
            "id", "user", "name", "phone", "gender", "birthday",
            "level", "level_name", "level_detail",
            "growth_value", "period_growth", "points_balance",
            "total_points_earned", "total_points_spent",
            "free_refund_used", "total_orders", "total_attended",
            "total_amount", "last_active_at", "joined_at",
        ]
        read_only_fields = [
            "id", "growth_value", "period_growth", "points_balance",
            "total_points_earned", "total_points_spent",
            "free_refund_used", "total_orders", "total_attended",
            "total_amount", "last_active_at", "joined_at",
        ]


class MemberCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    phone = serializers.CharField(max_length=32)
    gender = serializers.CharField(max_length=16, required=False, allow_blank=True, default="")
    birthday = serializers.DateField(required=False, default=None)


class PointRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointRule
        fields = [
            "id", "source", "name", "points", "per_yuan",
            "expire_days", "daily_limit", "enabled", "description",
        ]
        read_only_fields = ["id"]


class PointBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointBatch
        fields = [
            "id", "member", "source", "source_ref", "total_points",
            "remaining_points", "earned_at", "expire_at", "expired",
        ]
        read_only_fields = ["id"]


class PointTransactionSerializer(serializers.ModelSerializer):
    batch_id = serializers.IntegerField(source="batch.id", read_only=True, default=None)

    class Meta:
        model = PointTransaction
        fields = [
            "id", "member", "type", "points", "balance_after",
            "source", "source_ref", "batch_id", "remark", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PointEarnSerializer(serializers.Serializer):
    member = serializers.IntegerField()
    source = serializers.CharField(max_length=32)
    points = serializers.IntegerField(min_value=1)
    source_ref = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    remark = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class PointSpendSerializer(serializers.Serializer):
    member = serializers.IntegerField()
    points = serializers.IntegerField(min_value=1)
    source = serializers.CharField(max_length=32, default="manual")
    source_ref = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    remark = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class GrowthRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrowthRecord
        fields = [
            "id", "member", "source", "growth", "source_ref",
            "remark", "period_start", "period_end", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class LevelChangeLogSerializer(serializers.ModelSerializer):
    from_level_name = serializers.CharField(source="from_level.name", read_only=True, default="")
    to_level_name = serializers.CharField(source="to_level.name", read_only=True)

    class Meta:
        model = LevelChangeLog
        fields = [
            "id", "member", "direction", "from_level", "from_level_name",
            "to_level", "to_level_name", "growth_before", "growth_after",
            "notified", "remark", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PerformancePriorityQuotaSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)

    class Meta:
        model = PerformancePriorityQuota
        fields = [
            "id", "performance", "level", "level_name",
            "total_quota", "used_quota",
        ]
        read_only_fields = ["id"]


class PriorityWindowSerializer(serializers.Serializer):
    performance_id = serializers.IntegerField()
    member_id = serializers.IntegerField()


class MallProductSerializer(serializers.ModelSerializer):
    min_level_name = serializers.CharField(source="min_level.name", read_only=True, default="")

    class Meta:
        model = MallProduct
        fields = [
            "id", "name", "type", "description", "point_price",
            "stock", "min_level", "min_level_name", "limit_per_member",
            "coupon_discount", "coupon_amount", "coupon_valid_days",
            "enabled", "image_url", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class MallOrderSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_type = serializers.CharField(source="product.type", read_only=True)
    member_name = serializers.CharField(source="member.name", read_only=True)

    class Meta:
        model = MallOrder
        fields = [
            "id", "member", "member_name", "product", "product_name",
            "product_type", "quantity", "point_price", "total_points",
            "status", "coupon_code", "coupon_expire_at",
            "tracking_no", "remark", "created_at",
        ]
        read_only_fields = [
            "id", "point_price", "total_points", "status",
            "coupon_code", "coupon_expire_at", "created_at",
        ]


class MallExchangeSerializer(serializers.Serializer):
    member = serializers.IntegerField()
    product = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=10, default=1)
    remark = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class MemberCouponSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default="")

    class Meta:
        model = MemberCoupon
        fields = [
            "id", "member", "product", "product_name", "code",
            "discount", "amount", "status", "expire_at",
            "used_at", "used_order", "mall_order", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class PointDeductCalcSerializer(serializers.Serializer):
    member = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


class MemberStatsSerializer(serializers.Serializer):
    total_members = serializers.IntegerField()
    level_distribution = serializers.ListField(child=serializers.DictField())
    total_points_earned = serializers.IntegerField()
    total_points_spent = serializers.IntegerField()
    total_points_expired = serializers.IntegerField()
    new_members_today = serializers.IntegerField()
    new_members_this_month = serializers.IntegerField()
    mall_orders_total = serializers.IntegerField()
    mall_points_total = serializers.IntegerField()


class MemberPortraitSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()
    level_name = serializers.CharField()
    growth_value = serializers.IntegerField()
    points_balance = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    total_amount = serializers.FloatField()
    total_attended = serializers.IntegerField()
    recent_90d_orders = serializers.IntegerField()
    recent_90d_amount = serializers.FloatField()
    top_genre = serializers.CharField()
    activity_level = serializers.CharField()
    days_since_last_active = serializers.IntegerField()
    joined_days = serializers.IntegerField()
