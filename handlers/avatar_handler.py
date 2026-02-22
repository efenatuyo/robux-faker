from typing import Dict, Any
from mitmproxy import http
from mitmproxy import ctx
import random
from .base import BaseHandler
from config import ASSET_TYPES, AvatarConfig
from utils.persistence import StatePersistence

class AvatarHandler(BaseHandler):
    def __init__(self, state, roblox_api):
        super().__init__(state, roblox_api)
        self.avatar_config = AvatarConfig()
    
    async def handle_request(self, flow: http.HTTPFlow) -> bool:
        url = flow.request.pretty_url
        
        if self.state.user.user_id and f"avatar.roblox.com/v1/users/{self.state.user.user_id}/currently-wearing" in url:
            return False
        
        if "avatar.roblox.com/v1/avatar/render" in url:
            if "IGNORE_XOLO_MITM" in flow.request.headers:
                return False
            
            request_json = self.get_request_json(flow)
            if not request_json:
                return False
            
            already_added = []
            if "avatarDefinition" in request_json and "assets" in request_json["avatarDefinition"]:
                for asset in request_json["avatarDefinition"]["assets"]:
                    already_added.append(asset["id"])
            
            for asset in self.state.inventory.currently_wearing:
                if asset not in already_added:
                    if "avatarDefinition" not in request_json:
                        request_json["avatarDefinition"] = {}
                    if "assets" not in request_json["avatarDefinition"]:
                        request_json["avatarDefinition"]["assets"] = []
                    request_json["avatarDefinition"]["assets"].append({"id": asset})
            
            self.set_request_json(flow, request_json)
            return True
        
        if "rbxcdn.com/30DAY-" in url:
            flow.request.headers["cache-control"] = "no-cache, no-store, must-revalidate, max-age=0"
            flow.request.headers["pragma"] = "no-cache"
            for h in ["If-Modified-Since", "If-None-Match", "If-Range"]:
                if h in flow.request.headers:
                    del flow.request.headers[h]
            return True
        
        return False
    
    async def handle_response(self, flow: http.HTTPFlow) -> bool:
        url = flow.request.pretty_url
        
        if ("avatar.roblox.com/v1/avatar" in url and not "/v2/" in url) or "avatar.roblox.com/v2/avatar/avatar" in url:
            if "IGNORE_XOLO_MITM" in flow.request.headers:
                return False
            
            response_json = self.parse_json(flow.response.get_text())
            if not response_json:
                return False
            
            if "assets" not in response_json:
                response_json["assets"] = []
            
            is_v2 = "v2/avatar/avatar" in url
            
            self.state.avatar.avatar_wearing = response_json
            
            existing_asset_ids = {asset.get("id") for asset in response_json["assets"]}
            
            for wearing_asset in self.state.inventory.currently_wearing.copy():
                if str(wearing_asset) not in self.state.inventory.bought_items:
                    if wearing_asset in self.state.inventory.currently_wearing:
                        self.state.inventory.currently_wearing.remove(wearing_asset)
                        self.save_state()
                    self.state.cache.avatar_combo.data = {}
            
            item_data = [
                {"itemType": self.state.inventory.bought_items[str(item)][0]["details"]["type"], "id": self.state.inventory.bought_items[str(item)][0]["details"]["id"]}
                for item in self.state.inventory.currently_wearing
                if str(item) in self.state.inventory.bought_items and item not in existing_asset_ids
            ]
            
            item_detailed = await self.roblox_api.mass_asset_info(item_data) if item_data else None
            
            for index, wearing_asset in enumerate(self.state.inventory.currently_wearing):
                if str(wearing_asset) in self.state.inventory.bought_items:
                    if wearing_asset not in existing_asset_ids:
                        item_info = self.state.inventory.bought_items[str(wearing_asset)][0]
                        
                        asset_type_id = 0
                        if item_detailed and "data" in item_detailed:
                            item_data_index = next((i for i, data in enumerate(item_data) if data["id"] == wearing_asset), -1)
                            if item_data_index >= 0 and item_data_index < len(item_detailed["data"]):
                                asset_type_id = item_detailed["data"][item_data_index].get("assetType", 0)
                        
                        data = {
                            "id": wearing_asset,
                            "name": item_info["details"]["name"],
                            "assetType": {
                                "id": asset_type_id,
                                "name": ASSET_TYPES.get(asset_type_id, "Unknown")
                            },
                            "currentVersionId": random.randint(self.avatar_config.version_id_min, self.avatar_config.version_id_max)
                        }
                        
                        if is_v2 and asset_type_id in self.avatar_config.accessory_types:
                            data["meta"] = {
                                "order": random.randint(self.avatar_config.accessory_order_min, self.avatar_config.accessory_order_max),
                                "version": 1
                            }
                        
                        response_json["assets"].append(data)
                        existing_asset_ids.add(wearing_asset)
            
            for asset in response_json["assets"]:
                asset_id = asset.get("id")
                if asset_id and str(asset_id) in self.state.inventory.bought_items and asset_id not in self.state.inventory.currently_wearing:
                    self.state.inventory.currently_wearing.append(asset_id)
                    self.save_state()
            
            if is_v2:
                if "emotes" not in response_json:
                    response_json["emotes"] = []
                
                existing_emote_ids = {emote.get("assetId") for emote in response_json["emotes"]}
                
                for emote_data in self.state.inventory.emotes_wearing:
                    emote_id = emote_data[0] if isinstance(emote_data, list) and len(emote_data) >= 1 else None
                    position = emote_data[1] if isinstance(emote_data, list) and len(emote_data) >= 2 else None
                    
                    if emote_id and str(emote_id) in self.state.inventory.bought_items and emote_id not in existing_emote_ids:
                        emote_name = self.state.inventory.bought_items[str(emote_id)][0]["details"]["name"]
                        response_json["emotes"].append({
                            "assetId": emote_id,
                            "assetName": emote_name,
                            "position": position if position is not None else len(response_json["emotes"]) + 1
                        })
                        existing_emote_ids.add(emote_id)
            
            self.set_response_json(flow, response_json)
            return True
        
        if "avatar.roblox.com/v2/avatar/set-wearing-assets" in url:
            if flow.request.method == "POST":
                request_json = self.get_request_json(flow)
                requested_asset_ids = []
                if request_json and "assetIds" in request_json:
                    requested_asset_ids = [int(asset_id) for asset_id in request_json["assetIds"]]
                
                response = flow.response.get_text()
                if response:
                    response_json = self.parse_json(response)
                    if response_json:
                        passed_assets = []
                        cache_cleared = False
                        requested_set = set(requested_asset_ids)
                        
                        for asset_id in requested_asset_ids:
                            if str(asset_id) in self.state.inventory.bought_items:
                                if asset_id not in passed_assets:
                                    passed_assets.append(asset_id)
                                if asset_id not in self.state.inventory.currently_wearing:
                                    self.state.inventory.currently_wearing.append(asset_id)
                                    if not cache_cleared:
                                        self.state.cache.avatar_combo.data = {}
                                        cache_cleared = True
                        
                        if "invalidAssetIds" in response_json:
                            for item in response_json["invalidAssetIds"].copy():
                                if str(item) in self.state.inventory.bought_items:
                                    response_json["invalidAssetIds"].remove(item)
                                    if "invalidAssets" in response_json:
                                        for data in response_json["invalidAssets"].copy():
                                            if data.get("id") == item:
                                                response_json["invalidAssets"].remove(data)
                                    response_json["success"] = True
                                    if int(item) not in passed_assets:
                                        passed_assets.append(int(item))
                                    if int(item) not in self.state.inventory.currently_wearing:
                                        self.state.inventory.currently_wearing.append(int(item))
                                        self.save_state()
                                        if not cache_cleared:
                                            self.state.cache.avatar_combo.data = {}
                                            cache_cleared = True
                        
                        items_to_remove = []
                        for wearing_item_id in self.state.inventory.currently_wearing.copy():
                            if wearing_item_id in passed_assets:
                                continue
                            if wearing_item_id not in requested_set:
                                items_to_remove.append(wearing_item_id)
                            elif wearing_item_id in requested_set and wearing_item_id not in passed_assets:
                                items_to_remove.append(wearing_item_id)
                        
                        for item_id in items_to_remove:
                            if item_id in self.state.inventory.currently_wearing:
                                self.state.inventory.currently_wearing.remove(item_id)
                            if not cache_cleared:
                                self.state.cache.avatar_combo.data = {}
                                cache_cleared = True
                        
                        if items_to_remove:
                            self.save_state()
                        
                        self.set_response_json(flow, response_json)
                    
                    avatar = await self.roblox_api.current_avatar()
                    if avatar:
                        self.state.avatar.avatar_wearing = avatar
            return True
        
        if "avatar.roblox.com/v2/outfits/create" in url:
            request_json = self.get_request_json(flow)
            if request_json and flow.response.status_code != 200:
                if "assets" in request_json:
                    for asset_data in request_json["assets"]:
                        if asset_data["id"] in self.state.inventory.currently_wearing:
                            flow.response.status_code = 200
                            self.set_response_text(flow, "{}")
                            return True
            return False
        
        if "thumbnails.roblox.com/v1/batch" in url:
            response = flow.response.get_text()
            if response:
                response_json = self.parse_json(response)
                if response_json and "data" in response_json:
                    for image_data in response_json["data"]:
                        if image_data.get("targetId") and image_data.get("imageUrl"):
                            if image_data["targetId"] == int(self.state.user.user_id or 0):
                                if image_data["imageUrl"] not in self.state.cache.avatar_image_modify:
                                    self.state.cache.avatar_image_modify.append(image_data["imageUrl"])
            return True
        
        if f"https://thumbnails.roblox.com/v1/users/avatar-3d?userId={str(self.state.user.user_id)}" == url:
            response = flow.response.get_text()
            if response:
                response_json = self.parse_json(response)
                if response_json.get("targetId") and response_json.get("imageUrl"):
                    if response_json["targetId"] == int(self.state.user.user_id or 0):
                        if response_json["imageUrl"] not in self.state.cache.avatar_image_modify:
                            self.state.cache.avatar_image_modify.append(response_json["imageUrl"])
            return True
        
        if "rbxcdn.com/30DAY-" in url:
            for avatar_url in self.state.cache.avatar_image_modify:
                if url in avatar_url:
                    parts = url.rstrip("/").split("/")
                    avatar_type = parts[-3]
                    try:
                        resolution = parts[-5] + "x" + parts[-4]
                    except Exception:
                        resolution = "500x500"
                    
                    if url in self.state.cache.avatar_combo.data:
                        flow.response.set_content(self.state.cache.avatar_combo.get(url))
                    else:
                        render = await self.roblox_api.render_profile(
                            self.state.avatar.avatar_wearing or {},
                            self.state.inventory.currently_wearing,
                            self.state.avatar.avatar_rules_roblox or {},
                            False if "Obj" in url else True,
                            resolution,
                            avatar_type != "AvatarHeadshot"
                        )
                        if render:
                            self.state.cache.avatar_combo.set(url, render)
                        flow.response.set_content(render)
            
            flow.response.headers["cache-control"] = "no-store, no-cache, must-revalidate, max-age=0"
            flow.response.headers["pragma"] = "no-cache"
            flow.response.headers["expires"] = "0"
            
            for h in ["Last-Modified", "ETag"]:
                if h in flow.response.headers:
                    del flow.response.headers[h]
            
            return True
        
        if "avatar.roblox.com/v1/users/" in url and "/currently-wearing" in url:
            response_json = self.parse_json(flow.response.get_text())
            if not response_json:
                response_json = {}
            
            if "assetIds" not in response_json:
                response_json["assetIds"] = []
            
            existing_ids = set()
            for id_val in response_json["assetIds"]:
                try:
                    existing_ids.add(int(id_val))
                except (ValueError, TypeError):
                    pass
            
            for item_wearing in self.state.inventory.currently_wearing:
                if item_wearing not in existing_ids and str(item_wearing) in self.state.inventory.bought_items:
                    response_json["assetIds"].insert(0, item_wearing)
                    existing_ids.add(item_wearing)
            
            response_json["assetIds"] = [int(id) for id in response_json["assetIds"] if isinstance(id, (int, str)) and str(id).isdigit()]
            
            self.set_response_json(flow, response_json)
            return True
        
        if "avatar.roblox.com/v1/emotes" in url:
            if flow.request.method == "GET":
                response_json = self.parse_json(flow.response.get_text())
                if response_json:
                    for emote in self.state.inventory.emotes_wearing:
                        response_json.append({
                            "assetId": emote[0],
                            "assetName": self.state.inventory.bought_items[str(emote[0])][0]["details"]["name"],
                            "position": emote[1]
                        })
                    self.set_response_json(flow, response_json)
                    return True
            else:
                item_id = flow.request.path.split("/")[-2]
                slot = flow.request.path.split("/")[-1]
                
                if flow.request.method == "POST":
                    if str(item_id) in self.state.inventory.bought_items:
                        flow.response.status_code = 200
                        self.state.inventory.emotes_wearing.append([int(item_id), slot])
                        self.save_state()
                        self.set_response_text(flow, "{}")
                        return True
                elif flow.request.method == "DELETE":
                    if str(item_id) in self.state.inventory.bought_items:
                        flow.response.status_code = 200
                        for emote_data in self.state.inventory.emotes_wearing:
                            if emote_data[0] == int(item_id):
                                self.state.inventory.emotes_wearing.remove(emote_data)
                                self.save_state()
                                break
                        return True
            return False
        
        return False
