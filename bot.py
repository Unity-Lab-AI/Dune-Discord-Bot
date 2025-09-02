import discord
from discord.ext import commands
import asyncio
import os
import logging
import aiofiles
from config import Config
from api_client import APIClient
from message_handler import MessageHandler
from memory_manager import MemoryManager
from commands import setup_commands
from data_manager import DataManager
from message_queue import MessageQueue

if not os.path.exists("logs"):
    os.makedirs("logs")
logging.basicConfig(filename="logs/application.log", level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logging.getLogger("").addHandler(console)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

config = Config()
api_client = APIClient(config)
memory_manager = MemoryManager()
data_manager = DataManager("logs/chat_data.json")
bot.data_manager = data_manager
message_handler = MessageHandler(api_client, memory_manager, config, data_manager, bot)
memory_manager.api_client = api_client
bot.memory_manager = memory_manager
bot.api_client = api_client
bot.config = config
bot.message_handler = message_handler
message_queue = MessageQueue(bot, message_handler, memory_manager, data_manager, config)
bot.message_queue = message_queue

async def setup_bot():
    await bot.wait_until_ready()
    # Fetch available models from the Pollinations API
    models = await api_client.fetch_models()
    memory_manager.set_models(models)
    # Keep the configured default model (gpt-5-nano) when available
    if models and not any(m["name"].lower() == config.default_model.lower() for m in models):
        config.default_model = models[0]["name"]
    data_manager.load_data(memory_manager)
    setup_commands(bot)
    print(f"Loaded {config.default_model} model")
    bot.message_queue.start()

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    logging.info("Bot is ready and connected.")
    await setup_bot()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.guild and config.allowed_channels and str(message.channel.id) not in config.allowed_channels:
        return

    channel_id = str(message.channel.id)
    guild_id = str(message.guild.id) if message.guild else "DM"
    user_id = str(message.author.id)
    logging.info(
        f"Queued message from {user_id} in channel {channel_id} (guild: {guild_id}): {message.content}"
    )

    await bot.message_queue.enqueue(message)

@bot.command(name="wipe")
async def wipe(ctx):
    try:
        channel_id = str(ctx.channel.id)
        guild_id = str(ctx.guild.id) if ctx.guild else "DM"
        user_id = str(ctx.author.id)
        logging.info(f"Wipe command initiated by {user_id} in channel {channel_id}")

        bot.memory_manager.channel_histories[channel_id] = []
        if guild_id in bot.memory_manager.user_histories:
            if user_id in bot.memory_manager.user_histories[guild_id]:
                bot.memory_manager.user_histories[guild_id][user_id] = []
        if guild_id in bot.memory_manager.user_model_histories:
            if user_id in bot.memory_manager.user_model_histories[guild_id]:
                for model in bot.memory_manager.user_model_histories[guild_id][user_id]:
                    bot.memory_manager.user_model_histories[guild_id][user_id][model] = []

        await bot.data_manager.save_data_async(bot.memory_manager)
        await ctx.send(f"<@{user_id}> Chat history wiped for this server.")
        logging.info(f"Chat history wiped for user {user_id} in channel {channel_id}")
    except Exception as e:
        logging.error(f"Error in wipe command for user {user_id}: {e}")
        await ctx.send(f"<@{user_id}> Error wiping chat history: {str(e)}")

async def wipe_logs_periodically():
    while True:
        try:
            await asyncio.sleep(3600)
            async with aiofiles.open("logs/application.log", "w") as f:
                await f.write("")
            logging.info("Logs wiped successfully.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Error wiping logs: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        available = " ".join(f"!{cmd.name}" for cmd in bot.commands)
        await ctx.send(f"The command {ctx.message.content.split()[0]} does not exist. Available commands: {available}")
    else:
        raise error

@bot.event
async def on_connect():
    await api_client.initialize()
    print("Bot connected to Discord")

@bot.event
async def on_disconnect():
    await api_client.close()
    print("Bot disconnected from Discord")

async def main():
    try:
        await bot.start(config.discord_token)
    except discord.errors.LoginFailure as e:
        logging.error(f"Failed to login: {e}")
        print("Login failed. Please check your Discord token in the .env file (key: DISCORD_TOKEN). Ensure it's valid and not revoked. Visit https://discord.com/developers/applications to reset it.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print(f"Unexpected error: {e}")
    finally:
        await api_client.close()
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
