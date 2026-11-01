"""Aethon additive setup. Never edits/deletes pre-existing channels or roles.

Python 3.11+. Token is read from DISCORD_BOT_TOKEN or a hidden console prompt.
Keep state.json: it records the resources this bot is allowed to manage.
"""
import argparse
import asyncio
import getpass
import json
import logging
import random
import os
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord.http import Route

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
GUILD_ID = int(CONFIG["guild_id"])
STATE_FILE = ROOT / "state.json"
ROLE_NAMES = {
    "mmorpg": "Aethon • MMORPG",
    "smp": "Aethon • Volcanism SMP",
    "soon": "Aethon • Coming Soon",
    "mods": "Aethon • Mod Updates",
    "packs": "Aethon • Modpack Updates",
    "events": "Aethon • Events",
}
# key, name, category key, access mode, kind
CHANNELS = [
    ("welcome", "👋・welcome", "info", "read", "text"),
    ("rules", "📜・rules-and-info", "info", "read", "text"),
    ("socials", "💻・socials", "info", "read", "text"),
    ("announcements", "📢・announcements", "info", "read", "text"),
    ("roles", "🎭・get-roles", "info", "read", "text"),
    ("guide", "🌐・server-guide", "info", "read", "text"),
    ("general", "💬・general", "community", "public", "text"),
    ("media", "📸・media-and-memes", "community", "public", "text"),
    ("suggestions", "💡・suggestions", "community", "public", "text"),
    ("commands", "🤖・bot-commands", "community", "public", "text"),
    ("voice", "🔊 General", "community", "public", "voice"),
    ("releases", "📦・releases", "mods", "read", "text"),
    ("modchat", "💬・modpack-chat", "mods", "public", "text"),
    ("bugs", "🛠・help-and-bugs", "mods", "public", "forum"),
    ("mmorpg", "✨・astreon-mmorpg", "servers", "mmorpg", "text"),
    ("smp", "🌋・volcanism-smp", "servers", "smp", "text"),
    ("soon", "🚧・coming-soon", "servers", "soon", "text"),
    ("mcvoice", "🔊 Minecraft", "servers", "public", "voice"),
    ("events", "🎉・events-and-giveaways", "events", "read", "text"),
    ("staff", "💬・staff-chat", "staff", "staff", "text"),
    ("modlogs", "🛡・mod-logs", "staff", "staff", "text"),
    ("joins", "🚪・join-leave-logs", "staff", "staff", "text"),
    ("botlogs", "🤖・bot-logs", "staff", "staff", "text"),
]
CATEGORIES = {
    "info": "📌 AETHON INFORMATION", "community": "💬 AETHON COMMUNITY",
    "mods": "🧩 MODS & MODPACKS", "servers": "🎮 MINECRAFT SERVERS",
    "events": "🎉 AETHON EVENTS", "staff": "🔒 AETHON STAFF",
}


def save_state(state):
    temp = STATE_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp.replace(STATE_FILE)


def read_state():
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {
        "guild_id": GUILD_ID, "roles": {}, "categories": {}, "channels": {},
        "messages": {}, "invites": {},
    }
    if state["guild_id"] != GUILD_ID:
        raise RuntimeError("State belongs to another server. Stop and check config.json.")
    return state


def safe_role(role, me):
    # Never self-assign a role that was subsequently promoted to a privileged role.
    return role is not None and not role.managed and role.permissions.value == 0 and role < me.top_role


