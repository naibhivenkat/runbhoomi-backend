from fastapi import WebSocket

async def live_score(websocket:WebSocket):
    await websocket.accept()
    while True:
        data=await websocket.receive_text()
        await websocket.send_text(data)
