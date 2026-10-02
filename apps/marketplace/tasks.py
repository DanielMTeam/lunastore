"""Background tasks for marketplace app."""

import logging

from django.tasks import task
from django.utils.html import escape

from apps.core.tasks import send_telegram_notification

logger = logging.getLogger(__name__)


@task()
def moderate_review_task(review_id: int) -> None:
    """Asynchronously evaluate and moderate a review using the AI moderation service."""
    from .models import Review
    from .services.ai_moderation import moderate_review_text

    review = Review.objects.select_related("application", "user").filter(id=review_id).first()
    if not review:
        logger.warning("moderate_review_task: Review #%d not found", review_id)
        return

    # If the review already has no text, it is simply an approved rating
    if not review.text or not review.text.strip():
        if review.status != Review.STATUS_APPROVED:
            review.status = Review.STATUS_APPROVED
            review.save(update_fields=["status", "updated_at"])
        return

    result = moderate_review_text(
        text=review.text,
        app_title=review.application.title,
    )

    if result.decision == Review.STATUS_REJECTED:
        app = review.application
        logger.info(
            "AI Moderation for Review #%d: rejected (score=%s, reason=%s), deleting",
            review.id,
            result.score,
            result.reason,
        )
        review.delete()
        if app:
            app.update_rating_cache()
        return

    review.ai_score = result.score
    review.ai_flags = result.flags
    review.ai_reason = result.reason
    review.ai_raw_response = result.raw_response
    review.status = result.decision
    review.save()
    if review.status == Review.STATUS_APPROVED:
        review.application.update_rating_cache()

    logger.info(
        "AI Moderation for Review #%d: status=%s, score=%s, model=%s",
        review.id,
        result.decision,
        result.score,
        result.model_used,
    )

    # For borderline / pending cases, alert the moderators in Telegram
    if result.decision == Review.STATUS_PENDING:
        clean_preview = escape(review.text[:300])
        score_str = f"{result.score:.2f}" if result.score is not None else "N/A"
        flags_str = ", ".join(result.flags) if result.flags else "нет"

        message = (
            "📝 <b>Новый отзыв требует проверки модератором</b>\n\n"
            f"Приложение: <b>{escape(review.application.title)}</b>\n"
            f"Автор: <b>{escape(review.user.username)}</b> (Оценка: {review.rating} ★)\n"
            f"AI Скор: <code>{score_str}</code> (Флаги: {escape(flags_str)})\n"
            f"Причина: <i>{escape(result.reason or 'ручная очередь')}</i>\n\n"
            f"Текст:\n<blockquote>{clean_preview}</blockquote>"
        )
        try:
            send_telegram_notification(message)
        except Exception as exc:
            logger.warning("Failed to send telegram notification for review #%d: %s", review.id, exc)
