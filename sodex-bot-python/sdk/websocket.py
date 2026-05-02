import asyncio
import websockets
import json
from config import Config

class SodexWS:
    def __init__(self, is_spot: bool = False):
        self.is_spot = is_spot
        protocol = "spot" if is_spot else "perps"
        self.uri = f"wss://{Config.BASE_DOMAIN}/ws/{protocol}"
        self.subscriptions = []
        self.latest_data = {}
        self._running = False

    def subscribe(self, sub_obj: dict):
        self.subscriptions.append(sub_obj)

    async def start(self):
        self._running = True
        while self._running:
            try:
                async with websockets.connect(self.uri) as ws:
                    for sub in self.subscriptions:
                        await ws.send(json.dumps({"op": "subscribe", "params": sub}))
                    
                    while self._running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        topic = data.get("topic")
                        if topic:
                            self.latest_data[topic] = data.get("data", {})
            except Exception as e:
                print(f"WS Error: {e}")
                await asyncio.sleep(5)

    def get_latest(self, topic: str):
        return self.latest_data.get(topic, {})

    def stop(self):
        self._running = False
