import asyncio
import time
import logging
from collections import deque


class MessageQueue:
    def __init__(self, bot, handler, memory_manager, data_manager, config):
        self.bot = bot
        self.handler = handler
        self.memory_manager = memory_manager
        self.data_manager = data_manager
        self.config = config
        self.user_queue = deque()
        self.bot_queue = deque()
        self.last_sent_time = 0.0
        self.last_bot_response_time = 0.0
        self._task = None

    async def enqueue(self, message):
        entry = {
            "message": message,
            "user_id": str(message.author.id),
            "timestamp": time.time(),
        }
        if message.author.bot:
            self.bot_queue.append(entry)
        else:
            self.user_queue.append(entry)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self.process_queues())

    async def process_queues(self):
        while True:
            now = time.time()
            processed = False

            if self.user_queue:
                entry = self.user_queue[0]
                if now - entry["timestamp"] >= 5 and now - self.last_sent_time >= 5:
                    self.user_queue.popleft()
                    await self._handle(entry["message"], entry["user_id"])
                    self.last_sent_time = time.time()
                    processed = True

            if not processed and self.bot_queue:
                entry = self.bot_queue[0]
                if (
                    now - entry["timestamp"] >= 300
                    and now - self.last_sent_time >= 5
                    and now - self.last_bot_response_time >= 300
                ):
                    self.bot_queue.popleft()
                    await self._handle(entry["message"], entry["user_id"])
                    current = time.time()
                    self.last_sent_time = current
                    self.last_bot_response_time = current
                    processed = True

            if not processed:
                await asyncio.sleep(1)

    async def _handle(self, message, user_id):
        channel_id = str(message.channel.id)
        guild_id = str(message.guild.id) if message.guild else "DM"
        logging.info(
            f"Handling queued message from {user_id} in channel {channel_id} (guild: {guild_id})"
        )
        try:
            self.memory_manager.initialize_channel(channel_id)
            user_model = self.memory_manager.get_user_model(guild_id, user_id)
            logging.info(
                f"User {user_id} using model: {user_model} in guild {guild_id}"
            )
            async with message.channel.typing():
                await self.bot.process_commands(message)
                await self.handler.handle_message(message)
                await self.data_manager.save_data_async(self.memory_manager)
            history = self.memory_manager.channel_histories.get(channel_id, [])
            if len(history) > self.config.max_history:
                self.memory_manager.channel_histories[channel_id] = history[-self.config.max_history :]
        except Exception as e:
            logging.error(f"Error handling message for user {user_id}: {e}")
            try:
                await message.channel.send(
                    f"<@{user_id}> Something went wrong - please try again."
                )
            except Exception as send_error:
                logging.error(
                    f"Failed to send error message to user {user_id}: {send_error}"
                )
