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
		self.api_key = os.getenv("GROQ_API_KEY", "").strip()
		self.model_name = os.getenv("GROQ_MODEL", "llama3-8b-8192").strip()

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
			return "أيوه يا فندم؟ محتاجني في إيه؟"

		lq = q.lower()

		# 1) Commands/help
		if any(k in lq for k in ["اوامر", "commands", "ممكن تعملي ايه", "بتعملي ايه", "help", "هيلب"]):
			return self._commands_summary()

		# 2) Bot self info
		if any(k in lq for k in ["انت مين", "عن نفسك", "اسمك", "بتعملي ايه", "who are you"]):
			return "أنا رنا، سكرتارية السيرفر 👩‍💼. أقدر أساعدك في الأسئلة اليومية، أوامر البوت، وإحصائيات السيرفر والـ XP."

		# 3) Overall stats (DB)
		if any(k in lq for k in ["احصائ", "إحصائ", "stats", "stat", "الإحصائيات", "عدد"]):
			return self._server_stats(message.guild.id)

		# 4) User rank (author or mentioned)
		if any(k in lq for k in ["رانك", "رتبتي", "rank", "مستواي", "ليفلي", "مستوى"]):
			target = message.mentions[0] if message.mentions else message.author
			return self._user_rank(message.guild.id, target)

		# 5) Leaderboard (short text)
		if any(k in lq for k in ["ليدربورد", "leaderboard", "الترتيب", "الاوائل", "top"]):
			return self._short_leaderboard(message.guild)

		# Fallback: AI chat if configured, otherwise small talk
		if self.api_key:
			text = await self._ai_chat(message, q)
			if text:
				return text
		return "تمام يا فندم، حاضر. تحب أجيبلك أوامر البوت ولا تشوف ترتيبك؟"

	def _commands_summary(self) -> str:
		return (
			"تمام، دي أهم الأوامر:\n"
			"- !rank: يطلعلك الرانك والـ XP والمستوى بتوعك\n"
			"- !leaderboard: أفضل الناس بالـ XP الكلي\n"
			"- !weeklyleaderboard: ترتيب النشاط الأسبوعي\n"
			"- !config: تلخيص الإعدادات (للمشرفين)\n"
			"- !delete/!clear: مسح رسائل (صلاحيات مطلوبة)\n"
			"- وكمان تقدر تسألني بـ 'رنا!' عن: إحصائيات السيرفر، ترتيبك، أو أوامري."
		)

	def _server_stats(self, guild_id: int) -> str:
		import sqlite3
		try:
			with sqlite3.connect(self.db.db_path) as conn:
				cur = conn.cursor()
				cur.execute("SELECT COUNT(*) FROM users WHERE guild_id = ?", (guild_id,))
				total_users = cur.fetchone()[0] or 0
				cur.execute("SELECT SUM(permanent_xp) FROM users WHERE guild_id = ?", (guild_id,))
				total_xp = cur.fetchone()[0] or 0
				cur.execute("SELECT SUM(weekly_xp) FROM users WHERE guild_id = ?", (guild_id,))
				weekly_xp = cur.fetchone()[0] or 0
			return (
				f"إحصائيات السيرفر:\n"
				f"- المستخدمين المتتبعين: {total_users}\n"
				f"- إجمالي XP: {total_xp}\n"
				f"- إجمالي Weekly XP: {weekly_xp}"
			)
		except Exception:
			return "حاولت أجيب الإحصائيات بس حصلت مشكلة بسيطة. جرب تاني بعد شوية."

	def _user_rank(self, guild_id: int, member: discord.Member) -> str:
		stats = self.xp_manager.get_user_stats(guild_id, member.id)
		if not stats:
			return f"{member.mention} لسه مفيش بيانات XP عنده."
		return (
			f"بيانات {member.mention}:\n"
			f"- المستوى: {stats['level']}\n"
			f"- XP الكلي: {stats['total_xp']}\n"
			f"- XP الأسبوعي: {stats['weekly_xp']}\n"
			f"- الترتيب الكلي: #{stats['permanent_rank'] or 'N/A'} • الأسبوعي: #{stats['weekly_rank'] or 'N/A'}\n"
			f"- التقدم للمستوى الجاي: {stats['xp_progress']}/{stats['xp_needed']} ({stats['progress_percentage']:.1f}%)"
		)

	def _short_leaderboard(self, guild: discord.Guild, limit: int = 5) -> str:
		top = self.db.get_leaderboard(guild.id, limit)
		if not top:
			return "مفيش بيانات في اللّيدربورد دلوقتي."
		lines = ["أفضل " + str(len(top)) + ":"]
		for entry in top:
			member = guild.get_member(entry['user_id'])
			name = member.mention if member else f"User {entry['user_id']}"
			lines.append(f"#{entry['rank']} - {name}: {entry['permanent_xp']} XP (Lv {entry['level']})")
		return "\n".join(lines)

	async def _ai_chat(self, message: discord.Message, user_query: str) -> str:
		"""Call Groq Chat Completions to answer general queries in Egyptian Arabic."""
		try:
			if not self.api_key:
				return ""
			endpoint = "https://api.groq.com/openai/v1/chat/completions"
			headers = {
				"Authorization": f"Bearer {self.api_key}",
				"Content-Type": "application/json",
			}
			context_snippets = []
			# Basic self/commands context
			context_snippets.append("Bot name: RANA (رنا). Role: server secretary in Egyptian Arabic.")
			context_snippets.append("Key commands: !rank, !leaderboard, !weeklyleaderboard, !config, !delete/!clear.")
			context_snippets.append("You can summarize server stats on request and guide users to commands.")
			# Guild hint
			try:
				gname = message.guild.name if message.guild else "this server"
				context_snippets.append(f"Server: {gname}")
			except Exception:
				pass
			system_prompt = (
				"انت سكرتارية اسمك رنا بتتكلمي بالمصري العامي باحترام وخفة دم. "
				"ردودك قصيرة ومباشرة ومفيدة، ولو السؤال عن البوت/الأوامر/الإحصائيات "
				"اشرحي ببساطة ووجهي للأمر المناسب. لو طلبك يخص الداتا عندنا، "
				"لو مش معايا المعلومة جاهزة قولي هنستخدم الأوامر المناسبة."
			)
			messages = [
				{"role": "system", "content": system_prompt},
				{"role": "system", "content": "\n".join(context_snippets)},
				{"role": "user", "content": user_query},
			]
			model_to_use = self.model_name or "mixtral-8x7b-32768"
			payload = {
				"model": model_to_use,
				"messages": messages,
				"temperature": 0.3,
				"max_tokens": 512,
			}
			async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
				async with session.post(endpoint, headers=headers, json=payload) as resp:
					if resp.status != 200:
						err_text = await resp.text()
						logger.error(f"Groq API error: {resp.status} {err_text}")
						# Fallback تلقائي للموديل الافتراضي المدعوم
						if ("model_not_found" in err_text) or ("does not exist" in err_text):
							payload["model"] = "mixtral-8x7b-32768"
							async with session.post(endpoint, headers=headers, json=payload) as resp2:
								if resp2.status != 200:
									logger.error(f"Groq API fallback error: {resp2.status} {await resp2.text()}")
									return ""
								data2 = await resp2.json()
								text2 = (
									data2.get("choices", [{}])[0]
									.get("message", {})
									.get("content", "")
									.strip()
								)
								return text2[:1800]
						return ""
					data = await resp.json()
					text = (
						data.get("choices", [{}])[0]
						.get("message", {})
						.get("content", "")
						.strip()
					)
					return text[:1800]
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


