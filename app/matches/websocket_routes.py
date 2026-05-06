from fastapi import APIRouter, WebSocket

router = APIRouter()


@router.websocket("/ws/{match_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        match_id: str
):
    await websocket.accept()

    await websocket.send_json({
        "message": "Connected",
        "match_id": match_id
    })

    try:
        while True:
            data = await websocket.receive_text()

            await websocket.send_text(
                f"Live update: {data}"
            )

    except Exception:
        await websocket.close()