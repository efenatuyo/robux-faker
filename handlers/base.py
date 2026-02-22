from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from mitmproxy import http
import json
from mitmproxy import ctx
from utils.persistence import StatePersistence

class BaseHandler(ABC):
    def __init__(self, state, roblox_api):
        self.state = state
        self.roblox_api = roblox_api
    
    def save_state(self):
        StatePersistence.save_state(self.state)
    
    def parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text)
        except Exception as e:
            ctx.log.error(f"JSON parse error: {e}")
            return None
    
    def set_response_json(self, flow: http.HTTPFlow, data: Dict[str, Any]) -> None:
        try:
            flow.response.set_text(json.dumps(data))
        except Exception as e:
            ctx.log.error(f"Response set error: {e}")
    
    def set_response_text(self, flow: http.HTTPFlow, text: str) -> None:
        try:
            flow.response.set_text(text)
        except Exception as e:
            ctx.log.error(f"Response set error: {e}")
    
    def get_request_json(self, flow: http.HTTPFlow) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(flow.request.get_text())
        except Exception as e:
            ctx.log.error(f"Request JSON parse error: {e}")
            return None
    
    def set_request_json(self, flow: http.HTTPFlow, data: Dict[str, Any]) -> None:
        try:
            flow.request.set_text(json.dumps(data))
        except Exception as e:
            ctx.log.error(f"Request set error: {e}")
    
    @abstractmethod
    async def handle_request(self, flow: http.HTTPFlow) -> bool:
        pass
    
    @abstractmethod
    async def handle_response(self, flow: http.HTTPFlow) -> bool:
        pass
