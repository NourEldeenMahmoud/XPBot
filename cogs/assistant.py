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
		# AI Providers - Gemini only
		self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
		
		# Owner and special users
		self.owner_id = 677080266245668864  # البشمهندس نور - المدير
		self.advisor_role_id = self.config.get("assistant_advisor_role", 0)  # رول المستشار
		self.special_users = set(self.config.get("assistant_special_users", []))  # أشخاص محددين مسموح لهم

	def _is_author_allowed(self, member: discord.Member) -> bool:
		# المدير (البشمهندس نور) مسموح له دائماً
		if member.id == self.owner_id:
			return True
			
		# المستشار (رول معين) مسموح له
		if self.advisor_role_id and hasattr(member, 'roles'):
			member_role_ids = {r.id for r in member.roles}
			if self.advisor_role_id in member_role_ids:
				return True
		
		# الأشخاص المحددين مسموح لهم
		if member.id in self.special_users:
			return True
			
		# الرولز العامة
		allowed_roles = set(self.config.get_assistant_allowed_roles())
		if not allowed_roles:
			return True  # لو مفيش رولز محددة، اسمح للجميع
		
		if hasattr(member, 'roles'):
			member_role_ids = {r.id for r in member.roles}
			return any(rid in member_role_ids for rid in allowed_roles)
		
		return False

	def _get_user_title(self, member: discord.Member) -> str:
		"""Get appropriate title for user"""
		if member.id == self.owner_id:
			return "يا بشمهندس نور"  # المدير
		elif self.advisor_role_id and hasattr(member, 'roles') and any(r.id == self.advisor_role_id for r in member.roles):
			return "يا Consigliere "  # المستشار
		else:
			return "يا بشمهندس"  # باقي الناس

	def _save_special_users(self):
		"""Save special users to config"""
		self.config.set("assistant_special_users", list(self.special_users))

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
			await message.channel.send("حاضر يا بشمهندس.. حصلت مشكلة بسيطة بس تمام هظبطها.")
		
		# Process commands after assistant response
		await self.bot.process_commands(message)

	async def _handle_query(self, message: discord.Message, query: str) -> str:
		q = query.strip()
		if not q:
			return await self._ai_chat(message, "أيوه يا بشمهندس؟ محتاجني في إيه؟")

		# Send everything to AI for natural responses
		text = await self._ai_chat(message, q)
		if text:
			return text
		return "أيوه يا بشمهندس؟ محتاجني في إيه؟"





	async def _ai_chat(self, message: discord.Message, user_query: str) -> str:
		"""Call Gemini AI to answer queries in Egyptian Arabic."""
		try:
			# Try Gemini
			if self.gemini_key:
				response = await self._try_gemini(message, user_query)
				if response:
					return response
			
			# No AI available
			return "أيوه يا بشمهندس؟ 👩‍💼 أنا رنا، سكرتارية السيرفر! أقدر أساعدك في أي حاجة - أوامر البوت، معلومات السيرفر، أو أي استفسار تاني. تحب تعرف إيه؟"
		except Exception as e:
			logger.error(f"AI chat error: {e}")
			return ""



	async def _try_gemini(self, message: discord.Message, user_query: str) -> str:
		"""Try Gemini API."""
		try:
			endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
			headers = {
				"Content-Type": "application/json",
			}
			
			# Get appropriate title for user
			user_title = self._get_user_title(message.author)
			
			# Prepare context for Gemini
			context = (
				f"انت رنا، سكرتارية السيرفر المصرية المحترفة!‍\n\n"
				"**شخصيتك:**\n"
				"- بتتكلمي بالمصري العامي باحترام وخفة دم\n"
				"- سكرتارية محترفة ومهنية\n"
				"- بتساعدي الناس في أي حاجة\n"
				"- بتعرفي كل حاجة عن السيرفر والأوامر\n"
				"- ردودك ودودة ومفيدة\n\n"
				"**طريقة كلامك:**\n"
				f"- استخدمي المصري العامي: 'أيوه'، 'تمام'، 'حاضر'، '{user_title}'\n"
				"- متقوليش 'يا فندم' خالص، اللقب الرسمي 'يا بشمهندس'\n"
				"- كوني محترمة ومهنية\n"
				"- اضحكي وكوني ودودة\n"
				"- اشرحي ببساطة ووضوح\n"
				"- لو حد سأل عن أوامر البوت، اشرحيها له\n"
				"- لو حد سأل عن إحصائيات، قولي له يجرب !rank أو !leaderboard\n"
				"- ردودك تكون على قد السؤال، متقوليش كلام زيادة\n"
				"- لو حد منشن من غير ما يقول حاجة، عرفي نفسك باختصار\n"
				"- لو حد قال حاجة، رددي على السؤال بس\n\n"
				"**معلومات السيرفر:**\n"
				"- أوامر البوت: !rank (الرتبة)، !leaderboard (الترتيب)، !weeklyleaderboard (الأسبوعي)\n"
				"- أوامر المشرفين: !config (الإعدادات)، !delete/!clear (مسح رسائل)\n"
				"- البوت بيتبع XP للناس وبيحسب المستويات\n\n"
				"**تذكري:** انتي سكرتارية محترفة، مش بوت عادي. كوني ودودة ومفيدة!"
			)
			
			payload = {
				"contents": [
					{
						"parts": [
							{"text": context + "\n\n" + user_query}
						]
					}
				],
				"generationConfig": {
					"temperature": 0.3,
					"maxOutputTokens": 512,
				}
			}
			
			url = f"{endpoint}?key={self.gemini_key}"
			async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
				async with session.post(url, headers=headers, json=payload) as resp:
					if resp.status == 200:
						data = await resp.json()
						text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
						return text[:1800]
					else:
						err_text = await resp.text()
						logger.error(f"Gemini API error: {resp.status} {err_text}")
						return ""
		except Exception as e:
			logger.error(f"Gemini error: {e}")
			return ""

	# ------- Admin commands to manage assistant access -------
	@commands.command(name="assistantroles")
	@commands.has_permissions(administrator=True)
	async def list_assistant_roles(self, ctx: commands.Context):
		"""عرض كل الصلاحيات"""
		embed = discord.Embed(title="صلاحيات رنا", color=0x00ff00)
		
		# المدير
		owner = self.bot.get_user(self.owner_id)
		owner_name = owner.name if owner else "غير محدد"
		embed.add_field(name=" المدير", value=f"{owner_name} (ID: {self.owner_id})", inline=False)
		
		# المستشار
		if self.advisor_role_id:
			advisor_role = ctx.guild.get_role(self.advisor_role_id)
			advisor_name = advisor_role.name if advisor_role else "غير محدد"
			embed.add_field(name=" المستشار", value=f"@{advisor_name} (ID: {self.advisor_role_id})", inline=False)
		else:
			embed.add_field(name=" المستشار", value="غير محدد", inline=False)
		
		# الأشخاص المحددين
		if self.special_users:
			special_names = []
			for user_id in self.special_users:
				user = self.bot.get_user(user_id)
				name = user.name if user else f"User {user_id}"
				special_names.append(f"{name} (ID: {user_id})")
			embed.add_field(name="⭐ أشخاص محددين", value="\n".join(special_names), inline=False)
		else:
			embed.add_field(name="⭐ أشخاص محددين", value="لا يوجد", inline=False)
		
		# الرولز العامة
		roles = self.config.get_assistant_allowed_roles()
		if roles:
			mentions = [f"<@&{rid}>" for rid in roles]
			embed.add_field(name="🔧 رولز عامة", value=", ".join(mentions), inline=False)
		else:
			embed.add_field(name="🔧 رولز عامة", value="أي حد", inline=False)
		
		await ctx.send(embed=embed)

	@commands.command(name="assistantrole")
	@commands.has_permissions(administrator=True)
	async def assistant_role_command(self, ctx: commands.Context, action: str, role: discord.Role):
		"""إدارة الرولز العامة"""
		action = action.lower().strip()
		if action == "add":
			success = self.config.add_assistant_role(role.id)
			await ctx.send("تمام، ضفت " + role.mention) if success else await ctx.send("مقدرتش أضيف الرول.")
		elif action == "remove":
			success = self.config.remove_assistant_role(role.id)
			await ctx.send("تمام، شلت " + role.mention) if success else await ctx.send("مقدرتش أشيل الرول.")
		else:
			await ctx.send("استعمل: `!assistantrole add @role` أو `!assistantrole remove @role`")

	@commands.command(name="assistantuser")
	@commands.has_permissions(administrator=True)
	async def assistant_user_command(self, ctx: commands.Context, action: str, user: discord.Member):
		"""إدارة الأشخاص المحددين"""
		action = action.lower().strip()
		if action == "add":
			if user.id in self.special_users:
				await ctx.send(f"{user.mention} موجود بالفعل في القائمة.")
			else:
				self.special_users.add(user.id)
				self._save_special_users()
				await ctx.send(f"تمام، ضفت {user.mention} للقائمة.")
		elif action == "remove":
			if user.id in self.special_users:
				self.special_users.remove(user.id)
				self._save_special_users()
				await ctx.send(f"تمام، شلت {user.mention} من القائمة.")
			else:
				await ctx.send(f"{user.mention} مش موجود في القائمة.")
		else:
			await ctx.send("استعمل: `!assistantuser add @user` أو `!assistantuser remove @user`")

	@commands.command(name="setadvisor")
	@commands.has_permissions(administrator=True)
	async def set_advisor_role(self, ctx: commands.Context, role: discord.Role):
		"""تعيين رول المستشار"""
		self.advisor_role_id = role.id
		# Save to config
		self.config.set("assistant_advisor_role", role.id)
		await ctx.send(f"تمام، رول المستشار دلوقتي {role.mention}")

	@commands.command(name="setowner")
	@commands.has_permissions(administrator=True)
	async def set_owner(self, ctx: commands.Context, user: discord.Member):
		"""تعيين المدير"""
		self.owner_id = user.id
		# Save to config
		self.config.set("assistant_owner_id", user.id)
		await ctx.send(f"تمام، المدير دلوقتي {user.mention}")


async def setup(bot):
	await bot.add_cog(Assistant(bot, bot.xp_manager, bot.db, bot.config))


