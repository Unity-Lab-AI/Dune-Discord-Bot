import discord
from discord.ext import commands
import json
import logging
from io import BytesIO
import aiohttp
import re

from dune_logic import search as dune_search


logger = logging.getLogger(__name__)


def setup_commands(bot):
    @bot.command(name="bothelp")
    async def bothelp(ctx):
        embed = discord.Embed(
            title="Dune Bot Help",
            description="Available commands:",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`!bothelp` - Show this help\n"
                "`!savememory <text>` - Save a memory\n"
                "`!wipe` - Clear chat history\n"
                "`!search <query>` - Search Dune data\n"
                "`!item <name>` - Lookup item\n"
                "`!skill <name>` - Lookup skill\n"
                "`!contract <name>` - Lookup contract\n"
                "`!npc <name>` - Lookup NPC"
            ),
            inline=False
        )
        embed.add_field(
            name="Model",
            value=f"{bot.memory_manager.api_client.config.default_model} (default)",
            inline=False
        )
        embed.set_footer(text="Pollinations.ai")
        await ctx.send(embed=embed)

    @bot.command(name="savememory")
    async def savememory(ctx, *, memory_text):
        channel_id = str(ctx.channel.id)
        user_id = str(ctx.author.id)
        bot.memory_manager.add_memory(channel_id, memory_text)
        await bot.data_manager.save_data_async(bot.memory_manager)

        embed = discord.Embed(
            title="Memory Saved",
            description=f"Saved: {memory_text}",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        await ctx.send(f"<@{user_id}>", embed=embed)

    async def _send_response(ctx, final_message, user_id):
        files = []
        for url in final_message.get("images", []):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            filename = url.split("/")[-1].split("?")[0] or "image.png"
                            if not re.search(r"\.(png|jpg|jpeg|gif|webp)$", filename, re.IGNORECASE):
                                filename += ".png"
                            files.append(discord.File(BytesIO(data), filename=filename))
            except Exception as e:
                logger.warning(f"Failed to fetch image {url}: {e}")

        content = final_message.get("content", "")
        if not content and not files:
            await ctx.send(f"<@{user_id}> (No content)")
            return

        if content and len(content) <= 2000:
            await ctx.send(content, files=files if files else None)
        elif content and len(content) <= 4096:
            embed = discord.Embed(description=content[:4096])
            await ctx.send(embed=embed, files=files if files else None)
        else:
            if content:
                buffer = BytesIO(content.encode("utf-8"))
                text_file = discord.File(buffer, filename="response.txt")
                files = files + [text_file]
            await ctx.send(f"<@{user_id}> Response too long, attached as file and images:", files=files)

    async def _dune_query(ctx, query: str, data: dict):
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id) if ctx.guild else "DM"
        model = bot.memory_manager.get_user_model(guild_id, user_id)
        guardrails = (
            "Use ONLY the following GameData JSON for Dune Awakening specifics. "
            "If something is missing, say so briefly."
        )
        messages = [
            {"role": "system", "content": f"{bot.config.system_instructions}\n{guardrails}\nGameData:\n{json.dumps(data, ensure_ascii=False)}"},
            {"role": "user", "content": query},
        ]
        try:
            ai_response = await bot.api_client.send_message(messages, model)
        except Exception as e:
            await ctx.send(f"<@{user_id}> Error: Failed to fetch response - {e}")
            return
        ai_response_clean = bot.message_handler.clean_response(ai_response) or "Got it."
        final_message = bot.message_handler.build_message(ai_response_clean)
        await _send_response(ctx, final_message, user_id)

    @bot.command(name="search")
    async def search_cmd(ctx, *, query: str):
        locale = "en"
        results = await dune_search.search_autocomplete(locale, query, [])
        data = {"results": results[:5]}
        await _dune_query(ctx, query, data)

    async def _lookup_and_query(ctx, query: str, types: list):
        locale = "en"
        results = await dune_search.search_autocomplete(locale, query, types)
        if not results:
            await ctx.send(f'No results found for "{query}".')
            return
        path = results[0].get("path")
        try:
            _, card = await dune_search.route_path(locale, path)
        except Exception:
            await ctx.send(f'Could not retrieve data for "{query}".')
            return
        await _dune_query(ctx, query, card)

    @bot.command(name="item")
    async def item_cmd(ctx, *, query: str):
        await _lookup_and_query(ctx, query, ["items"])

    @bot.command(name="skill")
    async def skill_cmd(ctx, *, query: str):
        await _lookup_and_query(ctx, query, ["skills"])

    @bot.command(name="contract")
    async def contract_cmd(ctx, *, query: str):
        await _lookup_and_query(ctx, query, ["contracts"])

    @bot.command(name="npc")
    async def npc_cmd(ctx, *, query: str):
        await _lookup_and_query(ctx, query, ["npcs"])
