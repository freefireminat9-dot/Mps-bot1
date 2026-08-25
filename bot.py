"""
Bot Discord para liga de MPS (Modified Professional Soccer / Ro-Soccer)

Comandos slash (/):
  /say            - envia uma mensagem de texto pelo bot
  /say_embed      - envia uma mensagem em embed pelo bot
  /freeagent      - anuncia um jogador como free agent
  /scouting       - anuncia que um time está procurando jogadores
  /contract       - anuncia a assinatura de contrato de um jogador
  /release        - anuncia a liberação/dispensa de um jogador (pelo time)
  /drop           - jogo: adivinhe o país pela bandeira parcialmente revelada
  /elenco         - mostra o elenco de um time (baseado em cargo)
  /friendly       - anuncia/agenda um amistoso entre dois times
  /setup          - cria o painel de abertura de tickets
  /add            - adiciona membro/cargo a um ticket
  /remove         - remove membro/cargo de um ticket

Comando de prefixo (?):
  ?role <cargo>   - o próprio membro adiciona/remove um cargo autoatribuível

Todas as respostas de interação (slash commands) são ephemeral (visíveis
apenas para quem usou o comando). Comandos de anúncio (freeagent, scouting,
contract, release, friendly, say, say_embed) publicam o conteúdo no canal
normalmente (para a liga ver), mas a confirmação do comando em si só aparece
para quem executou.
"""

import os
import io
import random
import asyncio
import datetime
import logging
import unicodedata
from typing import Optional, Union

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# ============================================================
#  CONFIGURAÇÕES — edite conforme a sua liga
# ============================================================
GUILD_ID = 1540722239027023882
GUILD = discord.Object(id=GUILD_ID)

# ID da categoria onde os canais de ticket serão criados (opcional).
# Deixe None para criar os tickets sem categoria.
TICKET_CATEGORY_ID: Optional[int] = None

# ID do cargo de staff que deve enxergar TODOS os tickets automaticamente
# (opcional). Deixe None se não quiser isso.
TICKET_STAFF_ROLE_ID: Optional[int] = None

# Cor padrão usada nos embeds quando nenhuma cor é especificada.
EMBED_COLOR = 0x2B2D31

# --- /drop (jogo de bandeiras) ---
DROP_TIME_LIMIT = 60          # segundos que os membros têm para responder
DROP_ROLE_DURATION_DAYS = 7   # dias que a recompensa (cargo) dura

# IDs dos cargos de recompensa temporária do /drop (edite com os IDs reais).
# Deixe None em qualquer um deles se ainda não quiser liberar aquela opção.
SCRIM_HOSTER_ROLE_ID: Optional[int] = 1541065148590989332
PIC_PERM_ROLE_ID: Optional[int] = 1541600835472072724
SCOUTING_ROLE_ID: Optional[int] = 1541600905298714664

# --- ?role (auto-atribuição de cargo) ---
# Nomes exatos dos cargos que os membros podem pegar/tirar sozinhos com
# "?role NomeDoCargo". Deixe a lista vazia para permitir QUALQUER cargo por
# nome (não recomendado, pois isso incluiria cargos de staff/admin).
SELF_ASSIGNABLE_ROLES: list[str] = []
# ============================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mps-bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class MPSBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="?", intents=intents)
        self.http_session: Optional[aiohttp.ClientSession] = None

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()

        # Views persistentes (os botões continuam funcionando mesmo depois
        # de reiniciar o bot).
        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())

        # Sincroniza os slash commands apenas na guild da liga (fica
        # disponível instantaneamente, sem esperar a propagação global).
        synced = await self.tree.sync(guild=GUILD)
        log.info("Sincronizados %s comandos na guild %s", len(synced), GUILD_ID)

    async def close(self):
        if self.http_session:
            await self.http_session.close()
        await super().close()


bot = MPSBot()


@bot.event
async def on_ready():
    log.info("Bot conectado como %s (ID: %s)", bot.user, bot.user.id)


