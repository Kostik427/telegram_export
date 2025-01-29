import os
import json
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, User
from datetime import datetime

from dotenv import load_dotenv
import os

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
SESSION_FILE = os.getenv('SESSION_FILE')
LIMIT = None if os.getenv('LIMIT') == 'None' else int(os.getenv('LIMIT'))
EXPORT_FORMAT = os.getenv('EXPORT_FORMAT')
OUTPUT_DIR = os.getenv('OUTPUT_DIR')

def save_session(session_string):
    with open(SESSION_FILE, 'w') as f:
        f.write(session_string)

def load_session():
    try:
        with open(SESSION_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

async def get_all_dialogs(client):
    print("📋 Получение списка всех диалогов...")
    
    dialogs = []
    async for dialog in client.iter_dialogs():
        try:
            if isinstance(dialog.entity, Channel):
                dialog_type = "Channel" if dialog.entity.broadcast else "Group"
            elif isinstance(dialog.entity, Chat):
                dialog_type = "Group"
            elif isinstance(dialog.entity, User):
                dialog_type = "Private Chat"
            else:
                dialog_type = "Unknown"
            
            entity = dialog.entity
            dialog_info = {
                "id": dialog.id,
                "name": dialog.name,
                "type": dialog_type,
                "entity": entity,
                "unread_count": dialog.unread_count
            }
            
            if hasattr(entity, 'username') and entity.username:
                dialog_info["username"] = entity.username
            
            dialogs.append(dialog_info)
            
        except Exception as e:
            print(f"⚠️ Ошибка при обработке диалога: {e}")
            continue
    
    return dialogs

async def export_chat_history(dialog, client):
    print(f"\n🔄 Начинаем экспорт {dialog['type']}: {dialog['name']}...")
    try:
        safe_name = "".join(x for x in dialog['name'] if x.isalnum() or x in (' ', '-', '_')).strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(OUTPUT_DIR, f"{safe_name}_{dialog['type']}_{timestamp}.{EXPORT_FORMAT}")
        
        me = await client.get_me()
        my_id = me.id
        
        messages = []
        message_count = 0
        print("Загрузка сообщений...")
        
        async for msg in client.iter_messages(dialog['entity'], limit=LIMIT):
            try:
                message_count += 1
                if message_count % 100 == 0:
                    print(f"Обработано сообщений: {message_count}")
                
                is_outgoing = msg.out
                
                if msg.sender:
                    sender_name = getattr(msg.sender, 'first_name', '') or getattr(msg.sender, 'title', '')
                    sender_username = getattr(msg.sender, 'username', '')
                    sender_info = f"{sender_name} (@{sender_username})" if sender_username else sender_name
                else:
                    sender_info = "Unknown"

                # Обработка медиафайлов
                media_info = None
                if msg.media:
                    if hasattr(msg.media, 'photo'):
                        media_info = "Photo"
                    elif hasattr(msg.media, 'document'):
                        media_info = f"Document ({getattr(msg.media.document, 'mime_type', 'unknown')})"
                    elif hasattr(msg.media, 'video'):
                        media_info = "Video"
                    elif hasattr(msg.media, 'voice'):
                        media_info = "Voice Message"
                    elif hasattr(msg.media, 'audio'):
                        media_info = "Audio"
                    else:
                        media_info = "Other media"

                messages.append({
                    "id": msg.id,
                    "date": msg.date.isoformat(),
                    "sender": sender_info,
                    "direction": "Исходящее" if is_outgoing else "Входящее",
                    "text": msg.text or "",
                    "media": media_info,
                    "forward": bool(msg.forward),
                    "reply_to": msg.reply_to.reply_to_msg_id if msg.reply_to else None,
                    "edited": bool(msg.edit_date),
                    "views": getattr(msg, 'views', None)
                })
                
            except Exception as e:
                print(f"⚠️ Ошибка при обработке сообщения: {e}")
                continue

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        if EXPORT_FORMAT == "html":
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"""
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                        .message {{ 
                            margin: 10px 0; 
                            padding: 15px; 
                            border-radius: 10px;
                            max-width: 80%;
                        }}
                        .incoming {{ 
                            background: #ffffff;
                            margin-right: 20%;
                            border-left: 4px solid #2196F3;
                        }}
                        .outgoing {{ 
                            background: #E3F2FD;
                            margin-left: 20%;
                            border-right: 4px solid #2196F3;
                        }}
                        .media {{ color: #666; margin-top: 5px; }}
                        .forward {{ color: #888; margin-top: 5px; }}
                        .reply {{ color: #0066cc; margin-top: 5px; }}
                        .edited {{ color: #888; font-style: italic; margin-top: 5px; }}
                        .views {{ color: #888; margin-top: 5px; }}
                        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 5px; }}
                    </style>
                </head>
                <body>
                <h1>{dialog['name']} ({dialog['type']})</h1>
                <p>Экспортировано: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p>Всего сообщений: {len(messages)}</p>
                """)
                
                for msg in reversed(messages):  # Показываем сообщения в хронологическом порядке
                    message_class = "outgoing" if msg["direction"] == "Исходящее" else "incoming"
                    
                    media_text = f"<div class='media'>[{msg['media']}]</div>" if msg['media'] else ""
                    forward_text = "<div class='forward'>[Переслано]</div>" if msg['forward'] else ""
                    reply_text = f"<div class='reply'>[Ответ на сообщение {msg['reply_to']}]</div>" if msg['reply_to'] else ""
                    edited_text = "<div class='edited'>[Редактировано]</div>" if msg['edited'] else ""
                    views_text = f"<div class='views'>👁 {msg['views']}</div>" if msg['views'] else ""
                    
                    f.write(f"""
                    <div class='message {message_class}'>
                        <div class='meta'>
                            {msg['date']} - {msg['sender']} ({msg['direction']})
                        </div>
                        {media_text}
                        {forward_text}
                        {reply_text}
                        {msg['text']}
                        {edited_text}
                        {views_text}
                    </div>
                    """)
                
                f.write("</body></html>")
                
        print(f"✅ Диалог сохранён в {file_path}")
        print(f"📊 Всего экспортировано сообщений: {len(messages)}")
        
    except Exception as e:
        print(f"❌ Ошибка при экспорте диалога {dialog['name']}: {e}")

