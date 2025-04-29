import websocket
import json
import threading
import time

# Set your local server WebSocket URL
# Adjust the host and port if needed
RUN_ID = "your-test-run-id-here"  # Replace with an actual run_id for a running workflow
WS_URL = f"ws://localhost:8000/ws/logs/{RUN_ID}"

def on_message(ws, message):
    try:
        log = json.loads(message)
        print(f"[{log['timestamp']}] Step {log['step_id']} - {log['status'].upper()}")
        if 'output' in log:
            print(f"    Output: {log['output']}")
        if 'error' in log:
            print(f"    Error: {log['error']}")
    except Exception as e:
        print("Error parsing message:", e)

def on_error(ws, error):
    print("WebSocket Error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed:", close_status_code, close_msg)

def on_open(ws):
    print(f"✅ Connected to WebSocket: {WS_URL}")
    print(f"Listening for real-time logs for run: {RUN_ID}...\n")

def run_websocket_client():
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp(
        WS_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )
    ws.run_forever()

if __name__ == "__main__":
    print("Starting WebSocket client...")
    thread = threading.Thread(target=run_websocket_client)
    thread.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Interrupted. Closing...")
