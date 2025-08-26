import math
from typing import Dict, Any, List
from .api import api
from .common import DATABASE_URL, PROXY_URL, truncate_array, card

async def get_building_card(locale: str, path_or_id: str, *, quantity: int = 1, deep_desert: bool = False) -> Dict[str,Any]:
    data = await api.get(path_or_id, locale.lower())
    if not data:
        return card(description=f'The building "{path_or_id}" could not be found.')
    fields: List[Dict[str,Any]] = []

    ings = data.get("ingredients") or []
    if ings:
        lines = []
        for ing in ings:
            ent = (ing or {}).get("entity") or {}
            q = (ing or {}).get("quantity") or 0
            final_q = math.ceil((q * quantity) / 2) if deep_desert else q * quantity
            nm = ent.get("name") or "Unknown"
            url = f"{DATABASE_URL}/items/{ent.get('id')}" if ent.get("id") else None
            lines.append(f"- x{final_q} [{nm}]({url})" if url else f"- x{final_q} {nm}")
        fields.append({"name":"Ingredients","value":"\n".join(truncate_array(lines, 10)), "inline": True})

    return card(
        title=data.get("name"),
        url=f"{DATABASE_URL}/buildables/{data.get('id')}" if data.get("id") else None,
        description=data.get("description"),
        thumbnail=(PROXY_URL + data["iconPath"]) if data.get("iconPath") else None,
        fields=fields
    )
