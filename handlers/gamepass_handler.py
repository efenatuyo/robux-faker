from typing import Dict, Any
from mitmproxy import http
from mitmproxy import ctx
from bs4 import BeautifulSoup
import re
from .base import BaseHandler
from utils.datetime_utils import current_time
from utils.url_utils import parse_url_params

class GamePassHandler(BaseHandler):
    async def handle_request(self, flow: http.HTTPFlow) -> bool:
        return False
    
    async def handle_response(self, flow: http.HTTPFlow) -> bool:
        url = flow.request.pretty_url
        
        if bool(re.search(r"(?:https?://)?(?:www\.)?roblox\.com/game-pass/\d+(?:/|$)", url, re.I)):
            try:
                html = flow.response.get_text()
            except Exception:
                return False
            soup = BeautifulSoup(html, "html.parser")
            container = soup.find("div", id="item-container")
            if container:
                product_id = container.get("data-product-id")
                delete_id = container.get("data-delete-id")
                if product_id and delete_id:
                    self.state.cache.gamepass_product_id.set(str(product_id), str(delete_id))
            
            parts = flow.request.path.split('/')
            if len(parts) > 2:
                item_id = parts[2]
            else:
                return False
            
            if item_id not in self.state.inventory.bought_items:
                return False
            
            try:
                html = flow.response.get_text()
            except Exception as e:
                ctx.log.error(f"game-pass response read error: {e}")
                return False
            
            try:
                soup = BeautifulSoup(html, "html.parser")
                ajax_div = soup.select_one("#ItemPurchaseAjaxData")
                if ajax_div:
                    try:
                        if not self.state.balance.real_balance:
                            raw = ajax_div.get("data-user-balance-robux")
                            self.state.balance.real_balance = int(raw) if raw and raw.isdigit() else 0
                            self.state.balance.current_balance = self.state.balance.real_balance + self.state.balance.added_robux
                        ajax_div["data-user-balance-robux"] = str(self.state.balance.current_balance)
                    except Exception as e:
                        ctx.log.error(f"game-pass balance set error: {e}")
                
                item_container = soup.select_one('#item-container') or soup.select_one('.section.page-content.library-item')
                user_id = None
                try:
                    if item_container:
                        user_id = item_container.get("data-user-id") or item_container.get("data-userid")
                        
                        existing_menu = item_container.select_one("#item-context-menu")
                        if existing_menu:
                            existing_menu.decompose()
                        
                        context_menu_div = soup.new_tag("div", id="item-context-menu")
                        
                        menu_button = soup.new_tag("button", **{
                            "class": "rbx-menu-item item-context-menu btn-generic-more-sm",
                            "data-toggle": "popover",
                            "data-bind": "popover-content"
                        })
                        span_icon = soup.new_tag("span", **{"class": "icon-more"})
                        menu_button.append(span_icon)
                        context_menu_div.append(menu_button)
                        
                        popover_div = soup.new_tag("div", **{"class": "rbx-popover-content", "data-toggle": "popover-content"})
                        ul_dropdown = soup.new_tag("ul", **{"class": "dropdown-menu", "role": "menu"})
                        
                        li_delete = soup.new_tag("li")
                        delete_button = soup.new_tag("button", **{"role": "button", "id": "delete-item"})
                        delete_button.string = "Delete from Inventory"
                        li_delete.append(delete_button)
                        
                        li_report = soup.new_tag("li")
                        report_link = soup.new_tag("a", **{
                            "id": "report-item",
                            "href": f"https://www.roblox.com/report-abuse/?targetId={item_id or 0}&submitterId=0&abuseVector=gamepass"
                        })
                        report_link.string = "Report Item"
                        li_report.append(report_link)
                        
                        ul_dropdown.append(li_delete)
                        ul_dropdown.append(li_report)
                        popover_div.append(ul_dropdown)
                        context_menu_div.append(popover_div)
                        
                        if item_container.contents:
                            item_container.insert(-1, context_menu_div)
                        else:
                            item_container.append(context_menu_div)
                except Exception:
                    user_id = None
                
                price_container_text = soup.select_one('.price-container-text')
                if price_container_text:
                    if not price_container_text.select_one('.item-first-line'):
                        div_owned = soup.new_tag('div', **{'class': 'item-first-line'})
                        div_owned.string = "This item is available in your inventory."
                        price_container_text.insert(0, div_owned)
                
                buy_button = soup.select_one('button.PurchaseButton')
                if buy_button:
                    uid_for_href = (user_id if user_id else "0")
                    inventory_link = soup.new_tag('a', id='inventory-button',
                                                href=f'https://www.roblox.com/users/{uid_for_href}/inventory',
                                                **{'class': 'btn-fixed-width-lg btn-control-md', 'data-button-action': 'inventory'})
                    inventory_link.string = "Inventory"
                    buy_button.replace_with(inventory_link)
                
                name_div = soup.select_one('.border-bottom.item-name-container > div')
                if name_div:
                    owned_already = any(
                        (child.string and "Item Owned" in child.string) or (child.get("class") and "label-checkmark" in child.get("class", []))
                        for child in name_div.find_all(recursive=False)
                    )
                    if not owned_already:
                        divider = soup.new_tag('div', **{'class': 'divider'})
                        divider.string = "\xa0"
                        label_checkmark = soup.new_tag('div', **{'class': 'label-checkmark'})
                        span_icon = soup.new_tag('span', **{'class': 'icon-checkmark-white-bold'})
                        label_checkmark.append(span_icon)
                        span_owned = soup.new_tag('span')
                        span_owned.string = "Item Owned"
                        name_div.append(divider)
                        name_div.append(label_checkmark)
                        name_div.append(span_owned)
                
                self.set_response_text(flow, str(soup))
            except Exception as e:
                ctx.log.error(f"game-pass transform error: {e}")
            return True
        
        if "roblox.com/games/getgamepassesinnerpartial" in url:
            html = flow.response.get_text()
            soup = BeautifulSoup(html, "html.parser")
            
            for li in soup.select("li.list-item.real-game-pass"):
                a_tag = li.select_one("a.gear-passes-asset")
                if not a_tag:
                    continue
                
                match = re.search(r"/game-pass/(\d+)/", a_tag.get("href", ""))
                if not match:
                    continue
                item_id = match.group(1)
                button = li.select_one("button.PurchaseButton")
                product_id = None
                if button:
                    product_id = button.get("data-product-id")
                
                if product_id:
                    self.state.cache.gamepass_product_id.set(str(product_id), str(item_id))
                if item_id in self.state.inventory.bought_items:
                    footer = li.select_one("div.store-card-footer")
                    if footer:
                        button = footer.select_one("button.PurchaseButton")
                        if button:
                            button.decompose()
                        owned_tag = soup.new_tag("h5")
                        owned_tag.string = "Owned"
                        footer.append(owned_tag)
            self.set_response_text(flow, str(soup))
            return True
        
        if "apis.roblox.com/game-passes/v1/game-passes/" in url and "/purchase" in url:
            request_json = self.get_request_json(flow)
            if not request_json:
                return False
            
            request_json["expectedPrice"] -= 1
            if request_json["expectedPrice"] > (self.state.balance.current_balance or 0):
                return False
            
            self.state.balance.current_balance -= request_json["expectedPrice"]
            self.state.balance.fake_spent_robux += request_json["expectedPrice"]
            
            product_id = flow.request.path.split('/')[4]
            item_id = self.state.cache.gamepass_product_id.get(str(product_id))
            if not item_id:
                return False
            
            page = await self.roblox_api.fetch_badge_page(item_id, self.state.user.cookie)
            game_id = None
            game_name = None
            creator_id = None
            creator_name = None
            pass_name = None
            strange_item_id = None
            is_group = False
            
            if page:
                soup = BeautifulSoup(page, "html.parser")
                a = soup.select_one("div.asset-info a.text-name")
                if a:
                    game_id = a.get("href", "").rstrip("/").split("/")[-1]
                    game_name = a.get_text(strip=True)
                
                container = soup.select_one("#item-container")
                if container:
                    strange_item_id = int(container.get("data-item-id"))
                    creator_name = container.get("data-seller-name")
                    pass_name = container.get("data-item-name")
                    span_tag = soup.select_one('span.verified-badge-icon')
                    if span_tag and span_tag.has_attr('data-creatorid'):
                        try:
                            creator_id = int(span_tag['data-creatorid'])
                        except ValueError:
                            creator_id = None
                    
                    a_tag = soup.select_one('.item-name-container .text-label a.text-name')
                    if a_tag and 'href' in a_tag.attrs:
                        href = a_tag['href'].rstrip('/')
                        parts = href.split('/')
                        if "communities" in parts:
                            is_group = True
            
            try:
                bought_data = {
                    "id": 0,
                    "idHash": "x",
                    "created": current_time(),
                    "transactionType": "Purchase",
                    "isPending": False,
                    "agent": {
                        "id": creator_id,
                        "type": "Group" if is_group else "User",
                        "name": creator_name
                    },
                    "details": {
                        "id": int(item_id),
                        "name": pass_name,
                        "type": "GamePass",
                        "place": {
                            "placeId": int(game_id) if game_id else 0,
                            "universeId": 0,
                            "name": game_name or ""
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
                
                if page and strange_item_id:
                    description_elem = soup.find("p", id="item-details-description")
                    description = description_elem.get_text(strip=True) if description_elem else ""
                    gamepass_inventory_data = {
                        "gamePassId": int(item_id),
                        "iconAssetId": int(strange_item_id),
                        "name": pass_name,
                        "description": description,
                        "isForSale": True,
                        "price": request_json["expectedPrice"],
                        "creator": {
                            "creatorType": "Group" if is_group else "User",
                            "creatorId": creator_id,
                            "name": creator_name
                        }
                    }
                    self.state.inventory.gamepass_inventory.append(gamepass_inventory_data)
                
                response_data = {
                    "purchased": True,
                    "reason": "Success",
                    "productId": int(product_id),
                    "currency": 1,
                    "price": request_json["expectedPrice"],
                    "assetId": int(strange_item_id) if strange_item_id else 0,
                    "assetName": pass_name,
                    "assetType": "Game Pass",
                    "assetTypeDisplayName": "Pass",
                    "assetIsWearable": False,
                    "sellerName": creator_name,
                    "transactionVerb": "bought",
                    "isMultiPrivateSale": False
                }
                self.set_response_json(flow, response_data)
            except Exception as e:
                ctx.log.error(f"finalize gamepass purchase error: {e}")
            return True
        
        if "https://apis.roblox.com/game-passes/v1/game-passes/" in url and ":revokeownership" in url:
            item_id = flow.request.path.split('/')[-1].split(':')[0]
            if item_id in self.state.inventory.bought_items:
                del self.state.inventory.bought_items[item_id]
                flow.response.status_code = 200
                return True
            return False
        
        if "apis.roblox.com/game-passes/v1/users/" in url and "/game-passes" in url:
            response_json = self.parse_json(flow.response.get_text())
            if response_json:
                for gamepass in self.state.inventory.gamepass_inventory:
                    response_json["gamePasses"].insert(0, gamepass)
                self.set_response_json(flow, response_json)
                return True
            return False
        
        return False
