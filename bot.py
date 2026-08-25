import os
import sqlite3
import asyncio
import datetime
import logging
import unicodedata
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURAÇÕES
# ============================================================

GUILD_ID = 1540722239027023882
GUILD = discord.Object(id=GUILD_ID)

DB_FILE = "brs.db"

EMBED_COLOR = 0x2B2D31

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("BRS")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


# ============================================================
# BANCO DE DADOS
# ============================================================

db = sqlite3.connect(DB_FILE)
db.row_factory = sqlite3.Row


def init_db():
    cur = db.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            guild_id INTEGER PRIMARY KEY,
            staff_roles TEXT DEFAULT '',
            ticket_category INTEGER,
            ticket_log_channel INTEGER,
            ticket_name TEXT DEFAULT 'ticket-{user}',
            ticket_message TEXT DEFAULT 'Olá {user}! Descreva o motivo do seu atendimento.',
            drop_channel INTEGER,
            freeagent_channel INTEGER,
            scouting_channel INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS command_permissions (
            guild_id INTEGER,
            command_name TEXT,
            roles TEXT DEFAULT '',
            PRIMARY KEY (guild_id, command_name)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS freeagents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            player_id INTEGER,
            position TEXT,
            description TEXT,
            image TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS scouting (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            player_id INTEGER,
            position TEXT,
            description TEXT,
            observations TEXT,
            status TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS drops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            channel_id INTEGER,
            question TEXT,
            answer TEXT,
            active INTEGER DEFAULT 1,
            winner_id INTEGER,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS drop_rewards (
            drop_id INTEGER,
            role_id INTEGER,
            winner_id INTEGER,
            claimed INTEGER DEFAULT 0,
            PRIMARY KEY(drop_id, role_id)
        )
    """)

    cur.execute("""
        INSERT OR IGNORE INTO config
        (guild_id)
        VALUES (?)
    """, (GUILD_ID,))

    db.commit()


init_db()


# ============================================================
# UTILIDADES
# ============================================================

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def get_config():
    return db.execute(
        "SELECT * FROM config WHERE guild_id = ?",
        (GUILD_ID,)
    ).fetchone()


def parse_ids(value):
    if not value:
        return []

    result = []

    for x in value.split(","):
        x = x.strip()

        if x.isdigit():
            result.append(int(x))

    return result


def role_ids_string(ids):
    return ",".join(str(x) for x in ids)


def normalize(text):
    return unicodedata.normalize(
        "NFKD",
        text
    ).encode(
        "ascii",
        "ignore"
    ).decode().lower().strip()


def is_admin(interaction):
    return (
        interaction.user.guild_permissions.administrator
        if interaction.guild
        else False
    )


async def has_command_permission(
    interaction: discord.Interaction,
    command_name: str
):
    if is_admin(interaction):
        return True

    row = db.execute(
        """
        SELECT roles
        FROM command_permissions
        WHERE guild_id = ? AND command_name = ?
        """,
        (GUILD_ID, command_name)
    ).fetchone()

    if not row:
        return False

    allowed_roles = parse_ids(row["roles"])

    if not allowed_roles:
        return False

    return any(
        role.id in allowed_roles
        for role in interaction.user.roles
    )


async def permission_error(interaction):
    await interaction.response.send_message(
        "❌ Você não possui permissão para utilizar este comando.",
        ephemeral=True
    )


async def log_action(guild, message):
    config = get_config()

    channel_id = config["ticket_log_channel"]

    if not channel_id:
        return

    channel = guild.get_channel(channel_id)

    if channel:
        try:
            await channel.send(message)
        except discord.HTTPException:
            pass


# ============================================================
# BOT
# ============================================================

class BRSBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="?",
            intents=intents
        )

    async def setup_hook(self):

        await self.tree.sync(guild=GUILD)

        # Views persistentes
        self.add_view(TicketPanelView())

        # Recarrega recompensas de Drops pendentes
        rows = db.execute("""
            SELECT DISTINCT drop_id, winner_id
            FROM drop_rewards
            WHERE claimed = 0
        """).fetchall()

        for row in rows:
            self.add_view(
                DropRewardView(
                    row["drop_id"],
                    row["winner_id"]
                )
            )

        log.info("Comandos BRS sincronizados.")

    async def close(self):
        await super().close()


bot = BRSBot()


@bot.event
async def on_ready():

    log.info(
        "BRS conectada como %s (%s)",
        bot.user,
        bot.user.id
    )


# ============================================================
# TICKETS
# ============================================================

def ticket_channel(channel):

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
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        guild = interaction.guild
        config = get_config()

        existing = discord.utils.find(
            lambda c:
                ticket_channel(c)
                and str(interaction.user.id) in c.name,
            guild.text_channels
        )

        if existing:
            await interaction.response.send_message(
                f"❌ Você já possui um ticket aberto: {existing.mention}",
                ephemeral=True
            )
            return

        staff_roles = parse_ids(config["staff_roles"])

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
                    manage_channels=True
                )
        }

        for role_id in staff_roles:

            role = guild.get_role(role_id)

            if role:

                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        category = None

        if config["ticket_category"]:
            category = guild.get_channel(
                config["ticket_category"]
            )

        channel_name = config["ticket_name"]

        channel_name = channel_name.replace(
            "{user}",
            interaction.user.name
        )

        channel_name = channel_name.replace(
            "{id}",
            str(interaction.user.id)
        )

        channel_name = channel_name.lower()[:90]

        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites,
            reason="BRS Ticket"
        )

        message = config["ticket_message"]

        message = message.replace(
            "{user}",
            interaction.user.mention
        )

        embed = discord.Embed(
            title="🎫 Atendimento BRS",
            description=message,
            color=EMBED_COLOR,
            timestamp=datetime.datetime.now()
        )

        embed.set_footer(
            text=f"Ticket aberto por {interaction.user}"
        )

        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ Ticket criado: {channel.mention}",
            ephemeral=True
        )

        await log_action(
            guild,
            f"🎫 Ticket aberto por {interaction.user.mention}: {channel.mention}"
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
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not ticket_channel(interaction.channel):

            await interaction.response.send_message(
                "❌ Este botão só funciona em tickets.",
                ephemeral=True
            )
            return

        config = get_config()

        await interaction.response.send_message(
            "🔒 Ticket encerrado.",
            ephemeral=True
        )

        # Remove acesso de membros que não sejam Staff
        overwrites = interaction.channel.overwrites

        for target in list(overwrites):

            if isinstance(target, discord.Member):

                if target.id != interaction.guild.me.id:

                    await interaction.channel.set_permissions(
                        target,
                        overwrite=discord.PermissionOverwrite(
                            view_channel=False
                        )
                    )

        await interaction.channel.send(
            f"🔒 Ticket encerrado por {interaction.user.mention}."
        )

        await log_action(
            interaction.guild,
            f"🔒 Ticket fechado por {interaction.user.mention}: "
            f"{interaction.channel.name}"
        )

        await asyncio.sleep(3)

        try:
            await interaction.channel.delete(
                reason="Ticket BRS fechado"
            )
        except discord.HTTPException:
            pass


# ============================================================
# /ticket
# ============================================================

@bot.tree.command(
    name="ticket",
    description="Configura o painel de tickets da BRS.",
    guild=GUILD
)
@app_commands.describe(
    categoria="Categoria onde os tickets serão criados",
    mensagem="Mensagem inicial dos tickets",
    nome="Nome do canal. Use {user} ou {id}",
    logs="Canal de logs"
)
async def ticket_cmd(
    interaction: discord.Interaction,
    categoria: Optional[discord.CategoryChannel] = None,
    mensagem: Optional[str] = None,
    nome: Optional[str] = None,
    logs: Optional[discord.TextChannel] = None
):

    if not is_admin(interaction):

        await permission_error(interaction)
        return

    config = get_config()

    category_id = (
        categoria.id
        if categoria
        else config["ticket_category"]
    )

    log_id = (
        logs.id
        if logs
        else config["ticket_log_channel"]
    )

    ticket_name = (
        nome
        if nome
        else config["ticket_name"]
    )

    ticket_message = (
        mensagem
        if mensagem
        else config["ticket_message"]
    )

    db.execute("""
        UPDATE config
        SET ticket_category = ?,
            ticket_log_channel = ?,
            ticket_name = ?,
            ticket_message = ?
        WHERE guild_id = ?
    """, (
        category_id,
        log_id,
        ticket_name,
        ticket_message,
        GUILD_ID
    ))

    db.commit()

    embed = discord.Embed(
        title="🎫 CENTRAL DE ATENDIMENTO",
        description=(
            "Precisa de ajuda com a BRS?\n\n"
            "Clique no botão abaixo para abrir um ticket privado "
            "com a Staff."
        ),
        color=EMBED_COLOR
    )

    await interaction.channel.send(
        embed=embed,
        view=TicketPanelView()
    )

    await interaction.response.send_message(
        "✅ Painel de tickets configurado e enviado.",
        ephemeral=True
    )


# ============================================================
# /CONFIG STAFF
# ============================================================

@bot.tree.command(
    name="config_staff",
    description="Configura os cargos de Staff.",
    guild=GUILD
)
@app_commands.describe(
    cargos="Mencione os cargos separados por espaço"
)
async def config_staff(
    interaction: discord.Interaction,
    cargos: str
):

    if not is_admin(interaction):

        await permission_error(interaction)
        return

    import re

    ids = [
        int(x)
        for x in re.findall(r"<@&(\d+)>", cargos)
    ]

    if not ids:

        await interaction.response.send_message(
            "❌ Nenhum cargo válido encontrado.",
            ephemeral=True
        )
        return

    db.execute("""
        UPDATE config
        SET staff_roles = ?
        WHERE guild_id = ?
    """, (
        role_ids_string(ids),
        GUILD_ID
    ))

    db.commit()

    await interaction.response.send_message(
        "✅ Cargos de Staff configurados.",
        ephemeral=True
    )


# ============================================================
# PERMISSÕES
# ============================================================

@bot.tree.command(
    name="permissao",
    description="Define quais cargos podem usar um comando.",
    guild=GUILD
)
@app_commands.describe(
    comando="Nome do comando",
    cargos="Cargos autorizados"
)
async def permissao_cmd(
    interaction: discord.Interaction,
    comando: str,
    cargos: str
):

    if not is_admin(interaction):

        await permission_error(interaction)
        return

    import re

    ids = [
        int(x)
        for x in re.findall(r"<@&(\d+)>", cargos)
    ]

    db.execute("""
        INSERT INTO command_permissions
        (guild_id, command_name, roles)
        VALUES (?, ?, ?)

        ON CONFLICT(guild_id, command_name)
        DO UPDATE SET roles = excluded.roles
    """, (
        GUILD_ID,
        comando.lower().replace("/", ""),
        role_ids_string(ids)
    ))

    db.commit()

    await interaction.response.send_message(
        f"✅ Permissões de `/{comando}` atualizadas.",
        ephemeral=True
    )


# ============================================================
# /SAY
# ============================================================

@bot.tree.command(
    name="say",
    description="Envia uma mensagem pela BRS.",
    guild=GUILD
)
@app_commands.describe(
    mensagem="Mensagem"
)
async def say_cmd(
    interaction: discord.Interaction,
    mensagem: str
):

    if not await has_command_permission(
        interaction,
        "say"
    ):

        await permission_error(interaction)
        return

    await interaction.channel.send(
        mensagem.replace("\\n", "\n")
    )

    await interaction.response.send_message(
        "✅ Mensagem enviada.",
        ephemeral=True
    )


# ============================================================
# /SAY EMBED
# ============================================================

@bot.tree.command(
    name="say_embed",
    description="Envia uma Embed pela BRS.",
    guild=GUILD
)
@app_commands.describe(
    titulo="Título",
    descricao="Descrição",
    footer="Footer",
    thumbnail="URL da thumbnail",
    imagem="URL da imagem",
    autor="Nome do autor",
    canal="Canal"
)
async def say_embed_cmd(
    interaction: discord.Interaction,
    titulo: str,
    descricao: str,
    footer: Optional[str] = None,
    thumbnail: Optional[str] = None,
    imagem: Optional[str] = None,
    autor: Optional[str] = None,
    canal: Optional[discord.TextChannel] = None
):

    if not await has_command_permission(
        interaction,
        "say_embed"
    ):

        await permission_error(interaction)
        return

    canal = canal or interaction.channel

    embed = discord.Embed(
        title=titulo,
        description=descricao.replace(
            "\\n",
            "\n"
        ),
        color=EMBED_COLOR
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

    await canal.send(embed=embed)

    await interaction.response.send_message(
        "✅ Embed enviada.",
        ephemeral=True
    )


# ============================================================
# FREE AGENTS
# ============================================================

@bot.tree.command(
    name="freeagent",
    description="Gerencia Free Agents.",
    guild=GUILD
)
@app_commands.describe(
    acao="Ação",
    jogador="Jogador",
    posicao="Position",
    descricao="Descrição",
    imagem="URL da imagem",
    pesquisa="Nome para pesquisar"
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
    descricao: Optional[str] = None,
    imagem: Optional[str] = None,
    pesquisa: Optional[str] = None
):

    if not await has_command_permission(
        interaction,
        "freeagent"
    ):

        await permission_error(interaction)
        return

    action = acao.value

    if action == "add":

        if not jogador or not posicao or not descricao:

            await interaction.response.send_message(
                "❌ Informe jogador, posição e descrição.",
                ephemeral=True
            )
            return

        db.execute("""
            INSERT INTO freeagents
            (guild_id, player_id, position, description, image, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            GUILD_ID,
            jogador.id,
            posicao,
            descricao,
            imagem,
            now()
        ))

        db.commit()

        embed = discord.Embed(
            title="🆓 FREE AGENT",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Jogador",
            value=jogador.mention,
            inline=False
        )

        embed.add_field(
            name="Position",
            value=posicao,
            inline=True
        )

        embed.add_field(
            name="Descrição",
            value=descricao,
            inline=False
        )

        embed.add_field(
            name="Data",
            value=datetime.datetime.now().strftime(
                "%d/%m/%Y"
            ),
            inline=True
        )

        if imagem:
            embed.set_thumbnail(
                url=imagem
            )

        config = get_config()

        channel = (
            interaction.guild.get_channel(
                config["freeagent_channel"]
            )
            if config["freeagent_channel"]
            else interaction.channel
        )

        await channel.send(embed=embed)

        await interaction.response.send_message(
            "✅ Free Agent cadastrado.",
            ephemeral=True
        )

    elif action == "remove":

        if not jogador:

            await interaction.response.send_message(
                "❌ Informe o jogador.",
                ephemeral=True
            )
            return

        db.execute("""
            DELETE FROM freeagents
            WHERE guild_id = ? AND player_id = ?
        """, (
            GUILD_ID,
            jogador.id
        ))

        db.commit()

        await interaction.response.send_message(
            "✅ Free Agent removido.",
            ephemeral=True
        )

    elif action in ("view", "search"):

        if action == "search" and not pesquisa:

            await interaction.response.send_message(
                "❌ Informe o nome para pesquisar.",
                ephemeral=True
            )
            return

        rows = db.execute("""
            SELECT *
            FROM freeagents
            WHERE guild_id = ?
            ORDER BY id DESC
        """, (GUILD_ID,)).fetchall()

        if pesquisa:

            rows = [
                row for row in rows
                if pesquisa.lower()
                in str(row["player_id"]).lower()
            ]

        if not rows:

            await interaction.response.send_message(
                "❌ Nenhum Free Agent encontrado.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🆓 FREE AGENTS — BRS",
            color=discord.Color.blue()
        )

        for row in rows[:10]:

            member = interaction.guild.get_member(
                row["player_id"]
            )

            name = (
                member.mention
                if member
                else f"<@{row['player_id']}>"
            )

            embed.add_field(
                name=f"{name} • {row['position']}",
                value=row["description"],
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
    description="Gerencia relatórios de Scouting.",
    guild=GUILD
)
@app_commands.describe(
    acao="Ação",
    jogador="Jogador",
    posicao="Position",
    descricao="Descrição",
    observacoes="Observações",
    status="Status",
    pesquisa="Pesquisa"
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
            name="Alterar Status",
            value="status"
        ),
        app_commands.Choice(
            name="Pesquisar",
            value="search"
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
    status: Optional[str] = None,
    pesquisa: Optional[str] = None
):

    if not await has_command_permission(
        interaction,
        "scouting"
    ):

        await permission_error(interaction)
        return

    action = acao.value

    if action == "add":

        if not all([
            jogador,
            posicao,
            descricao,
            observacoes,
            status
        ]):

            await interaction.response.send_message(
                "❌ Preencha jogador, posição, descrição, observações e status.",
                ephemeral=True
            )
            return

        db.execute("""
            INSERT INTO scouting
            (guild_id, player_id, position, description,
             observations, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            GUILD_ID,
            jogador.id,
            posicao,
            descricao,
            observacoes,
            status,
            now()
        ))

        db.commit()

        embed = discord.Embed(
            title="🔎 SCOUTING REPORT",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Jogador",
            value=jogador.mention,
            inline=False
        )

        embed.add_field(
            name="Position",
            value=posicao,
            inline=True
        )

        embed.add_field(
            name="Descrição",
            value=descricao,
            inline=False
        )

        embed.add_field(
            name="Observações",
            value=observacoes,
            inline=False
        )

        embed.add_field(
            name="Status",
            value=status,
            inline=True
        )

        config = get_config()

        channel = (
            interaction.guild.get_channel(
                config["scouting_channel"]
            )
            if config["scouting_channel"]
            else interaction.channel
        )

        await channel.send(embed=embed)

        await interaction.response.send_message(
            "✅ Scouting criado.",
            ephemeral=True
        )

    elif action == "remove":

        if not jogador:

            await interaction.response.send_message(
                "❌ Informe o jogador.",
                ephemeral=True
            )
            return

        db.execute("""
            DELETE FROM scouting
            WHERE guild_id = ? AND player_id = ?
        """, (
            GUILD_ID,
            jogador.id
        ))

        db.commit()

        await interaction.response.send_message(
            "✅ Scouting removido.",
            ephemeral=True
        )

    elif action == "status":

        if not jogador or not status:

            await interaction.response.send_message(
                "❌ Informe jogador e novo status.",
                ephemeral=True
            )
            return

        db.execute("""
            UPDATE scouting
            SET status = ?
            WHERE guild_id = ? AND player_id = ?
        """, (
            status,
            GUILD_ID,
            jogador.id
        ))

        db.commit()

        await interaction.response.send_message(
            "✅ Status atualizado.",
            ephemeral=True
        )

    else:

        rows = db.execute("""
            SELECT *
            FROM scouting
            WHERE guild_id = ?
            ORDER BY id DESC
        """, (GUILD_ID,)).fetchall()

        if pesquisa:

            pesquisa = normalize(pesquisa)

            filtered = []

            for row in rows:

                member = interaction.guild.get_member(
                    row["player_id"]
                )

                if member and pesquisa in normalize(
                    member.display_name
                ):
                    filtered.append(row)

            rows = filtered

        if not rows:

            await interaction.response.send_message(
                "❌ Nenhum scouting encontrado.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🔎 SCOUTING REPORTS — BRS",
            color=discord.Color.orange()
        )

        for row in rows[:10]:

            member = interaction.guild.get_member(
                row["player_id"]
            )

            name = (
                member.mention
                if member
                else f"<@{row['player_id']}>"
            )

            embed.add_field(
                name=f"{name} • {row['position']}",
                value=(
                    f"**Descrição:** {row['description']}\n"
                    f"**Observações:** {row['observations']}\n"
                    f"**Status:** {row['status']}"
                ),
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ============================================================
# DROP
# ============================================================

active_drop = {}


class DropRewardView(discord.ui.View):

    def __init__(
        self,
        drop_id,
        winner_id
    ):

        super().__init__(timeout=None)

        self.drop_id = drop_id
        self.winner_id = winner_id

        rewards = db.execute("""
            SELECT role_id
            FROM drop_rewards
            WHERE drop_id = ?
            AND claimed = 0
        """, (drop_id,)).fetchall()

        for reward in rewards:

            role = discord.utils.get(
                bot.get_guild(GUILD_ID).roles,
                id=reward["role_id"]
            )

            if role:

                button = discord.ui.Button(
                    label=role.name[:80],
                    style=discord.ButtonStyle.blurple,
                    custom_id=f"brs_reward_{drop_id}_{role.id}"
                )

                async def callback(
                    interaction,
                    role_id=role.id
                ):

                    await self.claim(
                        interaction,
                        role_id
                    )

                button.callback = callback

                self.add_item(button)

    async def claim(
        self,
        interaction,
        role_id
    ):

        if interaction.user.id != self.winner_id:

            await interaction.response.send_message(
                "❌ Essa recompensa não é sua.",
                ephemeral=True
            )
            return

        row = db.execute("""
            SELECT claimed
            FROM drop_rewards
            WHERE drop_id = ?
            AND role_id = ?
        """, (
            self.drop_id,
            role_id
        )).fetchone()

        if not row or row["claimed"]:

            await interaction.response.send_message(
                "❌ Essa recompensa já foi utilizada.",
                ephemeral=True
            )
            return

        role = interaction.guild.get_role(
            role_id
        )

        if not role:

            await interaction.response.send_message(
                "❌ Cargo não encontrado.",
                ephemeral=True
            )
            return

        await interaction.user.add_roles(
            role,
            reason="BRS Drop Reward"
        )

        db.execute("""
            UPDATE drop_rewards
            SET claimed = 1
            WHERE drop_id = ?
            AND winner_id = ?
        """, (
            self.drop_id,
            self.winner_id
        ))

        db.commit()

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=(
                f"🏆 Você escolheu **{role.name}**!\n"
                "O cargo foi atribuído com sucesso."
            ),
            view=self
        )

        self.stop()


@bot.tree.command(
    name="drop",
    description="Cria ou cancela um Drop.",
    guild=GUILD
)
@app_commands.describe(
    acao="Ação",
    pergunta="Pergunta do Drop",
    resposta="Resposta correta",
    premios="IDs dos cargos separados por vírgula",
    canal="Canal do Drop"
)
@app_commands.choices(
    acao=[
        app_commands.Choice(
            name="Criar",
            value="create"
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
    resposta: Optional[str] = None,
    premios: Optional[str] = None,
    canal: Optional[discord.TextChannel] = None
):

    if not await has_command_permission(
        interaction,
        "drop"
    ):

        await permission_error(interaction)
        return

    action = acao.value

    if action == "cancel":

        row = db.execute("""
            SELECT id
            FROM drops
            WHERE guild_id = ?
            AND active = 1
            ORDER BY id DESC
            LIMIT 1
        """, (GUILD_ID,)).fetchone()

        if not row:

            await interaction.response.send_message(
                "❌ Não existe Drop ativo.",
                ephemeral=True
            )
            return

        db.execute("""
            UPDATE drops
            SET active = 0
            WHERE id = ?
        """, (row["id"],))

        db.commit()

        active_drop.pop(
            interaction.guild.id,
            None
        )

        await interaction.response.send_message(
            "🛑 Drop cancelado.",
            ephemeral=True
        )

        return

    if not pergunta or not resposta:

        await interaction.response.send_message(
            "❌ Informe pergunta e resposta.",
            ephemeral=True
        )
        return

    if active_drop.get(interaction.guild.id):

        await interaction.response.send_message(
            "❌ Já existe um Drop ativo.",
            ephemeral=True
        )
        return

    config = get_config()

    canal = (
        canal
        or interaction.guild.get_channel(
            config["drop_channel"]
        )
        or interaction.channel
    )

    db.execute("""
        INSERT INTO drops
        (guild_id, channel_id, question, answer, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        GUILD_ID,
        canal.id,
        pergunta,
        resposta,
        now()
    ))

    db.commit()

    drop_id = db.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    reward_ids = parse_ids(
        premios or ""
    )

    for role_id in reward_ids:

        db.execute("""
            INSERT OR IGNORE INTO drop_rewards
            (drop_id, role_id, winner_id)
            VALUES (?, ?, 0)
        """, (
            drop_id,
            role_id
        ))

    db.commit()

    active_drop[interaction.guild.id] = {
        "id": drop_id,
        "answer": normalize(resposta),
        "channel": canal.id
    }

    embed = discord.Embed(
        title="🎁 BRS DROP",
        description=(
            f"## {pergunta}\n\n"
            "💬 Envie sua resposta no chat.\n"
            "🏆 O primeiro jogador a acertar vence!"
        ),
        color=discord.Color.gold()
    )

    await canal.send(embed=embed)

    await interaction.response.send_message(
        "✅ Drop iniciado.",
        ephemeral=True
    )

    def check(message):

        return (
            message.channel.id == canal.id
            and not message.author.bot
            and normalize(message.content)
            == normalize(resposta)
        )

    try:

        winner = await bot.wait_for(
            "message",
            timeout=60,
            check=check
        )

    except asyncio.TimeoutError:

        db.execute("""
            UPDATE drops
            SET active = 0
            WHERE id = ?
        """, (drop_id,))

        db.commit()

        active_drop.pop(
            interaction.guild.id,
            None
        )

        await canal.send(
            f"⏰ Tempo esgotado!\n"
            f"A resposta era **{resposta}**."
        )

        return

    # Impede segunda premiação
    db.execute("""
        UPDATE drops
        SET active = 0,
            winner_id = ?
        WHERE id = ?
    """, (
        winner.author.id,
        drop_id
    ))

    db.execute("""
        UPDATE drop_rewards
        SET winner_id = ?
        WHERE drop_id = ?
    """, (
        winner.author.id,
        drop_id
    ))

    db.commit()

    active_drop.pop(
        interaction.guild.id,
        None
    )

    await canal.send(
        f"🏆 {winner.author.mention} venceu o Drop!"
    )

    # DM
    try:

        rows = db.execute("""
            SELECT role_id
            FROM drop_rewards
            WHERE drop_id = ?
            AND claimed = 0
        """, (drop_id,)).fetchall()

        if not rows:

            await winner.author.send(
                "🏆 Você venceu o Drop da BRS!"
            )

        else:

            embed = discord.Embed(
                title="🏆 VOCÊ VENCEU!",
                description=(
                    "Parabéns! Você foi o primeiro a acertar "
                    "o Drop da BRS.\n\n"
                    "Escolha sua recompensa abaixo:"
                ),
                color=discord.Color.gold()
            )

            await winner.author.send(
                embed=embed,
                view=DropRewardView(
                    drop_id,
                    winner.author.id
                )
            )

    except discord.Forbidden:

        await canal.send(
            f"⚠️ {winner.author.mention}, "
            "não consegui enviar sua recompensa por DM."
        )


# ============================================================
# CONFIGURAÇÃO DE CANAIS
# ============================================================

@bot.tree.command(
    name="config_canais",
    description="Configura os canais da BRS.",
    guild=GUILD
)
@app_commands.describe(
    drop="Canal padrão de Drops",
    freeagent="Canal de Free Agents",
    scouting="Canal de Scouting"
)
async def config_canais(
    interaction: discord.Interaction,
    drop: Optional[discord.TextChannel] = None,
    freeagent: Optional[discord.TextChannel] = None,
    scouting: Optional[discord.TextChannel] = None
):

    if not is_admin(interaction):

        await permission_error(interaction)
        return

    config = get_config()

    db.execute("""
        UPDATE config
        SET drop_channel = ?,
            freeagent_channel = ?,
            scouting_channel = ?
        WHERE guild_id = ?
    """, (
        drop.id if drop else config["drop_channel"],
        freeagent.id if freeagent else config["freeagent_channel"],
        scouting.id if scouting else config["scouting_channel"],
        GUILD_ID
    ))

    db.commit()

    await interaction.response.send_message(
        "✅ Canais configurados.",
        ephemeral=True
    )


# ============================================================
# CONFIG PRÊMIOS
# ============================================================

@bot.tree.command(
    name="config",
    description="Mostra as configurações da BRS.",
    guild=GUILD
)
async def config_cmd(
    interaction: discord.Interaction
):

    if not is_admin(interaction):

        await permission_error(interaction)
        return

    config = get_config()

    staff = parse_ids(
        config["staff_roles"]
    )

    staff_text = (
        "\n".join(
            f"<@&{x}>"
            for x in staff
        )
        if staff
        else "Nenhum"
    )

    embed = discord.Embed(
        title="⚙️ CONFIGURAÇÕES — BRS",
        color=EMBED_COLOR
    )

    embed.add_field(
        name="👮 Staff",
        value=staff_text,
        inline=False
    )

    embed.add_field(
        name="🎫 Categoria",
        value=(
            f"<#{config['ticket_category']}>"
            if config["ticket_category"]
            else "Não configurada"
        ),
        inline=True
    )

    embed.add_field(
        name="📝 Logs",
        value=(
            f"<#{config['ticket_log_channel']}>"
            if config["ticket_log_channel"]
            else "Não configurado"
        ),
        inline=True
    )

    embed.add_field(
        name="🎁 Drop",
        value=(
            f"<#{config['drop_channel']}>"
            if config["drop_channel"]
            else "Não configurado"
        ),
        inline=True
    )

    embed.add_field(
        name="🆓 Free Agent",
        value=(
            f"<#{config['freeagent_channel']}>"
            if config["freeagent_channel"]
            else "Não configurado"
        ),
        inline=True
    )

    embed.add_field(
        name="🔎 Scouting",
        value=(
            f"<#{config['scouting_channel']}>"
            if config["scouting_channel"]
            else "Não configurado"
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# COMANDO ?cargoid
# ============================================================

@bot.command(name="cargoid")
async def cargoid(
    ctx,
    *,
    cargo: Optional[str] = None
):

    if not cargo:

        await ctx.send(
            "❌ Use: `?cargoid Nome do cargo`"
        )
        return

    role = discord.utils.find(
        lambda r:
            r.name.lower() == cargo.lower(),
        ctx.guild.roles
    )

    if not role:

        await ctx.send(
            "❌ Cargo não encontrado."
        )
        return

    await ctx.send(
        f"🆔 ID de **{role.name}**: `{role.id}`"
    )


# ============================================================
# ERROS
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    log.error(
        "Erro em comando: %s",
        error
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
# INICIAR
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
