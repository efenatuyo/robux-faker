from typing import Dict, Any
from mitmproxy import http
from mitmproxy import ctx
import json
from .base import BaseHandler
from utils.datetime_utils import two_months_ago, parse_iso_z
from config import RobuxConfig

class TransactionHandler(BaseHandler):
    async def handle_request(self, flow: http.HTTPFlow) -> bool:
        return False
    
    async def handle_response(self, flow: http.HTTPFlow) -> bool:
        url = flow.request.pretty_url
        
        if "/apis.roblox.com/transaction-records/v1/users/" in url and "transaction-totals" in url:
            try:
                transaction_data = self.parse_json(flow.response.get_text())
                if transaction_data:
                    transaction_data["purchasesTotal"] -= self.state.balance.fake_spent_robux
                    transaction_data["outgoingRobuxTotal"] -= self.state.balance.fake_spent_robux
                    if "timeFrame=Month" in url or "timeFrame=Year" in url:
                        robux_config = RobuxConfig()
                        transaction_data["groupPayoutsTotal"] += robux_config.added_robux
                        transaction_data["incomingRobuxTotal"] += robux_config.added_robux
                    self.set_response_json(flow, transaction_data)
                    return True
            except Exception as e:
                ctx.log.error(f"transaction-totals error: {e}")
            return True
        
        if "/apis.roblox.com/transaction-records/v1/users/" in url and "/transactions" in url and "transactionType=Purchase" in url:
            try:
                response_json = self.parse_json(flow.response.get_text())
                if response_json:
                    for key, items in self.state.inventory.bought_items_history.items():
                        for item in items:
                            if "IGNORE" in item:
                                continue
                            response_json["data"].append(item)
                    self.set_response_json(flow, response_json)
                    return True
            except Exception as e:
                ctx.log.error(f"transactions purchase error: {e}")
            return True
        
        if "/apis.roblox.com/transaction-records/v1/users/" in url and "/transactions" in url and "transactionType=GroupPayout" in url:
            date_time = two_months_ago()
            robux_config = RobuxConfig()
            payout_data = {
                "id": 0,
                "idHash": "x",
                "transactionType": "Group Revenue Payout",
                "created": date_time,
                "isPending": False,
                "agent": {
                    "id": robux_config.group_id,
                    "type": "Group",
                    "name": robux_config.group_name
                },
                "details": {},
                "currency": {
                    "amount": robux_config.added_robux,
                    "type": "Robux"
                },
                "purchaseToken": None
            }
            try:
                transaction_data = self.parse_json(flow.response.get_text())
                if not transaction_data:
                    return True
                
                found_match = False
                if not transaction_data.get("data"):
                    transaction_data.setdefault("data", []).append(payout_data)
                    found_match = True
                else:
                    for index, transaction in enumerate(transaction_data["data"]):
                        try:
                            if parse_iso_z(date_time) > parse_iso_z(transaction["created"]):
                                transaction_data["data"].insert(index, payout_data)
                                found_match = True
                                break
                        except Exception:
                            continue
                    if not found_match:
                        if len(transaction_data["data"]) != 100:
                            transaction_data["data"].append(payout_data)
                            found_match = True
                
                if found_match:
                    self.set_response_json(flow, transaction_data)
                    return True
            except Exception as e:
                ctx.log.error(f"group payout parse error: {e}")
            return True
        
        return False
