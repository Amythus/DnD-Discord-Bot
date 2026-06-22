import discord
from discord.ext import commands
import uuid
from core.pipeline import PipelineOrchestrator, ActionIntent
from services.gemini_client import gemini_service

class ChatParserCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Instantiate the orchestration pipeline layer
        self.pipeline = PipelineOrchestrator()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Listens to all inbound server text channels to intercept player intents.
        """
        # Rule 1: Always ignore actions performed by the bot itself
        if message.author == self.bot.user:
            return

        # Rule 2: Filter out generic system commands (prefixed by !) or non-mentions
        if message.content.startswith("!"):
            return

        # Rule 3: Only parse if the bot is explicitly mentioned or it's an active play channel
        if not self.bot.user.mentioned_in(message):
            # If you track active play channels dynamically via DB config, check that here:
            # is_play_channel = await ChannelConfig.is_active(message.channel.id)
            # if not is_play_channel: return
            return

        # Clean the input text (strip out the actual @bot mention tag)
        clean_text = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
        if not clean_text:
            return

        # Inform the channel that processing has initialized
        async with message.channel.typing():
            try:
                # 1. Fetch or resolve the active session ID for this specific channel/guild
                # (You will replace this placeholder logic with your actual DB session locator)
                session_id = await self._resolve_active_session_id(message.channel.id)
                if not session_id:
                    await message.reply("❌ No active D&D session was found running in this channel. Start one with `/start_session`.")
                    return

                # 2. Package into your core contract DTO
                intent = ActionIntent(
                    session_id=session_id,
                    channel_id=message.channel.id,
                    user_id=message.author.id,
                    raw_text=clean_text
                )

                # 3. Fire-and-forget directly into the mutation orchestration pipeline
                response_narration = await self.pipeline.process_intent(intent)

                # 4. Deliver the resulting creative DM response block back to the chat
                await message.reply(response_narration)

            except Exception as e:
                print(f"❌ Error during chat parsing pipeline: {e}")
                await message.reply("⚠️ An unstable disturbance in the weave prevented processing your action.")

    async def _resolve_active_session_id(self, channel_id: int) -> uuid.UUID:
        """
        Helper to look up the active session mapping bound to the executing channel.
        """
        # Placeholder integration hook linking with SessionDelta tracking
        # session = await SessionDelta.find_one({"channel_id": channel_id, "active": True})
        # return session.session_id if session else None
        return uuid.uuid4() # Temporary mockup token string

async def setup(bot: commands.Bot):
    await bot.add_cog(ChatParserCog(bot))