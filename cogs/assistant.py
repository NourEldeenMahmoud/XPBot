import discord
from discord.ext import commands
import logging
from datetime import datetime
import os
import aiohttp

logger = logging.getLogger(__name__)

WAKE_TRIGGERS = ("رنا!", "rana!", "رنا", "rana")


class Assistant(commands.Cog):
	def __init__(self, bot, xp_manager, database, config):
		self.bot = bot
		self.xp_manager = xp_manager
		self.db = database
		self.config = config
		# OpenAI GPT-3.5 only
		self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
		self.model_name = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo").strip()


	def _is_author_allowed(self, member: discord.Member) -> bool:
		allowed = set(self.config.get_assistant_allowed_roles())
		if not allowed:
			return True  # لو مفيش رولز محددة، اسمح للجميع
		member_role_ids = {r.id for r in member.roles}
		return any(rid in member_role_ids for rid in allowed)

	def _extract_query(self, content: str):
		text = content.strip()
		lower = text.lower()
		for t in WAKE_TRIGGERS:
			if lower.startswith(t):
				return text[len(t):].strip(" ،,.-!ـ—_")
		return None

	@commands.Cog.listener()
	async def on_message(self, message: discord.Message):
		if message.author.bot or not message.guild:
			return
		if message.guild.id != self.config.get_guild_id():
			return
		# لا تتدخل في الأوامر
		content_stripped = (message.content or "").lstrip()
		if content_stripped.startswith("!"):
			return
		# لازم منشن للبوت عشان AI يرد
		if not self.bot.user or self.bot.user not in message.mentions:
			return 
		# تحقق من الرولز المسموح لها
		if not self._is_author_allowed(message.author):
			return
		# حضّر الاستعلام: شيل المنشنات وأي تريجر اختياري
		clean = message.content
		for m in message.mentions:
			try:
				clean = clean.replace(m.mention, "")
			except Exception:
				pass
		for t in WAKE_TRIGGERS:
			clean = clean.replace(t, "")
		query = clean.strip(" \t\n\r،,.-!ـ—_")
		try:
			reply = await self._handle_query(message, query)
			if reply:
				await message.channel.send(reply)
		except Exception as e:
			logger.error(f"Assistant error: {e}")
			await message.channel.send("حاضر يا فندم.. حصلت مشكلة بسيطة بس تمام هظبطها.")

	async def _handle_query(self, message: discord.Message, query: str) -> str:
		q = query.strip()
		if not q:
			return await self._ai_chat(message, "أيوه يا فندم؟ محتاجني في إيه؟")

		# Send everything to AI for natural responses
		text = await self._ai_chat(message, q)
		if text:
			return text
		return "أيوه يا فندم؟ محتاجني في إيه؟"





	async def _ai_chat(self, message: discord.Message, user_query: str) -> str:
		"""Call OpenAI Chat Completions to answer general queries in Egyptian Arabic."""
		try:
			if not self.api_key:
				return "أيوه يا فندم؟ 👩‍💼 أنا رنا، سكرتارية السيرفر! أقدر أساعدك في أي حاجة - أوامر البوت، معلومات السيرفر، أو أي استفسار تاني. تحب تعرف إيه؟"
			endpoint = "https://api.openai.com/v1/chat/completions"
			headers = {
				"Authorization": f"Bearer {self.api_key}",
				"Content-Type": "application/json",
			}
			context_snippets = []
			# Detailed secretary context
			context_snippets.append("**اسمك:** رنا (RANA)")
			context_snippets.append("**وظيفتك:** سكرتارية السيرفر المصرية المحترفة")
			context_snippets.append("**معلومات السيرفر:**")
			context_snippets.append("- أوامر البوت: !rank (الرتبة)، !leaderboard (الترتيب)، !weeklyleaderboard (الأسبوعي)")
			context_snippets.append("- أوامر المشرفين: !config (الإعدادات)، !delete/!clear (مسح رسائل)")
			context_snippets.append("- البوت بيتبع XP للناس وبيحسب المستويات")
			context_snippets.append("**تذكري:** انتي سكرتارية محترفة، مش بوت عادي!")
			# Guild hint
			try:
				gname = message.guild.name if message.guild else "this server"
				context_snippets.append(f"Server: {gname}")
			except Exception:
				pass
			system_prompt = (
				"انت رنا، سكرتارية السيرفر المصرية المحترفة! 👩‍💼\n\n"
				"**شخصيتك:**\n"
				"- بتتكلمي بالمصري العامي باحترام وخفة دم\n"
				"- سكرتارية محترفة ومهنية\n"
				"- بتساعدي الناس في أي حاجة\n"
				"- بتعرفي كل حاجة عن السيرفر والأوامر\n"
				"- ردودك ودودة ومفيدة\n\n"
				"**طريقة كلامك:**\n"
				"- استخدمي المصري العامي: 'أيوه'، 'تمام'، 'حاضر'، 'يا فندم'\n"
				"- كوني محترمة ومهنية\n"
				"- اضحكي وكوني ودودة\n"
				"- اشرحي ببساطة ووضوح\n"
				"- لو حد سأل عن أوامر البوت، اشرحيها له\n"
				"- لو حد سأل عن إحصائيات، قولي له يجرب !rank أو !leaderboard\n\n"
				"**تذكري:** انتي سكرتارية محترفة، مش بوت عادي. كوني ودودة ومفيدة!"
			)
			messages = [
				{"role": "system", "content": system_prompt},
				{"role": "system", "content": "\n".join(context_snippets)},
				{"role": "user", "content": user_query},
			]
			payload = {
				"model": self.model_name,
				"messages": messages,
				"temperature": 0.3,
				"max_tokens": 512,
			}
			async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
				async with session.post(endpoint, headers=headers, json=payload) as resp:
					if resp.status == 200:
						data = await resp.json()
						text = (
							data.get("choices", [{}])[0]
							.get("message", {})
							.get("content", "")
							.strip()
						)
						return text[:1800]
					else:
						err_text = await resp.text()
						logger.error(f"OpenAI API error: {resp.status} {err_text}")
						return ""
		except Exception as e:
			logger.error(f"AI chat error: {e}")
			return ""

	# ------- Admin commands to manage assistant access roles -------
	@commands.command(name="assistantroles")
	@commands.has_permissions(administrator=True)
	async def list_assistant_roles(self, ctx: commands.Context):
		roles = self.config.get_assistant_allowed_roles()
		if not roles:
			await ctx.send("أي حد يقدر يكلم رنا حالياً.")
			return
		mentions = [f"<@&{rid}>" for rid in roles]
		await ctx.send("الرولز المسموح لها: " + ", ".join(mentions))

	@commands.command(name="assistantrole")
	@commands.has_permissions(administrator=True)
	async def assistant_role_command(self, ctx: commands.Context, action: str, role: discord.Role):
		action = action.lower().strip()
		if action == "add":
			success = self.config.add_assistant_role(role.id)
			await ctx.send("تمام، ضفت " + role.mention) if success else await ctx.send("مقدرتش أضيف الرول.")
		elif action == "remove":
			success = self.config.remove_assistant_role(role.id)
			await ctx.send("تمام، شلت " + role.mention) if success else await ctx.send("مقدرتش أشيل الرول.")
		else:
			await ctx.send("استعمل: `!assistantrole add @role` أو `!assistantrole remove @role`")


async def setup(bot):
	await bot.add_cog(Assistant(bot, bot.xp_manager, bot.db, bot.config))


