from django.contrib.auth import authenticate
from django.db.models import F
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

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
from .serializers import (
    GrowthRecordSerializer,
    LevelChangeLogSerializer,
    LoginSerializer,
    MallExchangeSerializer,
    MallOrderSerializer,
    MallProductSerializer,
    MemberCouponSerializer,
    MemberCreateSerializer,
    MemberLevelSerializer,
    MemberPortraitSerializer,
    MemberSerializer,
    MemberStatsSerializer,
    OrderCreateSerializer,
    OrderSerializer,
    PerformancePriorityQuotaSerializer,
    PerformanceSerializer,
    PointBatchSerializer,
    PointDeductCalcSerializer,
    PointEarnSerializer,
    PointRuleSerializer,
    PointSpendSerializer,
    PointTransactionSerializer,
    PriorityWindowSerializer,
    ShowSerializer,
)
from .services import (
    LevelService,
    MallService,
    MemberStatsService,
    OrderService,
    PointService,
    PriorityService,
)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = authenticate(username=s.validated_data["username"], password=s.validated_data["password"])
        if user is None:
            return Response({"detail": "用户名或密码错误"}, status=status.HTTP_401_UNAUTHORIZED)
        token = RefreshToken.for_user(user)
        return Response({"access_token": str(token.access_token), "token_type": "bearer"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    u = request.user
    data = {"id": u.id, "username": u.username, "display_name": u.get_full_name() or "平台管理员"}
    try:
        m = u.member
        data["member"] = MemberSerializer(m).data
    except Member.DoesNotExist:
        data["member"] = None
    return Response(data)


class ShowViewSet(viewsets.ModelViewSet):
    queryset = Show.objects.all().order_by("id")
    serializer_class = ShowSerializer


class PerformanceViewSet(viewsets.ModelViewSet):
    queryset = Performance.objects.select_related("show").all().order_by("start_at")
    serializer_class = PerformanceSerializer

    @action(detail=True, methods=["get"], url_path="priority-quotas")
    def priority_quotas(self, request, pk=None):
        quotas = PerformancePriorityQuota.objects.select_related("level").filter(performance_id=pk)
        return Response(PerformancePriorityQuotaSerializer(quotas, many=True).data)


class OrderViewSet(viewsets.ModelViewSet):
    queryset = TicketOrder.objects.select_related("performance", "performance__show", "member").all().order_by("-id")
    http_method_names = ["get", "post"]

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        s = OrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        try:
            perf = Performance.objects.select_related("show").get(pk=data["performance"])
        except Performance.DoesNotExist:
            return Response({"detail": "场次不存在"}, status=status.HTTP_404_NOT_FOUND)

        member_id = data.get("member")
        use_points = data.get("use_points", True)
        is_priority = data.get("is_priority", False)

        if member_id:
            try:
                member = Member.objects.select_related("level").get(pk=member_id)
            except Member.DoesNotExist:
                return Response({"detail": "会员不存在"}, status=status.HTTP_404_NOT_FOUND)
            order, msg = OrderService.create_order_with_points(
                perf, member, data["customer_name"], data.get("phone", ""),
                data["quantity"], use_points=use_points, is_priority=is_priority,
            )
            if not order:
                return Response({"detail": msg}, status=status.HTTP_409_CONFLICT)
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

        remaining = perf.total_seats - perf.sold_seats
        if data["quantity"] > remaining:
            return Response({"detail": "余票不足"}, status=status.HTTP_409_CONFLICT)

        order = TicketOrder.objects.create(
            performance=perf,
            customer_name=data["customer_name"],
            phone=data.get("phone", ""),
            quantity=data["quantity"],
            amount=perf.price * data["quantity"],
            cash_amount=perf.price * data["quantity"],
            status="paid",
            channel="normal",
        )
        perf.sold_seats += data["quantity"]
        perf.save(update_fields=["sold_seats"])
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        try:
            order = TicketOrder.objects.select_related("member", "performance").get(pk=pk)
        except TicketOrder.DoesNotExist:
            return Response({"detail": "订单不存在"}, status=status.HTTP_404_NOT_FOUND)
        ok, msg = OrderService.refund_order(order)
        if not ok:
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    show_total = Show.objects.count()
    show_on_sale = Show.objects.filter(status="on_sale").count()
    perf_total = Performance.objects.count()
    order_paid = TicketOrder.objects.filter(status="paid").count()
    sold = sum(p.sold_seats for p in Performance.objects.all())
    capacity = sum(p.total_seats for p in Performance.objects.all())
    return Response({
        "show_total": show_total,
        "show_on_sale": show_on_sale,
        "performance_total": perf_total,
        "order_paid": order_paid,
        "seats_sold": sold,
        "seats_capacity": capacity,
    })


class MemberLevelViewSet(viewsets.ModelViewSet):
    queryset = MemberLevel.objects.all().order_by("level")
    serializer_class = MemberLevelSerializer


class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.select_related("level").all().order_by("-id")
    serializer_class = MemberSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return MemberCreateSerializer
        return MemberSerializer

    def create(self, request, *args, **kwargs):
        s = MemberCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        default_level = MemberLevel.objects.order_by("level").first()
        if not default_level:
            return Response({"detail": "请先配置会员等级"}, status=status.HTTP_400_BAD_REQUEST)
        member = Member.objects.create(
            name=data["name"],
            phone=data["phone"],
            gender=data.get("gender", ""),
            birthday=data.get("birthday"),
            level=default_level,
        )
        LevelChangeLog.objects.create(
            member=member,
            direction="initial",
            to_level=default_level,
            growth_before=0,
            growth_after=0,
            remark="初始入会",
        )
        return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="point-batches")
    def point_batches(self, request, pk=None):
        batches = PointBatch.objects.filter(member_id=pk).order_by("-earned_at")
        return Response(PointBatchSerializer(batches, many=True).data)

    @action(detail=True, methods=["get"], url_path="point-transactions")
    def point_transactions(self, request, pk=None):
        txs = PointTransaction.objects.filter(member_id=pk).order_by("-id")[:200]
        return Response(PointTransactionSerializer(txs, many=True).data)

    @action(detail=True, methods=["get"], url_path="growth-records")
    def growth_records(self, request, pk=None):
        records = GrowthRecord.objects.filter(member_id=pk).order_by("-id")[:200]
        return Response(GrowthRecordSerializer(records, many=True).data)

    @action(detail=True, methods=["get"], url_path="level-changes")
    def level_changes(self, request, pk=None):
        logs = LevelChangeLog.objects.select_related("from_level", "to_level").filter(member_id=pk).order_by("-id")
        return Response(LevelChangeLogSerializer(logs, many=True).data)

    @action(detail=True, methods=["get"], url_path="orders")
    def orders(self, request, pk=None):
        orders = TicketOrder.objects.select_related("performance", "performance__show").filter(member_id=pk).order_by("-id")
        return Response(OrderSerializer(orders, many=True).data)

    @action(detail=True, methods=["get"], url_path="coupons")
    def coupons(self, request, pk=None):
        coupons = MemberCoupon.objects.select_related("product").filter(member_id=pk).order_by("-id")
        return Response(MemberCouponSerializer(coupons, many=True).data)

    @action(detail=True, methods=["get"], url_path="mall-orders")
    def mall_orders(self, request, pk=None):
        orders = MallOrder.objects.select_related("product", "member").filter(member_id=pk).order_by("-id")
        return Response(MallOrderSerializer(orders, many=True).data)

    @action(detail=True, methods=["get"], url_path="portrait")
    def portrait(self, request, pk=None):
        try:
            member = Member.objects.select_related("level").get(pk=pk)
        except Member.DoesNotExist:
            return Response({"detail": "会员不存在"}, status=status.HTTP_404_NOT_FOUND)
        data = MemberStatsService.get_member_portrait(member)
        return Response(MemberPortraitSerializer(data).data)

    @action(detail=True, methods=["post"], url_path="checkin")
    def checkin(self, request, pk=None):
        try:
            member = Member.objects.get(pk=pk)
        except Member.DoesNotExist:
            return Response({"detail": "会员不存在"}, status=status.HTTP_404_NOT_FOUND)
        batch = PointService.earn_by_checkin(member)
        if not batch:
            return Response({"detail": "今日已签到或规则未启用"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"points": batch.total_points, "remark": "签到成功"})

    @action(detail=True, methods=["post"], url_path="review")
    def review_earn(self, request, pk=None):
        try:
            member = Member.objects.get(pk=pk)
        except Member.DoesNotExist:
            return Response({"detail": "会员不存在"}, status=status.HTTP_404_NOT_FOUND)
        batch = PointService.earn_by_review(member)
        if not batch:
            return Response({"detail": "今日评价积分已达上限或规则未启用"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"points": batch.total_points, "remark": "评价奖励已发放"})

    @action(detail=True, methods=["post"], url_path="birthday")
    def birthday_earn(self, request, pk=None):
        try:
            member = Member.objects.get(pk=pk)
        except Member.DoesNotExist:
            return Response({"detail": "会员不存在"}, status=status.HTTP_404_NOT_FOUND)
        batch = PointService.earn_by_birthday(member)
        if not batch:
            return Response({"detail": "非生日或已领取"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"points": batch.total_points, "remark": "生日礼已发放"})

    @action(detail=True, methods=["post"], url_path="activity-earn")
    def activity_earn(self, request, pk=None):
        try:
            member = Member.objects.get(pk=pk)
        except Member.DoesNotExist:
            return Response({"detail": "会员不存在"}, status=status.HTTP_404_NOT_FOUND)
        points = int(request.data.get("points", 0))
        activity_id = request.data.get("activity_id", "")
        remark = request.data.get("remark", "")
        if points <= 0:
            return Response({"detail": "积分必须大于0"}, status=status.HTTP_400_BAD_REQUEST)
        batch = PointService.earn_by_activity(member, points, activity_id, remark)
        return Response({"points": batch.total_points, "remark": "活动奖励已发放"})


class PointRuleViewSet(viewsets.ModelViewSet):
    queryset = PointRule.objects.all().order_by("source")
    serializer_class = PointRuleSerializer


class PointTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PointTransaction.objects.select_related("member", "batch").all().order_by("-id")
    serializer_class = PointTransactionSerializer


class PointBatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PointBatch.objects.select_related("member").all().order_by("-earned_at")
    serializer_class = PointBatchSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def point_earn(request):
    s = PointEarnSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data
    try:
        member = Member.objects.get(pk=data["member"])
    except Member.DoesNotExist:
        return Response({"detail": "会员不存在"}, status=status.HTTP_404_NOT_FOUND)
    batch = PointService.earn_points(
        member, data["points"], data["source"],
        data.get("source_ref", ""), data.get("remark", ""),
    )
    if not batch:
        return Response({"detail": "积分发放失败"}, status=status.HTTP_400_BAD_REQUEST)
    return Response(PointBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def point_spend(request):
    s = PointSpendSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data
    try:
        member = Member.objects.get(pk=data["member"])
    except Member.DoesNotExist:
        return Response({"detail": "会员不存在"}, status=status.HTTP_404_NOT_FOUND)
    ok, msg = PointService.spend_points(
        member, data["points"], data.get("source", "manual"),
        data.get("source_ref", ""), data.get("remark", ""),
    )
    if not ok:
        return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"points": data["points"], "remark": msg})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def point_expire_run(request):
    count = PointService.expire_points()
    return Response({"expired_count": count})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def point_calculate_deduct(request):
    s = PointDeductCalcSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data
    try:
        member = Member.objects.get(pk=data["member"])
    except Member.DoesNotExist:
        return Response({"detail": "会员不存在"}, status=status.HTTP_404_NOT_FOUND)
    deductible, points = PointService.calculate_deductible(data["amount"], member.points_balance)
    return Response({
        "deductible_amount": float(deductible),
        "points_required": points,
        "points_balance": member.points_balance,
    })


class GrowthRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GrowthRecord.objects.select_related("member").all().order_by("-id")
    serializer_class = GrowthRecordSerializer


class LevelChangeLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LevelChangeLog.objects.select_related("member", "from_level", "to_level").all().order_by("-id")
    serializer_class = LevelChangeLogSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def level_reassess_all(request):
    changed = LevelService.batch_reassess_all()
    return Response({"changed_count": changed})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def priority_window(request):
    s = PriorityWindowSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    data = s.validated_data
    try:
        perf = Performance.objects.get(pk=data["performance_id"])
        member = Member.objects.select_related("level").get(pk=data["member_id"])
    except (Performance.DoesNotExist, Member.DoesNotExist):
        return Response({"detail": "场次或会员不存在"}, status=status.HTTP_404_NOT_FOUND)
    start, end = PriorityService.get_priority_window(perf, member)
    in_window = PriorityService.is_in_priority_window(perf, member)
    remaining_quota = PriorityService.get_remaining_quota(perf, member)
    return Response({
        "start_at": start,
        "end_at": end,
        "is_in_window": in_window,
        "remaining_quota": remaining_quota,
        "has_priority": start is not None,
    })


class PerformancePriorityQuotaViewSet(viewsets.ModelViewSet):
    queryset = PerformancePriorityQuota.objects.select_related("performance", "level").all().order_by("-id")
    serializer_class = PerformancePriorityQuotaSerializer