class RoleButton(discord.ui.Button):
    def __init__(self, key):
        super().__init__(label=ROLE_NAMES[key], custom_id="astreon:add:" + key,
                         style=discord.ButtonStyle.secondary)
        self.key = key

    async def callback(self, interaction):
        bot = interaction.client
        if interaction.guild_id != GUILD_ID or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Use this inside Aethon.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        if interaction.user.pending:
            return await interaction.followup.send("Please finish the server's rules screening first.", ephemeral=True)
        # Fetch current permissions and membership rather than relying on a stale cache.
        roles = {r.id: r for r in await interaction.guild.fetch_roles()}
        role = roles.get(bot.state["roles"].get(self.key))
        if not safe_role(role, interaction.guild.me):
            return await interaction.followup.send("This role needs a staff check before it can be assigned.", ephemeral=True)
        try:
            member = await interaction.guild.fetch_member(interaction.user.id)
            if role in member.roles:
                message = "You already have this role. Your other roles are unchanged."
            else:
                await member.add_roles(role, reason="Member opted in via Aethon role panel", atomic=True)
                message = f"Added **{role.name}**. Your other roles are unchanged."
            await interaction.followup.send(message, ephemeral=True)
        except discord.HTTPException:
            logging.exception("Role assignment failed")
            await interaction.followup.send("Could not assign the role. Ask staff to check the bot's role position.", ephemeral=True)


class RolePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for key in ROLE_NAMES:
            self.add_item(RoleButton(key))

    async def on_error(self, interaction, error, item):
        logging.error("Role panel error: %s", type(error).__name__)
        if interaction.response.is_done():
            await interaction.followup.send("The role panel encountered an error. Please contact staff.", ephemeral=True)
        else:
            await interaction.response.send_message("Please contact staff; the role panel encountered an error.", ephemeral=True)


