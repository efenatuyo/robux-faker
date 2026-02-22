from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, List

def parse_url_params(url: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    flat_params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
    return flat_params

def split_dict(d: Dict[Any, Any], chunk_size: int = 100) -> List[Dict[Any, Any]]:
    items = list(d.items())
    return [dict(items[i:i + chunk_size]) for i in range(0, len(items), chunk_size)]
