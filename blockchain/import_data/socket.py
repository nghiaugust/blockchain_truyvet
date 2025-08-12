import websocket
import json
import os
from .views import _process_single_block

# Đường dẫn lưu file block
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

def on_message(ws, message):
    try:
        block = json.loads(message)
        height = block.get('height')
        # Bổ sung n_tx nếu thiếu
        if 'n_tx' not in block and 'txs' in block:
            block['n_tx'] = len(block['txs'])
        if not height:
            print('[WebSocket] Block JSON thiếu trường height')
            return
        filename = f"block_{height}.json"
        file_path = os.path.join(DATA_DIR, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(block, f, ensure_ascii=False, indent=2)
        print(f"[WebSocket] Đã nhận và lưu block {height} vào {file_path}")
        # Gọi hàm import block
        try:
            block_hash = _process_single_block(block)
            if block_hash:
                print(f"[WebSocket] Import thành công block {height} (hash: {block_hash})")
            else:
                print(f"[WebSocket] Block {height} đã tồn tại, bỏ qua import")
        except Exception as e:
            print(f"[WebSocket] Lỗi khi import block {height}: {str(e)}")
    except Exception as e:
        print(f"[WebSocket] Lỗi khi xử lý message: {str(e)}")

def on_error(ws, error):
    print(f"[WebSocket] Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("[WebSocket] Connection closed")

def on_open(ws):
    print("[WebSocket] Connection opened")

def run_ws_client():
    ws = websocket.WebSocketApp(
        "ws://localhost:8080/ws",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()