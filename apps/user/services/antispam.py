import ipaddress
import logging
import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from constance import config
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.core.utils import get_country_code
from apps.user.models import NoSpamEvent, NoSpamRule, User, UserBan

logger = logging.getLogger("user")

NOSPAM_RULES_CACHE_KEY = "nospam_rules_v1"
NOSPAM_SHIELD_CACHE_KEY = "nospam_shield_blocked_until"


@dataclass
class NoSpamContext:
    entrypoint: str
    ip: str | None = None
    email: str = ""
    username: str = ""
    user_agent: str = ""
    invite_code: str = ""
    user: User | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class NoSpamDecision:
    matched_rules: list[NoSpamRule] = field(default_factory=list)
    action: str = NoSpamRule.RuleAction.LOG
    reason: str = ""
    matched_value: str = ""

    @property
    def should_block(self) -> bool:
        return self.action in {NoSpamRule.RuleAction.BAN, NoSpamRule.RuleAction.DELETE}


class AntiSpamService:
    ACTION_WEIGHT = {
        NoSpamRule.RuleAction.LOG: 0,
        NoSpamRule.RuleAction.BAN: 1,
        NoSpamRule.RuleAction.DELETE: 2,
    }

    @classmethod
    def evaluate(cls, context: NoSpamContext) -> NoSpamDecision:
        if not getattr(config, "NOSPAM_ENABLED", False):
            return NoSpamDecision()

        if cls._is_shield_blocked():
            return NoSpamDecision(
                action=NoSpamRule.RuleAction.BAN,
                reason="shield mode active",
                matched_value=context.ip or "",
            )

        cls._update_shield_signals(context)

        matched_rules: list[NoSpamRule] = []
        for rule in cls._get_rules():
            try:
                if not rule.applies_to_entrypoint(context.entrypoint):
                    continue
                is_match, matched_value = cls._match_rule(rule, context)
                if is_match:
                    matched_rules.append(rule)
                    cls._store_event(
                        context=context,
                        rule=rule,
                        action=rule.action,
                        reason=rule.reason_template,
                        matched_value=matched_value,
                    )
            except Exception as exc:
                logger.exception("failed to evaluate noSpam rule id=%s: %s", rule.id, exc)
                cls._store_event(
                    context=context,
                    rule=rule,
                    action=NoSpamRule.RuleAction.LOG,
                    reason=f"rule_evaluation_error: {exc}",
                    matched_value="",
                )

        if not matched_rules:
            return NoSpamDecision()

        final_rule = min(
            matched_rules,
            key=lambda item: (-cls.ACTION_WEIGHT.get(item.action, 0), item.priority, -item.id),
        )
        return NoSpamDecision(
            matched_rules=matched_rules,
            action=final_rule.action,
            reason=final_rule.reason_template,
            matched_value=final_rule.pattern,
        )

    @classmethod
    def apply_decision(
        cls,
        context: NoSpamContext,
        decision: NoSpamDecision,
        target_user: User | None = None,
        target_object: Any | None = None,
    ) -> NoSpamDecision:
        if not getattr(config, "NOSPAM_ENABLED", False):
            return decision

        if not decision.matched_rules and not decision.reason:
            return decision

        rule = decision.matched_rules[0] if decision.matched_rules else None

        if decision.action == NoSpamRule.RuleAction.BAN:
            cls._apply_ban(context=context, rule=rule, target_user=target_user)
        elif decision.action == NoSpamRule.RuleAction.DELETE:
            cls._apply_delete(target_user=target_user, target_object=target_object)

        cls._store_event(
            context=context,
            rule=rule,
            action=decision.action,
            reason=decision.reason or "noSpam decision applied",
            matched_value=decision.matched_value,
        )
        return decision

    @classmethod
    def evaluate_and_apply(
        cls,
        context: NoSpamContext,
        target_user: User | None = None,
        target_object: Any | None = None,
    ) -> NoSpamDecision:
        decision = cls.evaluate(context)
        return cls.apply_decision(
            context=context,
            decision=decision,
            target_user=target_user,
            target_object=target_object,
        )

    @classmethod
    def _get_rules(cls) -> list[NoSpamRule]:
        ttl = int(getattr(config, "NOSPAM_CACHE_TTL", 300))
        cached = cache.get(NOSPAM_RULES_CACHE_KEY)
        if cached is not None:
            return cached
        rules = list(NoSpamRule.objects.filter(is_enabled=True).order_by("priority", "-id"))
        cache.set(NOSPAM_RULES_CACHE_KEY, rules, ttl)
        return rules

    @classmethod
    def _match_rule(cls, rule: NoSpamRule, context: NoSpamContext) -> tuple[bool, str]:
        email = context.email.lower().strip()
        username = context.username.lower().strip()
        user_agent = context.user_agent.strip()
        ip_value = context.ip or ""

        if rule.match_type == NoSpamRule.MatchType.EMAIL_DOMAIN:
            if "@" not in email:
                return False, ""
            domain = email.rsplit("@", 1)[1]
            return domain == rule.pattern.lower().strip(), domain

        if rule.match_type == NoSpamRule.MatchType.EMAIL_REGEX:
            return cls._safe_regex_match(rule.pattern, email), email

        if rule.match_type == NoSpamRule.MatchType.USERNAME_REGEX:
            return cls._safe_regex_match(rule.pattern, username), username

        if rule.match_type == NoSpamRule.MatchType.USER_AGENT_REGEX:
            return cls._safe_regex_match(rule.pattern, user_agent), user_agent

        if rule.match_type == NoSpamRule.MatchType.COUNTRY_CODE:
            if not ip_value:
                return False, ""
            country = get_country_code(ip_value)
            return country.upper() == rule.pattern.upper(), country

        if rule.match_type == NoSpamRule.MatchType.IP_CIDR:
            if not ip_value:
                return False, ""
            try:
                network = ipaddress.ip_network(rule.pattern.strip(), strict=False)
                ip_obj = ipaddress.ip_address(ip_value)
            except ValueError:
                return False, ""
            return ip_obj in network, ip_value

        if rule.match_type == NoSpamRule.MatchType.INVITE_PATTERN:
            invite_code = context.invite_code.strip()
            if not invite_code:
                return False, ""
            return cls._safe_regex_match(rule.pattern, invite_code), invite_code

        if rule.match_type == NoSpamRule.MatchType.USER_ID_RANGE:
            if context.user is None:
                return False, ""
            parsed_range = cls._parse_user_id_range(rule.pattern)
            if parsed_range is None:
                return False, ""
            min_id, max_id = parsed_range
            user_id = context.user.pk
            if user_id is None:
                return False, ""
            return min_id <= user_id <= max_id, str(user_id)

        if rule.match_type == NoSpamRule.MatchType.REQUEST_RATE_SIGNAL:
            if not ip_value:
                return False, ""
            max_hits = int(rule.payload.get("max_hits", 10))
            window_seconds = int(rule.payload.get("window_seconds", 60))
            signal_key = f"nospam_rate_{context.entrypoint}_{ip_value}_{rule.id}"
            hits = cache.get(signal_key, 0)
            if hits == 0:
                cache.set(signal_key, 1, window_seconds)
                return False, ""
            try:
                hits = cache.incr(signal_key)
            except ValueError:
                cache.set(signal_key, 1, window_seconds)
                hits = 1
            return hits >= max_hits, str(hits)

        return False, ""

    @classmethod
    def _apply_ban(cls, context: NoSpamContext, rule: NoSpamRule | None, target_user: User | None) -> None:
        if target_user is None:
            return
        is_permanent = bool(rule.is_permanent) if rule else False
        expires_at = None
        if not is_permanent:
            minutes = int(rule.ban_duration_minutes) if rule else 60
            expires_at = timezone.now() + timedelta(minutes=minutes)

        reason_text = rule.reason_template if rule else "noSpam auto-ban"
        with transaction.atomic():
            target_user.is_active = False
            target_user.save(update_fields=["is_active"])
            ban_values = {
                "reason": reason_text,
                "is_permanent": is_permanent,
                "expires_at": expires_at,
            }
            if rule and rule.ban_by_ip and context.ip:
                ban_values["ban_by_ip"] = True
                ban_values["ip"] = context.ip

            existing_ban = UserBan.objects.filter(user=target_user).order_by("-created_at").first()
            if existing_ban is None:
                UserBan.objects.create(user=target_user, **ban_values)
            else:
                for field_name, field_value in ban_values.items():
                    setattr(existing_ban, field_name, field_value)
                existing_ban.save(update_fields=list(ban_values.keys()))

    @classmethod
    def _apply_delete(cls, target_user: User | None, target_object: Any | None) -> None:
        if target_object is not None:
            target_object.delete()
            return
        if target_user is not None:
            target_user.delete()

    @classmethod
    def _store_event(
        cls,
        context: NoSpamContext,
        rule: NoSpamRule | None,
        action: str,
        reason: str,
        matched_value: str,
    ) -> None:
        try:
            NoSpamEvent.objects.create(
                rule=rule,
                user=context.user,
                entrypoint=context.entrypoint,
                action=action,
                reason=reason[:255],
                ip=context.ip,
                matched_value=matched_value[:255],
                context=context.extra,
            )
        except Exception as exc:
            logger.exception("failed to write noSpam event: %s", exc)

    @staticmethod
    def _parse_user_id_range(pattern: str) -> tuple[int, int] | None:
        raw_value = pattern.strip()
        if not raw_value:
            return None
        for separator in (":", "-", ".."):
            if separator in raw_value:
                left, right = raw_value.split(separator, 1)
                try:
                    min_id = int(left.strip())
                    max_id = int(right.strip())
                except ValueError:
                    return None
                if min_id > max_id:
                    min_id, max_id = max_id, min_id
                return min_id, max_id
        try:
            single_id = int(raw_value)
            return single_id, single_id
        except ValueError:
            return None

    @staticmethod
    def _safe_regex_match(pattern: str, value: str) -> bool:
        try:
            return bool(re.search(pattern, value, re.IGNORECASE))
        except re.error:
            return False

    @classmethod
    def clear_rules_cache(cls) -> None:
        cache.delete(NOSPAM_RULES_CACHE_KEY)

    @classmethod
    def _is_shield_blocked(cls) -> bool:
        blocked_until = cache.get(NOSPAM_SHIELD_CACHE_KEY)
        if blocked_until is None:
            return False
        return timezone.now().timestamp() < blocked_until

    @classmethod
    def _set_shield_block(cls, minutes: int) -> None:
        blocked_until = timezone.now() + timedelta(minutes=minutes)
        cache.set(NOSPAM_SHIELD_CACHE_KEY, blocked_until.timestamp(), minutes * 60)

    @classmethod
    def _update_shield_signals(cls, context: NoSpamContext) -> None:
        if not getattr(config, "NOSPAM_SHIELD_ENABLED", True):
            return
        ip_limit = int(getattr(config, "NOSPAM_SHIELD_REG_PER_MIN", 20))
        domain_limit = int(getattr(config, "NOSPAM_SHIELD_DOMAIN_PER_MIN", 30))
        ua_limit = int(getattr(config, "NOSPAM_SHIELD_UA_PER_MIN", 40))
        block_minutes = int(getattr(config, "NOSPAM_SHIELD_BLOCK_MINUTES", 15))
        window_seconds = 60

        if context.entrypoint not in {"register", "login", "jwt_token"}:
            return

        if context.ip:
            if cls._bump_counter(f"shield_ip_{context.ip}", window_seconds) >= ip_limit:
                cls._set_shield_block(block_minutes)
                return

        if "@" in context.email:
            domain = context.email.lower().rsplit("@", 1)[1]
            if cls._bump_counter(f"shield_domain_{domain}", window_seconds) >= domain_limit:
                cls._set_shield_block(block_minutes)
                return

        if context.user_agent:
            ua_hash = hash(context.user_agent) % 1000000
            if cls._bump_counter(f"shield_ua_{ua_hash}", window_seconds) >= ua_limit:
                cls._set_shield_block(block_minutes)

    @staticmethod
    def _bump_counter(counter_key: str, ttl: int) -> int:
        cached = cache.get(counter_key, 0)
        if cached == 0:
            cache.set(counter_key, 1, ttl)
            return 1
        try:
            return int(cache.incr(counter_key))
        except ValueError:
            cache.set(counter_key, 1, ttl)
            return 1

    @classmethod
    def find_users_by_filter(
        cls,
        match_type: str,
        pattern: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[Any, str]:
        """Find existing users matching a single ad-hoc filter."""
        from django.db.models import QuerySet
        from apps.user.models import InviteToken, UserActivityLog, UserSession

        payload = payload or {}
        pattern_value = pattern.strip()
        empty_qs: QuerySet[User] = User.objects.none()

        if not pattern_value and match_type != NoSpamRule.MatchType.REQUEST_RATE_SIGNAL:
            return empty_qs, pattern_value

        if match_type == NoSpamRule.MatchType.EMAIL_DOMAIN:
            domain = pattern_value.lower()
            return User.objects.filter(email__iendswith=f"@{domain}").distinct(), domain

        if match_type == NoSpamRule.MatchType.EMAIL_REGEX:
            return User.objects.filter(email__iregex=pattern_value).distinct(), pattern_value

        if match_type == NoSpamRule.MatchType.USERNAME_REGEX:
            return User.objects.filter(username__iregex=pattern_value).distinct(), pattern_value

        if match_type == NoSpamRule.MatchType.USER_AGENT_REGEX:
            user_ids = UserSession.objects.filter(
                user_agent__iregex=pattern_value,
            ).values_list("user_id", flat=True)
            return User.objects.filter(id__in=user_ids).distinct(), pattern_value

        if match_type == NoSpamRule.MatchType.IP_CIDR:
            try:
                network = ipaddress.ip_network(pattern_value, strict=False)
            except ValueError:
                return empty_qs, pattern_value
            matched_ids: set[int] = set()
            for user_id, ip_value in UserActivityLog.objects.values_list("user_id", "ip").distinct():
                if not ip_value:
                    continue
                try:
                    if ipaddress.ip_address(ip_value) in network:
                        matched_ids.add(user_id)
                except ValueError:
                    continue
            return User.objects.filter(id__in=matched_ids).distinct(), pattern_value

        if match_type == NoSpamRule.MatchType.COUNTRY_CODE:
            target_country = pattern_value.upper()
            matched_ids = set()
            for user_id, ip_value in UserActivityLog.objects.values_list("user_id", "ip").distinct():
                if not ip_value:
                    continue
                if get_country_code(ip_value).upper() == target_country:
                    matched_ids.add(user_id)
            return User.objects.filter(id__in=matched_ids).distinct(), pattern_value

        if match_type == NoSpamRule.MatchType.INVITE_PATTERN:
            owner_ids = InviteToken.objects.filter(
                code__iregex=pattern_value,
            ).values_list("owner_id", flat=True)
            return User.objects.filter(invited_by_id__in=owner_ids).distinct(), pattern_value

        if match_type == NoSpamRule.MatchType.USER_ID_RANGE:
            parsed_range = cls._parse_user_id_range(pattern_value)
            if parsed_range is None:
                return empty_qs, pattern_value
            min_id, max_id = parsed_range
            matched_label = f"{min_id}:{max_id}"
            return (
                User.objects.filter(id__gte=min_id, id__lte=max_id).distinct(),
                matched_label,
            )

        if match_type == NoSpamRule.MatchType.REQUEST_RATE_SIGNAL:
            return empty_qs, pattern_value

        return empty_qs, pattern_value

    @classmethod
    def apply_mass_action(
        cls,
        users: list[User],
        action: str,
        reason: str,
        matched_value: str = "",
        ban_by_ip: bool = False,
        is_permanent: bool = False,
        ban_duration_minutes: int = 60,
    ) -> dict[str, int]:
        """Apply selected action to users found by mass scan."""
        from types import SimpleNamespace
        from apps.user.models import UserActivityLog

        stats = {"processed": 0, "banned": 0, "deleted": 0, "logged": 0}
        for user in users:
            context = NoSpamContext(
                entrypoint="admin_mass_scan",
                user=user,
                email=user.email,
                username=user.username,
            )
            if ban_by_ip:
                latest_log = UserActivityLog.objects.filter(user=user).order_by("-timestamp").first()
                if latest_log:
                    context.ip = latest_log.ip

            if action == NoSpamRule.RuleAction.BAN:
                ban_rule = SimpleNamespace(
                    is_permanent=is_permanent,
                    ban_duration_minutes=ban_duration_minutes,
                    ban_by_ip=ban_by_ip,
                    reason_template=reason,
                )
                cls._apply_ban(context=context, rule=ban_rule, target_user=user)
                stats["banned"] += 1
            elif action == NoSpamRule.RuleAction.LOG:
                stats["logged"] += 1

            cls._store_event(
                context=context,
                rule=None,
                action=action,
                reason=reason,
                matched_value=matched_value,
            )

            if action == NoSpamRule.RuleAction.DELETE:
                cls._apply_delete(target_user=user, target_object=None)
                stats["deleted"] += 1

            stats["processed"] += 1
        return stats
