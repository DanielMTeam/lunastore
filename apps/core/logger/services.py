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

        admin_url = ""
        if content_type and object_id and log_entry.action_flag != DELETION:
            try:
                url_path = reverse(f"admin:{app_label}_{model_str}_change", args=[object_id])
                # try to build a full URL if we can
                base_domain = getattr(settings, 'LUNASPIRE_URL_WITHOUT_PROTO', 'lunastore.app')
                admin_url = f"\n🔗 <b>Ссылка:</b> <a href='https://{base_domain}{url_path}'>Перейти в админку</a>"
            except Exception:
                pass

        # check for approvals (status changed to approved)
        if log_entry.action_flag == CHANGE and 'status' in change_message.lower() and 'approved' in change_message.lower():
            action_text = "✅ <b>Одобрил(а) заявку:</b>"

        if change_message.startswith("Вход в систему"):
            ip = change_message.split("IP: ")[1].strip(")") if "IP: " in change_message else "Неизвестен"
            return (
                f"🔓 <b>Успешный вход в LunaStore:</b>\n\n"
                f"👤 <b>Пользователь:</b> {log_entry.user}\n"
                f"🌐 <b>IP-адрес:</b> {ip}"
            )
            
        if change_message.startswith("Неудачная попытка входа"):
            ip = change_message.split("IP: ")[1].strip(")") if "IP: " in change_message else "Неизвестен"
            return (
                f"🚨 <b>Неудачная попытка входа:</b>\n\n"
                f"👤 <b>Пользователь:</b> {log_entry.user}\n"
                f"🌐 <b>IP-адрес:</b> {ip}"
            )

        return (
            f"🛠 <b>Кто-то что-то сделал и вот что я узнал на этот счет:</b>\n\n"
            f"👤 <b>Юзер:</b> {log_entry.user}\n"
            f"⚡️ <b>Действие:</b> {action_text} {model_name}\n"
            f"🏷 <b>Объект:</b> <code>{object_repr}</code> (ID: {object_id})\n"
            f"📝 <b>Детали:</b> {change_message}{admin_url}"
        )
