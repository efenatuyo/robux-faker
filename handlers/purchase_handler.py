from typing import Dict, Any
from mitmproxy import http
from mitmproxy import ctx
from .base import BaseHandler
from utils.datetime_utils import current_time
from config import PURCHASE_OVERRIDE

class PurchaseHandler(BaseHandler):
    async def handle_request(self, flow: http.HTTPFlow) -> bool:
        url = flow.request.pretty_url
        
        if ("/marketplace-sales/v1/item/" in url and ("/purchase-item" in url or "/purchase-resale" in url)) or ("apis.roblox.com/game-passes/v1/game-passes/" in url and "/purchase" in url) or ("apis.roblox.com/developer-products/v1/developer-products/" in url and "/purchase" in url):
            try:
                request_json = self.get_request_json(flow)
                if request_json and request_json.get("expectedPrice", 0) != 0:
                    request_json["expectedPrice"] += 1
                    self.set_request_json(flow, request_json)
                    return True
            except Exception as e:
                ctx.log.error(f"request modify error: {e}")
            return True
        
        return False
    
    async def handle_response(self, flow: http.HTTPFlow) -> bool:
        url = flow.request.pretty_url
        
        if "apis.roblox.com/marketplace-sales/v1/item" in url and ("/purchase-item" in url or "/purchase-resale" in url):
            uuid = flow.request.path.split("/")[4]
            if uuid not in self.state.cache.item_info.data:
                return False
            
            request_json = self.get_request_json(flow)
            if not request_json:
                return False
            
            if request_json["expectedPrice"] == 0:
                return False
            
            request_json["expectedPrice"] -= 1
            if request_json["expectedPrice"] > (self.state.balance.current_balance or 0):
                return False
            
            self.state.balance.current_balance -= request_json["expectedPrice"]
            self.state.balance.fake_spent_robux += request_json["expectedPrice"]
            self.save_state()
            item_info = self.state.cache.item_info.get(uuid)
            if not item_info:
                return False
            
            creator_id = item_info["creatorTargetId"]
            creator_type = item_info["creatorType"]
            creator_name = item_info["creatorName"]
            item_id = str(item_info["id"])
            item_name = item_info["name"]
            item_type = item_info["itemType"]
            
            if "collectibleItemInstanceId" in request_json:
                reseller_data = None
                for reseller in self.state.cache.resellers_data:
                    if reseller.get("collectibleItemInstanceId") == request_json["collectibleItemInstanceId"]:
                        reseller_data = reseller
                        break
                if reseller_data:
                    bought_data = {
                        "id": 0,
                        "idHash": "x",
                        "created": current_time(),
                        "transactionType": "Purchase",
                        "isPending": False,
                        "agent": {
                            "id": reseller_data["seller"]["sellerId"],
                            "type": reseller_data["seller"]["sellerType"],
                            "name": reseller_data["seller"]["name"]
                        },
                        "details": {
                            "id": int(item_id),
                            "collectibleItemId": uuid,
                            "name": item_name,
                            "type": item_type,
                            "serialNumber": reseller_data["serialNumber"]
                        },
                        "currency": {
                            "amount": request_json["expectedPrice"] * -1,
                            "type": "Robux"
                        },
                        "purchaseToken": "x",
                        "resaleData": reseller_data
                    }
                else:
                    bought_data = None
            else:
                bought_data = {
                    "id": 0,
                    "idHash": "x",
                    "created": current_time(),
                    "transactionType": "Purchase",
                    "isPending": False,
                    "agent": {
                        "id": creator_id,
                        "type": creator_type,
                        "name": creator_name
                    },
                    "details": {
                        "id": int(item_id),
                        "name": item_name,
                        "type": item_type,
                    },
                    "currency": {
                        "amount": request_json["expectedPrice"] * -1,
                        "type": "Robux"
                    },
                    "purchaseToken": "x"
                }
            
            if not bought_data:
                return False
            
            if item_id not in self.state.inventory.bought_items:
                self.state.inventory.bought_items[item_id] = []
            if item_id not in self.state.inventory.bought_items_history:
                self.state.inventory.bought_items_history[item_id] = []
            
            self.state.inventory.bought_items[item_id].append(bought_data)
            self.state.inventory.bought_items_history[item_id].append(bought_data)
            self.save_state()
            
            if item_type.lower() == "bundle":
                nested_assets = await self.roblox_api.asset_info(item_id, item_type.lower())
                if nested_assets and "bundledItems" in nested_assets:
                    for asset in nested_assets["bundledItems"]:
                        bundle_bought_data = {
                            "id": 0,
                            "idHash": "x",
                            "created": current_time(),
                            "transactionType": "Purchase",
                            "isPending": False,
                            "agent": {
                                "id": creator_id,
                                "type": creator_type,
                                "name": creator_name
                            },
                            "details": {
                                "id": int(asset["id"]),
                                "name": asset["name"],
                                "type": asset["type"],
                            },
                            "purchaseToken": "x",
                            "IGNORE": True
                        }
                        if asset["type"] == "Asset":
                            if str(asset["id"]) not in self.state.inventory.bought_items:
                                self.state.inventory.bought_items[str(asset["id"])] = []
                            if str(asset["id"]) not in self.state.inventory.bought_items_history:
                                self.state.inventory.bought_items_history[str(asset["id"])] = []
                            
                            self.state.inventory.bought_items[str(asset["id"])].append(bundle_bought_data)
                            self.state.inventory.bought_items_history[str(asset["id"])].append(bundle_bought_data)
                            self.save_state()
                        else:
                            for index in range(len(self.state.inventory.bought_items[item_id])):
                                if "specialId" not in self.state.inventory.bought_items[item_id][index]:
                                    self.state.inventory.bought_items[item_id][index]["specialId"] = asset["id"]
            
            self.set_response_json(flow, PURCHASE_OVERRIDE)
            return True
        
        if "apis.roblox.com/developer-products/v1/developer-products/" in url and "/purchase" in url:
            request_json = self.get_request_json(flow)
            if not request_json:
                return False
            
            request_json["expectedPrice"] -= 1
            if request_json["expectedPrice"] > (self.state.balance.current_balance or 0):
                return False
            
            self.state.balance.current_balance -= request_json["expectedPrice"]
            self.state.balance.fake_spent_robux += request_json["expectedPrice"]
            
            item_id = int(flow.request.path.split('?')[0].split('/')[4])
            developer_product_data = self.state.cache.developer_proudct_id.get(str(item_id))
            if not developer_product_data:
                return False
            
            universe_data = self.state.cache.universe_ids.get(str(developer_product_data["universeId"]))
            if not universe_data:
                return False
            
            creator_id = universe_data["creator"]["id"]
            creator_type = universe_data["creator"]["type"]
            creator_name = universe_data["creator"]["name"]
            game_id = str(universe_data["rootPlaceId"])
            game_name = universe_data["name"]
            
            product_id = developer_product_data["ProductId"]
            product_name = developer_product_data["Name"]
            
            bought_data = {
                "id": 0,
                "idHash": "x",
                "created": current_time(),
                "transactionType": "Purchase",
                "isPending": False,
                "agent": {
                    "id": creator_id,
                    "type": creator_type,
                    "name": creator_name
                },
                "details": {
                    "id": int(product_id),
                    "name": product_name,
                    "type": "DeveloperProduct",
                    "place": {
                        "placeId": int(game_id),
                        "universeId": 0,
                        "name": game_name
                    }
                },
                "currency": {
                    "amount": request_json["expectedPrice"] * -1,
                    "type": "Robux"
                },
                "purchaseToken": "x"
            }
            if item_id not in self.state.inventory.bought_items:
                self.state.inventory.bought_items[item_id] = []
            if item_id not in self.state.inventory.bought_items_history:
                self.state.inventory.bought_items_history[item_id] = []
            
            self.state.inventory.bought_items[item_id].append(bought_data)
            self.state.inventory.bought_items_history[item_id].append(bought_data)
            
            pending_data = {
                "playerId": self.state.user.user_id,
                "placeId": 0,
                "gameInstanceId": "x",
                "receipt": "x",
                "actionArgs": [
                    {
                        "Key": "productId",
                        "Value": item_id
                    },
                    {
                        "Key": "currencyTypeId",
                        "Value": "1"
                    },
                    {
                        "Key": "unitPrice",
                        "Value": request_json["expectedPrice"]
                    }
                ],
                "action": "Purchase"
            }
            
            if game_id not in self.state.inventory.pending_products:
                self.state.inventory.pending_products[game_id] = []
            
            self.state.inventory.pending_products[game_id].append(pending_data)
            
            response_data = {
                "purchased": True,
                "transactionStatus": "Success",
                "productId": product_id,
                "price": request_json["expectedPrice"],
                "receipt": "x",
                "success": True
            }
            self.set_response_json(flow, response_data)
            return True
        
        return False
