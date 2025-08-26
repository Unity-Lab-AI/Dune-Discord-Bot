from typing import Dict, Any, List
from .api import api
from .common import DATABASE_URL, PROXY_URL, truncate_array, card

def _fmt_attributes(attrs: List[Dict[str,Any]]) -> List[str]:
    out: List[str] = []
    for a in attrs:
        attribute = (a or {}).get("attribute") or {}
        nm = (attribute.get("name") or "").rstrip(":")
        val = (a or {}).get("value")
        if not nm or val is None:
            continue
        if isinstance(val, (int, float)):
            if attribute.get("percentBased"):
                vv = f"{round(float(val)*100, 1)}%"
            else:
                vv = str(round(float(val), 3))
        elif isinstance(val, str) and val.strip():
            vv = val
        else:
            continue
        out.append(f"**{nm}**: {vv}")
    return out

async def get_item_card(locale: str, path_or_id: str) -> Dict[str,Any]:
    data = await api.get(path_or_id, locale.lower())
    if not data:
        return card(description=f'The item "{path_or_id}" could not be found.')
    fields: List[Dict[str,Any]] = []

    attrs = data.get("attributeValues") or []
    lines = _fmt_attributes(attrs)
    if lines:
        fields.append({"name":"Attributes","value":"\n".join(f"- {l}" for l in lines),"inline":False})

    rfc = data.get("requiredForContract") or []
    if rfc:
        vals = []
        for c in rfc:
            nm = c.get("name") or "Unknown"
            url = f"{DATABASE_URL}/{c.get('mainCategoryId')}/{c.get('id')}" if c.get("id") else None
            vals.append(f"- [{nm}]({url})" if url else f"- {nm}")
        fields.append({"name":"Related Contracts","value":"\n".join(truncate_array(vals, 5)), "inline": False})

    sold_by = data.get("soldBy") or []
    if sold_by:
        vals = []
        for v in sold_by:
            ent = (v or {}).get("entity") or {}
            nm = ent.get("name") or "Unknown"
            url = f"{DATABASE_URL}/{ent.get('mainCategoryId')}/{ent.get('id')}" if ent.get("id") else None
            vals.append(f"- [{nm}]({url})" if url else f"- {nm}")
        fields.append({"name":"Sold By","value":"\n".join(truncate_array(vals, 5)), "inline": False})

    reward_from = data.get("rewardFrom") or []
    if reward_from:
        vals = []
        for r in reward_from:
            ent = (r or {}).get("entity") or {}
            nm = ent.get("name") or "Unknown"
            cnt = (r or {}).get("count")
            url = f"{DATABASE_URL}/{ent.get('mainCategoryId')}/{ent.get('id')}" if ent.get("id") else None
            prefix = f"x{cnt} " if (cnt and cnt>1) else ""
            vals.append(f"- {prefix}[{nm}]({url})" if url else f"- {prefix}{nm}")
        fields.append({"name":"Rewarded From","value":"\n".join(truncate_array(vals, 5)), "inline": False})

    return card(
        title=data.get("name"),
        url=f"{DATABASE_URL}/{data.get('mainCategoryId')}/{data.get('id')}" if data.get("id") else None,
        description=data.get("description"),
        thumbnail=(PROXY_URL + data["iconPath"]) if data.get("iconPath") else None,
        fields=fields
    )
