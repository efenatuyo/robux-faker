import json
import os
from typing import Any, Dict
from collections import deque
from models.state import ApplicationState, UserState, BalanceState, InventoryState, AvatarState, CacheState
from utils.data_structures import DequeDict
from config import CacheConfig, PersistenceConfig

_persistence_config = PersistenceConfig()
STATE_FILE = _persistence_config.state_file

class StatePersistence:
    @staticmethod
    def serialize_dequedict(dd: DequeDict) -> Dict[str, Any]:
        data_dict = {}
        order_list = []
        for key in dd.order:
            key_str = json.dumps(key) if not isinstance(key, (str, int, float, bool)) or key is None else str(key)
            data_dict[key_str] = StatePersistence.serialize_value(dd.data[key])
            order_list.append(key_str)
        return {
            "_type": "DequeDict",
            "maxlen": dd.maxlen,
            "data": data_dict,
            "order": order_list
        }
    
    @staticmethod
    def deserialize_dequedict(data: Dict[str, Any]) -> DequeDict:
        dd = DequeDict(maxlen=data["maxlen"])
        for key_str in data["order"]:
            try:
                if key_str.startswith(("[", "{")):
                    key = json.loads(key_str)
                elif key_str.isdigit():
                    key = int(key_str)
                elif key_str.replace(".", "", 1).isdigit():
                    key = float(key_str)
                elif key_str.lower() in ("true", "false"):
                    key = key_str.lower() == "true"
                elif key_str.lower() == "null":
                    key = None
                else:
                    key = key_str
            except (ValueError, TypeError, json.JSONDecodeError):
                key = key_str
            dd.set(key, StatePersistence.deserialize_value(data["data"][key_str]))
        return dd
    
    @staticmethod
    def serialize_deque(d: deque) -> Dict[str, Any]:
        return {
            "_type": "deque",
            "maxlen": d.maxlen,
            "items": list(d)
        }
    
    @staticmethod
    def deserialize_deque(data: Dict[str, Any]) -> deque:
        d = deque(data["items"], maxlen=data.get("maxlen"))
        return d
    
    @staticmethod
    def serialize_set(s: set) -> list:
        return list(s)
    
    @staticmethod
    def serialize_value(value: Any) -> Any:
        if isinstance(value, bytes):
            return None
        elif isinstance(value, DequeDict):
            serialized = StatePersistence.serialize_dequedict(value)
            if serialized.get("data"):
                cleaned_data = {}
                for k, v in serialized["data"].items():
                    if not isinstance(v, bytes):
                        cleaned_data[k] = StatePersistence.serialize_value(v)
                serialized["data"] = cleaned_data
            return serialized
        elif isinstance(value, deque):
            items = []
            for item in value:
                if not isinstance(item, bytes):
                    items.append(StatePersistence.serialize_value(item))
            return {
                "_type": "deque",
                "maxlen": value.maxlen,
                "items": items
            }
        elif isinstance(value, set):
            return [StatePersistence.serialize_value(item) for item in value if not isinstance(item, bytes)]
        elif isinstance(value, dict):
            return {k: StatePersistence.serialize_value(v) for k, v in value.items() if not isinstance(v, bytes)}
        elif isinstance(value, (list, tuple)):
            return [StatePersistence.serialize_value(item) for item in value if not isinstance(item, bytes)]
        else:
            return value
    
    @staticmethod
    def deserialize_value(value: Any) -> Any:
        if isinstance(value, dict):
            if value.get("_type") == "DequeDict":
                return StatePersistence.deserialize_dequedict(value)
            elif value.get("_type") == "deque":
                return StatePersistence.deserialize_deque(value)
            else:
                return {k: StatePersistence.deserialize_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [StatePersistence.deserialize_value(item) for item in value]
        else:
            return value
    
    @staticmethod
    def state_to_dict(state: ApplicationState) -> Dict[str, Any]:
        return {
            "user": {
                "user_id": state.user.user_id,
                "user_name": state.user.user_name,
                "user_premium": state.user.user_premium,
                "cookie": state.user.cookie,
                "x_csrf_token": state.user.x_csrf_token
            },
            "balance": {
                "real_balance": state.balance.real_balance,
                "current_balance": state.balance.current_balance,
                "fake_spent_robux": state.balance.fake_spent_robux,
                "added_robux": state.balance.added_robux
            },
            "inventory": StatePersistence.serialize_value(state.inventory.__dict__),
            "avatar": {
                "avatar_rules_roblox": state.avatar.avatar_rules_roblox,
                "avatar_wearing": state.avatar.avatar_wearing
            },
            "cache": {
                "gamepass_product_id": StatePersistence.serialize_value(state.cache.gamepass_product_id) if state.cache.gamepass_product_id else None,
                "developer_proudct_id": StatePersistence.serialize_value(state.cache.developer_proudct_id) if state.cache.developer_proudct_id else None,
                "universe_ids": StatePersistence.serialize_value(state.cache.universe_ids) if state.cache.universe_ids else None,
                "item_info": StatePersistence.serialize_value(state.cache.item_info) if state.cache.item_info else None,
                "avatar_combo": None,
                "lowest_resale": StatePersistence.serialize_value(state.cache.lowest_resale) if state.cache.lowest_resale else None,
                "resellers_data": StatePersistence.serialize_value(state.cache.resellers_data) if state.cache.resellers_data else None,
                "avatar_image_modify": StatePersistence.serialize_value(state.cache.avatar_image_modify) if state.cache.avatar_image_modify else None,
                "resellers_ids": StatePersistence.serialize_value(state.cache.resellers_ids) if state.cache.resellers_ids else None
            },
            "state": state.state
        }
    
    @staticmethod
    def dict_to_state(data: Dict[str, Any]) -> ApplicationState:
        state = ApplicationState()
        
        if "user" in data:
            user_data = data["user"]
            state.user = UserState(
                user_id=user_data.get("user_id"),
                user_name=user_data.get("user_name"),
                user_premium=user_data.get("user_premium"),
                cookie=user_data.get("cookie"),
                x_csrf_token=user_data.get("x_csrf_token")
            )
        
        if "balance" in data:
            balance_data = data["balance"]
            state.balance = BalanceState(
                real_balance=balance_data.get("real_balance"),
                current_balance=balance_data.get("current_balance"),
                fake_spent_robux=balance_data.get("fake_spent_robux", 0),
                added_robux=balance_data.get("added_robux", 3640478)
            )
        
        if "inventory" in data:
            inventory_data = StatePersistence.deserialize_value(data["inventory"])
            state.inventory = InventoryState(
                bought_items=inventory_data.get("bought_items", {}),
                bought_items_history=inventory_data.get("bought_items_history", {}),
                pending_products=inventory_data.get("pending_products", {}),
                gamepass_inventory=inventory_data.get("gamepass_inventory", []),
                profile_items=inventory_data.get("profile_items", []),
                currently_wearing=inventory_data.get("currently_wearing", []),
                avatar_creations=inventory_data.get("avatar_creations", []),
                emotes_wearing=inventory_data.get("emotes_wearing", [])
            )
        
        if "avatar" in data:
            avatar_data = data["avatar"]
            state.avatar = AvatarState(
                avatar_rules_roblox=avatar_data.get("avatar_rules_roblox"),
                avatar_wearing=avatar_data.get("avatar_wearing")
            )
        
        if "cache" in data:
            cache_data = data["cache"]
            cache_config = CacheConfig()
            
            state.cache = CacheState()
            
            if cache_data.get("gamepass_product_id"):
                state.cache.gamepass_product_id = StatePersistence.deserialize_value(cache_data["gamepass_product_id"])
            else:
                state.cache.gamepass_product_id = DequeDict(maxlen=cache_config.gamepass_product_id_maxlen)
            
            if cache_data.get("developer_proudct_id"):
                state.cache.developer_proudct_id = StatePersistence.deserialize_value(cache_data["developer_proudct_id"])
            else:
                state.cache.developer_proudct_id = DequeDict(maxlen=cache_config.developer_product_id_maxlen)
            
            if cache_data.get("universe_ids"):
                state.cache.universe_ids = StatePersistence.deserialize_value(cache_data["universe_ids"])
            else:
                state.cache.universe_ids = DequeDict(maxlen=cache_config.universe_ids_maxlen)
            
            if cache_data.get("item_info"):
                state.cache.item_info = StatePersistence.deserialize_value(cache_data["item_info"])
            else:
                state.cache.item_info = DequeDict(maxlen=cache_config.item_info_maxlen)
            
            if cache_data.get("avatar_combo"):
                state.cache.avatar_combo = StatePersistence.deserialize_value(cache_data["avatar_combo"])
            else:
                state.cache.avatar_combo = DequeDict(maxlen=cache_config.avatar_combo_maxlen)
            
            if cache_data.get("lowest_resale"):
                state.cache.lowest_resale = StatePersistence.deserialize_value(cache_data["lowest_resale"])
            else:
                state.cache.lowest_resale = DequeDict(maxlen=cache_config.lowest_resale_maxlen)
            
            if cache_data.get("resellers_data"):
                state.cache.resellers_data = StatePersistence.deserialize_value(cache_data["resellers_data"])
            else:
                state.cache.resellers_data = deque(maxlen=cache_config.resellers_data_maxlen)
            
            if cache_data.get("avatar_image_modify"):
                state.cache.avatar_image_modify = StatePersistence.deserialize_value(cache_data["avatar_image_modify"])
            else:
                state.cache.avatar_image_modify = deque(maxlen=cache_config.avatar_image_modify_maxlen)
            
            if cache_data.get("resellers_ids"):
                state.cache.resellers_ids = set(StatePersistence.deserialize_value(cache_data["resellers_ids"]))
            else:
                state.cache.resellers_ids = set()
        
        if "state" in data:
            state.state = data["state"]
        
        return state
    
    @staticmethod
    def save_state(state: ApplicationState, filepath: str = STATE_FILE) -> bool:
        try:
            state_dict = StatePersistence.state_to_dict(state)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(state_dict, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            try:
                from mitmproxy import ctx
                ctx.log.error(f"Failed to save state: {e}")
            except Exception:
                print(f"Failed to save state: {e}")
            return False
    
    @staticmethod
    def load_state(filepath: str = STATE_FILE) -> ApplicationState:
        if not os.path.exists(filepath):
            return ApplicationState()
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return StatePersistence.dict_to_state(data)
        except Exception as e:
            try:
                from mitmproxy import ctx
                ctx.log.error(f"Failed to load state: {e}")
            except Exception:
                print(f"Failed to load state: {e}")
            try:
                import shutil
                backup_path = filepath + ".backup"
                if os.path.exists(filepath):
                    shutil.copy2(filepath, backup_path)
                os.remove(filepath)
            except Exception:
                pass
            return ApplicationState()
