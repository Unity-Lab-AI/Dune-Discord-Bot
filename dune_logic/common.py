from typing import Iterable, List, TypeVar, Dict, Any

DATABASE_URL = "https://dune.gaming.tools"
PROXY_URL = "https://proxy.wali.glazk0.dev"
KO_FI_URL = "https://ko-fi.com/glazk0"
DEVELOPERS = ["247344130798256130"]

SUPPORTED_LOCALES = (
    "en","de","es","fr","it","ja","ko","pl","pt-br","ru","tr","uk","zh-cn","zh-tw"
)

SUPPORTED_LOCALES_NAMES = {
  "en": "English",
  "de": "Deutsch",
  "es": "Español",
  "fr": "Français",
  "it": "Italiano",
  "ja": "日本語",
  "ko": "한국어",
  "pl": "Polski",
  "pt-br": "Português (Brasil)",
  "ru": "Русский",
  "tr": "Türkçe",
  "uk": "Українська",
  "zh-cn": "中文（中国）",
  "zh-tw": "中文（台灣）",
}

def truncate_array(arr: List[str], length: int) -> List[str]:
    if len(arr) <= length:
        return list(arr)
    truncated = list(arr[:length])
    remaining = len(arr) - length
    return truncated + [f"and {remaining} more"]

def card(*, title=None, url=None, description=None, thumbnail=None, fields=None) -> Dict[str, Any]:
    return {
        "title": title, "url": url, "description": description, "thumbnail": thumbnail,
        "fields": fields or []
    }