def guild_icon_url() -> Optional[str]:
    guild = bot.get_guild(GUILD_ID)
    if guild and guild.icon:
        return guild.icon.url
    return None


# ============================================================
#  SISTEMA DE TICKETS
# ============================================================

def is_ticket_channel(channel: discord.abc.GuildChannel) -> bool:
    return isinstance(channel, discord.TextChannel) and channel.name.startswith("ticket-")


class TicketPanelView(discord.ui.View):
    """View fixada na mensagem de abertura de tickets (/setup)."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Abrir Ticket",
        emoji="🎫",
        style=discord.ButtonStyle.green,
        custom_id="mps_open_ticket",
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        channel_name = f"ticket-{interaction.user.name}".lower().replace(" ", "-")[:90]

        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await interaction.response.send_message(
                f"❌ Você já possui um ticket aberto: {existing.mention}",
                ephemeral=True,
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
        }

        if TICKET_STAFF_ROLE_ID:
            staff_role = guild.get_role(TICKET_STAFF_ROLE_ID)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )

        category = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket aberto por {interaction.user} ({interaction.user.id})",
        )

        embed = discord.Embed(
            title="🎫 Ticket aberto",
            description=(
                f"Olá {interaction.user.mention}, seja bem-vindo(a)!\n\n"
                "Descreva o motivo do seu ticket e aguarde o atendimento da staff.\n"
                "Use o botão abaixo para fechar o ticket quando finalizado."
            ),
            color=EMBED_COLOR,
            timestamp=datetime.datetime.now(),
        )
        embed.set_footer(text=f"Aberto por {interaction.user}", icon_url=interaction.user.display_avatar.url)

        await ticket_channel.send(content=interaction.user.mention, embed=embed, view=TicketControlView())
        await interaction.response.send_message(
            f"✅ Ticket criado com sucesso: {ticket_channel.mention}", ephemeral=True
        )


class TicketControlView(discord.ui.View):
    """View fixada dentro de cada canal de ticket (botão de fechar)."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fechar Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="mps_close_ticket",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message(
                "❌ Este botão só funciona dentro de um canal de ticket.", ephemeral=True
            )
            return

        await interaction.response.send_message("🔒 Fechando o ticket em 5 segundos...", ephemeral=True)
        await interaction.channel.send(f"🔒 Ticket fechado por {interaction.user.mention}. Apagando em 5 segundos...")
        await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
        await interaction.channel.delete(reason=f"Ticket fechado por {interaction.user}")


@bot.tree.command(name="setup", description="Cria o painel de abertura de tickets no canal.", guild=GUILD)
@app_commands.describe(canal="Canal onde o painel será enviado (padrão: canal atual)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_cmd(interaction: discord.Interaction, canal: Optional[discord.TextChannel] = None):
    canal = canal or interaction.channel
    embed = discord.Embed(
        title="🎫 Central de Atendimento",
        description="Clique no botão abaixo para abrir um ticket com a nossa staff.",
        color=EMBED_COLOR,
    )
    await canal.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message(f"✅ Painel de tickets enviado em {canal.mention}.", ephemeral=True)


@bot.tree.command(name="add", description="Adiciona um membro ou cargo ao ticket atual.", guild=GUILD)
@app_commands.describe(alvo="Membro ou cargo a ser adicionado ao ticket")
async def add_cmd(interaction: discord.Interaction, alvo: Union[discord.Member, discord.Role]):
    if not is_ticket_channel(interaction.channel):
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado dentro de um canal de ticket.", ephemeral=True
        )
        return

    await interaction.channel.set_permissions(
        alvo, view_channel=True, send_messages=True, read_message_history=True
    )
    await interaction.response.send_message(f"✅ {alvo.mention} foi adicionado(a) ao ticket.", ephemeral=True)
    await interaction.channel.send(f"➕ {alvo.mention} foi adicionado(a) ao ticket por {interaction.user.mention}.")


