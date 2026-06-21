import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F, Sum

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
    TicketOrder,
)


POINTS_PER_YUAN = 1
MAX_POINT_DEDUCT_RATE = Decimal("0.3")
GROWTH_PER_YUAN = 1
GROWTH_PER_ATTEND = 10
GROWTH_PERIOD_DAYS = 180


def get_today():
    return datetime.now().date()


def get_now():
    return datetime.now()


def make_midnight(d):
    return datetime(d.year, d.month, d.day, 0, 0, 0)


class PointService:
    """积分服务：分批次获取、FIFO 扣减、过期处理。"""

    @staticmethod
    def _get_rule(source):
        try:
            return PointRule.objects.get(source=source, enabled=True)
        except PointRule.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def earn_points(member, points, source, source_ref="", remark=""):
        if points <= 0:
            return None
        rule = PointService._get_rule(source)
        expire_days = rule.expire_days if rule else 365
        earned_at = get_now()
        expire_at = earned_at + timedelta(days=expire_days)
        batch = PointBatch.objects.create(
            member=member,
            source=source,
            source_ref=source_ref,
            total_points=points,
            remaining_points=points,
            earned_at=earned_at,
            expire_at=expire_at,
        )
        member.points_balance = F("points_balance") + points
        member.total_points_earned = F("total_points_earned") + points
        member.save(update_fields=["points_balance", "total_points_earned"])
        member.refresh_from_db(fields=["points_balance"])
        PointTransaction.objects.create(
            member=member,
            type="earn",
            points=points,
            balance_after=member.points_balance,
            source=source,
            source_ref=source_ref,
            batch=batch,
            remark=remark,
        )
        return batch

    @staticmethod
    @transaction.atomic
    def earn_by_purchase(member, amount, order_id):
        points = int(Decimal(str(amount)) * POINTS_PER_YUAN)
        return PointService.earn_points(
            member, points, "purchase", source_ref=str(order_id), remark="购票获得积分"
        )

    @staticmethod
    @transaction.atomic
    def earn_by_review(member):
        rule = PointService._get_rule("review")
        if not rule:
            return None
        today = get_today()
        start = make_midnight(today)
        end = start + timedelta(days=1)
        today_count = PointTransaction.objects.filter(
            member=member, source="review", created_at__gte=start, created_at__lt=end
        ).count()
        if rule.daily_limit > 0 and today_count >= rule.daily_limit:
            return None
        return PointService.earn_points(member, rule.points, "review", remark="评价演出获得积分")

    @staticmethod
    @transaction.atomic
    def earn_by_checkin(member):
        rule = PointService._get_rule("checkin")
        if not rule:
            return None
        today = get_today()
        start = make_midnight(today)
        end = start + timedelta(days=1)
        exists = PointTransaction.objects.filter(
            member=member, source="checkin", created_at__gte=start, created_at__lt=end
        ).exists()
        if exists:
            return None
        return PointService.earn_points(member, rule.points, "checkin", remark="每日签到")

    @staticmethod
    @transaction.atomic
    def earn_by_activity(member, points, activity_id="", remark=""):
        return PointService.earn_points(
            member, points, "activity", source_ref=activity_id, remark=remark or "活动奖励"
        )

    @staticmethod
    @transaction.atomic
    def earn_by_birthday(member):
        rule = PointService._get_rule("birthday")
        if not rule or not member.birthday:
            return None
        today = get_today()
        if member.birthday.month != today.month or member.birthday.day != today.day:
            return None
        year_start = datetime(today.year, 1, 1)
        year_end = datetime(today.year + 1, 1, 1)
        exists = PointTransaction.objects.filter(
            member=member, source="birthday", created_at__gte=year_start, created_at__lt=year_end
        ).exists()
        if exists:
            return None
        return PointService.earn_points(member, rule.points, "birthday", remark="生日礼积分")

    @staticmethod
    @transaction.atomic
    def spend_points(member, points, source, source_ref="", remark=""):
        if points <= 0:
            return False, "积分数量必须大于0"
        if member.points_balance < points:
            return False, "积分余额不足"
        remaining = points
        batches = PointBatch.objects.select_for_update().filter(
            member=member,
            remaining_points__gt=0,
            expired=False,
        ).order_by("expire_at")
        used_batches = []
        for batch in batches:
            if remaining <= 0:
                break
            use = min(batch.remaining_points, remaining)
            batch.remaining_points -= use
            remaining -= use
            used_batches.append((batch, use))
        if remaining > 0:
            return False, "可用积分不足"
        for batch, use in used_batches:
            batch.save(update_fields=["remaining_points"])
            PointTransaction.objects.create(
                member=member,
                type="spend",
                points=-use,
                balance_after=0,
                source=source,
                source_ref=source_ref,
                batch=batch,
                remark=remark,
            )
        member.points_balance = F("points_balance") - points
        member.total_points_spent = F("total_points_spent") + points
        member.save(update_fields=["points_balance", "total_points_spent"])
        member.refresh_from_db(fields=["points_balance"])
        PointTransaction.objects.filter(
            member=member, type="spend", balance_after=0, source=source, source_ref=source_ref
        ).update(balance_after=member.points_balance)
        return True, "ok"

    @staticmethod
    @transaction.atomic
    def refund_points(member, points, order_id):
        if points <= 0:
            return False, "积分数量必须大于0"
        txs = PointTransaction.objects.filter(
            member=member,
            type="spend",
            source="order",
            source_ref=str(order_id),
        ).select_related("batch")
        if not txs.exists():
            earned_at = get_now()
            batch = PointBatch.objects.create(
                member=member,
                source="refund_return",
                source_ref=str(order_id),
                total_points=points,
                remaining_points=points,
                earned_at=earned_at,
                expire_at=earned_at + timedelta(days=365),
            )
            PointTransaction.objects.create(
                member=member,
                type="refund",
                points=points,
                balance_after=member.points_balance + points,
                source="refund_return",
                source_ref=str(order_id),
                batch=batch,
                remark="退票返还积分",
            )
            member.points_balance = F("points_balance") + points
            member.save(update_fields=["points_balance"])
            return True, "ok"
        for tx in txs:
            if tx.batch and not tx.batch.expired:
                tx.batch.remaining_points = F("remaining_points") + abs(tx.points)
                tx.batch.save(update_fields=["remaining_points"])
            else:
                earned_at = get_now()
                new_batch = PointBatch.objects.create(
                    member=member,
                    source="refund_return",
                    source_ref=str(order_id),
                    total_points=abs(tx.points),
                    remaining_points=abs(tx.points),
                    earned_at=earned_at,
                    expire_at=earned_at + timedelta(days=365),
                )
                PointTransaction.objects.create(
                    member=member,
                    type="refund",
                    points=abs(tx.points),
                    balance_after=0,
                    source="refund_return",
                    source_ref=str(order_id),
                    batch=new_batch,
                    remark="退票返还积分",
                )
        total_returned = sum(abs(tx.points) for tx in txs)
        member.points_balance = F("points_balance") + total_returned
        member.save(update_fields=["points_balance"])
        member.refresh_from_db(fields=["points_balance"])
        PointTransaction.objects.filter(
            member=member, type="refund", balance_after=0, source_ref=str(order_id)
        ).update(balance_after=member.points_balance)
        return True, "ok"

    @staticmethod
    @transaction.atomic
    def expire_points(before=None):
        if before is None:
            before = get_now()
        expired_batches = PointBatch.objects.select_for_update().filter(
            expired=False,
            expire_at__lte=before,
            remaining_points__gt=0,
        )
        count = 0
        for batch in expired_batches:
            points = batch.remaining_points
            if points <= 0:
                continue
            batch.member.points_balance = F("points_balance") - points
            batch.member.save(update_fields=["points_balance"])
            batch.member.refresh_from_db(fields=["points_balance"])
            batch.expired = True
            batch.remaining_points = 0
            batch.save(update_fields=["expired", "remaining_points"])
            PointTransaction.objects.create(
                member=batch.member,
                type="expire",
                points=-points,
                balance_after=batch.member.points_balance,
                source="expire",
                batch=batch,
                remark="积分过期",
            )
            count += 1
        return count

    @staticmethod
    def calculate_deductible(amount, points):
        max_deduct = Decimal(str(amount)) * MAX_POINT_DEDUCT_RATE
        max_by_points = Decimal(points)
        deductible = min(max_deduct, max_by_points)
        deductible = int(deductible.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return deductible, deductible


class LevelService:
    """成长等级服务：滚动周期累计、升降级判定。"""

    @staticmethod
    def _get_period():
        today = get_today()
        period_start = today - timedelta(days=GROWTH_PERIOD_DAYS - 1)
        return period_start, today

    @staticmethod
    def determine_level(growth):
        levels = list(MemberLevel.objects.all().order_by("-level"))
        for lv in levels:
            if growth >= lv.min_growth:
                return lv
        if levels:
            return levels[-1]
        return None

    @staticmethod
    def recalculate_period_growth(member):
        period_start, _ = LevelService._get_period()
        start_dt = make_midnight(period_start)
        total = GrowthRecord.objects.filter(
            member=member, created_at__gte=start_dt
        ).aggregate(total=Sum("growth"))["total"] or 0
        member.period_growth = total
        member.save(update_fields=["period_growth"])
        return total

    @staticmethod
    @transaction.atomic
    def add_growth(member, growth, source, source_ref="", remark=""):
        if growth <= 0:
            return None
        period_start, period_end = LevelService._get_period()
        record = GrowthRecord.objects.create(
            member=member,
            source=source,
            growth=growth,
            source_ref=source_ref,
            period_start=period_start,
            period_end=period_end,
            remark=remark,
        )
        member.growth_value = F("growth_value") + growth
        member.period_growth = F("period_growth") + growth
        member.save(update_fields=["growth_value", "period_growth"])
        member.refresh_from_db(fields=["growth_value", "period_growth"])
        LevelService._check_level_change(member)
        return record

    @staticmethod
    def add_growth_by_purchase(member, amount, order_id):
        growth = int(Decimal(str(amount)) * GROWTH_PER_YUAN)
        return LevelService.add_growth(
            member, growth, "purchase", source_ref=str(order_id), remark="购票成长值"
        )

    @staticmethod
    def add_growth_by_attend(member, attend_id=""):
        return LevelService.add_growth(
            member, GROWTH_PER_ATTEND, "attend", source_ref=str(attend_id), remark="观演成长值"
        )

    @staticmethod
    @transaction.atomic
    def _check_level_change(member):
        new_level = LevelService.determine_level(member.period_growth)
        if not new_level:
            return
        old_level = member.level
        if new_level.pk == old_level.pk:
            return
        direction = "upgrade" if new_level.level > old_level.level else "downgrade"
        LevelChangeLog.objects.create(
            member=member,
            direction=direction,
            from_level=old_level,
            to_level=new_level,
            growth_before=member.growth_value,
            growth_after=member.growth_value,
            remark=f"{old_level.name} → {new_level.name}",
        )
        member.level = new_level
        member.save(update_fields=["level"])

    @staticmethod
    @transaction.atomic
    def batch_reassess_all():
        members = Member.objects.select_related("level").all()
        changed = 0
        for m in members:
            LevelService.recalculate_period_growth(m)
            old_level_id = m.level_id
            LevelService._check_level_change(m)
            m.refresh_from_db(fields=["level"])
            if m.level_id != old_level_id:
                changed += 1
        return changed


class PriorityService:
    """优先购服务：窗口校验、配额扣减。"""

    @staticmethod
    def get_priority_window(performance, member):
        if not performance.priority_start_at:
            return None, None
        level = member.level
        if level.priority_hours <= 0:
            return None, None
        start = performance.priority_start_at
        end = start + timedelta(hours=level.priority_hours)
        return start, end

    @staticmethod
    def is_in_priority_window(performance, member):
        start, end = PriorityService.get_priority_window(performance, member)
        if not start or not end:
            return False
        now = get_now()
        return start <= now <= end

    @staticmethod
    def get_remaining_quota(performance, member):
        level = member.level
        try:
            quota = PerformancePriorityQuota.objects.get(
                performance=performance, level=level
            )
            return max(0, quota.total_quota - quota.used_quota)
        except PerformancePriorityQuota.DoesNotExist:
            return level.priority_quota

    @staticmethod
    @transaction.atomic
    def consume_quota(performance, member, quantity):
        level = member.level
        if level.priority_hours <= 0:
            return False, "该等级无优先购权益"
        if not PriorityService.is_in_priority_window(performance, member):
            return False, "不在优先购窗口"
        quota, _created = PerformancePriorityQuota.objects.get_or_create(
            performance=performance,
            level=level,
            defaults={"total_quota": level.priority_quota, "used_quota": 0},
        )
        remaining = quota.total_quota - quota.used_quota
        if quantity > remaining:
            return False, "优先购配额不足"
        PerformancePriorityQuota.objects.filter(pk=quota.pk).update(
            used_quota=F("used_quota") + quantity
        )
        return True, "ok"

    @staticmethod
    @transaction.atomic
    def release_quota(performance, member, quantity):
        level = member.level
        try:
            quota = PerformancePriorityQuota.objects.get(
                performance=performance, level=level
            )
            PerformancePriorityQuota.objects.filter(pk=quota.pk).update(
                used_quota=F("used_quota") - quantity
            )
            return True
        except PerformancePriorityQuota.DoesNotExist:
            return True


class MallService:
    """权益商城服务：兑换（并发一致）。"""

    @staticmethod
    def _generate_coupon_code():
        return uuid.uuid4().hex[:12].upper()

    @staticmethod
    def can_exchange(member, product, quantity=1):
        if not product.enabled:
            return False, "商品已下架"
        if product.min_level and member.level.level < product.min_level.level:
            return False, f"需要{product.min_level.name}及以上等级"
        if product.limit_per_member > 0:
            exchanged = MallOrder.objects.filter(
                member=member, product=product, status="completed"
            ).aggregate(total=Sum("quantity"))["total"] or 0
            if exchanged + quantity > product.limit_per_member:
                return False, "超过限兑次数"
        if product.stock < quantity:
            return False, "库存不足"
        total_points = product.point_price * quantity
        if member.points_balance < total_points:
            return False, "积分不足"
        return True, "ok"

    @staticmethod
    @transaction.atomic
    def exchange(member, product, quantity=1, remark=""):
        ok, msg = MallService.can_exchange(member, product, quantity)
        if not ok:
            return None, msg
        total_points = product.point_price * quantity
        updated = MallProduct.objects.filter(
            pk=product.pk, stock__gte=quantity
        ).update(stock=F("stock") - quantity)
        if updated == 0:
            return None, "库存不足"
        ok, msg = PointService.spend_points(
            member, total_points, "mall_exchange", source_ref="", remark=f"兑换{product.name}"
        )
        if not ok:
            MallProduct.objects.filter(pk=product.pk).update(stock=F("stock") + quantity)
            return None, msg
        order = MallOrder.objects.create(
            member=member,
            product=product,
            quantity=quantity,
            point_price=product.point_price,
            total_points=total_points,
            status="completed",
            remark=remark,
        )
        last_code = ""
        last_expire = None
        if product.type == "coupon":
            for _ in range(quantity):
                code = MallService._generate_coupon_code()
                expire_at = get_now() + timedelta(days=product.coupon_valid_days or 30)
                MemberCoupon.objects.create(
                    member=member,
                    product=product,
                    code=code,
                    discount=product.coupon_discount,
                    amount=product.coupon_amount,
                    expire_at=expire_at,
                    mall_order=order,
                )
                last_code = code
                last_expire = expire_at
            order.coupon_code = last_code
            order.coupon_expire_at = last_expire
            order.save(update_fields=["coupon_code", "coupon_expire_at"])
        return order, "ok"


class OrderService:
    """订单服务：积分抵扣下单、退票。"""

    @staticmethod
    @transaction.atomic
    def create_order_with_points(
        performance, member, customer_name, phone, quantity,
        use_points=True, is_priority=False
    ):
        remaining = performance.total_seats - performance.sold_seats
        if quantity > remaining:
            return None, "余票不足"
        base_amount = Decimal(str(performance.price)) * quantity
        if is_priority:
            ok, msg = PriorityService.consume_quota(performance, member, quantity)
            if not ok:
                return None, msg
        discount_rate = Decimal(str(member.level.discount_rate))
        discounted_amount = (base_amount * discount_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        points_used = 0
        point_amount = Decimal("0")
        cash_amount = discounted_amount
        if use_points and member.points_balance > 0:
            deductible, pts = PointService.calculate_deductible(discounted_amount, member.points_balance)
            if deductible > 0:
                ok, msg = PointService.spend_points(
                    member, pts, "order", source_ref="", remark="购票积分抵扣"
                )
                if ok:
                    points_used = pts
                    point_amount = Decimal(deductible)
                    cash_amount = discounted_amount - point_amount
        Performance.objects.filter(pk=performance.pk).update(
            sold_seats=F("sold_seats") + quantity
        )
        order = TicketOrder.objects.create(
            performance=performance,
            member=member,
            customer_name=customer_name,
            phone=phone,
            quantity=quantity,
            amount=discounted_amount,
            cash_amount=cash_amount,
            point_amount=point_amount,
            points_used=points_used,
            channel="priority" if is_priority else "normal",
            status="paid",
        )
        PointTransaction.objects.filter(
            member=member, type="spend", source="order", balance_after=0
        ).update(source_ref=str(order.id))
        member.total_orders = F("total_orders") + 1
        member.total_amount = F("total_amount") + cash_amount
        member.save(update_fields=["total_orders", "total_amount"])
        PointService.earn_by_purchase(member, cash_amount, order.id)
        LevelService.add_growth_by_purchase(member, cash_amount, order.id)
        return order, "ok"

    @staticmethod
    @transaction.atomic
    def refund_order(order):
        if order.status not in ("paid",):
            return False, "订单状态不支持退票"
        if order.member:
            if order.member.free_refund_used < order.member.level.free_refund_count:
                order.member.free_refund_used = F("free_refund_used") + 1
                order.member.save(update_fields=["free_refund_used"])
            if order.points_used > 0:
                PointService.refund_points(order.member, order.points_used, order.id)
            if order.channel == "priority":
                PriorityService.release_quota(order.performance, order.member, order.quantity)
        Performance.objects.filter(pk=order.performance_id).update(
            sold_seats=F("sold_seats") - order.quantity
        )
        order.status = "refunded"
        order.save(update_fields=["status"])
        return True, "ok"


class MemberStatsService:
    """会员统计与画像服务。"""

    @staticmethod
    def get_member_portrait(member):
        period_start = get_today() - timedelta(days=90)
        start_dt = make_midnight(period_start)
        recent_orders = member.orders.filter(status="paid", created_at__gte=start_dt)
        recent_amount = recent_orders.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        recent_count = recent_orders.count()
        genre_counts = {}
        for o in recent_orders.select_related("performance__show"):
            genre = o.performance.show.genre
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
        top_genre = max(genre_counts, key=genre_counts.get) if genre_counts else ""
        active_days = (get_now() - member.last_active_at).days
        if active_days <= 7:
            activity = "high"
        elif active_days <= 30:
            activity = "medium"
        else:
            activity = "low"
        return {
            "member_id": member.id,
            "level_name": member.level.name,
            "growth_value": member.growth_value,
            "points_balance": member.points_balance,
            "total_orders": member.total_orders,
            "total_amount": float(member.total_amount),
            "total_attended": member.total_attended,
            "recent_90d_orders": recent_count,
            "recent_90d_amount": float(recent_amount),
            "top_genre": top_genre,
            "activity_level": activity,
            "days_since_last_active": active_days,
            "joined_days": (get_today() - member.joined_at.date()).days,
        }

    @staticmethod
    def get_overall_stats():
        total_members = Member.objects.count()
        level_stats = []
        for lv in MemberLevel.objects.all():
            level_stats.append({
                "level_id": lv.id,
                "level_name": lv.name,
                "count": lv.members.count(),
            })
        total_points_earned = PointTransaction.objects.filter(type="earn").aggregate(
            total=Sum("points"))["total"] or 0
        total_points_spent = PointTransaction.objects.filter(type="spend").aggregate(
            total=Sum("points"))["total"] or 0
        total_points_expired = PointTransaction.objects.filter(type="expire").aggregate(
            total=Sum("points"))["total"] or 0
        today = get_today()
        start_dt = make_midnight(today)
        month_start = datetime(today.year, today.month, 1)
        new_members_month = Member.objects.filter(joined_at__gte=month_start).count()
        new_members_today = Member.objects.filter(joined_at__gte=start_dt).count()
        mall_total = MallOrder.objects.filter(status="completed").count()
        mall_points = MallOrder.objects.filter(status="completed").aggregate(
            total=Sum("total_points"))["total"] or 0
        return {
            "total_members": total_members,
            "level_distribution": level_stats,
            "total_points_earned": total_points_earned,
            "total_points_spent": abs(total_points_spent),
            "total_points_expired": abs(total_points_expired),
            "new_members_today": new_members_today,
            "new_members_this_month": new_members_month,
            "mall_orders_total": mall_total,
            "mall_points_total": mall_points,
        }