class MallProductViewSet(viewsets.ModelViewSet):
    queryset = MallProduct.objects.select_related("min_level").all().order_by("-id")
    serializer_class = MallProductSerializer

    @action(detail=True, methods=["get"], url_path="can-exchange")
    def can_exchange(self, request, pk=None):
        member_id = request.query_params.get("member")
        quantity = int(request.query_params.get("quantity", 1))
        if not member_id:
            return Response({"detail": "请提供会员ID"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            member = Member.objects.select_related("level").get(pk=member_id)
            product = MallProduct.objects.get(pk=pk)
        except (Member.DoesNotExist, MallProduct.DoesNotExist):
            return Response({"detail": "会员或商品不存在"}, status=status.HTTP_404_NOT_FOUND)
        ok, msg = MallService.can_exchange(member, product, quantity)
        return Response({"can_exchange": ok, "message": msg})


class MallOrderViewSet(viewsets.ModelViewSet):
    queryset = MallOrder.objects.select_related("product", "member").all().order_by("-id")
    serializer_class = MallOrderSerializer
    http_method_names = ["get", "post"]

    def get_serializer_class(self):
        if self.action == "create":
            return MallExchangeSerializer
        return MallOrderSerializer

    def create(self, request, *args, **kwargs):
        s = MallExchangeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        try:
            member = Member.objects.select_related("level").get(pk=data["member"])
            product = MallProduct.objects.get(pk=data["product"])
        except (Member.DoesNotExist, MallProduct.DoesNotExist):
            return Response({"detail": "会员或商品不存在"}, status=status.HTTP_404_NOT_FOUND)
        order, msg = MallService.exchange(member, product, data["quantity"], data.get("remark", ""))
        if not order:
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MallOrderSerializer(order).data, status=status.HTTP_201_CREATED)


class MemberCouponViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MemberCoupon.objects.select_related("member", "product").all().order_by("-id")
    serializer_class = MemberCouponSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def member_overall_stats(request):
    data = MemberStatsService.get_overall_stats()
    return Response(MemberStatsSerializer(data).data)
