import discord
import re
import logging
import asyncio
import aiohttp
from io import BytesIO
import json
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, api_client=None, memory_manager=None, config=None, data_manager=None, bot=None):
        self.api_client = api_client
        self.memory_manager = memory_manager
        self.config = config
        self.data_manager = data_manager
        self.bot = bot

        self.synonyms = {
            "shotgun": ["scattergun", "12 gauge", "12g", "pump-action", "auto-shotgun"],
            "copter": ["ornithopter"],
        }

        # Load game data from individual JSON files in the information directory.
        # Each file's contents are stored under a key matching the filename
        # (without extension) so the bot can look up specific domains on demand.
        self.game_data: Dict[str, Dict[str, Any]] = {}
        info_dir = Path("information")
        for json_file in info_dir.glob("*.json"):
            name = json_file.stem
            self.game_data[name] = self.load_game_data(json_file)

        # Build a short summary of each information file so the LLM knows
        # what domains are available when planning which files to request.
        self.file_summaries: Dict[str, str] = {}
        for name, data in self.game_data.items():
            self.file_summaries[name] = self._summarize_game_data(data)

        # Merge item dictionaries across all loaded domains for quick lookup
        # (used when mapping user text to a canonical item name).
        self.items: Dict[str, Dict[str, Any]] = {}
        for data in self.game_data.values():
            self.items.update(self._extract_items(data))

        self.item_lookup: Dict[str, Tuple[str, Dict[str, Any]]] = {
            self.normalize_text(name): (name, details) for name, details in self.items.items()
        }

        # Grab a game summary if any file provides one
        self.game_summary = ""
        for data in self.game_data.values():
            if isinstance(data, dict) and data.get("game_summary"):
                self.game_summary = data["game_summary"]
                break

        self.domain_terms = {
            "item", "items", "gear", "weapon", "weapons", "gun", "guns", "shotgun",
            "knife", "sword", "shield", "armor", "vehicle", "ornithopter", "thopter",
            "stats", "stat", "damage", "dps", "cost", "craft", "crafting", "blueprint",
            "recipe", "build", "best", "which", "recommend", "recommendation", "compare",
            "vs", "versus", "loadout", "kit"
        }
        self.greeting_terms = {"hi","hello","hey","yo","sup","howdy","greetings","hola"}

    def load_game_data(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load game data from {path}: {e}")
            return {}

    def _extract_items(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        if isinstance(data, dict):
            if "items" in data and isinstance(data["items"], dict):
                return data["items"]
            if "item_dictionary" in data and isinstance(data["item_dictionary"], dict):
                return data["item_dictionary"]
            meta_keys = {"game_summary", "version", "_meta"}
            items = {k: v for k, v in data.items() if k not in meta_keys and isinstance(v, dict)}
            if items:
                return items
        return {}

    def _summarize_game_data(self, data: Dict[str, Any]) -> str:
        """Generate a brief, human-readable summary of a game data file.

        The summary lists a handful of top-level item names or keys so the LLM
        has an idea of what the file contains before requesting it.
        """

        if not isinstance(data, dict):
            return ""

        # Prefer explicit summaries if present
        summary = data.get("game_summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()

        # Otherwise build a summary from item names or keys
        items = self._extract_items(data)
        if items:
            if len(items) == 1 and isinstance(next(iter(items.values())), dict):
                inner = next(iter(items.values()))
                keys = list(inner.keys())[:5]
            else:
                keys = list(items.keys())[:5]
        else:
            keys = list(data.keys())[:5]
        return ", ".join(map(str, keys))

    def normalize_text(self, text: str) -> str:
        text = (text or "").lower()
        synonyms = getattr(self, "synonyms", {})
        for src, alts in synonyms.items():
            pattern = r"\b(" + re.escape(src) + r"|" + "|".join(map(re.escape, alts)) + r")\b"
            text = re.sub(pattern, src, text)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def is_small_talk(self, user_message: str) -> bool:
        norm = self.normalize_text(user_message)
        tokens = set(norm.split())
        if not tokens:
            return False
        if len(norm.split()) <= 6 and (tokens & self.greeting_terms):
            if tokens & self.domain_terms:
                return False
            return True
        return False

    def is_item_query(self, user_message: str) -> bool:
        norm = self.normalize_text(user_message)
        tokens = set(norm.split())
        return bool(tokens & self.domain_terms)


    async def _ai_query_plan(self, model: str, user_message: str) -> Dict[str, Any]:
        """Ask the LLM which information files and keywords are relevant.

        The model is prompted to return JSON with two arrays:
        - ``files``: information domain filenames (e.g., "weapons", "armor").
        - ``keywords``: search terms to locate specific entries.
        """

        sys = self.config.info_request_instructions
        overview_lines = [f"{name}: {summary}" for name, summary in self.file_summaries.items()]
        overview = "\n".join(overview_lines)
        usr = (
            f"Available files and summaries:\n{overview}\n\n"
            f"User question: {user_message}\nReturn only JSON."
        )
        try:
            out = await self.api_client.send_message(
                [{"role": "system", "content": sys}, {"role": "user", "content": usr}],
                model,
            )
            m = re.search(r"\{[\s\S]*\}", out or "")
            plan = json.loads(m.group(0)) if m else {}
            plan["files"] = [self.normalize_text(f) for f in plan.get("files", []) if isinstance(f, str)]
            plan["keywords"] = [self.normalize_text(k) for k in plan.get("keywords", []) if isinstance(k, str)]
            return plan
        except Exception as e:
            logger.warning(f"Query-plan parse failed, falling back to heuristic: {e}")
            return {}

    def _retrieve_data(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Return the raw contents of each requested information file."""

        results: Dict[str, Any] = {}
        for file in plan.get("files", []):
            data = self.game_data.get(file)
            if data is not None:
                results[file] = data
        return results

    def _game_context_json(self, matches: Dict[str, Any]) -> str:
        """Serialize matched game data to JSON for LLM consumption."""

        return json.dumps(matches, ensure_ascii=False, indent=2)

    async def handle_message(self, message):
        channel_id = str(message.channel.id)
        guild_id = str(message.guild.id) if message.guild else "DM"
        user_id = str(message.author.id)
        user_message = message.content

        if user_message.lower().startswith("!"):
            return

        self.memory_manager.add_user_message(channel_id, guild_id, user_id, user_message)
        user_model = self.memory_manager.get_user_model(guild_id, user_id)

        if self.is_small_talk(user_message):
            system_prompt = f"{self.config.system_instructions}\nYou are {user_model}."
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
            try:
                ai_response = await self.api_client.send_message(messages, user_model)
            except Exception as e:
                await message.channel.send(f"<@{user_id}> Error: Failed to fetch response - {e}")
                return
            ai_response_clean = self.clean_response(ai_response) or "Hey!"
            final_message = self.build_message(ai_response_clean)
            await self._send_message(message, user_id, final_message, user_message.lower())
            return

        messages = []
        system_prompt = f"{self.config.system_instructions}\nYou are {user_model}."
        messages.append({"role": "system", "content": system_prompt})

        channel_memories = self.memory_manager.channel_memories.get(channel_id, [])
        if channel_memories:
            messages.append({"role": "user", "content": "\n".join(channel_memories)})

        model_history = self.memory_manager.get_user_model_history(guild_id, user_id, user_model)
        for msg in model_history:
            if msg["content"].strip():
                role = "assistant" if msg["role"] == "ai" else msg["role"]
                messages.append({"role": role, "content": msg["content"]})

        include_gamedata = self.is_item_query(user_message)
        if include_gamedata:
            plan = await self._ai_query_plan(user_model, user_message)
            matches = self._retrieve_data(plan)
            game_context = self._game_context_json(matches)
            guardrails = (
                "When the question concerns items, gear, or stats, use ONLY the following GameData JSON "
                "for concrete names or numbers. If an asked-for item is missing, say so briefly and ask a short follow-up. "
                "Do not comment about GameData if the user wasn't asking about items."
            )
            messages.append({"role": "system", "content": f"{guardrails}\n\nGameData:\n{game_context}"})

        messages.append({"role": "user", "content": user_message})

        try:
            ai_response = await self.api_client.send_message(messages, user_model)
            if not ai_response or not ai_response.strip():
                await message.channel.send(f"<@{user_id}> Error: Empty response from API")
                return
        except Exception as e:
            await message.channel.send(f"<@{user_id}> Error: Failed to fetch response - {e}")
            return

        ai_response_clean = self.clean_response(ai_response) or "Got it."
        final_message = self.build_message(ai_response_clean)
        await self._send_message(message, user_id, final_message, user_message.lower())

    def clean_response(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"\[/?CODE\]", "", text, flags=re.IGNORECASE)
        return text.strip()

    def build_message(self, content: str) -> Dict[str, Any]:
        lines = [ln.strip() for ln in content.splitlines()]
        text_lines = []
        image_urls = []
        for ln in lines:
            if re.match(r"^https?://\S+\.(png|jpg|jpeg|gif|webp)(\?.*)?$", ln, flags=re.IGNORECASE):
                image_urls.append(ln)
            else:
                text_lines.append(ln)
        return {"content": "\n".join(text_lines).strip(), "images": image_urls}

    async def _send_message(self, message, user_id: str, final_message: Dict[str, Any], user_message_lower: str):
        files = []
        for url in final_message.get("images", []):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            filename = url.split("/")[-1].split("?")[0] or "image.png"
                            files.append(discord.File(BytesIO(data), filename=filename))
            except Exception as e:
                logger.warning(f"Failed to fetch image {url}: {e}")

        content = final_message.get("content", "")
        if not content and not files:
            await message.channel.send(f"<@{user_id}> (No content)")
            return

        if content and len(content) <= 2000:
            await message.channel.send(content, files=files if files else None)
        elif content and len(content) <= 4096:
            embed = discord.Embed(description=content[:4096])
            await message.channel.send(embed=embed, files=files if files else None)
        else:
            if content:
                buffer = BytesIO(content.encode("utf-8"))
                text_file = discord.File(buffer, filename="response.txt")
                files = files + [text_file]
            await message.channel.send(f"<@{user_id}> Response too long, attached as file and images:", files=files)

        if content.strip():
            guild_id = str(message.guild.id) if message.guild else "DM"
            self.memory_manager.add_ai_message(str(message.channel.id), guild_id, user_id, content)