async def main():
    print("🚀 Запуск Telethon-клиента...")
    
    # Загружаем или создаем сессию
    session_string = load_session()
    if session_string:
        print("✅ Найдена сохранённая сессия")
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH, system_version="4.16.30-vxCUSTOM", device_model="CustomDevice", app_version="1.0.0")
    else:
        print("📝 Создание новой сессии...")
        client = TelegramClient(StringSession(), API_ID, API_HASH, system_version="4.16.30-vxCUSTOM", device_model="CustomDevice", app_version="1.0.0")
    
    try:
        # Запускаем клиент без автоматического отключения других сессий
        await client.start()
        
        # Сохраняем сессию после успешного входа
        if not session_string:
            session_string = client.session.save()
            save_session(session_string)
            print("✅ Сессия сохранена")
        
        print("✅ Клиент успешно запущен!")
        
        dialogs = await get_all_dialogs(client)
        total_count = len(dialogs)
        print(f"\n📊 Найдено диалогов: {total_count}")
        
        # Сортируем и выводим диалоги
        dialogs_by_type = {
            "Private Chat": [],
            "Group": [],
            "Channel": [],
            "Unknown": []
        }
        
        for dialog in dialogs:
            dialogs_by_type[dialog['type']].append(dialog)
        
        for dialog_type, dialog_list in dialogs_by_type.items():
            if dialog_list:
                print(f"\n{dialog_type}s ({len(dialog_list)}):")
                for i, dialog in enumerate(dialog_list, 1):
                    unread = f"[{dialog['unread_count']} непрочитано]" if dialog['unread_count'] > 0 else ""
                    username = f" (@{dialog['username']})" if 'username' in dialog else ""
                    print(f"{i}. {dialog['name']}{username} {unread}")

        while True:
            print("\nВыберите действие:")
            print("1. Экспортировать конкретный диалог")
            print("2. Экспортировать все диалоги")
            print("0. Выход")
            
            choice = input("Ваш выбор: ")
            
            if choice == "1":
                print("\nДоступные диалоги:")
                for i, dialog in enumerate(dialogs, 1):
                    username = f" (@{dialog['username']})" if 'username' in dialog else ""
                    print(f"{i}. {dialog['name']}{username} ({dialog['type']})")
                
                try:
                    dialog_num = int(input("Введите номер диалога для экспорта (0 для отмены): "))
                    if dialog_num == 0:
                        continue
                    if 1 <= dialog_num <= len(dialogs):
                        await export_chat_history(dialogs[dialog_num-1], client)
                    else:
                        print("❌ Неверный номер диалога")
                except ValueError:
                    print("❌ Пожалуйста, введите число")
            
            elif choice == "2":
                print("\n🚀 Начинаем экспорт всех диалогов...")
                for i, dialog in enumerate(dialogs, 1):
                    print(f"\nОбработка диалога {i}/{total_count}")
                    await export_chat_history(dialog, client)
                print("✅ Экспорт всех диалогов завершён!")
                break
            
            elif choice == "0":
                break

        # Закрываем соединение без разлогина
        await client.disconnect()
        
    except Exception as e:
        print(f"❌ Ошибка при запуске клиента: {e}")

if __name__ == "__main__":
    import asyncio
    print("🔄 Запуск asyncio...")
    asyncio.run(main())
    print("🏁 Скрипт завершён!")