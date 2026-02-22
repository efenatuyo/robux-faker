from dataclasses import dataclass
from typing import Dict

PURCHASE_OVERRIDE = {
    "purchaseResult": "Purchase transaction success",
    "purchased": True,
    "pending": False,
    "errorMessage": None
}

ASSET_TYPES: Dict[int, str] = {
    1: "Image",
    2: "TShirt",
    3: "Audio",
    4: "Mesh",
    5: "Lua",
    6: "HTML",
    7: "Text",
    8: "Hat",
    9: "Place",
    10: "Model",
    11: "Shirt",
    12: "Pants",
    13: "Decal",
    16: "Avatar",
    17: "Head",
    18: "Face",
    19: "Gear",
    21: "Badge",
    22: "GroupEmblem",
    24: "Animation",
    25: "Arms",
    26: "Legs",
    27: "Torso",
    28: "RightArm",
    29: "LeftArm",
    30: "LeftLeg",
    31: "RightLeg",
    32: "Package",
    33: "YouTubeVideo",
    34: "GamePass",
    37: "Code",
    38: "Plugin",
    39: "SolidModel",
    40: "MeshPart",
    41: "HairAccessory",
    42: "FaceAccessory",
    43: "NeckAccessory",
    44: "ShoulderAccessory",
    45: "FrontAccessory",
    46: "BackAccessory",
}

@dataclass
class CacheConfig:
    gamepass_product_id_maxlen: int = 100
    developer_product_id_maxlen: int = 250
    universe_ids_maxlen: int = 250
    item_info_maxlen: int = 250
    avatar_combo_maxlen: int = 250
    lowest_resale_maxlen: int = 1000
    resellers_data_maxlen: int = 10000
    avatar_image_modify_maxlen: int = 100

@dataclass
class HTTPConfig:
    timeout_seconds: int = 10
    retry_count: int = 30
    chunk_size: int = 100

@dataclass
class RobuxConfig:
    added_robux: int = 3640478
    group_id: int = 14116868
    group_name: str = "Dust bunnys"

@dataclass
class PersistenceConfig:
    state_file: str = "state.json"
    auto_save_interval: int = 300

@dataclass
class AvatarConfig:
    version_id_min: int = 999999
    version_id_max: int = 999999999
    accessory_order_min: int = 1
    accessory_order_max: int = 20
    accessory_types: list = None
    
    def __post_init__(self):
        if self.accessory_types is None:
            self.accessory_types = [41, 42, 43, 44, 45, 46]

@dataclass
class InventoryConfig:
    user_asset_id_min: int = 99999999
    user_asset_id_max: int = 9999999999

@dataclass
class ProxyConfig:
    default_port: int = 8080
    listen_host: str = "0.0.0.0"
