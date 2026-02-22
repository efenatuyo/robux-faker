from mitmproxy import http, ctx
import asyncio
from models.state import ApplicationState
from services.http_client import HTTPClient
from services.roblox_api import RobloxAPI
from router import Router
from config import RobuxConfig, PersistenceConfig
from utils.persistence import StatePersistence

class SimpleAddon:
    def __init__(self):
        self.state = StatePersistence.load_state()
        robux_config = RobuxConfig()
        if self.state.balance.added_robux != robux_config.added_robux:
            self.state.balance.added_robux = robux_config.added_robux
            if self.state.balance.real_balance is not None:
                self.state.balance.current_balance = self.state.balance.real_balance + self.state.balance.added_robux
            StatePersistence.save_state(self.state)
        self.http_client = HTTPClient.get_instance()
        self.roblox_api = RobloxAPI(self.http_client, self.state.user.cookie, self.state.user.x_csrf_token)
        self.router = Router(self.state, self.roblox_api)
        self._save_counter = 0
        self.persistence_config = PersistenceConfig()
    
    def load(self, loader):
        ctx.log.info("SimpleAddon loaded")

    def done(self):
        ctx.log.info("SimpleAddon shutting down")
        StatePersistence.save_state(self.state)
        if self.http_client:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.http_client.close())
            except RuntimeError:
                try:
                    asyncio.get_event_loop().run_until_complete(self.http_client.close())
                except Exception:
                    pass

    async def request(self, flow: http.HTTPFlow) -> None:
        if not self.state.avatar.avatar_rules_roblox:
            self.state.avatar.avatar_rules_roblox = await self.roblox_api.avatar_rules()
        
        if not self.state.avatar.avatar_wearing and self.state.user.x_csrf_token and self.state.user.cookie:
            avatar = await self.roblox_api.current_avatar()
            if avatar:
                self.state.avatar.avatar_wearing = avatar

        url = flow.request.pretty_url

        if "roblox.com" in url:
            cookies = dict(flow.request.cookies)
            if ".ROBLOSECURITY" in cookies:
                old_cookie = self.state.user.cookie
                self.state.user.cookie = cookies[".ROBLOSECURITY"]
                self.roblox_api.cookie = self.state.user.cookie
                if old_cookie != self.state.user.cookie:
                    StatePersistence.save_state(self.state)
            x_csrf_token = flow.request.headers.get("x-csrf-token")
            if x_csrf_token:
                old_token = self.state.user.x_csrf_token
                self.state.user.x_csrf_token = x_csrf_token
                self.roblox_api.x_csrf_token = self.state.user.x_csrf_token
                if old_token != self.state.user.x_csrf_token:
                    StatePersistence.save_state(self.state)
        
        await self.router.handle_request(flow)
        
    async def response(self, flow: http.HTTPFlow) -> None:
        await self.router.handle_response(flow)

    def tick(self) -> None:
        pass

addons = [SimpleAddon()]
