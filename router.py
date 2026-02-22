from mitmproxy import http, ctx
import json
from bs4 import BeautifulSoup
from handlers import (
    PurchaseHandler,
    InventoryHandler,
    AvatarHandler,
    TransactionHandler,
    GamePassHandler
)
from utils.persistence import StatePersistence

class Router:
    def __init__(self, state, roblox_api):
        self.state = state
        self.handlers = [
            PurchaseHandler(state, roblox_api),
            InventoryHandler(state, roblox_api),
            AvatarHandler(state, roblox_api),
            TransactionHandler(state, roblox_api),
            GamePassHandler(state, roblox_api),
        ]
    
    async def handle_request(self, flow: http.HTTPFlow) -> bool:
        for handler in self.handlers:
            try:
                if await handler.handle_request(flow):
                    return True
            except Exception as e:
                ctx.log.error(f"Handler {handler.__class__.__name__} request error: {e}")
        return False
    
    async def handle_response(self, flow: http.HTTPFlow) -> bool:
        url = flow.request.pretty_url
        
        if "economy.roblox.com/v1/users/" in url and "/currency" in url:
            if not self.state.balance.real_balance:
                try:
                    response_data = json.loads(flow.response.get_text())
                    self.state.balance.real_balance = response_data.get("robux", 0)
                    self.state.balance.current_balance = self.state.balance.real_balance + self.state.balance.added_robux
                    StatePersistence.save_state(self.state)
                except Exception as e:
                    ctx.log.error(f"currency parse error: {e}")
                    return True
            flow.response.set_text(json.dumps({"robux": self.state.balance.current_balance}))
            return True
        
        if "roblox.com" in url:
            try:
                soup = BeautifulSoup(flow.response.get_text(), "html.parser")
                div = soup.select_one("#ItemPurchaseAjaxData")
                if div:
                    if not self.state.balance.real_balance:
                        self.state.balance.real_balance = int(div.get("data-user-balance-robux", 0))
                        self.state.balance.current_balance = self.state.balance.real_balance + self.state.balance.added_robux
                        StatePersistence.save_state(self.state)
                    div["data-user-balance-robux"] = str(self.state.balance.current_balance)
                    flow.response.set_text(str(soup))
                
                meta_tag = soup.find('meta', attrs={'name': 'user-data'})
                if meta_tag:
                    old_user_id = self.state.user.user_id
                    self.state.user.user_id = meta_tag.get('data-userid')
                    self.state.user.user_name = meta_tag.get('data-name')
                    self.state.user.user_premium = meta_tag.get('data-ispremiumuser')
                    if old_user_id != self.state.user.user_id or not old_user_id:
                        StatePersistence.save_state(self.state)
            except Exception as e:
                ctx.log.debug(f"HTML parse error: {e}")
        
        for handler in self.handlers:
            try:
                if await handler.handle_response(flow):
                    return True
            except Exception as e:
                ctx.log.error(f"Handler {handler.__class__.__name__} response error: {e}")
        return False
