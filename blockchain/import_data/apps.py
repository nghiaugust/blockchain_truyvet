from django.apps import AppConfig
import os
import threading

class ImportDataConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'import_data'
    def ready(self):
        # Chỉ chạy khi là process chính của runserver
        if os.environ.get('RUN_MAIN') == 'true':
            print('[WebSocket] Đang khởi động websocket client...')
            from . import socket
            import threading
            t = threading.Thread(target=socket.run_ws_client, daemon=True)
            t.start()