class Astreon(discord.Client):
    def __init__(self, mode):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = mode == "run"
        intents.moderation = mode == "run"
        intents.voice_states = mode == "run"
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.mode, self.state = mode, read_state()
        self.started = False
        self.created_roles = {}

    async def setup_hook(self):
        if self.mode == "run":
            self.add_view(RolePanel())

    def channel(self, key):
        cid = CONFIG["reuse_channels"].get(key) or self.state["channels"].get(key)
        return self.get_guild(GUILD_ID).get_channel(int(cid)) if cid else None

    async def on_ready(self):
        if self.started:
            return
        self.started = True
        try:
            guild = self.get_guild(GUILD_ID)
            if guild is None:
                raise RuntimeError("Bot is not a member of the configured server.")
            print(f"Connected to {guild.name} ({guild.id})")
            self.preflight(guild)
            if self.mode == "run":
                if any(k not in self.state["channels"] for k in ("roles", "welcome", "joins", "modlogs", "botlogs")):
                    raise RuntimeError("Run --apply successfully before --run.")
                print("Bot running. Keep this window open. Ctrl+C stops it.")
                await self.log_to("botlogs", "Aethon bot started. Role buttons, welcome messages and live audit logging are active.")
                return
            if self.mode in ("preview", "apply"):
                plan = self.plan(guild)
                print(plan)
                (ROOT / "plan.txt").write_text(plan, encoding="utf-8")
                if self.mode == "apply":
                    confirmation = await asyncio.to_thread(input, "Type the server ID to apply these additions: ")
                    if confirmation.strip() != str(GUILD_ID):
                        raise RuntimeError("Confirmation did not match; no changes made.")
                    self.snapshot(guild)
                    await self.apply(guild)
                    print("Setup finished. Start --run to activate the bot. Existing resources were not edited.")
            elif self.mode == "invites":
                await self.invites(guild)
        except Exception as exc:
            logging.exception("Operation failed")
            print(f"STOPPED: {exc}\nAny completed additions remain. Keep state.json and rerun after fixing the cause.")
            self.failed = True
        await self.close()

    def preflight(self, guild):
        if guild.name != CONFIG["expected_guild_name"]:
            raise RuntimeError("Server name differs from config.json. Verify both name and ID before updating config.")
        for rid in CONFIG["staff_role_ids"]:
            role = guild.get_role(int(rid))
            if not role or role.is_default() or role.managed:
                raise RuntimeError(f"Invalid staff role ID: {rid}")
        for key, cid in CONFIG["reuse_channels"].items():
            channel = guild.get_channel(int(cid))
            if not isinstance(channel, discord.TextChannel):
                raise RuntimeError(f"Existing channel {key} ({cid}) is missing or not text. Correct config; nothing will be replaced.")
        for group, getter in (("roles", guild.get_role), ("categories", guild.get_channel), ("channels", guild.get_channel)):
            for key, value in self.state[group].items():
                if getter(value) is None:
                    raise RuntimeError(f"Recorded {group}/{key} was deleted. Stop and review state.json; no automatic replacement.")
        needed = ["view_channel", "send_messages", "read_message_history"]
        if self.mode in ("apply", "preview"):
            needed += ["manage_channels", "manage_roles"]
        if self.mode == "run":
            needed += ["manage_roles", "view_audit_log"]
        if self.mode == "invites":
            needed += ["manage_roles", "create_instant_invite"]
        missing = [p for p in needed if not getattr(guild.me.guild_permissions, p)]
        if missing:
            raise RuntimeError("Bot needs permissions: " + ", ".join(missing))

    def plan(self, guild):
        lines = ["ADDITIVE AETHON PLAN", f"Server: {guild.name} ({guild.id})",
                 "No deletion, rename, move, existing permission edits, or member role replacement.",
                 "Staff access: owner/admins and explicit staff_role_ids only."]
        for key, name in ROLE_NAMES.items():
            if key not in self.state["roles"]:
                if any(r.name == name for r in guild.roles):
                    raise RuntimeError(f"Untracked role collision: {name}. Will not adopt a potentially privileged role.")
                lines.append("CREATE zero-permission opt-in role: " + name)
        for key, name in CATEGORIES.items():
            if key not in self.state["categories"]:
                if any(c.name == name for c in guild.categories):
                    raise RuntimeError(f"Untracked category collision: {name}. Review before proceeding.")
                lines.append("CREATE category: " + name)
        for key, name, category, access, kind in CHANNELS:
            if key in CONFIG["reuse_channels"]:
                lines.append(f"KEEP existing {key}: {self.channel(key).name} (no edits or posts)")
            elif key not in self.state["channels"]:
                if any(c.name == name for c in guild.channels):
                    raise RuntimeError(f"Untracked channel collision: {name}. Review before proceeding.")
                actual = "text (forum fallback)" if kind == "forum" and "COMMUNITY" not in guild.features else kind
                lines.append(f"CREATE {actual}: {name} / {CATEGORIES[category]} / access={access}")
        lines.append("POST starter messages only to new bot-created channels; existing messages remain untouched.")
        return "\n".join(lines)

    def snapshot(self, guild):
        folder = ROOT / "snapshots"
        folder.mkdir(exist_ok=True)
        data = {"guild_id": guild.id, "roles": [{"id": r.id, "name": r.name,
            "permissions": r.permissions.value, "position": r.position} for r in guild.roles],
            "channels": [{"id": c.id, "name": c.name, "type": str(c.type),
                "category_id": c.category_id, "overwrites": [{"id": target.id,
                    "allow": ow.pair()[0].value, "deny": ow.pair()[1].value}
                    for target, ow in c.overwrites.items()]} for c in guild.channels]}
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ.json")
        (folder / name).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def overwrites(self, guild, access):
        public = access in ("public", "read")
        everyone = discord.PermissionOverwrite(view_channel=public)
        if access == "read":
            everyone.send_messages = False
            everyone.create_public_threads = False
            everyone.create_private_threads = False
            everyone.send_messages_in_threads = False
        result = {guild.default_role: everyone, guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            embed_links=True, attach_files=True, connect=True, speak=True)}
        for rid in CONFIG["staff_role_ids"]:
            result[guild.get_role(int(rid))] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True)
        if access in ROLE_NAMES:
            result[self.created_roles.get(access) or guild.get_role(self.state["roles"][access])] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True)
        return result

    async def apply(self, guild):
        for key, name in ROLE_NAMES.items():
            if key not in self.state["roles"]:
                role = await guild.create_role(name=name, permissions=discord.Permissions.none(),
                    mentionable=False, reason="Aethon additive setup")
                self.state["roles"][key] = role.id
                self.created_roles[key] = role
                save_state(self.state)
        for key, name in CATEGORIES.items():
            if key not in self.state["categories"]:
                category = await guild.create_category(name, overwrites=self.overwrites(guild, "staff" if key == "staff" else "public"),
                    reason="Aethon additive setup")
                self.state["categories"][key] = category.id
                save_state(self.state)
        for key, name, cat, access, kind in CHANNELS:
            if key in CONFIG["reuse_channels"] or key in self.state["channels"]:
                continue
            kwargs = dict(category=guild.get_channel(self.state["categories"][cat]),
                          overwrites=self.overwrites(guild, access), reason="Aethon additive setup")
            if kind == "voice":
                channel = await guild.create_voice_channel(name, **kwargs)
            elif kind == "forum" and "COMMUNITY" in guild.features:
                channel = await guild.create_forum(name, topic="One issue per post: pack/mod, version, reproduction steps and a redacted crash report. Never post passwords or tokens.", **kwargs)
            else:
                channel = await guild.create_text_channel(name, **kwargs)
            self.state["channels"][key] = channel.id
            save_state(self.state)
        await self.post_once("roles", "Pick your interests below. You can select several. These buttons only ADD roles; they never remove your existing roles. For removal, contact staff.", RolePanel())
        await self.post_once("guide", f"**Aethon — Minecraft Community**\nMinecraft address supplied by staff: `{CONFIG['minecraft_address']}`\nSupported versions supplied by staff: {CONFIG['minecraft_versions']}\nGeneral invite: {CONFIG['general_invite']}\nChoose interests in {self.channel('roles').mention} to reveal **Aethon MMORPG**, **Volcanism SMP**, or **Coming Soon**.\nFind releases in {self.channel('releases').mention} and discuss mods and modpacks in {self.channel('modchat').mention}.\nThe third server is not named or launched yet. Server addresses and release dates must be confirmed by staff.")
        await self.post_once("mmorpg", "**Aethon MMORPG**\nDiscuss quests, progression, classes, builds, and groups here. Staff will confirm connection details and availability.")
        await self.post_once("smp", "**Volcanism SMP**\nFind teammates, share builds, and discuss the SMP. Staff will post the correct address, modpack version, and server rules.")
        await self.post_once("soon", "**Coming Soon**\nOur third Minecraft server is still unnamed. Choose this interest to follow future announcements. No launch date has been announced.")
        await self.post_once("events", "**Events & Giveaways**\nCommunity events and giveaway announcements will appear here. Select the Events role for optional pings. This bot does not draw giveaway winners; staff can use the existing GiveawayBot.")
        await self.post_once("staff", "**Staff workspace**\nOnly the owner, administrators, explicitly configured staff roles and this bot receive access from this setup. Keep member reports private. Review log access before use.")

    async def post_once(self, key, content, view=None):
        if key not in self.state["channels"] or key in self.state["messages"]:
            return
        channel = self.channel(key)
        # Recover a successful post if the process stopped before saving its ID.
        async for message in channel.history(limit=50):
            if message.author.id == self.user.id and message.content == content:
                self.state["messages"][key] = message.id
                save_state(self.state)
                return
        message = await channel.send(content, view=view)
        self.state["messages"][key] = message.id
        save_state(self.state)

    async def invites(self, guild):
        if not self.channel("roles"):
            raise RuntimeError("Run --apply first.")
        roles = {r.id: r for r in await guild.fetch_roles()}
        for key in ("mmorpg", "smp", "soon"):
            role = roles.get(self.state["roles"].get(key))
            if not safe_role(role, guild.me):
                raise RuntimeError("Unsafe or unassignable role: " + key)
            if key in self.state["invites"]:
                print(f"KEEP recorded invite for {key}; validity is not rechecked.")
                continue
            data = await self.http.request(Route("POST", "/channels/{channel_id}/invites",
                channel_id=self.channel("roles").id), json={"max_age": 0, "max_uses": 0,
                "temporary": False, "unique": True, "role_ids": [str(role.id)]},
                reason="Aethon permanent opt-in role invite")
            # Fail visibly if the API does not confirm the role binding. Never claim a plain invite grants roles.
            confirmed = {str(r["id"]) for r in data.get("roles", [])}
            confirmed.update(str(r) for r in data.get("role_ids", []))
            record = {"url": "https://discord.gg/" + data["code"],
                      "role_id": role.id, "role_binding_confirmed": str(role.id) in confirmed}
            self.state["invites"][key] = record
            save_state(self.state)
            if not record["role_binding_confirmed"]:
                print(f"WARNING: {key} invite created but role binding unconfirmed. Use the role panel until tested.")
        (ROOT / "invite-links.json").write_text(json.dumps(self.state["invites"], indent=2), encoding="utf-8")
        print("Saved invite-links.json. Test each with a non-admin account before sharing.")

    async def log_to(self, key, content):
        channel = self.channel(key)
        if channel:
            try:
                await channel.send(content[:1900])
            except discord.HTTPException:
                logging.exception("Could not send %s log", key)

    async def on_member_join(self, member):
        if member.guild.id != GUILD_ID:
            return
        await self.log_to("joins", f"JOIN: {member} — ID {member.id}")
        if not member.bot:
            channel = self.channel("general")
            try:
                embed=discord.Embed(title='Your next adventure starts here',description=f"Welcome, {member.mention}!\n\nDiscover community mods, explore our Minecraft servers and find your people.\n\n📜 **Start here:** {self.channel('rules').mention}\n🌌 **Choose your server:** {self.channel('roles').mention}\n💬 **Say hello:** {self.channel('general').mention}",color=0x987EFF)
                gifs = [
                    'https://media1.tenor.com/m/tDuVNU9wmewAAAAC/happy-happy-happy-cat.gif',
                    'https://media1.tenor.com/m/Ce_EIG6qg0kAAAAC/happy-happy-happy-happy.gif',
                    'https://media1.tenor.com/m/bUoNtGjmF1cAAAAC/happy-happy-happy.gif',
                ]
                choices = [url for url in gifs if url != self.state.get('last_welcome_gif')]
                gif = random.choice(choices or gifs)
                embed.set_image(url=gif)
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text='AETHON • Minecraft Community')
                await channel.send(content=f'Welcome to Aethon, {member.mention}! 🌌',embed=embed,allowed_mentions=discord.AllowedMentions(users=[member]))
                self.state['last_welcome_gif'] = gif
                save_state(self.state)
            except discord.HTTPException:
                logging.exception("Welcome failed")

    async def on_member_remove(self, member):
        if member.guild.id == GUILD_ID:
            await self.log_to("joins", f"LEFT: {member} — ID {member.id}. This event alone does not distinguish voluntary leave from removal.")

    async def on_audit_log_entry_create(self, entry):
        if entry.guild.id != GUILD_ID or entry.user_id == self.user.id:
            return
        # No message content or private ticket transcripts are copied.
        await self.log_to("modlogs", f"**{entry.action.name}**\nActor ID: {entry.user_id}\nTarget ID: {getattr(entry.target, 'id', 'unknown')}\nAudit entry: {entry.id}\nReason: {discord.utils.escape_markdown(entry.reason or 'Not supplied')[:800]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    for mode in ("preview", "apply", "run", "invites"):
        group.add_argument("--" + mode, action="store_true")
    args = parser.parse_args()
    mode = next(m for m in ("preview", "apply", "run", "invites") if getattr(args, m))
    token = os.environ.get("DISCORD_BOT_TOKEN") or getpass.getpass("Bot token (hidden; never your personal Discord token): ")
    if not token.strip():
        raise SystemExit("No token supplied.")
    bot = Astreon(mode)
    bot.run(token.strip(), log_level=logging.INFO)
    if getattr(bot, "failed", False):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
