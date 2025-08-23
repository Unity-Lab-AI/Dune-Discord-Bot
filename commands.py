import discord
from discord.ext import commands


def setup_commands(bot):
    @bot.command(name="unityhelp")
    async def unityhelp(ctx):
        embed = discord.Embed(
            title="Unity Bot Help",
            description="Available commands:",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="Commands",
            value="`!unityhelp` - Show this help\n`!savememory <text>` - Save a memory\n`!wipe` - Clear chat history",
            inline=False
        )
        embed.add_field(
            name="Model",
            value="Unity (default)",
            inline=False
        )
        embed.set_footer(text="Unity | Pollinations.ai")
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