@bot.tree.command(name="remove", description="Remove um membro ou cargo do ticket atual.", guild=GUILD)
@app_commands.describe(alvo="Membro ou cargo a ser removido do ticket")
async def remove_cmd(interaction: discord.Interaction, alvo: Union[discord.Member, discord.Role]):
    if not is_ticket_channel(interaction.channel):
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado dentro de um canal de ticket.", ephemeral=True
        )
        return

    await interaction.channel.set_permissions(alvo, overwrite=None)
    await interaction.response.send_message(f"✅ {alvo.mention} foi removido(a) do ticket.", ephemeral=True)
    await interaction.channel.send(f"➖ {alvo.mention} foi removido(a) do ticket por {interaction.user.mention}.")


# ============================================================
#  COMANDOS GERAIS (say / say_embed)
# ============================================================

@bot.tree.command(name="say", description="Envia uma mensagem de texto através do bot.", guild=GUILD)
@app_commands.describe(mensagem="Texto a ser enviado", canal="Canal de destino (padrão: canal atual)")
@app_commands.checks.has_permissions(manage_messages=True)
async def say_cmd(interaction: discord.Interaction, mensagem: str, canal: Optional[discord.TextChannel] = None):
    canal = canal or interaction.channel
    await canal.send(mensagem.replace("\\n", "\n"))
    await interaction.response.send_message(f"✅ Mensagem enviada em {canal.mention}.", ephemeral=True)


@bot.tree.command(name="say_embed", description="Envia uma mensagem em formato de embed através do bot.", guild=GUILD)
@app_commands.describe(
    titulo="Título do embed",
    descricao="Descrição do embed (use \\n para quebrar linha)",
    canal="Canal de destino (padrão: canal atual)",
    cor="Cor em hexadecimal, ex: #FF0000",
    imagem="URL de uma imagem grande",
    thumbnail="URL de uma imagem pequena (miniatura)",
    rodape="Texto do rodapé",
)
@app_commands.checks.has_permissions(manage_messages=True)
async def say_embed_cmd(
    interaction: discord.Interaction,
    titulo: str,
    descricao: str,
    canal: Optional[discord.TextChannel] = None,
    cor: Optional[str] = None,
    imagem: Optional[str] = None,
    thumbnail: Optional[str] = None,
    rodape: Optional[str] = None,
):
    canal = canal or interaction.channel

    if cor:
        try:
            color = discord.Color(int(cor.replace("#", ""), 16))
        except ValueError:
            await interaction.response.send_message(
                "❌ Cor inválida. Use um código hexadecimal, ex: #FF0000", ephemeral=True
            )
            return
    else:
        color = discord.Color(EMBED_COLOR)

    embed = discord.Embed(title=titulo, description=descricao.replace("\\n", "\n"), color=color)
    if imagem:
        embed.set_image(url=imagem)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if rodape:
        embed.set_footer(text=rodape)

    await canal.send(embed=embed)
    await interaction.response.send_message(f"✅ Embed enviado em {canal.mention}.", ephemeral=True)


# ============================================================
#  COMANDOS DA LIGA (mercado / elenco / amistosos)
# ============================================================

@bot.tree.command(name="freeagent", description="Anuncia um jogador como free agent (sem clube).", guild=GUILD)
@app_commands.describe(
    jogador="Jogador que está free agent",
    posicao="Posição do jogador (ex: ATA, MEI, ZAG, GOL)",
    plataforma="Plataforma (PC, Console, Mobile) (opcional)",
    observacoes="Observações adicionais (opcional)",
)
async def freeagent_cmd(
    interaction: discord.Interaction,
    jogador: discord.Member,
    posicao: str,
    plataforma: Optional[str] = None,
    observacoes: Optional[str] = None,
):
    embed = discord.Embed(
        title="🆓  FREE AGENT",
        description=f"### {jogador.mention} está disponível no mercado!",
        color=discord.Color.from_rgb(52, 152, 219),
        timestamp=datetime.datetime.now(),
    )
    embed.add_field(name="⚽ Posição", value=f"```{posicao}```", inline=True)
    if plataforma:
        embed.add_field(name="🖥️ Plataforma", value=f"```{plataforma}```", inline=True)
    if observacoes:
        embed.add_field(name="📝 Observações", value=observacoes, inline=False)
    embed.set_thumbnail(url=jogador.display_avatar.url)
    embed.set_author(name="Mercado da Liga", icon_url=guild_icon_url())
    embed.set_footer(text="📢 Interessados, entrem em contato!")

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Anúncio de free agent enviado.", ephemeral=True)


