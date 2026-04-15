from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.urls import reverse
from django.conf import settings

class LoggerService:
    @staticmethod
    def format_log_message(log_entry: LogEntry) -> str:
        action_map = {
            ADDITION: "🟢 <b>Создал(а)</b>",
            CHANGE: "🟡 <b>Изменил(а)</b>",
            DELETION: "🔴 <b>Удалил(а)</b>"
        }
        action_text = action_map.get(log_entry.action_flag, "совершил(а) действие над")

        # check metadata
        content_type = log_entry.content_type
        if content_type:
            model_name = content_type.name.capitalize()
            app_label = content_type.app_label
            model_str = content_type.model
        else:
            model_name = "Неизвестный объект"
            app_label = ""
            model_str = ""

        # base data
        object_repr = log_entry.object_repr
        object_id = log_entry.object_id
        change_message = log_entry.get_change_message() or "Без деталей"

        return (
            f"🛠 <b>Кто-то что-то сделал, и вот что я узнал на этот счет:</b>\n\n"
            f"👤 <b>Юзер:</b> {log_entry.user}\n"
            f"⚡️ <b>Действие:</b> {action_text} {model_name}\n"
            f"🏷 <b>Объект:</b> <code>{object_repr}</code> (ID: {object_id})\n"
            f"📝 <b>Детали:</b> {change_message}"
        )
