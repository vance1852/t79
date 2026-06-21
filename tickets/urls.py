from django.http import JsonResponse
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    GrowthRecordViewSet,
    LevelChangeLogViewSet,
    LoginView,
    MallOrderViewSet,
    MallProductViewSet,
    MemberCouponViewSet,
    MemberLevelViewSet,
    MemberViewSet,
    OrderViewSet,
    PerformancePriorityQuotaViewSet,
    PerformanceViewSet,
    PointBatchViewSet,
    PointRuleViewSet,
    PointTransactionViewSet,
    ShowViewSet,
    dashboard_stats,
    level_reassess_all,
    me,
    member_overall_stats,
    point_calculate_deduct,
    point_earn,
    point_expire_run,
    point_spend,
    priority_window,
)


def health(_request):
    return JsonResponse({"status": "ok", "service": "show-ticketing-admin"})


router = DefaultRouter(trailing_slash=False)
router.register("shows", ShowViewSet)
router.register("performances", PerformanceViewSet)
router.register("orders", OrderViewSet)
router.register("member-levels", MemberLevelViewSet)
router.register("members", MemberViewSet)
router.register("point-rules", PointRuleViewSet)
router.register("point-transactions", PointTransactionViewSet)
router.register("point-batches", PointBatchViewSet)
router.register("growth-records", GrowthRecordViewSet)
router.register("level-change-logs", LevelChangeLogViewSet)
router.register("priority-quotas", PerformancePriorityQuotaViewSet)
router.register("mall-products", MallProductViewSet)
router.register("mall-orders", MallOrderViewSet)
router.register("member-coupons", MemberCouponViewSet)

urlpatterns = [
    path("health", health),
    path("auth/login", LoginView.as_view()),
    path("auth/me", me),
    path("dashboard/stats", dashboard_stats),
    path("points/earn", point_earn),
    path("points/spend", point_spend),
    path("points/expire", point_expire_run),
    path("points/calculate-deduct", point_calculate_deduct),
    path("levels/reassess-all", level_reassess_all),
    path("priority/window", priority_window),
    path("members/stats/overall", member_overall_stats),
]

urlpatterns += router.urls