@bot.tree.command(name="scouting", description="Anuncia que um time está procurando jogadores.", guild=GUILD)
@app_commands.describe(
    time="Nome do time que está scoutando",
    posicao="Posição desejada",
    requisitos="Requisitos para o jogador (nível mínimo, disponibilidade, etc.)",
    contato="Pessoa responsável pelo contato (opcional)",
)
async def scouting_cmd(
    interaction: discord.Interaction,
    time: str,
    posicao: str,
    requisitos: Optional[str] = None,
    contato: Optional[discord.Member] = None,
):
    embed = discord.Embed(
        title="🔍  SCOUTING",
        description=f"### O time **{time}** está em busca de novos talentos!",
        color=discord.Color.from_rgb(241, 196, 15),
        timestamp=datetime.datetime.now(),
    )
    embed.add_field(name="⚽ Posição desejada", value=f"```{posicao}```", inline=True)
    if contato:
        embed.add_field(name="📞 Contato", value=contato.mention, inline=True)
    if requisitos:
        embed.add_field(name="📋 Requisitos", value=requisitos, inline=False)
    embed.set_author(name="Scouting da Liga", icon_url=guild_icon_url())
    embed.set_footer(text="👀 Fique de olho, sua chance pode estar aqui!")

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Anúncio de scouting enviado.", ephemeral=True)


@bot.tree.command(name="contract", description="Anuncia a assinatura de contrato de um jogador com um time.", guild=GUILD)
@app_commands.describe(
    jogador="Jogador que assinou",
    time="Nome do time",
    posicao="Posição do jogador (opcional)",
    valor="Valor do contrato (opcional)",
    temporadas="Duração do contrato (opcional)",
)
async def contract_cmd(
    interaction: discord.Interaction,
    jogador: discord.Member,
    time: str,
    posicao: Optional[str] = None,
    valor: Optional[str] = None,
    temporadas: Optional[str] = None,
):
    embed = discord.Embed(
        title="✍️  CONTRATO ASSINADO",
        description=f"### {jogador.mention} agora faz parte do **{time}**! 🎉",
        color=discord.Color.from_rgb(46, 204, 113),
        timestamp=datetime.datetime.now(),
    )
    if posicao:
        embed.add_field(name="⚽ Posição", value=f"```{posicao}```", inline=True)
    if valor:
        embed.add_field(name="💰 Valor", value=f"```{valor}```", inline=True)
    if temporadas:
        embed.add_field(name="📅 Duração", value=f"```{temporadas}```", inline=True)
    embed.set_thumbnail(url=jogador.display_avatar.url)
    embed.set_author(name=time, icon_url=guild_icon_url())
    embed.set_footer(text=f"Assinado por {interaction.user}", icon_url=interaction.user.display_avatar.url)

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Anúncio de contrato enviado.", ephemeral=True)


@bot.tree.command(name="release", description="Anuncia a liberação/dispensa de um jogador de um time.", guild=GUILD)
@app_commands.describe(
    jogador="Jogador que foi liberado",
    time="Nome do time",
    motivo="Motivo da liberação (opcional)",
)
async def release_cmd(
    interaction: discord.Interaction,
    jogador: discord.Member,
    time: str,
    motivo: Optional[str] = None,
):
    embed = discord.Embed(
        title="❌  JOGADOR LIBERADO",
        description=f"### {jogador.mention} foi liberado(a) do **{time}**.",
        color=discord.Color.from_rgb(231, 76, 60),
        timestamp=datetime.datetime.now(),
    )
    if motivo:
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
    embed.set_thumbnail(url=jogador.display_avatar.url)
    embed.set_author(name=time, icon_url=guild_icon_url())
    embed.set_footer(text=f"Liberado por {interaction.user}", icon_url=interaction.user.display_avatar.url)

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Anúncio de liberação enviado.", ephemeral=True)


