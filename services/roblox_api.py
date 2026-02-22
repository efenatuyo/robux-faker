import asyncio
import io
from typing import Optional, Dict, Any, List
from PIL import Image
from mitmproxy import ctx
from services.http_client import HTTPClient
from config import HTTPConfig

class RobloxAPI:
    def __init__(self, http_client: HTTPClient, cookie: Optional[str] = None, x_csrf_token: Optional[str] = None):
        self.http_client = http_client
        self.cookie = cookie
        self.x_csrf_token = x_csrf_token
        self._config = HTTPConfig()
    
    async def avatar_rules(self) -> Optional[Dict[str, Any]]:
        await self.http_client.ensure_session()
        url = "https://avatar.roblox.com/v1/avatar-rules"
        try:
            async with self.http_client.session.get(url) as r:
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            ctx.log.error(f"avatar rules error: {e}")
            return None
    
    async def resellers(self, uuid: str) -> Optional[Dict[str, Any]]:
        await self.http_client.ensure_session()
        url = f"https://apis.roblox.com/marketplace-sales/v1/item/{uuid}/resellers?cursor=&limit=100"
        headers = {"x-csrf-token": self.x_csrf_token} if self.x_csrf_token else {}
        cookies = {".ROBLOSECURITY": self.cookie} if self.cookie else None
        try:
            async with self.http_client.session.get(url, headers=headers, cookies=cookies) as r:
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            ctx.log.error(f"reseller error: {e}")
            return None
    
    async def current_avatar(self) -> Optional[Dict[str, Any]]:
        await self.http_client.ensure_session()
        url = "https://avatar.roblox.com/v1/avatar"
        headers = {"x-csrf-token": self.x_csrf_token, "IGNORE_XOLO_MITM": "True"} if self.x_csrf_token else {"IGNORE_XOLO_MITM": "True"}
        cookies = {".ROBLOSECURITY": self.cookie} if self.cookie else None
        try:
            async with self.http_client.session.get(url, headers=headers, cookies=cookies) as r:
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            ctx.log.error(f"avatar error: {e}")
            return None
    
    async def collectible_item_id(self, collectible_item_id: int, cookie: Optional[str] = None, x_csrf_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        await self.http_client.ensure_session()
        headers = {}
        if x_csrf_token:
            headers["x-csrf-token"] = x_csrf_token
        cookies = {".ROBLOSECURITY": cookie} if cookie else None
        url = "https://apis.roblox.com/marketplace-items/v1/items/details"
        try:
            async with self.http_client.session.post(url, json={"itemIds": [collectible_item_id]}, headers=headers, cookies=cookies) as r:
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            ctx.log.error(f"collectible_item_id error: {e}")
            return None
    
    async def render_profile(self, avatar_wearing: Dict[str, Any], currently_wearing: List[int], avatar_rules: Dict[str, Any], is2D: bool, size: str, full_avatar: bool) -> Optional[bytes]:
        if not avatar_wearing:
            return None
        already = [asset["id"] for asset in avatar_wearing["assets"]]
        assets = [{"id": asset["id"]} for asset in avatar_wearing["assets"]]
        for asset in currently_wearing:
            if asset not in already:
                assets.append({"id": asset})
        
        body_colors = {}
        for body_color_type, body_color in avatar_wearing["bodyColors"].items():
            for body_color_id in avatar_rules["bodyColorsPalette"]:
                if body_color_id["brickColorId"] == body_color:
                    body_colors[body_color_type.removesuffix("Id")] = body_color_id["hexColor"]
        
        data = {
            "thumbnailConfig": {
                "thumbnailId": 16630147,
                "thumbnailType": "2d" if is2D else "3d",
                "size": size
            },
            "avatarDefinition": {
                "assets": assets,
                "bodyColors": body_colors,
                "scales": avatar_wearing["scales"],
                "playerAvatarType": {
                    "playerAvatarType": avatar_wearing["playerAvatarType"]
                }
            }
        }
        
        await self.http_client.ensure_session()
        url = "https://avatar.roblox.com/v1/avatar/render"
        headers = {"x-csrf-token": self.x_csrf_token, "IGNORE_XOLO_MITM": "True"} if self.x_csrf_token else {"IGNORE_XOLO_MITM": "True"}
        cookies = {".ROBLOSECURITY": self.cookie} if self.cookie else None
        
        for i in range(self._config.retry_count):
            try:
                async with self.http_client.session.post(url, cookies=cookies, headers=headers, json=data) as r:
                    r.raise_for_status()
                    response = await r.json()
                    if response["state"] == "Completed":
                        if not full_avatar:
                            response["imageUrl"] = "/".join(response["imageUrl"].split("/")[:-5] + ["500", "500"] + response["imageUrl"].split("/")[-3:])
                        async with self.http_client.session.get(response["imageUrl"], headers={"accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"}) as img_r:
                            if img_r.status == 200:
                                if full_avatar:
                                    return await img_r.read()
                                else:
                                    img_data = await img_r.read()
                                    img = Image.open(io.BytesIO(img_data))
                                    w, h = img.size
                                    left = w * 0.34
                                    top = h * 0.13
                                    right = w * 0.66
                                    bottom = top + (right - left)
                                    headshot = img.crop((left, top, right, bottom))
                                    headshot = headshot.convert("RGBA")
                                    out = io.BytesIO()
                                    headshot.save(out, format="WEBP", lossless=True)
                                    return out.getvalue()
            except Exception as e:
                ctx.log.debug(f"render profile error: {e}")
                await asyncio.sleep(1)
        return None
    
    async def asset_info(self, item_id: str, item_type: str) -> Optional[Dict[str, Any]]:
        await self.http_client.ensure_session()
        url = f"https://catalog.roblox.com/v1/catalog/items/{item_id}/details?itemType={item_type.capitalize()}"
        cookies = {".ROBLOSECURITY": self.cookie} if self.cookie else None
        try:
            async with self.http_client.session.get(url, cookies=cookies) as r:
                if r.status == 404:
                    return None
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            ctx.log.debug(f"asset info fetch error: {e}")
            return None
    
    async def mass_asset_info(self, item_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        await self.http_client.ensure_session()
        url = "https://catalog.roblox.com/v1/catalog/items/details"
        cookies = {".ROBLOSECURITY": self.cookie} if self.cookie else None
        headers = {"x-csrf-token": self.x_csrf_token} if self.x_csrf_token else {}
        try:
            async with self.http_client.session.post(url, json={"items": item_data}, headers=headers, cookies=cookies) as r:
                if r.status == 404:
                    return None
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            ctx.log.debug(f"mass asset info fetch error: {e}")
            return None
    
    async def fetch_thumbnail(self, item_id: str, item_type: str) -> Optional[Dict[str, Any]]:
        await self.http_client.ensure_session()
        if item_type == "asset":
            url = f"https://thumbnails.roblox.com/v1/assets?assetIds={item_id}&format=png&isCircular=false&size=140x140"
        elif item_type == "bundle":
            url = f"https://thumbnails.roblox.com/v1/bundles/thumbnails?bundleIds={item_id}&format=png&isCircular=false&size=150x150"
        else:
            return None
        try:
            async with self.http_client.session.get(url) as r:
                if r.status == 404:
                    return None
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            ctx.log.debug(f"thumbnail fetch error: {e}")
            return None
    
    async def gamepass_info(self, product_or_item_id: str, cookie: Optional[str] = None, x_csrf_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        await self.http_client.ensure_session()
        headers = {}
        if x_csrf_token:
            headers["x-csrf-token"] = x_csrf_token
        cookies = {".ROBLOSECURITY": cookie} if cookie else None
        url = f"https://apis.roblox.com/game-passes/v1/game-passes/{product_or_item_id}/product-info"
        try:
            async with self.http_client.session.get(url, headers=headers, cookies=cookies) as r:
                if r.status == 404:
                    return None
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            ctx.log.debug(f"gamepass_info fetch error: {e}")
            return None
    
    async def fetch_badge_page(self, item_id: str, cookie: Optional[str] = None) -> Optional[str]:
        await self.http_client.ensure_session()
        cookies = {".ROBLOSECURITY": cookie} if cookie else None
        url = f"https://www.roblox.com/game-pass/{item_id}/"
        try:
            async with self.http_client.session.get(url, cookies=cookies) as r:
                if r.status == 404:
                    return None
                r.raise_for_status()
                return await r.text()
        except Exception as e:
            ctx.log.debug(f"fetch_badge_page error: {e}")
            return None
