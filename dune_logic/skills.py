from typing import Dict, Any, List
from .api import api
from .common import DATABASE_URL, PROXY_URL, card

def _fmt_attr(a: Dict[str,Any]) -> str:
    nm = a.get("name")
    val = a.get("value")
    if nm is None or val is None:
        return ""
    if a.get("isPercentBased"):
        v = f"{abs(val*100):.2f}%"
    else:
        v = f"{val}"
    sign = "-" if (val or 0) < 0 else ""
    suffix = f"\n> {a.get('internalName')} - {a.get('operation')}" if a.get("operation") and a.get("internalName") else ""
    return f"{nm}: {sign}{v}{suffix}"

async def get_skill_card(locale: str, path_or_id: str) -> Dict[str,Any]:
    data = await api.get(path_or_id, locale.lower())
    if not data:
        return card(description=f'The skill "{path_or_id}" could not be found.')
    fields: List[Dict[str,Any]] = []
    if data.get("skillTree"):
        fields.append({"name":"Skill Tree","value":str(data["skillTree"]),"inline":True})
    if data.get("skillType"):
        fields.append({"name":"Skill Type","value":str(data["skillType"]),"inline":True})
    if data.get("maxLevel"):
        fields.append({"name":"Max Level","value":str(data["maxLevel"]),"inline":True})
    # Group by level
    by_level = {}
    for a in (data.get("attributeBonuses") or []):
        lvl = a.get("level")
        if lvl is None: 
            continue
        by_level.setdefault(lvl, []).append(a)
    for lvl in sorted(by_level.keys()):
        values = []
        costs = data.get("costPerlevel") or []
        if len(costs) >= lvl and costs[lvl-1]:
            values.append(f"Cost: {costs[lvl-1]} Skill Points")
        for a in by_level[lvl]:
            s = _fmt_attr(a)
            if s:
                values.append(s)
        if not values:
            continue
        reqs = data.get("levelRequirements") or []
        level_req = reqs[lvl-1] if len(reqs) >= lvl else None
        body = "\n".join([*(f"- {v}" for v in values), *( [f"*{level_req}*"] if level_req else [] )])
        fields.append({"name": f"Level {lvl}", "value": body, "inline": False})
    return card(
        title=data.get("name"),
        url=f"{DATABASE_URL}/{data.get('mainCategoryId')}/{data.get('id')}" if data.get("id") else None,
        description=data.get("description"),
        thumbnail=(PROXY_URL + data["iconPath"]) if data.get("iconPath") else None,
        fields=fields
    )
