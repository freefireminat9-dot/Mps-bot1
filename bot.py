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
from PIL import Image

load_dotenv()

# ============================================================
# CONFIGURAÇÃO PRINCIPAL
# ============================================================

GUILD_ID = 1540722239027023882

EMBED_COLOR = 0x2B2D31
CONFIG_FILE = "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

log = logging.getLogger("BRS-BOT")

GUILD = discord.Object(id=GUILD_ID)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


# ============================================================
# CONFIG JSON
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
        "config": []
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
    }
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Garante que configurações novas existam
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


def save_config(data=None):
    if data is None:
        data = CONFIG

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


CONFIG = load_config()


# ============================================================
# BOT
# ============================================================

class BRSBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="?",
            intents=intents
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

def guild_icon_url():

    guild = bot.get_guild(GUILD_ID)

    if guild and guild.icon:
        return guild.icon.url

    return None


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


def is_admin(member: discord.Member):

    return member.guild_permissions.administrator


def has_configured_permission(
    member: discord.Member,
    command_name: str
):

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


async def require_permission(
    interaction: discord.Interaction,
    command_name: str
):

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


def get_channel(channel_id):

    if not channel_id:
        return None

    return bot.get_channel(channel_id)


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

        super().__init__(
            timeout=None
        )

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
            category = guild.get_channel(
                category_id
            )

        channel_name = CONFIG["ticket"].get(
            "channel_name",
            "ticket-{user}"
        )

        channel_name = channel_name.replace(
            "{user}",
            interaction.user.name.lower()
        )

        channel_name = channel_name[:90]

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

        staff_roles = CONFIG["ticket"].get(
            "staff_roles",
            []
        )

        for role_id in staff_roles:

            role = guild.get_role(
                role_id
            )

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
        )

        welcome = welcome.replace(
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

        super().__init__(
            timeout=None
        )

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

        if not is_ticket_channel(
            interaction.channel
        ):
            await interaction.response.send_message(
                "❌ Este botão só funciona em tickets.",
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
    acao="Escolha a ação do sistema de tickets."
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
            "✅ Painel de tickets enviado.",
            ephemeral=True
        )

        return

    if acao.value == "config":

        if not is_admin(interaction.user):

            await interaction.response.send_message(
                "🚫 Apenas Administradores podem configurar tickets.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "⚙️ Use `/config` para configurar o sistema de tickets.",
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
    valor="ID do cargo/canal/categoria."
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
async def config_cmd(
    interaction: discord.Interaction,
    tipo: app_commands.Choice[str],
    valor: str
):

    if not is_admin(interaction.user):

        await interaction.response.send_message(
            "🚫 Apenas Administradores podem alterar configurações.",
            ephemeral=True
        )

        return

    try:

        value = int(valor)

    except ValueError:

        await interaction.response.send_message(
            "❌ Informe um ID numérico válido.",
            ephemeral=True
        )

        return

    if tipo.value == "staff":

        CONFIG["staff_roles"].append(
            value
        )

        CONFIG["ticket"]["staff_roles"].append(
            value
        )

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

        message = "canal de Free Agents"

    elif tipo.value == "scouting_channel":

        CONFIG["scouting"]["channel_id"] = value

        message = "canal de Scouting"

    else:

        await interaction.response.send_message(
            "❌ Configuração inválida.",
            ephemeral=True
        )

        return

    save_config()

    await interaction.response.send_message(
        f"✅ {message} configurado com sucesso.",
        ephemeral=True
    )


@bot.tree.command(
    name="config_role",
    description="Define cargos autorizados para comandos.",
    guild=GUILD
)
@app_commands.describe(
    comando="Comando",
    cargo="Cargo autorizado"
)
async def config_role_cmd(
    interaction: discord.Interaction,
    comando: str,
    cargo: discord.Role
):

    if not is_admin(interaction.user):

        await interaction.response.send_message(
            "🚫 Apenas Administradores podem configurar permissões.",
            ephemeral=True
        )

        return

    comandos = [
        "ticket",
        "drop",
        "freeagent",
        "scouting",
        "say",
        "say_embed",
        "config"
    ]

    comando = comando.lower()

    if comando not in comandos:

        await interaction.response.send_message(
            "❌ Comando inválido.\n\n"
            f"Disponíveis: {', '.join(comandos)}",
            ephemeral=True
        )

        return

    lista = CONFIG["command_roles"][comando]

    if cargo.id not in lista:
        lista.append(cargo.id)

    save_config()

    await interaction.response.send_message(
        f"✅ O cargo {cargo.mention} agora pode usar `/{comando}`.",
        ephemeral=True
    )


# ============================================================
# DROP
# ============================================================

class DropRewardView(discord.ui.View):

    def __init__(
        self,
        user_id,
        drop_id
    ):

        super().__init__(
            timeout=300
        )

        self.user_id = user_id
        self.drop_id = drop_id

        roles = CONFIG["drop"].get(
            "reward_roles",
            []
        )

        for role_id in roles[:5]:

            self.add_item(
                DropRewardButton(
                    role_id,
                    user_id,
                    drop_id
                )
            )


class DropRewardButton(discord.ui.Button):

    def __init__(
        self,
        role_id,
        user_id,
        drop_id
    ):

        self.role_id = role_id
        self.user_id = user_id
        self.drop_id = drop_id

        super().__init__(
            label="Escolher prêmio",
            emoji="🏆",
            style=discord.ButtonStyle.blurple
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "❌ Essa recompensa não pertence a você.",
                ephemeral=True
            )

            return

        drop = bot.active_drops.get(
            self.drop_id
        )

        if not drop or drop.get("reward_claimed"):

            await interaction.response.send_message(
                "❌ Essa recompensa já foi utilizada.",
                ephemeral=True
            )

            return

        guild = bot.get_guild(
            GUILD_ID
        )

        if not guild:

            return

        member = guild.get_member(
            self.user_id
        )

        role = guild.get_role(
            self.role_id
        )

        if not member or not role:

            await interaction.response.send_message(
                "❌ Não consegui localizar o cargo.",
                ephemeral=True
            )

            return

        if role >= guild.me.top_role:

            await interaction.response.send_message(
                "❌ Não consigo atribuir esse cargo devido à hierarquia.",
                ephemeral=True
            )

            return

        await member.add_roles(
            role,
            reason="BRS Drop Reward"
        )

        drop["reward_claimed"] = True

        for child in self.view.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=(
                f"🏆 Você escolheu o cargo **{role.name}**!\n"
                "O prêmio foi atribuído com sucesso."
            ),
            view=self.view
        )


@bot.tree.command(
    name="drop",
    description="Cria ou cancela um Drop.",
    guild=GUILD
)
@app_commands.describe(
    acao="Ação",
    pergunta="Pergunta do Drop",
    resposta="Resposta correta"
)
@app_commands.choices(
    acao=[
        app_commands.Choice(
            name="Iniciar",
            value="start"
        ),
        app_commands.Choice(
            name="Cancelar",
            value="cancel"
        )
    ]
)
async def drop_cmd(
    interaction: discord.Interaction,
    acao: app_commands.Choice[str],
    pergunta: Optional[str] = None,
    resposta: Optional[str] = None
):

    if not await require_permission(
        interaction,
        "drop"
    ):
        return

    channel = interaction.channel

    if acao.value == "cancel":

        found = None

        for drop_id, drop in bot.active_drops.items():

            if drop["channel_id"] == channel.id:
                found = drop_id
                break

        if not found:

            await interaction.response.send_message(
                "❌ Não existe Drop ativo neste canal.",
                ephemeral=True
            )

            return

        bot.active_drops.pop(
            found
        )

        await interaction.response.send_message(
            "🛑 Drop cancelado.",
            ephemeral=True
        )

        await channel.send(
            "🛑 **DROP CANCELADO PELA STAFF.**"
        )

        return

    if not pergunta or not resposta:

        await interaction.response.send_message(
            "❌ Informe a pergunta e a resposta correta.",
            ephemeral=True
        )

        return

    drop_id = str(
        random.randint(
            100000,
            999999
        )
    )

    bot.active_drops[drop_id] = {
        "channel_id": channel.id,
        "answer": normalize(resposta),
        "winner": None,
        "reward_claimed": False
    }

    embed = discord.Embed(
        title="🎁 BRS DROP",
        description=(
            f"## {pergunta}\n\n"
            "⚡ **Quem responder corretamente primeiro vence!**"
        ),
        color=discord.Color.gold()
    )

    embed.set_footer(
        text="Boa sorte!"
    )

    await channel.send(
        embed=embed
    )

    await interaction.response.send_message(
        "✅ Drop iniciado.",
        ephemeral=True
    )

    async def wait_answer():

        def check(message):

            return (
                message.channel.id == channel.id
                and not message.author.bot
            )

        try:

            while drop_id in bot.active_drops:

                message = await bot.wait_for(
                    "message",
                    timeout=CONFIG["drop"].get(
                        "time_limit",
                        60
                    ),
                    check=check
                )

                drop = bot.active_drops.get(
                    drop_id
                )

                if not drop:
                    return

                if normalize(
                    message.content
                ) == drop["answer"]:

                    if drop["winner"] is not None:
                        continue

                    drop["winner"] = message.author.id

                    await channel.send(
                        f"🏆 {message.author.mention} "
                        f"**venceu o Drop!**"
                    )

                    try:

                        dm = discord.Embed(
                            title="🏆 VOCÊ VENCEU!",
                            description=(
                                "Parabéns! Você foi o primeiro a "
                                "responder corretamente.\n\n"
                                "Escolha seu prêmio abaixo:"
                            ),
                            color=discord.Color.gold()
                        )

                        await message.author.send(
                            embed=dm,
                            view=DropRewardView(
                                message.author.id,
                                drop_id
                            )
                        )

                    except discord.Forbidden:

                        await channel.send(
                            f"⚠️ {message.author.mention}, "
                            "não consegui enviar sua DM."
                        )

                    return

        except asyncio.TimeoutError:

            if drop_id in bot.active_drops:

                await channel.send(
                    "⏰ **Tempo esgotado! Ninguém venceu o Drop.**"
                )

        finally:

            bot.active_drops.pop(
                drop_id,
                None
            )

    asyncio.create_task(
        wait_answer()
    )


# ============================================================
# FREE AGENT
# ============================================================

@bot.tree.command(
    name="freeagent",
    description="Gerenciamento de Free Agents.",
    guild=GUILD
)
@app_commands.describe(
    acao="Ação",
    jogador="Jogador",
    posicao="Position",
    descricao="Descrição"
)
@app_commands.choices(
    acao=[
        app_commands.Choice(
            name="Adicionar",
            value="add"
        ),
        app_commands.Choice(
            name="Remover",
            value="remove"
        ),
        app_commands.Choice(
            name="Visualizar",
            value="view"
        ),
        app_commands.Choice(
            name="Pesquisar",
            value="search"
        )
    ]
)
async def freeagent_cmd(
    interaction: discord.Interaction,
    acao: app_commands.Choice[str],
    jogador: Optional[discord.Member] = None,
    posicao: Optional[str] = None,
    descricao: Optional[str] = None
):

    if not await require_permission(
        interaction,
        "freeagent"
    ):
        return

    players = CONFIG["freeagent"]["players"]

    if acao.value == "add":

        if not jogador or not posicao or not descricao:

            await interaction.response.send_message(
                "❌ Informe jogador, posição e descrição.",
                ephemeral=True
            )

            return

        players[str(jogador.id)] = {
            "name": jogador.display_name,
            "mention": jogador.mention,
            "position": posicao,
            "description": descricao,
            "avatar": str(jogador.display_avatar.url),
            "date": datetime.datetime.now().strftime(
                "%d/%m/%Y"
            )
        }

        save_config()

        embed = discord.Embed(
            title="🆓 FREE AGENT",
            description=(
                f"**Jogador:** {jogador.mention}\n"
                f"**Position:** `{posicao}`\n\n"
                f"**Descrição:**\n{descricao}"
            ),
            color=discord.Color.blue()
        )

        embed.set_thumbnail(
            url=jogador.display_avatar.url
        )

        embed.add_field(
            name="📅 Cadastro",
            value=datetime.datetime.now().strftime(
                "%d/%m/%Y"
            )
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

    elif acao.value == "remove":

        if not jogador:

            await interaction.response.send_message(
                "❌ Informe o jogador.",
                ephemeral=True
            )

            return

        if str(jogador.id) not in players:

            await interaction.response.send_message(
                "❌ Esse jogador não está cadastrado.",
                ephemeral=True
            )

            return

        del players[str(jogador.id)]

        save_config()

        await interaction.response.send_message(
            "✅ Free Agent removido.",
            ephemeral=True
        )

    elif acao.value in ["view", "search"]:

        if not players:

            await interaction.response.send_message(
                "📭 Não existem Free Agents cadastrados.",
                ephemeral=True
            )

            return

        if acao.value == "search" and jogador:

            data = players.get(
                str(jogador.id)
            )

            if not data:

                await interaction.response.send_message(
                    "❌ Jogador não encontrado.",
                    ephemeral=True
                )

                return

            embed = discord.Embed(
                title="🆓 FREE AGENT",
                description=(
                    f"**Jogador:** {data['mention']}\n"
                    f"**Position:** `{data['position']}`\n\n"
                    f"**Descrição:** {data['description']}"
                ),
                color=discord.Color.blue()
            )

            embed.set_footer(
                text=f"Cadastro: {data['date']}"
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title="🆓 FREE AGENTS DA BRS",
            color=discord.Color.blue()
        )

        for data in list(players.values())[:25]:

            embed.add_field(
                name=data["name"],
                value=(
                    f"**Position:** `{data['position']}`\n"
                    f"{data['description']}"
                ),
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ============================================================
# SCOUTING
# ============================================================

@bot.tree.command(
    name="scouting",
    description="Gerenciamento de Scouting.",
    guild=GUILD
)
@app_commands.describe(
    acao="Ação",
    jogador="Jogador",
    posicao="Position",
    descricao="Descrição",
    observacoes="Observações do Scout",
    status="Status"
)
@app_commands.choices(
    acao=[
        app_commands.Choice(
            name="Criar",
            value="add"
        ),
        app_commands.Choice(
            name="Remover",
            value="remove"
        ),
        app_commands.Choice(
            name="Visualizar",
            value="view"
        ),
        app_commands.Choice(
            name="Pesquisar",
            value="search"
        )
    ],
    status=[
        app_commands.Choice(
            name="Em avaliação",
            value="Em avaliação"
        ),
        app_commands.Choice(
            name="Aprovado",
            value="Aprovado"
        ),
        app_commands.Choice(
            name="Reprovado",
            value="Reprovado"
        ),
        app_commands.Choice(
            name="Observação",
            value="Observação"
        )
    ]
)
async def scouting_cmd(
    interaction: discord.Interaction,
    acao: app_commands.Choice[str],
    jogador: Optional[discord.Member] = None,
    posicao: Optional[str] = None,
    descricao: Optional[str] = None,
    observacoes: Optional[str] = None,
    status: Optional[app_commands.Choice[str]] = None
):

    if not await require_permission(
        interaction,
        "scouting"
    ):
        return

    players = CONFIG["scouting"]["players"]

    if acao.value == "add":

        if not jogador:

            await interaction.response.send_message(
                "❌ Informe o jogador.",
                ephemeral=True
            )

            return

        players[str(jogador.id)] = {

            "name": jogador.display_name,

            "mention": jogador.mention,

            "position": posicao or "N/A",

            "description": descricao or "N/A",

            "observations": observacoes or "N/A",

            "status": (
                status.value
                if status
                else "Em avaliação"
            ),

            "avatar": str(
                jogador.display_avatar.url
            ),

            "date": datetime.datetime.now().strftime(
                "%d/%m/%Y"
            )
        }

        save_config()

        embed = discord.Embed(
            title="🔍 SCOUTING REPORT",
            description=(
                f"**Jogador:** {jogador.mention}\n"
                f"**Position:** `{posicao or 'N/A'}`\n\n"
                f"**Descrição:** {descricao or 'N/A'}\n\n"
                f"**Observações:** {observacoes or 'N/A'}\n\n"
                f"**Status:** {status.value if status else 'Em avaliação'}"
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

    elif acao.value == "remove":

        if not jogador:

            await interaction.response.send_message(
                "❌ Informe o jogador.",
                ephemeral=True
            )

            return

        if str(jogador.id) not in players:

            await interaction.response.send_message(
                "❌ Scouting não encontrado.",
                ephemeral=True
            )

            return

        del players[str(jogador.id)]

        save_config()

        await interaction.response.send_message(
            "✅ Scouting removido.",
            ephemeral=True
        )

    elif acao.value in ["view", "search"]:

        if acao.value == "search" and jogador:

            data = players.get(
                str(jogador.id)
            )

            if not data:

                await interaction.response.send_message(
                    "❌ Jogador não encontrado.",
                    ephemeral=True
                )

                return

            embed = discord.Embed(
                title="🔍 SCOUTING REPORT",
                description=(
                    f"**Jogador:** {data['mention']}\n"
                    f"**Position:** `{data['position']}`\n\n"
                    f"**Descrição:** {data['description']}\n\n"
                    f"**Observações:** {data['observations']}\n\n"
                    f"**Status:** {data['status']}"
                ),
                color=discord.Color.orange()
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

            return

        if not players:

            await interaction.response.send_message(
                "📭 Nenhum scouting cadastrado.",
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title="🔍 SCOUTING BRS",
            color=discord.Color.orange()
        )

        for data in list(players.values())[:25]:

            embed.add_field(
                name=data["name"],
                value=(
                    f"**Position:** `{data['position']}`\n"
                    f"**Status:** {data['status']}"
                ),
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
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
    canal="Canal de destino"
)
async def say_cmd(
    interaction: discord.Interaction,
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


# ============================================================
# SAY EMBED
# ============================================================

@bot.tree.command(
    name="say_embed",
    description="Envia uma Embed através do bot.",
    guild=GUILD
)
@app_commands.describe(
    titulo="Título",
    descricao="Descrição",
    canal="Canal",
    footer="Footer",
    thumbnail="Thumbnail URL",
    imagem="Imagem URL",
    autor="Nome do autor"
)
async def say_embed_cmd(
    interaction: discord.Interaction,
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
        embed.set_footer(
            text=footer
        )

    if thumbnail:
        embed.set_thumbnail(
            url=thumbnail
        )

    if imagem:
        embed.set_image(
            url=imagem
        )

    if autor:
        embed.set_author(
            name=autor
        )

    await canal.send(
        embed=embed
    )

    await interaction.response.send_message(
        "✅ Embed enviada.",
        ephemeral=True
    )


# ============================================================
# ?CARGOID
# ============================================================

@bot.command(
    name="cargoid"
)
async def cargoid_cmd(
    ctx: commands.Context,
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
#
# SOMENTE ADMINISTRADORES PODEM USAR.
#
# ALÉM DISSO, O CARGO PRECISA ESTAR NA LISTA.
# ============================================================

SELF_ASSIGNABLE_ROLE_IDS = [

    # Coloque aqui os IDs dos cargos
    # que os administradores poderão
    # adicionar/remover.

    # 123456789012345678,
    # 987654321098765432,

]


@bot.command(
    name="role"
)
async def role_cmd(
    ctx: commands.Context,
    *,
    cargo: Optional[str] = None
):

    if not ctx.guild:

        return

    # Somente ADM+
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

    # Nunca @everyone
    if role.is_default():

        await ctx.reply(
            "❌ Esse cargo não pode ser utilizado.",
            mention_author=False
        )

        return

    # Cargo precisa estar autorizado
    if role.id not in SELF_ASSIGNABLE_ROLE_IDS:

        await ctx.reply(
            "🚫 Esse cargo não está liberado no sistema.",
            mention_author=False
        )

        return

    # Nunca cargo de administrador
    if role.permissions.administrator:

        await ctx.reply(
            "🚫 Cargos com permissão de Administrador não podem ser alterados por `?role`.",
            mention_author=False
        )

        return

    # Hierarquia
    if role >= ctx.guild.me.top_role:

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
# COMANDO: LIMPAR
# ============================================================

@bot.tree.command(
    name="clear",
    description="Apaga mensagens do canal.",
    guild=GUILD
)
@app_commands.describe(
    quantidade="Quantidade de mensagens"
)
async def clear_cmd(
    interaction: discord.Interaction,
    quantidade: int
):

    if not await require_permission(
        interaction,
        "say"
    ):
        return

    if quantidade < 1 or quantidade > 100:

        await interaction.response.send_message(
            "❌ Escolha entre 1 e 100 mensagens.",
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
# COMANDO: STATUS
# ============================================================

@bot.tree.command(
    name="status",
    description="Mostra o status do bot.",
    guild=GUILD
)
async def status_cmd(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🇧🇷 BRS SYSTEM",
        description="Bot operacional.",
        color=discord.Color.green()
    )

    embed.add_field(
        name="🤖 Bot",
        value="Online",
        inline=True
    )

    embed.add_field(
        name="📡 Latência",
        value=f"{round(bot.latency * 1000)}ms",
        inline=True
    )

    embed.add_field(
        name="🎁 Drops ativos",
        value=str(len(bot.active_drops)),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# ERROS SLASH
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    log.exception(
        "Erro em slash command",
        exc_info=error
    )

    message = (
        "❌ Ocorreu um erro ao executar o comando."
    )

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

    bot.run(
        TOKEN
        )
