from typing import Dict, Any, List
from .api import api
from .common import DATABASE_URL, PROXY_URL, truncate_array, card

async def get_contract_card(locale: str, path_or_id: str) -> Dict[str,Any]:
    data = await api.get(path_or_id, locale.lower())
    if not data:
        return card(description=f'The contract "{path_or_id}" could not be found.')
    fields: List[Dict[str,Any]] = []

    # XP
    if data.get("xpReward"):
        fields.append({"name":"XP Reward","value":f"{int(data['xpReward']):,}", "inline":False})

    # Conditions
    conds = data.get("conditions") or []
    if conds:
        lines = []
        for c in conds:
            nm = c.get("name")
            if nm:
                if c.get("number"):
                    nm = nm.replace("{number}", str(c["number"]))
                ent = ((c.get("contractItem") or {}).get("entity") or {})
                if ent.get("name"):
                    url = f"{DATABASE_URL}/{ent.get('mainCategoryId')}/{ent.get('id')}"
                    nm = nm.replace("{item_name}", f"[{ent['name']}]({url})")
                lines.append(nm)
            else:
                lines.append("Unknown")
        if lines:
            fields.append({"name":"Conditions","value":"\n".join(truncate_array([f"- {l}" for l in lines], 5)), "inline":False})

    # Rewards
    rewards: List[str] = []
    for it in (data.get("itemRewards") or []):
        ent = (it or {}).get("entity") or {}
        cnt = (it or {}).get("count")
        nm = ent.get("name")
        if not nm:
            rewards.append("Unknown")
        else:
            if cnt:
                if ent.get("isHidden"):
                    rewards.append(f"x{cnt} {nm}")
                else:
                    url = f"{DATABASE_URL}/{ent.get('mainCategoryId')}/{ent.get('id')}"
                    rewards.append(f"x{cnt} [{nm}]({url})")
            else:
                rewards.append(nm)
    for cr in (data.get("contractCustomRewards") or []):
        rewards.append(cr.get("name") or "Unknown")
    if rewards:
        fields.append({"name":"Rewards","value":"\n".join(truncate_array([f"- {r}" for r in rewards], 5)), "inline":False})

    # Chain
    if data.get("chainName") and data.get("chainContracts"):
        vals = []
        for c in data["chainContracts"]:
            url = f"{DATABASE_URL}/{c.get('mainCategoryId')}/{c.get('id')}"
            vals.append(f"- [{c.get('name','Unknown')}]({url})")
        fields.append({"name": data["chainName"], "value": "\n".join(truncate_array(vals, 5)), "inline": False})

    return card(
        title=data.get("name"),
        url=f"{DATABASE_URL}/{data.get('mainCategoryId')}/{data.get('id')}" if data.get("id") else None,
        description=data.get("description"),
        thumbnail=(PROXY_URL + data["iconPath"]) if data.get("iconPath") else None,
        fields=fields
    )