@bot.tree.command(name="elenco", description="Mostra o elenco de um time com base em um cargo.", guild=GUILD)
@app_commands.describe(cargo="Cargo que representa o time")
async def elenco_cmd(interaction: discord.Interaction, cargo: discord.Role):
    membros = [m for m in cargo.members if not m.bot]

    embed = discord.Embed(
        title=f"📋  ELENCO — {cargo.name.upper()}",
        color=cargo.color if cargo.color.value != 0 else discord.Color(EMBED_COLOR),
        timestamp=datetime.datetime.now(),
    )
    embed.description = "\n".join(f"▸ {m.mention}" for m in membros) if membros else "*Nenhum jogador encontrado com este cargo.*"
    embed.set_author(name="Elenco da Liga", icon_url=guild_icon_url())
    embed.set_footer(text=f"👥 Total: {len(membros)} jogador(es)")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="friendly", description="Anuncia/agenda um amistoso entre dois times.", guild=GUILD)
@app_commands.describe(
    time1="Primeiro time",
    time2="Segundo time",
    data="Data do amistoso (ex: 24/08)",
    horario="Horário do amistoso (ex: 20h)",
    observacoes="Observações adicionais (opcional)",
)
async def friendly_cmd(
    interaction: discord.Interaction,
    time1: str,
    time2: str,
    data: str,
    horario: str,
    observacoes: Optional[str] = None,
):
    embed = discord.Embed(
        title="🤝  AMISTOSO CONFIRMADO",
        description=f"### {time1}   🆚   {time2}",
        color=discord.Color.from_rgb(155, 89, 182),
        timestamp=datetime.datetime.now(),
    )
    embed.add_field(name="📅 Data", value=f"```{data}```", inline=True)
    embed.add_field(name="⏰ Horário", value=f"```{horario}```", inline=True)
    if observacoes:
        embed.add_field(name="📝 Observações", value=observacoes, inline=False)
    embed.set_author(name="Amistosos da Liga", icon_url=guild_icon_url())
    embed.set_footer(text=f"Agendado por {interaction.user}", icon_url=interaction.user.display_avatar.url)

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Amistoso anunciado.", ephemeral=True)


# ============================================================
#  /drop — JOGO DE ADIVINHAR A BANDEIRA
# ============================================================

