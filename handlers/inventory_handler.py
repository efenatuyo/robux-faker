from typing import Dict, Any
from mitmproxy import http
from mitmproxy import ctx
import random
import uuid as uuuid
from .base import BaseHandler
from utils.url_utils import split_dict
from config import InventoryConfig

class InventoryHandler(BaseHandler):
    def __init__(self, state, roblox_api):
        super().__init__(state, roblox_api)
        self.inventory_config = InventoryConfig()
    
    async def handle_request(self, flow: http.HTTPFlow) -> bool:
        return False
    
    async def handle_response(self, flow: http.HTTPFlow) -> bool:
        url = flow.request.pretty_url
        
        if "inventory.roblox.com/v1/collections/items/" in url:
            parts = [p for p in flow.request.path.split("/") if p]
            try:
                idx = parts.index("items")
                asset_type = parts[idx + 1].lower()
                item_id = parts[idx + 2]
            except (ValueError, IndexError):
                return False
            
            if item_id in self.state.inventory.bought_items:
                if flow.response.status_code != 200:
                    flow.response.status_code = 200
                
                if flow.request.method == "DELETE":
                    for index, item_data in enumerate(self.state.inventory.profile_items):
                        if str(item_id) == str(item_data["id"]):
                            del self.state.inventory.profile_items[index]
                            return True
                    return True
                
                item_name = self.state.inventory.bought_items[item_id][0]["details"]["name"]
                thumbnail = await self.roblox_api.fetch_thumbnail(item_id, asset_type)
                if not thumbnail or "data" not in thumbnail or not thumbnail["data"]:
                    return False
                
                asset_info = await self.roblox_api.asset_info(item_id, asset_type)
                if not asset_info:
                    return False
                
                seo_name = item_name.replace(" ", "-")
                fco = "catalog" if asset_type != "bundle" else "bundles"
                data = {
                    "id": int(item_id),
                    "assetSeoUrl": f"https://www.roblox.com/{fco}/{item_id}/{seo_name}",
                    "thumbnail": {
                        "final": True,
                        "url": thumbnail["data"][0]["imageUrl"],
                        "retryUrl": None,
                        "userId": 0,
                        "endpointType": "Avatar"
                    },
                    "name": item_name,
                    "formatName": None,
                    "description": asset_info.get("description", ""),
                    "assetRestrictionIcon": None,
                    "hasPremiumBenefit": False,
                    "assetAttribution": None,
                    "assetType": asset_type
                }
                
                self.state.inventory.profile_items.append(data)
                self.save_state()
            return True
        
        if f"apis.roblox.com/showcases-api/v1/users/profile/robloxcollections-json?userId={self.state.user.user_id}" in url:
            if self.state.inventory.profile_items:
                response_json = self.parse_json(flow.response.get_text())
                if response_json:
                    for profile_item in self.state.inventory.profile_items:
                        response_json.insert(0, profile_item)
                    self.set_response_json(flow, response_json)
                    return True
            return False
        
        if "inventory.roblox.com/v1/users/" in url and "/is-owned" in url:
            path = flow.request.path.lower()
            parts = [p for p in path.split("/") if p]
            try:
                idx = parts.index("items")
                asset_type = parts[idx + 1]
                item_id = parts[idx + 2]
            except (ValueError, IndexError):
                return False
            
            owned = False
            if item_id in self.state.inventory.bought_items:
                stored = self.state.inventory.bought_items[item_id][0] if isinstance(self.state.inventory.bought_items[item_id], (list, tuple)) else self.state.inventory.bought_items[item_id]
                stored_type = None
                if isinstance(stored, dict):
                    stored_type = stored.get("type") or stored.get("assetType") or stored.get("itemType")
                if stored_type:
                    owned = stored_type.lower() == asset_type.lower()
                else:
                    owned = True
            
            if owned:
                flow.response.status_code = 200
                self.set_response_text(flow, "true")
                return True
            return False
        
        if "apis.roblox.com/profile-platform-api/v1/profiles/get" in url:
            response = flow.response.get_text()
            if response:
                response_json = self.parse_json(response)
                if response_json and int(response_json.get("profileId", 0)) == int(self.state.user.user_id or 0):
                    if self.state.inventory.profile_items:
                        for item in self.state.inventory.profile_items:
                            data = {
                                "assetId": item["id"],
                                "itemType": item["assetType"].capitalize()
                            }
                            if "components" in response_json and "Collections" in response_json["components"]:
                                response_json["components"]["Collections"]["assets"].append(data)
                    
                    if "CurrentlyWearing" in response_json.get("componentOrdering", []):
                        for item_wearing in self.state.inventory.currently_wearing:
                            if "components" in response_json and "CurrentlyWearing" in response_json["components"]:
                                response_json["components"]["CurrentlyWearing"]["assets"].insert(0, {
                                    "assetId": item_wearing,
                                    "itemType": "Asset"
                                })
                
                self.set_response_json(flow, response_json)
                return True
            return False
        
        if f"/inventory.roblox.com/v2/users/{self.state.user.user_id}/inventory" in url:
            response_json = self.parse_json(flow.response.get_text())
            if not response_json:
                return False
            
            if "assetTypes=EmoteAnimation" in flow.request.path:
                item_list = split_dict(self.state.inventory.bought_items)
                for items in item_list:
                    item_data = [{"itemType": item[0]["details"]["type"], "id": item[0]["details"]["id"]} for _, item in items.items() if item[0]["details"]["type"] == "Asset"]
                    item_infos = await self.roblox_api.mass_asset_info(item_data)
                    if item_infos and "data" in item_infos:
                        for index, item_info in enumerate(item_infos["data"]):
                            if "assetType" in item_info and item_info["assetType"] == 61:
                                response_json["data"].insert(0, {
                                    "assetId": item_info["id"],
                                    "name": item_info["name"],
                                    "assetType": "EmoteAnimation",
                                    "created": self.state.inventory.bought_items[str(item_info["id"])][0]["created"]
                                })
            else:
                inventory_id = flow.request.path.split("inventory/")[1].split("?")[0]
                sort_order = flow.request.path.split("sortOrder=")[1]
                
                if sort_order == "Desc":
                    item_list = split_dict(self.state.inventory.bought_items)
                else:
                    item_list = split_dict(dict(reversed(self.state.inventory.bought_items.items())))
                
                for items in item_list:
                    item_data = [{"itemType": item[0]["details"]["type"], "id": item[0]["details"]["id"]} for _, item in items.items()]
                    item_infos = await self.roblox_api.mass_asset_info(item_data)
                    if item_infos and "data" in item_infos:
                        for index, item_info in enumerate(item_infos["data"]):
                            if "assetType" in item_info and item_info["assetType"] == int(inventory_id):
                                for i in range(len(self.state.inventory.bought_items[str(item_info["id"])])):
                                    data = {
                                        "userAssetId": random.randint(self.inventory_config.user_asset_id_min, self.inventory_config.user_asset_id_max),
                                        "assetId": item_info["id"],
                                        "assetName": item_info["name"],
                                        "collectibleItemId": item_info["collectibleItemId"] if "collectibleItemId" in item_info else None,
                                        "collectibleItemInstanceId": str(uuuid.uuid4()),
                                        "serialNumber": None,
                                        "owner": {
                                            "userId": self.state.user.user_id,
                                            "username": self.state.user.user_name,
                                            "buildersClubMembershipType": "None"
                                        },
                                        "created": self.state.inventory.bought_items[str(item_info["id"])][i]["created"],
                                        "updated": self.state.inventory.bought_items[str(item_info["id"])][i]["created"]
                                    }
                                    response_json["data"].insert(0, data)
            
            self.set_response_json(flow, response_json)
            return True
        
        if f"catalog.roblox.com/v1/users/{self.state.user.user_id}/bundles/1" in url:
            sort_order = flow.request.path.split("sortOrder=")[1]
            
            if sort_order == "Desc":
                item_list = split_dict(self.state.inventory.bought_items)
            else:
                item_list = split_dict(dict(reversed(self.state.inventory.bought_items.items())))
            
            response_json = self.parse_json(flow.response.get_text())
            if not response_json:
                return False
            
            for items in item_list:
                item_data = [{"itemType": item[0]["details"]["type"], "id": item[0]["details"]["id"]} for _, item in items.items()]
                item_infos = await self.roblox_api.mass_asset_info(item_data)
                if item_infos and "data" in item_infos:
                    for index, item_info in enumerate(item_infos["data"]):
                        if "bundleType" in item_info:
                            for i in range(len(self.state.inventory.bought_items[str(item_info["id"])])):
                                data = {
                                    "id": item_info["id"],
                                    "name": item_info["name"],
                                    "bundleType": "BodyParts",
                                    "creator": {
                                        "id": item_info["creatorTargetId"],
                                        "name": item_info["creatorName"],
                                        "type": item_info["creatorType"],
                                        "hasVerifiedBadge": item_info["creatorHasVerifiedBadge"]
                                    }
                                }
                                if sort_order == "Desc":
                                    response_json["data"].insert(0, data)
                                else:
                                    response_json["data"].append(data)
            
            self.set_response_json(flow, response_json)
            return True
        
        if "inventory.roblox.com/v2/inventory/asset/" in url:
            if flow.request.method == "DELETE":
                item_id = flow.request.path.split("/")[-1]
                if item_id in self.state.inventory.bought_items:
                    flow.response.status_code = 200
                    if len(self.state.inventory.bought_items[item_id]) == 1:
                        del self.state.inventory.bought_items[item_id]
                    else:
                        del self.state.inventory.bought_items[item_id][0]
                    self.save_state()
                    return True
            return False
        
        if "apis.roblox.com/experience-store/v1/universes/" in url and "/store" in url:
            response_json = self.parse_json(flow.response.get_text())
            if response_json and "developerProducts" in response_json:
                for product in response_json["developerProducts"]:
                    data = {
                        "ProductId": product["DeveloperProductId"],
                        "Name": product["Name"],
                        "universeId": flow.request.path.split("/")[4]
                    }
                    self.state.cache.developer_proudct_id.set(str(product["ProductId"]), data)
            return True
        
        if "games.roblox.com/v1/games?universeIds=" in url:
            response_json = self.parse_json(flow.response.get_text())
            if response_json and "data" in response_json:
                for data in response_json["data"]:
                    saved_data = {
                        "creator": {
                            "id": data["creator"]["id"],
                            "type": data["creator"]["type"],
                            "name": data["creator"]["name"]
                        },
                        "rootPlaceId": data["rootPlaceId"],
                        "name": data["name"]
                    }
                    self.state.cache.universe_ids.set(str(data["id"]), saved_data)
            return True
        
        if "apis.roblox.com/developer-products/v1/developer-products/" in url and "/details" in url:
            response_json = self.parse_json(flow.response.get_text())
            if response_json:
                data = {
                    "ProductId": response_json["TargetId"],
                    "Name": response_json["Name"],
                    "universeId": response_json["UniverseId"]
                }
                self.state.cache.developer_proudct_id.set(str(response_json["ProductId"]), data)
            return True
        
        if "apis.roblox.com/developer-products/v1/game-transactions" in url and "locationType=ExperienceDetailPage" in url and "status=pending" in url:
            response_json = self.parse_json(flow.response.get_text())
            if response_json:
                game_id = flow.request.path.split("placeId=", 1)[1].split("&", 1)[0]
                if game_id in self.state.inventory.pending_products:
                    for pending_data in self.state.inventory.pending_products[game_id]:
                        response_json.append(pending_data)
                    self.set_response_json(flow, response_json)
                    return True
            return False
        
        if "catalog.roblox.com/v1/catalog/items/" in url and "/details" in url and "?itemType=" in url:
            response_json = self.parse_json(flow.response.get_text())
            if not response_json:
                return False
            
            item_id_str = str(response_json.get("id", ""))
            if item_id_str in self.state.inventory.bought_items:
                if "owned" in response_json and not response_json["owned"]:
                    response_json["owned"] = True
                if "isPurchasable" in response_json and response_json["isPurchasable"] and not response_json.get("itemRestrictions"):
                    response_json["isPurchasable"] = False
                if "bundledItems" in response_json:
                    for index, bundled_item in enumerate(response_json["bundledItems"]):
                        response_json["bundledItems"][index]["owned"] = True
                
                self.set_response_json(flow, response_json)
            
            collectible_item_id = response_json.get("collectibleItemId")
            if collectible_item_id:
                self.state.cache.item_info.set(collectible_item_id, response_json)
            else:
                self.state.cache.item_info.set(item_id_str, response_json)
            
            if response_json.get("lowestResalePrice") and item_id_str in self.state.inventory.bought_items:
                reseller_resp = await self.roblox_api.resellers(response_json["collectibleItemId"])
                if reseller_resp and "data" in reseller_resp:
                    already_bought = [
                        bought_item["resaleData"]["collectibleItemInstanceId"]
                        for bought_item in self.state.inventory.bought_items[item_id_str]
                        if "resaleData" in bought_item
                    ]
                    lowest_resale = None
                    for reseller in reseller_resp["data"]:
                        if reseller["collectibleItemInstanceId"] not in already_bought:
                            lowest_resale = reseller
                            break
                    
                    if lowest_resale:
                        response_json["lowestPrice"] = lowest_resale["price"]
                        response_json["lowestResalePrice"] = lowest_resale["price"]
                        self.set_response_json(flow, response_json)
            return True
        
        if "apis.roblox.com/marketplace-items/v1/items/details" in url:
            response_json = self.parse_json(flow.response.get_text())
            if not response_json:
                return False
            
            for index, item in enumerate(response_json):
                if "lowestAvailableResaleProductId" in item and str(item["itemTargetId"]) in self.state.inventory.bought_items:
                    resellers_resp = await self.roblox_api.resellers(item["collectibleItemId"])
                    if resellers_resp and "data" in resellers_resp:
                        resellers_list = resellers_resp["data"]
                        
                        already_bought = {
                            b.get("resaleData", {}).get("collectibleItemInstanceId")
                            for b in self.state.inventory.bought_items[str(item["itemTargetId"])]
                            if "resaleData" in b
                        }
                        
                        lowest_resale = next(
                            (r for r in resellers_list if r["collectibleItemInstanceId"] not in already_bought),
                            None
                        )
                        
                        if lowest_resale:
                            item["lowestAvailableResaleProductId"] = lowest_resale["collectibleProductId"]
                            item["lowestAvailableResaleItemInstanceId"] = lowest_resale["collectibleItemInstanceId"]
                            item["lowestPrice"] = lowest_resale["price"]
                            item["lowestResalePrice"] = lowest_resale["price"]
            
            self.set_response_json(flow, response_json)
            return True
        
        if "apis.roblox.com/marketplace-sales/v1/item/" in url and "/resellers" in url:
            import asyncio
            await asyncio.sleep(1)
            response_json = self.parse_json(flow.response.get_text())
            if not response_json:
                return False
            
            data = response_json.get("data")
            if not data:
                return False
            
            parts = flow.request.path.split("/")
            uuid = parts[4] if len(parts) > 4 else None
            if not uuid:
                return False
            
            bought_instance_ids = set()
            for items in self.state.inventory.bought_items.values():
                if not items:
                    continue
                details = items[0].get("details", {})
                if details.get("collectibleItemId") != uuid:
                    continue
                for bought_item in items:
                    resale = bought_item.get("resaleData", {})
                    iid = resale.get("collectibleItemInstanceId")
                    if iid:
                        bought_instance_ids.add(iid)
            
            if not hasattr(self.state.cache, "resellers_ids"):
                self.state.cache.resellers_ids = set()
            
            filtered_data = []
            for item in data:
                iid = item.get("collectibleItemInstanceId")
                if not iid:
                    continue
                if iid in bought_instance_ids:
                    continue
                if iid not in self.state.cache.resellers_ids:
                    self.state.cache.resellers_ids.add(iid)
                    self.state.cache.resellers_data.append(item)
                filtered_data.append(item)
            
            response_json["data"] = filtered_data
            self.set_response_json(flow, response_json)
            return True
        
        if "apis.roblox.com/marketplace-sales/v1/item/" in url and "/resellable-instances" in url:
            collectible_item_id = flow.request.path.split("/item/")[1].split("/")[0]
            for items in self.state.inventory.bought_items.values():
                if items and "resaleData" in items[0]:
                    if items[0]["details"]["collectibleItemId"] == collectible_item_id:
                        response_json = self.parse_json(flow.response.get_text())
                        if not response_json:
                            return False
                        for item in items:
                            response_json["itemInstances"].append({
                                "collectibleInstanceId": item["resaleData"]["collectibleItemInstanceId"],
                                "collectibleItemId": item["details"]["collectibleItemId"],
                                "collectibleProductId": "e3d146da-4478-48ee-a2be-5157cea26381",
                                "serialNumber": item["details"]["serialNumber"],
                                "isHeld": True,
                                "saleState": "OffSale",
                                "price": 0
                            })
                        self.set_response_json(flow, response_json)
                        return True
            return False
        
        if "avatar.roblox.com/v1/avatar-inventory" in url:
            from utils.url_utils import parse_url_params
            params = parse_url_params(url)
            item_display = []
            param_list = list(params.items())
            for index, (param, value) in enumerate(param_list):
                if "ItemSubType" in param:
                    item_display.append([int(value), list(params.values())[index + 1] if index + 1 < len(param_list) else []])
            
            item_list = split_dict(self.state.inventory.bought_items)
            
            response_json = self.parse_json(flow.response.get_text())
            if not response_json:
                return False
            
            for items in item_list:
                item_data = [{"itemType": item[0]["details"]["type"], "id": item[0]["details"]["id"]} for _, item in items.items()]
                item_infos = await self.roblox_api.mass_asset_info(item_data)
                if item_infos and "data" in item_infos:
                    for index, item_info in enumerate(item_infos["data"]):
                        if item_info["itemType"] == "Bundle":
                            item_info["itemType"] = "Outfit"
                        
                        special_id = None
                        
                        if item_info["itemType"] == "Outfit":
                            for item in item_info.get("bundledItems", []):
                                if item["name"] == item_info["name"]:
                                    special_id = item["id"]
                        if item_info.get("bundleType") == 2:
                            item_info["bundleType"] = 5
                        
                        if not len(item_display):
                            if item_info.get("assetType") == 61:
                                continue
                            data = {
                                "itemId": item_info["id"] if not special_id else special_id,
                                "itemCategory": {
                                    "itemType": 1 if item_info.get("itemType") == "Asset" else 2,
                                    "itemSubType": item_info.get("assetType", 5) or item_info.get("bundleType")
                                },
                                "itemName": item_info["name"],
                                "acquisitionTime": self.state.inventory.bought_items[str(item_info["id"])][-1]["created"]
                            }
                            response_json["avatarInventoryItems"].insert(0, data)
                        else:
                            added = []
                            for display in item_display:
                                if (special_id or item_info["id"]) in added:
                                    continue
                                if item_info["itemType"] not in display or (item_info.get("bundleType") or item_info.get("assetType")) not in display:
                                    continue
                                data = {
                                    "itemId": item_info["id"] if not special_id else special_id,
                                    "itemCategory": {
                                        "itemType": 1 if item_info.get("itemType") == "Asset" else 2,
                                        "itemSubType": item_info.get("assetType") or item_info.get("bundleType")
                                    },
                                    "itemName": item_info["name"],
                                    "acquisitionTime": self.state.inventory.bought_items[str(item_info["id"])][-1]["created"]
                                }
                                added.append(special_id or item_info["id"])
                                response_json["avatarInventoryItems"].insert(0, data)
            
            self.set_response_json(flow, response_json)
            return True
        
        return False
