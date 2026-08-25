import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
import random
import datetime
import unicodedata
from typing import Optional

# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1540722239027023882
PREFIX = "?"

GUILD = discord.Object(id=GUILD_ID)
CONFIG_FILE = "config.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# =========================================================
# CONFIG JSON
# =========================================================

DEFAULT_CONFIG = {
    "staff_roles": [],
    "role_ids": [],
    "command_roles": {
        "ticket": [],
        "drop": [],
        "freeagent": [],
        "scouting": [],
        "say": [],
        "say_embed": []
    },
    "ticket": {
        "category_id": None,
        "staff_roles": [],
        "log_channel_id": None
    },
    "drop": {
        "channel_id": None,
        "time": 60,
        "reward_roles": []
    },
    "freeagent": {},
    "scouting": {}
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        config = json.loads(json.dumps(DEFAULT_CONFIG))

        def merge(a, b):
            for key, value in b.items():
                if isinstance(value, dict) and isinstance(a.get(key), dict):
                    merge(a[key], value)
                else:
                    a[key] = value

        merge(config, data)
        return config

    except Exception:
        return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CONFIG, f, indent=4, ensure_ascii=False)


CONFIG = load_config()

# =========================================================
# BOT
# =========================================================

class BRSBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=intents
        )

        self.active_drops = {}

    async def setup_hook(self):
        self.add_view(TicketPanel())
        self.add_view(TicketControl())

        synced = await self.tree.sync(guild=GUILD)
        print(f"✅ {len(synced)} slash commands sincronizados.")


bot = BRSBot()

# =========================================================
# UTILIDADES
# =========================================================

def normalize(text):
    return unicodedata.normalize(
        "NFKD",
        text
    ).encode(
        "ascii",
        "ignore"
    ).decode().lower().strip()


def is_admin(member):
    return member.guild_permissions.administrator


def has_permission(member, command):
    if is_admin(member):
        return True

    ids = CONFIG["command_roles"].get(command, [])

    return any(role.id in ids for role in member.roles)


async def permission(interaction, command):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Use este comando dentro do servidor.",
            ephemeral=True
        )
        return False

    if has_permission(interaction.user, command):
        return True

    await interaction.response.send_message(
        "🚫 Você não tem permissão para usar esse comando.",
        ephemeral=True
    )
    return False


def get_channel(channel_id):
    if not channel_id:
        return None

    return bot.get_channel(channel_id)


# =========================================================
# TICKET
# =========================================================

class TicketPanel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Abrir Ticket",
        emoji="🎫",
        style=discord.ButtonStyle.green,
        custom_id="brs_open_ticket"
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        guild = interaction.guild

        if guild is None:
            return

        for channel in guild.text_channels:
            if channel.topic == f"ticket:{interaction.user.id}":
                await interaction.response.send_message(
                    f"❌ Você já possui um ticket: {channel.mention}",
                    ephemeral=True
                )
                return

        category = None
        category_id = CONFIG["ticket"].get("category_id")

        if category_id:
            category = guild.get_channel(category_id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),

            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            )

        for role_id in CONFIG["ticket"].get("staff_roles", []):
            role = guild.get_role(role_id)

            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}".lower()[:90],
            category=category,
            overwrites=overwrites,
            topic=f"ticket:{interaction.user.id}"
        )

        embed = discord.Embed(
            title="🎫 Atendimento",
            description=(
                f"Olá {interaction.user.mention}!\n\n"
                "Explique seu problema e aguarde a Staff."
            ),
            color=0x2B2D31
        )

        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=TicketControl()
        )

        await interaction.response.send_message(
            f"✅ Ticket criado: {channel.mention}",
            ephemeral=True
        )


class TicketControl(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fechar Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="brs_close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Canal inválido.",
                ephemeral=True
            )
            return

        if not channel.name.startswith("ticket-"):
            await interaction.response.send_message(
                "❌ Este canal não é um ticket.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🔒 Ticket fechado. Apagando em 5 segundos."
        )

        await asyncio.sleep(5)

        try:
            await channel.delete(reason="Ticket fechado")
        except discord.Forbidden:
            pass