FLAGS = [
    # nível fácil
    {"nome": "Brasil", "codigo": "br", "nivel": "fácil"},
    {"nome": "Argentina", "codigo": "ar", "nivel": "fácil"},
    {"nome": "Estados Unidos", "codigo": "us", "nivel": "fácil"},
    {"nome": "Espanha", "codigo": "es", "nivel": "fácil"},
    {"nome": "França", "codigo": "fr", "nivel": "fácil"},
    {"nome": "Alemanha", "codigo": "de", "nivel": "fácil"},
    {"nome": "Itália", "codigo": "it", "nivel": "fácil"},
    {"nome": "Portugal", "codigo": "pt", "nivel": "fácil"},
    {"nome": "Japão", "codigo": "jp", "nivel": "fácil"},
    {"nome": "México", "codigo": "mx", "nivel": "fácil"},
    {"nome": "Canadá", "codigo": "ca", "nivel": "fácil"},
    {"nome": "China", "codigo": "cn", "nivel": "fácil"},
    # nível médio
    {"nome": "Holanda", "codigo": "nl", "nivel": "médio"},
    {"nome": "Bélgica", "codigo": "be", "nivel": "médio"},
    {"nome": "Suíça", "codigo": "ch", "nivel": "médio"},
    {"nome": "Suécia", "codigo": "se", "nivel": "médio"},
    {"nome": "Noruega", "codigo": "no", "nivel": "médio"},
    {"nome": "Polônia", "codigo": "pl", "nivel": "médio"},
    {"nome": "Grécia", "codigo": "gr", "nivel": "médio"},
    {"nome": "Turquia", "codigo": "tr", "nivel": "médio"},
    {"nome": "Coreia do Sul", "codigo": "kr", "nivel": "médio"},
    {"nome": "Austrália", "codigo": "au", "nivel": "médio"},
    {"nome": "Egito", "codigo": "eg", "nivel": "médio"},
    {"nome": "Marrocos", "codigo": "ma", "nivel": "médio"},
    {"nome": "Chile", "codigo": "cl", "nivel": "médio"},
    {"nome": "Colômbia", "codigo": "co", "nivel": "médio"},
    {"nome": "Uruguai", "codigo": "uy", "nivel": "médio"},
    # nível difícil
    {"nome": "Butão", "codigo": "bt", "nivel": "difícil"},
    {"nome": "Nepal", "codigo": "np", "nivel": "difícil"},
    {"nome": "Laos", "codigo": "la", "nivel": "difícil"},
    {"nome": "Mongólia", "codigo": "mn", "nivel": "difícil"},
    {"nome": "Eritreia", "codigo": "er", "nivel": "difícil"},
    {"nome": "Burundi", "codigo": "bi", "nivel": "difícil"},
    {"nome": "Suriname", "codigo": "sr", "nivel": "difícil"},
    {"nome": "Belize", "codigo": "bz", "nivel": "difícil"},
    {"nome": "Vanuatu", "codigo": "vu", "nivel": "difícil"},
    {"nome": "Tuvalu", "codigo": "tv", "nivel": "difícil"},
    {"nome": "Comores", "codigo": "km", "nivel": "difícil"},
    {"nome": "Lesoto", "codigo": "ls", "nivel": "difícil"},
    {"nome": "Kiribati", "codigo": "ki", "nivel": "difícil"},
    {"nome": "Palau", "codigo": "pw", "nivel": "difícil"},
]

