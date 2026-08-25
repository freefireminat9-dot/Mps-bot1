import os
import json
import random
import asyncio
import datetime
import logging
import unicodedata
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURAÇÃO
# ============================================================

GUILD_ID = 1540722239027023882
CONFIG_FILE = "config.json"
EMBED_COLOR = 0x2B2D31

GUILD = discord.Object(id=GUILD_ID)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

log = logging.getLogger("BRS-BOT")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


# ============================================================
# CONFIG PADRÃO
# ============================================================

DEFAULT_CONFIG = {
    "staff_roles": [],

    "command_roles": {
        "ticket": [],
        "drop": [],
        "freeagent": [],
        "scouting": [],
        "say": [],
        "say_embed": [],
        "clear": [],
        "amis": [],
        "treino": [],
        "ofc": [],
        "jogo": [],
        "resultado": [],
        "mvp": [],
        "announce": [],
        "poll": [],
        "warn": [],
        "kick": [],
        "ban": [],
        "timeout": [],
        "unban": [],
        "lock": [],
        "unlock": [],
        "nick": [],
        "roleadd": [],
        "roleremove": []
    },

    "ticket": {
        "category_id": None,
        "staff_roles": [],
        "log_channel_id": None,
        "channel_name": "ticket-{user}",
        "welcome_message": (
            "Olá {user}! 👋\n\n"
            "Obrigado por entrar em contato com a BRS.\n"
            "Explique o motivo do atendimento e aguarde a Staff."
        )
    },

    "drop": {
        "default_channel_id": None,
        "reward_roles": [],
        "time_limit": 60
    },

    "freeagent": {
        "channel_id": None,
        "players": {}
    },

    "scouting": {
        "channel_id": None,
        "players": {}
    },

    "warnings": {},

    "matches": []
}


def save_config(data=None):
    if data is None:
        data = CONFIG

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        merged = json.loads(json.dumps(DEFAULT_CONFIG))

        def merge(a, b):
            for key, value in b.items():
                if isinstance(value, dict) and isinstance(a.get(key), dict):
                    merge(a[key], value)
                else:
                    a[key] = value

        merge(merged, data)
        return merged

    except Exception:
        log.exception("Erro ao carregar config.json")
        return json.loads(json.dumps(DEFAULT_CONFIG))


CONFIG = load_config()


# ============================================================
# BOT
# ============================================================

class BRSBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="?",
            intents=intents,
            help_command=None
        )

        self.http_session = None
        self.active_drops = {}

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()

        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())

        synced = await self.tree.sync(guild=GUILD)

        log.info(
            "Sincronizados %s comandos na guild %s",
            len(synced),
            GUILD_ID
        )

    async def close(self):
        if self.http_session:
            await self.http_session.close()

        await super().close()


bot = BRSBot()


@bot.event
async def on_ready():
    log.info(
        "BRS conectado como %s | ID: %s",
        bot.user,
        bot.user.id
    )


# ============================================================
# UTILIDADES
# ============================================================

def normalize(text):
    text = unicodedata.normalize(
        "NFKD",
        text
    ).encode(
        "ascii",
        "ignore"
    ).decode(
        "ascii"
    )

    return text.strip().lower()


def get_channel(channel_id):
    if not channel_id:
        return None

    return bot.get_channel(channel_id)


def is_admin(member):
    return member.guild_permissions.administrator


def has_configured_permission(member, command_name):
    if is_admin(member):
        return True

    roles = CONFIG["command_roles"].get(
        command_name,
        []
    )

    return any(
        role.id in roles
        for role in member.roles
    )


async def require_permission(interaction, command_name):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado dentro da BRS.",
            ephemeral=True
        )
        return False

    if has_configured_permission(
        interaction.user,
        command_name
    ):
        return True

    await interaction.response.send_message(
        "🚫 Você não possui autorização para usar este comando.",
        ephemeral=True
    )

    return False


async def send_log(message, embed=None):
    channel_id = CONFIG["ticket"].get(
        "log_channel_id"
    )

    channel = get_channel(channel_id)

    if channel:
        try:
            await channel.send(
                content=message,
                embed=embed
            )
        except discord.HTTPException:
            pass


def bot_can_manage_role(guild, role):
    me = guild.me

    if not me:
        return False

    if role.is_default():
        return False

    if role.managed:
        return False

    return role < me.top_role


# ============================================================
# TICKET
# ============================================================

def is_ticket_channel(channel):
    return (
        isinstance(channel, discord.TextChannel)
        and channel.name.startswith("ticket-")
    )


class TicketPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Abrir Ticket",
        emoji="🎫",
        style=discord.ButtonStyle.green,
        custom_id="brs_open_ticket"
    )
    async def open_ticket(self, interaction, button):

        guild = interaction.guild

        if not guild:
            return

        existing = discord.utils.find(
            lambda c:
            isinstance(c, discord.TextChannel)
            and c.topic
            and str(interaction.user.id) in c.topic,
            guild.text_channels
        )

        if existing:
            await interaction.response.send_message(
                f"❌ Você já possui um ticket aberto: {existing.mention}",
                ephemeral=True
            )
            return

        category = None

        category_id = CONFIG["ticket"].get(
            "category_id"
        )

        if category_id:
            category = guild.get_channel(category_id)

        channel_name = CONFIG["ticket"].get(
            "channel_name",
            "ticket-{user}"
        )

        channel_name = channel_name.replace(
            "{user}",
            interaction.user.name.lower()
        )[:90]

        overwrites = {
            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            interaction.user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True
                )
        }

        for role_id in CONFIG["ticket"].get(
            "staff_roles",
            []
        ):
            role = guild.get_role(role_id)

            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        ticket = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"BRS Ticket | Criador: {interaction.user.id}",
            reason="BRS Ticket aberto"
        )

        welcome = CONFIG["ticket"].get(
            "welcome_message",
            "Olá {user}!"
        ).replace(
            "{user}",
            interaction.user.mention
        )

        embed = discord.Embed(
            title="🎫 Atendimento BRS",
            description=welcome,
            color=EMBED_COLOR,
            timestamp=datetime.datetime.now()
        )

        embed.set_footer(
            text=f"Ticket de {interaction.user}"
        )

        await ticket.send(
            content=interaction.user.mention,
            embed=embed,
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ Ticket criado: {ticket.mention}",
            ephemeral=True
        )

        await send_log(
            f"🎫 Ticket aberto por {interaction.user.mention}: {ticket.mention}"
        )


class TicketControlView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fechar Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="brs_close_ticket"
    )
    async def close_ticket(self, interaction, button):

        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message(
                "❌ Este botão só funciona em tickets.",
                ephemeral=True
            )
            return

        if not is_admin(interaction.user):
            if not any(
                role.id in CONFIG["ticket"].get(
                    "staff_roles",
                    []
                )
                for role in interaction.user.roles
            ):
                await interaction.response.send_message(
                    "🚫 Você não pode fechar este ticket.",
                    ephemeral=True
                )
                return

        await interaction.response.send_message(
            "🔒 Ticket encerrado. O canal será apagado em 5 segundos.",
            ephemeral=True
        )

        await interaction.channel.send(
            f"🔒 Ticket fechado por {interaction.user.mention}."
        )

        await send_log(
            f"🔒 Ticket fechado por {interaction.user.mention}: "
            f"#{interaction.channel.name}"
        )

        await asyncio.sleep(5)

        try:
            await interaction.channel.delete(
                reason="BRS Ticket fechado"
            )
        except discord.HTTPException:
            pass


@bot.tree.command(
    name="ticket",
    description="Sistema de tickets da BRS.",
    guild=GUILD
)
@app_commands.describe(
    acao="Ação do sistema"
)
@app_commands.choices(
    acao=[
        app_commands.Choice(
            name="Enviar painel",
            value="painel"
        ),
        app_commands.Choice(
            name="Configurar",
            value="config"
        )
    ]
)
async def ticket_cmd(
    interaction: discord.Interaction,
    acao: app_commands.Choice[str]
):

    if acao.value == "painel":

        if not await require_permission(
            interaction,
            "ticket"
        ):
            return

        embed = discord.Embed(
            title="🎫 CENTRAL DE ATENDIMENTO",
            description=(
                "Precisa de ajuda com a BRS?\n\n"
                "Clique no botão abaixo para abrir um atendimento "
                "privado com a Staff."
            ),
            color=EMBED_COLOR
        )

        await interaction.channel.send(
            embed=embed,
            view=TicketPanelView()
        )

        await interaction.response.send_message(
            "✅ Painel enviado.",
            ephemeral=True
        )

    else:

        if not is_admin(interaction.user):
            await interaction.response.send_message(
                "🚫 Apenas Administradores.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "⚙️ Use `/config` para configurar.",
            ephemeral=True
        )


# ============================================================
# CONFIG
# ============================================================

@bot.tree.command(
    name="config",
    description="Configura o sistema da BRS.",
    guild=GUILD
)
@app_commands.describe(
    tipo="Tipo de configuração",
    valor="ID"
)
@app_commands.choices(
    tipo=[
        app_commands.Choice(
            name="Staff",
            value="staff"
        ),
        app_commands.Choice(
            name="Categoria Tickets",
            value="ticket_category"
        ),
        app_commands.Choice(
            name="Log Tickets",
            value="ticket_logs"
        ),
        app_commands.Choice(
            name="Canal Drops",
            value="drop_channel"
        ),
        app_commands.Choice(
            name="Canal Free Agent",
            value="freeagent_channel"
        ),
        app_commands.Choice(
            name="Canal Scouting",
            value="scouting_channel"
        )
    ]
)
async def config_cmd(interaction, tipo, valor):

    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "🚫 Apenas Administradores.",
            ephemeral=True
        )
        return

    try:
        value = int(valor)
    except ValueError:
        await interaction.response.send_message(
            "❌ ID inválido.",
            ephemeral=True
        )
        return

    if tipo.value == "staff":

        if value not in CONFIG["staff_roles"]:
            CONFIG["staff_roles"].append(value)

        if value not in CONFIG["ticket"]["staff_roles"]:
            CONFIG["ticket"]["staff_roles"].append(value)

        message = "cargo de Staff"

    elif tipo.value == "ticket_category":
        CONFIG["ticket"]["category_id"] = value
        message = "categoria dos tickets"

    elif tipo.value == "ticket_logs":
        CONFIG["ticket"]["log_channel_id"] = value
        message = "canal de logs"

    elif tipo.value == "drop_channel":
        CONFIG["drop"]["default_channel_id"] = value
        message = "canal dos Drops"

    elif tipo.value == "freeagent_channel":
        CONFIG["freeagent"]["channel_id"] = value
        message = "canal de Free Agent"

    elif tipo.value == "scouting_channel":
        CONFIG["scouting"]["channel_id"] = value
        message = "canal de Scouting"

    else:
        return

    save_config()

    await interaction.response.send_message(
        f"✅ {message} configurado.",
        ephemeral=True
    )


