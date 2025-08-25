from typing import List, Dict, Any, Optional, Sequence, Tuple
from .api import api

async def search_autocomplete(locale: str, current: str, types: Sequence[str]) -> List[Dict[str,Any]]:
    data = await api.search(locale.lower(), current, types)
    return data[:25]

async def route_path(locale: str, full_path: str) -> Tuple[str, Dict[str,Any]]:
    """Return (kind, card) where kind is one of 'item','contract','building','npc','skill'."""
    full_path = full_path.strip()
    low = full_path.lower()
    if low.startswith("items/"):
        from .items import get_item_card
        return "item", await get_item_card(locale, full_path)
    if low.startswith("contracts/"):
        from .contracts import get_contract_card
        return "contract", await get_contract_card(locale, full_path)
    if low.startswith("buildables/") or low.startswith("placeables/"):
        from .buildings import get_building_card
        return "building", await get_building_card(locale, full_path)
    if low.startswith("npcs/"):
        from .npcs import get_npc_card
        return "npc", await get_npc_card(locale, full_path)
    if low.startswith("skills/"):
        from .skills import get_skill_card
        return "skill", await get_skill_card(locale, full_path)
    raise ValueError(f"Unrecognized path: {full_path}")