DROP_REWARD_ROLES = {
    "scrim": SCRIM_HOSTER_ROLE_ID,
    "picperm": PIC_PERM_ROLE_ID,
    "scouting": SCOUTING_ROLE_ID,
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto.strip().lower()


async def gerar_bandeira_parcial(codigo: str) -> Optional[discord.File]:
    """Baixa a bandeira do país e devolve apenas um pedaço dela (recorte
    aleatório), pra dificultar a adivinhação."""
    if bot.http_session is None:
        return None

    url = f"https://flagcdn.com/w320/{codigo}.png"
    try:
        async with bot.http_session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
    except Exception:
        log.exception("Falha ao baixar bandeira %s", codigo)
        return None

    def _processar() -> io.BytesIO:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = img.size
        crop_w = max(1, int(w * random.uniform(0.35, 0.5)))
        x0 = random.randint(0, max(0, w - crop_w))
        cortada = img.crop((x0, 0, x0 + crop_w, h))
        buffer = io.BytesIO()
        cortada.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    buffer = await bot.loop.run_in_executor(None, _processar)
    return discord.File(buffer, filename="bandeira.png")


async def remover_cargo_depois(member_id: int, role_id: int, dias: int):
    await asyncio.sleep(dias * 24 * 60 * 60)
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    member = guild.get_member(member_id)
    role = guild.get_role(role_id)
    if member and role and role in member.roles:
        try:
            await member.remove_roles(role, reason="Recompensa do /drop expirou")
        except discord.HTTPException:
            pass


class DropRewardView(discord.ui.View):
    """View enviada por DM para quem acerta o /drop, com 3 cargos
    temporários (7 dias) à escolha: Scrim Hoster, Pic Perm e Scouting."""

    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id

    async def _conceder(self, interaction: discord.Interaction, chave: str, label: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Essa recompensa não é sua.", ephemeral=True)
            return

        role_id = DROP_REWARD_ROLES.get(chave)
        if not role_id:
            await interaction.response.send_message(
                "❌ Esse cargo ainda não foi configurado pela staff (ID vazio no bot.py).",
                ephemeral=True,
            )
            return

        guild = bot.get_guild(GUILD_ID)
        role = guild.get_role(role_id) if guild else None
        member = guild.get_member(self.user_id) if guild else None

        if not (guild and role and member):
            await interaction.response.send_message(
                "❌ Não consegui aplicar o cargo. Fale com a staff.", ephemeral=True
            )
            return

        await member.add_roles(role, reason="Recompensa do /drop")
        asyncio.create_task(remover_cargo_depois(self.user_id, role_id, DROP_ROLE_DURATION_DAYS))

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"✅ Você recebeu o cargo **{label}** por {DROP_ROLE_DURATION_DAYS} dias!",
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Scrim Hoster", emoji="🎮", style=discord.ButtonStyle.blurple)
    async def scrim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._conceder(interaction, "scrim", "Scrim Hoster")

    @discord.ui.button(label="Pic Perm", emoji="🖼️", style=discord.ButtonStyle.blurple)
    async def picperm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._conceder(interaction, "picperm", "Pic Perm")

    @discord.ui.button(label="Scouting", emoji="🔍", style=discord.ButtonStyle.blurple)
    async def scouting(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._conceder(interaction, "scouting", "Scouting")


@bot.tree.command(name="drop", description="Jogo: adivinhe o país pela bandeira parcialmente revelada.", guild=GUILD)
@app_commands.describe(dificuldade="Nível de dificuldade da pergunta")
@app_commands.choices(dificuldade=[
    app_commands.Choice(name="Fácil", value="fácil"),
    app_commands.Choice(name="Médio", value="médio"),
    app_commands.Choice(name="Difícil", value="difícil"),
    app_commands.Choice(name="Aleatório", value="aleatório"),
])
async def drop_cmd(interaction: discord.Interaction, dificuldade: Optional[app_commands.Choice[str]] = None):
    nivel = dificuldade.value if dificuldade else "aleatório"
    pool = FLAGS if nivel == "aleatório" else [f for f in FLAGS if f["nivel"] == nivel]
    if not pool:
        pool = FLAGS
    pais = random.choice(pool)

    await interaction.response.send_message("🏳️ Desafio de bandeira iniciado!", ephemeral=True)

    arquivo = await gerar_bandeira_parcial(pais["codigo"])
    if not arquivo:
        await interaction.followup.send("❌ Não consegui carregar a bandeira, tente novamente.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🏳️  QUAL É A BANDEIRA?",
        description=(
            "### Um pedaço da bandeira foi revelado... consegue adivinhar o país?\n"
            f"🎯 Nível: **{pais['nivel'].capitalize()}**\n"
            f"⏳ Vocês têm **{DROP_TIME_LIMIT} segundos** para responder no chat!"
        ),
        color=discord.Color.from_rgb(155, 89, 182),
    )
    embed.set_image(url="attachment://bandeira.png")
    embed.set_author(name="Quiz da Liga", icon_url=guild_icon_url())
    embed.set_footer(text="Digite o nome do país no chat para responder")

    await interaction.channel.send(embed=embed, file=arquivo)

    def check(m: discord.Message):
        return (
            m.channel.id == interaction.channel.id
            and not m.author.bot
            and normalizar(m.content) == normalizar(pais["nome"])
        )

    try:
        resposta = await bot.wait_for("message", timeout=DROP_TIME_LIMIT, check=check)
    except asyncio.TimeoutError:
        esgotado = discord.Embed(
            title="⏰  TEMPO ESGOTADO",
            description=f"### Ninguém acertou a tempo!\nA resposta era **{pais['nome']}**.",
            color=discord.Color.dark_grey(),
        )
        await interaction.channel.send(embed=esgotado)
        return

    acerto = discord.Embed(
        title="🎉  ACERTOU!",
        description=f"### {resposta.author.mention} acertou! A bandeira era de **{pais['nome']}**! 🏆",
        color=discord.Color.from_rgb(46, 204, 113),
    )
    await interaction.channel.send(content=resposta.author.mention, embed=acerto)

    # Envia DM para o vencedor escolher uma recompensa temporária.
    try:
        dm_embed = discord.Embed(
            title="🏆 Você ganhou uma recompensa!",
            description=(
                f"Parabéns por acertar a bandeira de **{pais['nome']}**!\n\n"
                f"Escolha um dos cargos abaixo para receber por **{DROP_ROLE_DURATION_DAYS} dias**:"
            ),
            color=discord.Color.gold(),
        )
        await resposta.author.send(embed=dm_embed, view=DropRewardView(resposta.author.id))
    except discord.Forbidden:
        await interaction.channel.send(
            f"⚠️ {resposta.author.mention}, não consegui te enviar DM. "
            "Habilite mensagens diretas do servidor para receber sua recompensa!"
        )


# ============================================================
#  ?role — AUTO-ATRIBUIÇÃO DE CARGO (comando de prefixo)
# ============================================================

@bot.command(name="cargoid")
async def cargoid_cmd(ctx: commands.Context, *, cargo: Optional[str] = None):
    """Comando utilitário: mostra o ID de um cargo pelo nome (fácil de usar no celular)."""
    if not cargo:
        await ctx.reply("❌ Use assim: `?cargoid NomeDoCargo`", mention_author=False)
        return

    role = discord.utils.find(lambda r: r.name.lower() == cargo.lower(), ctx.guild.roles)
    if not role:
        await ctx.reply(f"❌ Não encontrei o cargo **{cargo}**.", mention_author=False)
        return

    await ctx.reply(f"🆔 ID do cargo **{role.name}**: `{role.id}`", mention_author=False)


@bot.command(name="role")
async def role_cmd(ctx: commands.Context, *, cargo: Optional[str] = None):
    if not cargo:
        await ctx.reply("❌ Use assim: `?role NomeDoCargo`", mention_author=False)
        return

    if SELF_ASSIGNABLE_ROLES and cargo.lower() not in [r.lower() for r in SELF_ASSIGNABLE_ROLES]:
        disponiveis = ", ".join(SELF_ASSIGNABLE_ROLES)
        await ctx.reply(
            f"❌ Esse cargo não está liberado para auto-atribuição.\nDisponíveis: {disponiveis}",
            mention_author=False,
        )
        return

    role = discord.utils.find(lambda r: r.name.lower() == cargo.lower(), ctx.guild.roles)
    if not role:
        await ctx.reply(f"❌ Não encontrei o cargo **{cargo}**.", mention_author=False)
        return

    if role in ctx.author.roles:
        await ctx.author.remove_roles(role, reason="Auto-remoção via ?role")
        await ctx.reply(f"➖ Cargo **{role.name}** removido.", mention_author=False)
    else:
        await ctx.author.add_roles(role, reason="Auto-atribuição via ?role")
        await ctx.reply(f"➕ Cargo **{role.name}** adicionado!", mention_author=False)


# ============================================================
#  TRATAMENTO DE ERROS
# ============================================================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ Você não tem permissão para usar este comando."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Aguarde {error.retry_after:.1f}s para usar este comando novamente."
    else:
        msg = "❌ Ocorreu um erro ao executar este comando."
        log.exception("Erro no comando %s", getattr(interaction.command, "name", "?"), exc_info=error)

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise SystemExit(
            "❌ Defina a variável de ambiente DISCORD_TOKEN (ou crie um arquivo .env) "
            "com o token do seu bot antes de rodar."
        )
    bot.run(TOKEN)