@bot.tree.command(
    name="config_role",
    description="Autoriza um cargo para usar um comando.",
    guild=GUILD
)
@app_commands.describe(
    comando="Comando",
    cargo="Cargo"
)
async def config_role_cmd(interaction, comando, cargo: discord.Role):

    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "🚫 Apenas Administradores.",
            ephemeral=True
        )
        return

    comando = comando.lower()

    if comando not in CONFIG["command_roles"]:
        await interaction.response.send_message(
            "❌ Comando inválido.",
            ephemeral=True
        )
        return

    if cargo.id not in CONFIG["command_roles"][comando]:
        CONFIG["command_roles"][comando].append(cargo.id)

    save_config()

    await interaction.response.send_message(
        f"✅ {cargo.mention} autorizado para `/{comando}`.",
        ephemeral=True
    )


# ============================================================
# HELP
# ============================================================

@bot.tree.command(
    name="help",
    description="Mostra os comandos do bot.",
    guild=GUILD
)
async def help_cmd(interaction):

    embed = discord.Embed(
        title="🇧🇷 BRS BOT — COMANDOS",
        color=EMBED_COLOR
    )

    embed.add_field(
        name="⚽ Futebol",
        value=(
            "`/amis`\n"
            "`/treino`\n"
            "`/ofc`\n"
            "`/jogo`\n"
            "`/resultado`\n"
            "`/mvp`"
        ),
        inline=True
    )

    embed.add_field(
        name="👥 Jogadores",
        value=(
            "`/freeagent`\n"
            "`/scouting`"
        ),
        inline=True
    )

    embed.add_field(
        name="🛠️ Staff",
        value=(
            "`/ticket`\n"
            "`/drop`\n"
            "`/config`\n"
            "`/config_role`\n"
            "`/say`\n"
            "`/say_embed`\n"
            "`/clear`"
        ),
        inline=True
    )

    embed.add_field(
        name="🔨 Moderação",
        value=(
            "`/warn`\n"
            "`/warnings`\n"
            "`/kick`\n"
            "`/ban`\n"
            "`/timeout`\n"
            "`/unban`\n"
            "`/lock`\n"
            "`/unlock`\n"
            "`/nick`\n"
            "`/roleadd`\n"
            "`/roleremove`"
        ),
        inline=True
    )

    embed.add_field(
        name="ℹ️ Informações",
        value=(
            "`/userinfo`\n"
            "`/avatar`\n"
            "`/serverinfo`\n"
            "`/status`"
        ),
        inline=True
    )

    embed.set_footer(
        text="BRS System"
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# INFORMAÇÕES
# ============================================================

@bot.tree.command(
    name="userinfo",
    description="Mostra informações de um usuário.",
    guild=GUILD
)
@app_commands.describe(
    membro="Usuário"
)
async def userinfo_cmd(
    interaction,
    membro: Optional[discord.Member] = None
):

    membro = membro or interaction.user

    embed = discord.Embed(
        title=f"👤 {membro.display_name}",
        color=EMBED_COLOR
    )

    embed.set_thumbnail(
        url=membro.display_avatar.url
    )

    embed.add_field(
        name="ID",
        value=f"`{membro.id}`"
    )

    embed.add_field(
        name="Conta criada",
        value=discord.utils.format_dt(
            membro.created_at,
            "F"
        ),
        inline=False
    )

    if membro.joined_at:
        embed.add_field(
            name="Entrou no servidor",
            value=discord.utils.format_dt(
                membro.joined_at,
                "F"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@bot.tree.command(
    name="avatar",
    description="Mostra o avatar de um usuário.",
    guild=GUILD
)
@app_commands.describe(
    membro="Usuário"
)
async def avatar_cmd(
    interaction,
    membro: Optional[discord.Member] = None
):

    membro = membro or interaction.user

    embed = discord.Embed(
        title=f"🖼️ Avatar de {membro.display_name}",
        color=EMBED_COLOR
    )

    embed.set_image(
        url=membro.display_avatar.url
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="serverinfo",
    description="Mostra informações do servidor.",
    guild=GUILD
)
async def serverinfo_cmd(interaction):

    guild = interaction.guild

    embed = discord.Embed(
        title=f"🏠 {guild.name}",
        color=EMBED_COLOR
    )

    if guild.icon:
        embed.set_thumbnail(
            url=guild.icon.url
        )

    embed.add_field(
        name="👥 Membros",
        value=str(guild.member_count)
    )

    embed.add_field(
        name="📁 Canais",
        value=str(len(guild.channels))
    )

    embed.add_field(
        name="🎭 Cargos",
        value=str(len(guild.roles))
    )

    embed.add_field(
        name="🆔 ID",
        value=f"`{guild.id}`"
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# MODERAÇÃO
# ============================================================

@bot.tree.command(
    name="warn",
    description="Adverte um usuário.",
    guild=GUILD
)
@app_commands.describe(
    membro="Usuário",
    motivo="Motivo"
)
async def warn_cmd(
    interaction,
    membro: discord.Member,
    motivo: str
):

    if not await require_permission(
        interaction,
        "warn"
    ):
        return

    if membro == interaction.user:
        await interaction.response.send_message(
            "❌ Você não pode advertir a si mesmo.",
            ephemeral=True
        )
        return

    uid = str(membro.id)

    if uid not in CONFIG["warnings"]:
        CONFIG["warnings"][uid] = []

    CONFIG["warnings"][uid].append({
        "reason": motivo,
        "moderator": interaction.user.id,
        "date": datetime.datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        )
    })

    save_config()

    await interaction.response.send_message(
        f"⚠️ {membro.mention} recebeu uma advertência.\n"
        f"**Motivo:** {motivo}"
    )


@bot.tree.command(
    name="warnings",
    description="Mostra as advertências.",
    guild=GUILD
)
@app_commands.describe(
    membro="Usuário"
)
async def warnings_cmd(
    interaction,
    membro: discord.Member
):

    if not await require_permission(
        interaction,
        "warn"
    ):
        return

    warnings = CONFIG["warnings"].get(
        str(membro.id),
        []
    )

    if not warnings:
        await interaction.response.send_message(
            f"📭 {membro.mention} não possui advertências.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"⚠️ Warns — {membro.display_name}",
        color=discord.Color.orange()
    )

    for i, warn in enumerate(warnings[:20], 1):
        embed.add_field(
            name=f"Warn #{i}",
            value=(
                f"**Motivo:** {warn['reason']}\n"
                f"**Data:** {warn['date']}"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@bot.tree.command(
    name="kick",
    description="Expulsa um usuário.",
    guild=GUILD
)
@app_commands.describe(
    membro="Usuário",
    motivo="Motivo"
)
async def kick_cmd(
    interaction,
    membro: discord.Member,
    motivo: str = "Sem motivo informado"
):

    if not await require_permission(
        interaction,
        "kick"
    ):
        return

    if not membro.kickable:
        await interaction.response.send_message(
            "❌ Não consigo expulsar esse usuário.",
            ephemeral=True
        )
        return

    await membro.kick(reason=motivo)

    await interaction.response.send_message(
        f"👢 {membro.mention} foi expulso.\n**Motivo:** {motivo}"
    )


@bot.tree.command(
    name="ban",
    description="Bane um usuário.",
    guild=GUILD
)
@app_commands.describe(
    membro="Usuário",
    motivo="Motivo"
)
async def ban_cmd(
    interaction,
    membro: discord.Member,
    motivo: str = "Sem motivo informado"
):

    if not await require_permission(
        interaction,
        "ban"
    ):
        return

    if not membro.bannable:
        await interaction.response.send_message(
            "❌ Não consigo banir esse usuário.",
            ephemeral=True
        )
        return

    await membro.ban(
        reason=motivo,
        delete_message_days=0
    )

    await interaction.response.send_message(
        f"🔨 {membro.mention} foi banido.\n**Motivo:** {motivo}"
    )


@bot.tree.command(
    name="timeout",
    description="Coloca um usuário em timeout.",
    guild=GUILD
)
@app_commands.describe(
    membro="Usuário",
    minutos="Duração",
    motivo="Motivo"
)
async def timeout_cmd(
    interaction,
    membro: discord.Member,
    minutos: int,
    motivo: str = "Sem motivo informado"
):

    if not await require_permission(
        interaction,
        "timeout"
    ):
        return

    if minutos < 1 or minutos > 40320:
        await interaction.response.send_message(
            "❌ Use entre 1 e 40320 minutos.",
            ephemeral=True
        )
        return

    until = discord.utils.utcnow() + datetime.timedelta(
        minutes=minutos
    )

    await membro.timeout(
        until,
        reason=motivo
    )

    await interaction.response.send_message(
        f"⏱️ {membro.mention} recebeu timeout por "
        f"**{minutos} minutos**."
    )


@bot.tree.command(
    name="unban",
    description="Remove um banimento.",
    guild=GUILD
)
@app_commands.describe(
    id_usuario="ID do usuário"
)
async def unban_cmd(
    interaction,
    id_usuario: str
):

    if not await require_permission(
        interaction,
        "unban"
    ):
        return

    try:
        user_id = int(id_usuario)
    except ValueError:
        await interaction.response.send_message(
            "❌ ID inválido.",
            ephemeral=True
        )
        return

    try:
        user = await bot.fetch_user(user_id)

        await interaction.guild.unban(
            user
        )

        await interaction.response.send_message(
            f"✅ {user} foi desbanido."
        )

    except discord.NotFound:
        await interaction.response.send_message(
            "❌ Usuário não está banido ou ID inválido.",
            ephemeral=True
        )


@bot.tree.command(
    name="lock",
    description="Bloqueia o canal.",
    guild=GUILD
)
async def lock_cmd(interaction):

    if not await require_permission(
        interaction,
        "lock"
    ):
        return

    overwrite = interaction.channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = False

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    await interaction.response.send_message(
        "🔒 Canal bloqueado."
    )


@bot.tree.command(
    name="unlock",
    description="Desbloqueia o canal.",
    guild=GUILD
)
async def unlock_cmd(interaction):

    if not await require_permission(
        interaction,
        "unlock"
    ):
        return

    overwrite = interaction.channel.overwrites_for(
        interaction.guild.default_role
    )

    overwrite.send_messages = None

    await interaction.channel.set_permissions(
        interaction.guild.default_role,
        overwrite=overwrite
    )

    await interaction.response.send_message(
        "🔓 Canal desbloqueado."
    )


@bot.tree.command(
    name="nick",
    description="Altera o apelido de um usuário.",
    guild=GUILD
)
@app_commands.describe(
    membro="Usuário",
    apelido="Novo apelido"
)
async def nick_cmd(
    interaction,
    membro: discord.Member,
    apelido: Optional[str] = None
):

    if not await require_permission(
        interaction,
        "nick"
    ):
        return

    if not membro.editable:
        await interaction.response.send_message(
            "❌ Não consigo alterar o apelido desse usuário.",
            ephemeral=True
        )
        return

    await membro.edit(
        nick=apelido
    )

    await interaction.response.send_message(
        "✅ Apelido alterado."
    )


@bot.tree.command(
    name="roleadd",
    description="Adiciona um cargo.",
    guild=GUILD
)
@app_commands.describe(
    membro="Usuário",
    cargo="Cargo"
)
async def roleadd_cmd(
    interaction,
    membro: discord.Member,
    cargo: discord.Role
):

    if not await require_permission(
        interaction,
        "roleadd"
    ):
        return

    if not bot_can_manage_role(
        interaction.guild,
        cargo
    ):
        await interaction.response.send_message(
            "❌ Não consigo gerenciar esse cargo por causa da hierarquia.",
            ephemeral=True
        )
        return

    await membro.add_roles(
        cargo,
        reason=f"BRS roleadd por {interaction.user}"
    )

    await interaction.response.send_message(
        f"➕ {cargo.mention} adicionado a {membro.mention}."
    )


@bot.tree.command(
    name="roleremove",
    description="Remove um cargo.",
    guild=GUILD
)
@app_commands.describe(
    membro="Usuário",
    cargo="Cargo"
)
async def roleremove_cmd(
    interaction,
    membro: discord.Member,
    cargo: discord.Role
):

    if not await require_permission(
        interaction,
        "roleremove"
    ):
        return

    if not bot_can_manage_role(
        interaction.guild,
        cargo
    ):
        await interaction.response.send_message(
            "❌ Não consigo gerenciar esse cargo.",
            ephemeral=True
        )
        return

    await membro.remove_roles(
        cargo,
        reason=f"BRS roleremove por {interaction.user}"
    )

    await interaction.response.send_message(
        f"➖ {cargo.mention} removido de {membro.mention}."
    )


# ============================================================
# ANÚNCIO / VOTAÇÃO
# ============================================================

@bot.tree.command(
    name="announce",
    description="Envia um anúncio.",
    guild=GUILD
)
@app_commands.describe(
    titulo="Título",
    mensagem="Mensagem"
)
async def announce_cmd(
    interaction,
    titulo: str,
    mensagem: str
):

    if not await require_permission(
        interaction,
        "announce"
    ):
        return

    embed = discord.Embed(
        title=f"📢 {titulo}",
        description=mensagem.replace(
            "\\n",
            "\n"
        ),
        color=EMBED_COLOR,
        timestamp=datetime.datetime.now()
    )

    await interaction.channel.send(
        content="@everyone",
        embed=embed
    )

    await interaction.response.send_message(
        "✅ Anúncio enviado.",
        ephemeral=True
    )


@bot.tree.command(
    name="poll",
    description="Cria uma votação.",
    guild=GUILD
)
@app_commands.describe(
    pergunta="Pergunta"
)
async def poll_cmd(
    interaction,
    pergunta: str
):

    if not await require_permission(
        interaction,
        "poll"
    ):
        return

    message = await interaction.channel.send(
        f"📊 **VOTAÇÃO**\n\n{pergunta}\n\n"
        "👍 = Sim\n"
        "👎 = Não"
    )

    await message.add_reaction("👍")
    await message.add_reaction("👎")

    await interaction.response.send_message(
        "✅ Votação criada.",
        ephemeral=True
    )


# ============================================================
# FUTEBOL
# ============================================================

async def futebol_announcement(
    interaction,
    titulo,
    descricao,
    command_name
):

    if not await require_permission(
        interaction,
        command_name
    ):
        return

    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=EMBED_COLOR,
        timestamp=datetime.datetime.now()
    )

    embed.set_footer(
        text=f"BRS • {interaction.user.display_name}"
    )

    await interaction.channel.send(
        content="@everyone",
        embed=embed
    )

    await interaction.response.send_message(
        "✅ Publicado.",
        ephemeral=True
    )


@bot.tree.command(
    name="amis",
    description="Abre uma votação para amistoso.",
    guild=GUILD
)
@app_commands.describe(
    adversario="Adversário"
)
async def amis_cmd(
    interaction,
    adversario: str
):

    await futebol_announcement(
        interaction,
        "⚽ AMISTOSO",
        (
            f"## 🆚 BRS x {adversario}\n\n"
            "👥 **Votação para amistoso**\n\n"
            "👍 = Vou jogar\n"
            "👎 = Não vou\n\n"
            "**Formação:** 4/5 + 1 GK"
        ),
        "amis"
    )


@bot.tree.command(
    name="treino",
    description="Abre uma votação para treino.",
    guild=GUILD
)
async def treino_cmd(interaction):

    await futebol_announcement(
        interaction,
        "🏋️ TREINO",
        (
            "## 🇧🇷 TREINO BRS\n\n"
            "Quem vai participar?\n\n"
            "👍 = Vou\n"
            "👎 = Não vou"
        ),
        "treino"
    )


@bot.tree.command(
    name="ofc",
    description="Anuncia uma partida oficial.",
    guild=GUILD
)
@app_commands.describe(
    adversario="Adversário",
    horario="Horário"
)
async def ofc_cmd(
    interaction,
    adversario: str,
    horario: str
):

    await futebol_announcement(
        interaction,
        "🏆 PARTIDA OFICIAL",
        (
            f"## 🇧🇷 BRS x {adversario}\n\n"
            f"🕐 **Horário:** {horario}\n\n"
            "🔥 **PARTIDA OFICIAL**"
        ),
        "ofc"
    )


@bot.tree.command(
    name="jogo",
    description="Registra uma partida.",
    guild=GUILD
)
@app_commands.describe(
    adversario="Adversário",
    horario="Horário",
    tipo="Tipo da partida"
)
async def jogo_cmd(
    interaction,
    adversario: str,
    horario: str,
    tipo: str = "Amistoso"
):

    if not await require_permission(
        interaction,
        "jogo"
    ):
        return

    partida = {
        "adversario": adversario,
        "horario": horario,
        "tipo": tipo,
        "autor": interaction.user.id,
        "date": datetime.datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        )
    }

    CONFIG["matches"].append(partida)
    save_config()

    await interaction.response.send_message(
        f"⚽ Partida registrada: **BRS x {adversario}**\n"
        f"🕐 {horario}\n"
        f"📌 {tipo}"
    )


@bot.tree.command(
    name="resultado",
    description="Registra o resultado de uma partida.",
    guild=GUILD
)
@app_commands.describe(
    adversario="Adversário",
    gols_brs="Gols da BRS",
    gols_adversario="Gols do adversário"
)
async def resultado_cmd(
    interaction,
    adversario: str,
    gols_brs: int,
    gols_adversario: int
):

    if not await require_permission(
        interaction,
        "resultado"
    ):
        return

    if gols_brs > gols_adversario:
        resultado = "🏆 VITÓRIA"
    elif gols_brs < gols_adversario:
        resultado = "❌ DERROTA"
    else:
        resultado = "🤝 EMPATE"

    embed = discord.Embed(
        title="📊 RESULTADO",
        description=(
            f"## 🇧🇷 BRS {gols_brs} x "
            f"{gols_adversario} {adversario}\n\n"
            f"### {resultado}"
        ),
        color=EMBED_COLOR
    )

    await interaction.channel.send(
        embed=embed
    )

    await interaction.response.send_message(
        "✅ Resultado publicado.",
        ephemeral=True
    )


@bot.tree.command(
    name="mvp",
    description="Define o MVP da partida.",
    guild=GUILD
)
@app_commands.describe(
    jogador="Jogador",
    partida="Partida"
)
async def mvp_cmd(
    interaction,
    jogador: discord.Member,
    partida: str
):

    if not await require_permission(
        interaction,
        "mvp"
    ):
        return

    embed = discord.Embed(
        title="⭐ MVP DA PARTIDA",
        description=(
            f"🏆 **MVP:** {jogador.mention}\n"
            f"⚽ **Partida:** {partida}"
        ),
        color=discord.Color.gold()
    )

    embed.set_thumbnail(
        url=jogador.display_avatar.url
    )

    await interaction.channel.send(
        embed=embed
    )

    await interaction.response.send_message(
        "✅ MVP registrado.",
        ephemeral=True
    )


# ============================================================
# SAY
# ============================================================

@bot.tree.command(
    name="say",
    description="Envia uma mensagem através do bot.",
    guild=GUILD
)
@app_commands.describe(
    mensagem="Mensagem",
    canal="Canal"
)
async def say_cmd(
    interaction,
    mensagem: str,
    canal: Optional[discord.TextChannel] = None
):

    if not await require_permission(
        interaction,
        "say"
    ):
        return

    canal = canal or interaction.channel

    await canal.send(
        mensagem.replace(
            "\\n",
            "\n"
        )
    )

    await interaction.response.send_message(
        "✅ Mensagem enviada.",
        ephemeral=True
    )


@bot.tree.command(
    name="say_embed",
    description="Envia uma Embed.",
    guild=GUILD
)
@app_commands.describe(
    titulo="Título",
    descricao="Descrição",
    canal="Canal",
    footer="Footer",
    thumbnail="Thumbnail URL",
    imagem="Imagem URL",
    autor="Autor"
)
async def say_embed_cmd(
    interaction,
    titulo: str,
    descricao: str,
    canal: Optional[discord.TextChannel] = None,
    footer: Optional[str] = None,
    thumbnail: Optional[str] = None,
    imagem: Optional[str] = None,
    autor: Optional[str] = None
):

    if not await require_permission(
        interaction,
        "say_embed"
    ):
        return

    canal = canal or interaction.channel

    embed = discord.Embed(
        title=titulo,
        description=descricao.replace(
            "\\n",
            "\n"
        ),
        color=EMBED_COLOR,
        timestamp=datetime.datetime.now()
    )

    if footer:
        embed.set_footer(text=footer)

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    if imagem:
        embed.set_image(url=imagem)

    if autor:
        embed.set_author(name=autor)

    await canal.send(
        embed=embed
    )

    await interaction.response.send_message(
        "✅ Embed enviada.",
        ephemeral=True
    )


# ============================================================
# CLEAR
# ============================================================

@bot.tree.command(
    name="clear",
    description="Apaga mensagens.",
    guild=GUILD
)
@app_commands.describe(
    quantidade="Quantidade"
)
async def clear_cmd(
    interaction,
    quantidade: int
):

    if not await require_permission(
        interaction,
        "clear"
    ):
        return

    if quantidade < 1 or quantidade > 100:
        await interaction.response.send_message(
            "❌ Escolha entre 1 e 100.",
            ephemeral=True
        )
        return

    await interaction.response.defer(
        ephemeral=True
    )

    deleted = await interaction.channel.purge(
        limit=quantidade
    )

    await interaction.followup.send(
        f"🧹 {len(deleted)} mensagens apagadas.",
        ephemeral=True
    )


# ============================================================
# FREE AGENT
# ============================================================

@bot.tree.command(
    name="freeagent",
    description="Gerencia Free Agents.",
    guild=GUILD
)
@app_commands.describe(
    jogador="Jogador",
    posicao="Posição",
    descricao="Descrição"
)
async def freeagent_cmd(
    interaction,
    jogador: discord.Member,
    posicao: str,
    descricao: str
):

    if not await require_permission(
        interaction,
        "freeagent"
    ):
        return

    players = CONFIG["freeagent"]["players"]

    players[str(jogador.id)] = {
        "name": jogador.display_name,
        "mention": jogador.mention,
        "position": posicao,
        "description": descricao,
        "date": datetime.datetime.now().strftime(
            "%d/%m/%Y"
        )
    }

    save_config()

    embed = discord.Embed(
        title="🆓 FREE AGENT",
        description=(
            f"**Jogador:** {jogador.mention}\n"
            f"**Posição:** `{posicao}`\n\n"
            f"**Descrição:** {descricao}"
        ),
        color=discord.Color.blue()
    )

    embed.set_thumbnail(
        url=jogador.display_avatar.url
    )

    channel = get_channel(
        CONFIG["freeagent"].get(
            "channel_id"
        )
    )

    if channel:
        await channel.send(
            embed=embed
        )

    await interaction.response.send_message(
        "✅ Free Agent cadastrado.",
        ephemeral=True
    )


# ============================================================
# SCOUTING
# ============================================================

@bot.tree.command(
    name="scouting",
    description="Cria um relatório de scouting.",
    guild=GUILD
)
@app_commands.describe(
    jogador="Jogador",
    posicao="Posição",
    descricao="Descrição",
    observacoes="Observações",
    status="Status"
)
async def scouting_cmd(
    interaction,
    jogador: discord.Member,
    posicao: str,
    descricao: str,
    observacoes: str,
    status: str = "Em avaliação"
):

    if not await require_permission(
        interaction,
        "scouting"
    ):
        return

    players = CONFIG["scouting"]["players"]

    players[str(jogador.id)] = {
        "name": jogador.display_name,
        "mention": jogador.mention,
        "position": posicao,
        "description": descricao,
        "observations": observacoes,
        "status": status,
        "date": datetime.datetime.now().strftime(
            "%d/%m/%Y"
        )
    }

    save_config()

    embed = discord.Embed(
        title="🔍 SCOUTING REPORT",
        description=(
            f"**Jogador:** {jogador.mention}\n"
            f"**Posição:** `{posicao}`\n\n"
            f"**Descrição:** {descricao}\n\n"
            f"**Observações:** {observacoes}\n\n"
            f"**Status:** {status}"
        ),
        color=discord.Color.orange()
    )

    embed.set_thumbnail(
        url=jogador.display_avatar.url
    )

    channel = get_channel(
        CONFIG["scouting"].get(
            "channel_id"
        )
    )

    if channel:
        await channel.send(
            embed=embed
        )

    await interaction.response.send_message(
        "✅ Scouting criado.",
        ephemeral=True
    )


# ============================================================
# ?CARGOID
# ============================================================

@bot.command(
    name="cargoid"
)
async def cargoid_cmd(
    ctx,
    *,
    cargo: Optional[str] = None
):

    if not ctx.guild:
        return

    if not cargo:
        await ctx.reply(
            "❌ Use: `?cargoid NomeDoCargo`",
            mention_author=False
        )
        return

    role = discord.utils.find(
        lambda r:
        r.name.lower() == cargo.lower(),
        ctx.guild.roles
    )

    if not role:
        await ctx.reply(
            f"❌ Não encontrei o cargo **{cargo}**.",
            mention_author=False
        )
        return

    await ctx.reply(
        f"🆔 ID do cargo **{role.name}**: `{role.id}`",
        mention_author=False
    )


# ============================================================
# ?ROLE
# ============================================================

# COLOQUE AQUI OS IDs DOS CARGOS PERMITIDOS.
SELF_ASSIGNABLE_ROLE_IDS = [
    # 123456789012345678,
    # 987654321098765432,
]


@bot.command(
    name="role"
)
async def role_cmd(
    ctx,
    *,
    cargo: Optional[str] = None
):

    if not ctx.guild:
        return

    # SOMENTE ADMINISTRADOR
    if not ctx.author.guild_permissions.administrator:
        await ctx.reply(
            "🚫 Apenas Administradores podem usar `?role`.",
            mention_author=False
        )
        return

    if not cargo:
        await ctx.reply(
            "❌ Use: `?role NomeDoCargo`",
            mention_author=False
        )
        return

    role = discord.utils.find(
        lambda r:
        r.name.lower() == cargo.lower(),
        ctx.guild.roles
    )

    if not role:
        await ctx.reply(
            f"❌ Não encontrei o cargo **{cargo}**.",
            mention_author=False
        )
        return

    if role.is_default():
        await ctx.reply(
            "❌ Esse cargo não pode ser utilizado.",
            mention_author=False
        )
        return

    if role.managed:
        await ctx.reply(
            "❌ Esse cargo é gerenciado por integração.",
            mention_author=False
        )
        return

    if role.id not in SELF_ASSIGNABLE_ROLE_IDS:
        await ctx.reply(
            "🚫 Esse cargo não está liberado no sistema.",
            mention_author=False
        )
        return

    if role.permissions.administrator:
        await ctx.reply(
            "🚫 Cargo com Administrador não pode ser usado.",
            mention_author=False
        )
        return

    if not bot_can_manage_role(
        ctx.guild,
        role
    ):
        await ctx.reply(
            "❌ O cargo está acima ou no mesmo nível do meu cargo.",
            mention_author=False
        )
        return

    try:

        if role in ctx.author.roles:

            await ctx.author.remove_roles(
                role,
                reason="BRS ?role"
            )

            await ctx.reply(
                f"➖ Cargo **{role.name}** removido.",
                mention_author=False
            )

        else:

            await ctx.author.add_roles(
                role,
                reason="BRS ?role"
            )

            await ctx.reply(
                f"➕ Cargo **{role.name}** adicionado.",
                mention_author=False
            )

    except discord.Forbidden:

        await ctx.reply(
            "❌ Não tenho permissão para alterar esse cargo.",
            mention_author=False
        )


# ============================================================
# STATUS
# ============================================================

@bot.tree.command(
    name="status",
    description="Mostra o status do bot.",
    guild=GUILD
)
async def status_cmd(interaction):

    embed = discord.Embed(
        title="🇧🇷 BRS SYSTEM",
        description="Bot operacional.",
        color=discord.Color.green()
    )

    embed.add_field(
        name="🤖 Bot",
        value="Online"
    )

    embed.add_field(
        name="📡 Latência",
        value=f"{round(bot.latency * 1000)}ms"
    )

    embed.add_field(
        name="🎁 Drops",
        value=str(len(bot.active_drops))
    )

    embed.add_field(
        name="⚽ Partidas",
        value=str(len(CONFIG["matches"]))
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# ERROS
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    log.exception(
        "Erro em slash command",
        exc_info=error
    )

    message = "❌ Ocorreu um erro ao executar o comando."

    try:

        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except discord.HTTPException:
        pass


# ============================================================
# TOKEN
# ============================================================

if __name__ == "__main__":

    TOKEN = os.getenv(
        "DISCORD_TOKEN"
    )

    if not TOKEN:
        raise SystemExit(
            "❌ A variável DISCORD_TOKEN não foi encontrada."
        )

    bot.run(TOKEN)
