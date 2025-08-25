from typing import Dict, Any, List, Optional
from .api import api
from .common import DATABASE_URL

def _dedupe_uniques(uniques_list: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    seen = {}
    for u in uniques_list:
        for loot in (u.get("visibleLoot") or []):
            ent = (loot or {}).get("entity") or {}
            eid = ent.get("id")
            if eid and eid not in seen:
                seen[eid] = ent
    return sorted(seen.values(), key=lambda e: (e.get("name") or "").lower())

async def get_weekly_uniques_message() -> Dict[str,Any]:
    """Return a dict with keys: content (str) and next_coriolis_time (int|None)."""
    data = await api.get("en/dd-live-data", "en")
    if not data:
        return {"content": "Deep Desert data is currently unavailable.", "next_coriolis_time": None}
    next_time = data.get("nextCoriolisTime")
    uniques = _dedupe_uniques(data.get("uniquesList") or [])
    lines = [
        "**This Week's Deep Desert Uniques**",
        "",
        f"Next Coriolis Reset: <t:{next_time}:F> (<t:{next_time}:R>)" if next_time else "Next Coriolis Reset: Unknown"
    ]
    if uniques:
        items = [f"[{u['name']}]({DATABASE_URL}/{u['mainCategoryId']}/{u['id']})" for u in uniques if u.get('name') and u.get('id')]
        items.sort()
        lines += ["", *[f"- {x}" for x in items], "", f"To see locations and probabilities, visit the [Dune Awakening Database]({DATABASE_URL}/deep-desert)."]
    else:
        lines += ["", "No unique items available this week."]
    lines += ["", "*The times are in your local timezone.*"]
    return {"content": "\n".join(lines), "next_coriolis_time": next_time}
