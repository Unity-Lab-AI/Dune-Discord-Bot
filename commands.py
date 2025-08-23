import discord
from discord.ext import commands


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
            value="`!bothelp` - Show this help\n`!savememory <text>` - Save a memory\n`!wipe` - Clear chat history",
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