@bot.tree.command(
    name="ticket",
    description="Sistema de tickets",
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

        if not await permission(interaction, "ticket"):
            return

        embed = discord.Embed(
            title="🎫 CENTRAL DE ATENDIMENTO",
            description=(
                "Clique no botão abaixo para abrir "
                "um ticket privado."
            ),
            color=0x2B2D31
        )

        await interaction.channel.send(
            embed=embed,
            view=TicketPanel()
        )

        await interaction.response.send_message(
            "✅ Painel enviado.",
            ephemeral=True
        )

    elif acao.value == "config":

        if not is_admin(interaction.user):
            await interaction.response.send_message(
                "🚫 Apenas administradores.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Use `/config` para configurar.",
            ephemeral=True
        )


# =========================================================
# CONFIG
# =========================================================

@bot.tree.command(
    name="config",
    description="Configura o bot",
    guild=GUILD
)
@app_commands.describe(
    tipo="O que deseja configurar",
    valor="ID"
)
@app_commands.choices(
    tipo=[
        app_commands.Choice(name="Staff", value="staff"),
        app_commands.Choice(
            name="Categoria Ticket",
            value="ticket_category"
        ),
        app_commands.Choice(
            name="Logs Ticket",
            value="ticket_logs"
        ),
        app_commands.Choice(
            name="Canal Drop",
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
async def config_cmd(
    interaction: discord.Interaction,
    tipo: app_commands.Choice[str],
    valor: str
):

    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "🚫 Apenas administradores.",
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

        msg = "Staff"

    elif tipo.value == "ticket_category":
        CONFIG["ticket"]["category_id"] = value
        msg = "categoria de tickets"

    elif tipo.value == "ticket_logs":
        CONFIG["ticket"]["log_channel_id"] = value
        msg = "logs"

    elif tipo.value == "drop_channel":
        CONFIG["drop"]["channel_id"] = value
        msg = "canal de Drop"

    elif tipo.value == "freeagent_channel":
        CONFIG["freeagent"]["channel_id"] = value
        msg = "canal de Free Agent"

    elif tipo.value == "scouting_channel":
        CONFIG["scouting"]["channel_id"] = value
        msg = "canal de Scouting"

    else:
        return

    save_config()

    await interaction.response.send_message(
        f"✅ {msg} configurado.",
        ephemeral=True
    )


@bot.tree.command(
    name="config_role",
    description="Libera um cargo para usar um comando",
    guild=GUILD
)
@app_commands.describe(
    comando="Comando",
    cargo="Cargo"
)
async def config_role_cmd(
    interaction: discord.Interaction,
    comando: str,
    cargo: discord.Role
):

    if not is_admin(interaction.user):
        await interaction.response.send_message(
            "🚫 Apenas administradores.",
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


# =========================================================
# CARGO ID
# =========================================================

@bot.command(name="cargoid")
async def cargoid(ctx, *, nome=None):

    if not ctx.guild:
        return

    if not nome:
        await ctx.send("❌ Use `?cargoid Nome do Cargo`")
        return

    role = discord.utils.find(
        lambda r: r.name.lower() == nome.lower(),
        ctx.guild.roles
    )

    if not role:
        await ctx.send("❌ Cargo não encontrado.")
        return

    await ctx.send(
        f"🆔 ID de **{role.name}**: `{role.id}`"
    )


# =========================================================
# ROLE
# =========================================================

# COLOQUE AQUI OS IDs DOS CARGOS PERMITIDOS
SELF_ASSIGNABLE_ROLE_IDS = [
    # 123456789012345678,
]


@bot.command(name="role")
async def role_cmd(ctx, *, nome=None):

    if not ctx.guild:
        return

    if not ctx.author.guild_permissions.administrator:
        await ctx.send(
            "🚫 Apenas administradores podem usar `?role`."
        )
        return

    if not nome:
        await ctx.send(
            "❌ Use `?role Nome do Cargo`."
        )
        return

    role = discord.utils.find(
        lambda r: r.name.lower() == nome.lower(),
        ctx.guild.roles
    )

    if not role:
        await ctx.send(
            f"❌ Cargo **{nome}** não encontrado."
        )
        return

    if role.is_default():
        await ctx.send("❌ Não pode usar @everyone.")
        return

    if role.id not in SELF_ASSIGNABLE_ROLE_IDS:
        await ctx.send(
            "🚫 Esse cargo não está liberado no sistema."
        )
        return

    if role.permissions.administrator:
        await ctx.send(
            "🚫 Cargo com Administrador não pode ser usado."
        )
        return

    if ctx.guild.me and role >= ctx.guild.me.top_role:
        await ctx.send(
            "❌ Meu cargo precisa estar acima desse cargo."
        )
        return

    try:

        if role in ctx.author.roles:
            await ctx.author.remove_roles(role)
            await ctx.send(
                f"➖ **{role.name}** removido."
            )
        else:
            await ctx.author.add_roles(role)
            await ctx.send(
                f"➕ **{role.name}** adicionado."
            )

    except discord.Forbidden:
        await ctx.send(
            "❌ Não tenho permissão para mexer nesse cargo."
        )


# =========================================================
# STATUS
# =========================================================

@bot.tree.command(
    name="status",
    description="Mostra o status do bot",
    guild=GUILD
)
async def status_cmd(interaction):

    embed = discord.Embed(
        title="🤖 BRS SYSTEM",
        color=discord.Color.green()
    )

    embed.add_field(
        name="Status",
        value="🟢 Online"
    )

    embed.add_field(
        name="Ping",
        value=f"{round(bot.latency * 1000)}ms"
    )

    embed.add_field(
        name="Drops",
        value=str(len(bot.active_drops))
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# SAY
# =========================================================

@bot.tree.command(
    name="say",
    description="Faz o bot enviar uma mensagem",
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

    if not await permission(interaction, "say"):
        return

    canal = canal or interaction.channel

    await canal.send(
        mensagem.replace("\\n", "\n")
    )

    await interaction.response.send_message(
        "✅ Mensagem enviada.",
        ephemeral=True
    )


# =========================================================
# SAY EMBED
# =========================================================

@bot.tree.command(
    name="say_embed",
    description="Envia uma Embed",
    guild=GUILD
)
@app_commands.describe(
    titulo="Título",
    descricao="Descrição",
    canal="Canal",
    footer="Rodapé"
)
async def say_embed_cmd(
    interaction,
    titulo: str,
    descricao: str,
    canal: Optional[discord.TextChannel] = None,
    footer: Optional[str] = None
):

    if not await permission(interaction, "say_embed"):
        return

    canal = canal or interaction.channel

    embed = discord.Embed(
        title=titulo,
        description=descricao.replace("\\n", "\n"),
        color=0x2B2D31
    )

    if footer:
        embed.set_footer(text=footer)

    await canal.send(embed=embed)

    await interaction.response.send_message(
        "✅ Embed enviada.",
        ephemeral=True
    )


# =========================================================
# CLEAR
# =========================================================

@bot.tree.command(
    name="clear",
    description="Apaga mensagens",
    guild=GUILD
)
@app_commands.describe(
    quantidade="Quantidade de mensagens"
)
async def clear_cmd(
    interaction,
    quantidade: int
):

    if not await permission(interaction, "say"):
        return

    if quantidade < 1 or quantidade > 100:
        await interaction.response.send_message(
            "❌ Use entre 1 e 100.",
            ephemeral=True
        )
        return

    await interaction.response.defer(
        ephemeral=True
    )

    mensagens = await interaction.channel.purge(
        limit=quantidade
    )

    await interaction.followup.send(
        f"🧹 {len(mensagens)} mensagens apagadas.",
        ephemeral=True
    )


# =========================================================
# ERROS
# =========================================================

@bot.tree.error
async def tree_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    print("ERRO:", repr(error))

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                "❌ Deu erro ao executar o comando.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Deu erro ao executar o comando.",
                ephemeral=True
            )
    except:
        pass


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print(
        f"✅ Bot online: {bot.user} | ID: {bot.user.id}"
    )


# =========================================================
# INICIAR
# =========================================================

if not TOKEN:
    raise SystemExit(
        "❌ DISCORD_TOKEN não encontrado."
    )

bot.run(TOKEN)
