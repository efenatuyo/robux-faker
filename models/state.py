from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from collections import deque
from utils.data_structures import DequeDict
from config import CacheConfig

@dataclass
class UserState:
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    user_premium: Optional[str] = None
    cookie: Optional[str] = None
    x_csrf_token: Optional[str] = None

@dataclass
class BalanceState:
    real_balance: Optional[int] = None
    current_balance: Optional[int] = None
    fake_spent_robux: int = 0
    added_robux: int = 3640478

@dataclass
class InventoryState:
    bought_items: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    bought_items_history: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    pending_products: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    gamepass_inventory: List[Dict[str, Any]] = field(default_factory=list)
    profile_items: List[Dict[str, Any]] = field(default_factory=list)
    currently_wearing: List[int] = field(default_factory=list)
    avatar_creations: List[Any] = field(default_factory=list)
    emotes_wearing: List[List[Any]] = field(default_factory=list)

@dataclass
class AvatarState:
    avatar_rules_roblox: Optional[Dict[str, Any]] = None
    avatar_wearing: Optional[Dict[str, Any]] = None

@dataclass
class CacheState:
    gamepass_product_id: DequeDict = field(default=None)
    developer_proudct_id: DequeDict = field(default=None)
    universe_ids: DequeDict = field(default=None)
    item_info: DequeDict = field(default=None)
    avatar_combo: DequeDict = field(default=None)
    lowest_resale: DequeDict = field(default=None)
    resellers_data: deque = field(default=None)
    avatar_image_modify: deque = field(default=None)
    resellers_ids: set = field(default_factory=set)

@dataclass
class ApplicationState:
    user: UserState = field(default_factory=UserState)
    balance: BalanceState = field(default_factory=BalanceState)
    inventory: InventoryState = field(default_factory=InventoryState)
    avatar: AvatarState = field(default_factory=AvatarState)
    cache: CacheState = field(default_factory=CacheState)
    state: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        cache_config = CacheConfig()
        if self.cache.gamepass_product_id is None:
            self.cache.gamepass_product_id = DequeDict(maxlen=cache_config.gamepass_product_id_maxlen)
        if self.cache.developer_proudct_id is None:
            self.cache.developer_proudct_id = DequeDict(maxlen=cache_config.developer_product_id_maxlen)
        if self.cache.universe_ids is None:
            self.cache.universe_ids = DequeDict(maxlen=cache_config.universe_ids_maxlen)
        if self.cache.item_info is None:
            self.cache.item_info = DequeDict(maxlen=cache_config.item_info_maxlen)
        if self.cache.avatar_combo is None:
            self.cache.avatar_combo = DequeDict(maxlen=cache_config.avatar_combo_maxlen)
        if self.cache.lowest_resale is None:
            self.cache.lowest_resale = DequeDict(maxlen=cache_config.lowest_resale_maxlen)
        if self.cache.resellers_data is None:
            self.cache.resellers_data = deque(maxlen=cache_config.resellers_data_maxlen)
        if self.cache.avatar_image_modify is None:
            self.cache.avatar_image_modify = deque(maxlen=cache_config.avatar_image_modify_maxlen)
