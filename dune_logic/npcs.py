from typing import Dict, Any, List
from .api import api
from .common import DATABASE_URL, PROXY_URL, truncate_array, card

async def get_npc_card(locale: str, path_or_id: str) -> Dict[str,Any]:
    data = await api.get(path_or_id, locale.lower())
    if not data:
        return card(description=f'The npc "{path_or_id}" could not be found.')
    fields: List[Dict[str,Any]] = []

    # Contracts
    contracts = data.get("contracts") or []
    if contracts:
        lines = []
        for c in contracts:
            nm = c.get("name") or "Unknown"
            url = f"{DATABASE_URL}/{c.get('mainCategoryId')}/{c.get('id')}" if c.get("id") else None
            lines.append(f"- [{nm}]({url})" if url else f"- {nm}")
        fields.append({"name":"Related Contracts","value":"\n".join(truncate_array(lines, 10)), "inline": False})

    # Quests
    quests = data.get("quests") or []
    if quests:
        lines = []
        for q in quests:
            nm = q.get("name") or "Unknown"
            url = f"{DATABASE_URL}/{q.get('mainCategoryId')}/{q.get('id')}" if q.get("id") else None
            lines.append(f"- [{nm}]({url})" if url else f"- {nm}")
        fields.append({"name":"Related Quests","value":"\n".join(truncate_array(lines, 10)), "inline": False})

    # Sells Items
    sells = data.get("sellsItems") or []
    if sells:
        lines = []
        for it in sells:
            ent = (it or {}).get("entity") or {}
            nm = ent.get("name") or "Unknown"
            url = f"{DATABASE_URL}/{ent.get('mainCategoryId')}/{ent.get('id')}" if ent.get("id") else None
            base = ent.get("baseBuyFromVendorPrice")
            pct = it.get("percentToApplyOnBaseItemPrice")
            price = round(base * pct) if (base is not None and pct) else None
            stock = it.get("stockAmount")
            stock_str = f"x{stock}" if stock else "∞"
            pr = f" for {price:,}/unit" if price is not None else ""
            line = f"- {stock_str} [{nm}]({url}){pr}" if url else f"- {stock_str} {nm}{pr}"
            lines.append(line)
        fields.append({"name":"Sells Items","value":"\n".join(truncate_array(lines, 10)), "inline": False})

    return card(
        title=data.get("name"),
        url=f"{DATABASE_URL}/{data.get('mainCategoryId')}/{data.get('id')}" if data.get("id") else None,
        description=data.get("description"),
        thumbnail=(PROXY_URL + data["iconPath"]) if data.get("iconPath") else None,
        fields=fields
    )
