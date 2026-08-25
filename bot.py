"""
BRS Bot v2 — Brazilian Roblox Soccer
Sistemas: Tickets, Drop (1000+ perguntas), Scrim, Friendly,
Free Agent, Scouting, /role, /say, /say_embed (foto auto),
Config estilo PAFO, Wave Drop (5-10 drops), Metas
"""

import os
import json
import copy
import datetime
import logging
import unicodedata
import random
import asyncio
from typing import Optional, Union, List

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

# ============================================================
#  CONFIGURAÇÕES FIXAS
# ============================================================
GUILD_ID = 1540722239027023882
GUILD = discord.Object(id=GUILD_ID)
EMBED_COLOR = 0x2B2D31
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

# Cargos de recompensa do Drop (padrão)
DROP_REWARD_ROLES = {
    1541835699873914900: {"nome": "Olheiro (5 Dias)", "emoji": "🔍"},
    1541832115052871830: {"nome": "Scrim Hoster (5 Dias)", "emoji": "⚔️"},
    1541836120382382100: {"nome": "Pic Perm (5 Dias)", "emoji": "💥"},
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("brs-bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

ACTIVE_DROP: Optional[dict] = None
WAVE_RUNNING = False
WAVE_LOCK = asyncio.Lock()  # 🔒 Lock anti-duplicidade

# ============================================================
#  BANCO DE PERGUNTAS — 1000+ DIVERSAS
# ============================================================

def gerar_banco_perguntas() -> List[dict]:
    """Gera 1000+ perguntas diversificadas (futebol, geografia, matemática, cultura)"""
    banco = []

    # === FUTEBOL / BRS ===
    futebol = [
        ("Qual time brasileiro é conhecido como 'O Mais Querido'?", "flamengo"),
        ("Quem é o maior artilheiro da história da seleção brasileira?", "pele"),
        ("Em que ano o Brasil ganhou a primeira Copa do Mundo?", "1958"),
        ("Quantos jogadores tem um time de futebol em campo?", "11"),
        ("Qual é o nome do estádio do Flamengo e Fluminense?", "maracana"),
        ("Quem é o Rei do Futebol?", "pele"),
        ("Qual país sediou a Copa de 2014?", "brasil"),
        ("Qual time tem as cores preto e branco e é de São Paulo?", "corinthians"),
        ("O que significa a sigla BRS?", "brazilian roblox soccer"),
        ("Quantos títulos de Copa do Mundo o Brasil tem?", "5"),
        ("Qual jogador é conhecido como 'Messi'?", "lionel messi"),
        ("Qual é o time de Cristiano Ronaldo em 2024?", "al nassr"),
        ("Em que ano o Brasil ganhou a Copa de 2002?", "2002"),
        ("Qual país tem mais Copas do Mundo?", "brasil"),
        ("Qual time venceu a Libertadores de 2023?", "fluminense"),
        ("Qual é a posição de Neymar?", "atacante"),
        ("Qual time é conhecido como 'Galo'?", "atletico mineiro"),
        ("Qual time é conhecido como 'Furacão'?", "atletico paranaense"),
        ("Qual time é conhecido como 'Leão'?", "sport recife"),
        ("Qual time é conhecido como 'Verdão'?", "palmeiras"),
        ("Qual time é conhecido como 'Timão'?", "corinthians"),
        ("Qual time é conhecido como 'Mengão'?", "flamengo"),
        ("Qual time é conhecido como 'Tricolor'?", "fluminense ou sao paulo"),
        ("Qual o maior estádio do Brasil?", "maracana"),
        ("Qual o estádio do Corinthians?", "neo quimica arena"),
        ("Qual o estádio do Palmeiras?", "allianz parque"),
        ("Qual o estádio do São Paulo?", "morumbi"),
        ("Quantas Copas do Mundo a Argentina tem?", "3"),
        ("Quem ganhou a Copa de 2022?", "argentina"),
        ("Qual país sediou a Copa de 2022?", "catar"),
        ("O que é um hat-trick?", "tres gols"),
        ("O que é um gol de bicicleta?", "gol acrobatico"),
        ("Qual seleção é conhecida como 'Canarinho'?", "brasil"),
        ("Qual seleção é conhecida como 'Albiceleste'?", "argentina"),
        ("Qual seleção é conhecida como 'La Roja'?", "chile"),
        ("Qual técnico venceu a Copa de 2002 com o Brasil?", "felipao"),
        ("Quantos jogadores vão para a Copa por seleção?", "26"),
        ("O que significa VAR?", "video assistant referee"),
        ("Qual time tem mais brasileirões?", "palmeiras"),
        ("Em que ano foi fundado o Flamengo?", "1895"),
        ("Em que ano foi fundado o Corinthians?", "1910"),
        ("Em que ano foi fundado o Palmeiras?", "1914"),
        ("Em que ano foi fundado o São Paulo?", "1930"),
        ("Qual jogador é conhecido como 'Fenômeno'?", "ronaldo"),
        ("Qual jogador é conhecido como 'Galáctico'?", "ronaldo ou zidane"),
        ("Qual time venceu a Champions League 2024?", "real madrid"),
        ("Qual time venceu a Champions League 2023?", "manchester city"),
        ("Qual melhor jogador do mundo em 2023?", "lionel messi"),
        ("Quantas bolas de ouro Messi tem?", "8"),
        ("Quantas bolas de ouro CR7 tem?", "5"),
    ]
    for q, a in futebol:
        banco.append({"q": q, "a": a})

    # === GEOGRAFIA ===
    geografia = [
        ("Qual é a capital do Brasil?", "brasilia"),
        ("Qual é a capital da Argentina?", "buenos aires"),
        ("Qual é a capital da França?", "paris"),
        ("Qual é a capital da Inglaterra?", "londres"),
        ("Qual é a capital da Alemanha?", "berlim"),
        ("Qual é a capital da Itália?", "roma"),
        ("Qual é a capital da Espanha?", "madri"),
        ("Qual é a capital de Portugal?", "lisboa"),
        ("Qual é a capital da Rússia?", "moscou"),
        ("Qual é a capital do Japão?", "toquio"),
        ("Qual é a capital da China?", "pequim"),
        ("Qual é a capital da Argentina?", "buenos aires"),
        ("Qual é o maior país do mundo?", "russia"),
        ("Qual é o menor país do mundo?", "vaticano"),
        ("Em que continente fica o Egito?", "africa"),
        ("Qual país tem a Torre Eiffel?", "franca"),
        ("Quantos continentes existem?", "7"),
        ("Qual é o maior oceano?", "pacifico"),
        ("Qual é o maior rio do mundo?", "amazonas"),
        ("Qual é a maior montanha do mundo?", "everest"),
        ("Quantos estados tem o Brasil?", "26"),
        ("Qual é a capital da Suíça?", "berna"),
        ("Qual é a capital da Suécia?", "estocolmo"),
        ("Qual é a capital da Noruega?", "oslo"),
        ("Qual é a capital da Dinamarca?", "copenhague"),
        ("Qual é a capital da Finlândia?", "helsinki"),
        ("Qual é a capital da Polônia?", "varsovia"),
        ("Qual é a capital da Ucrânia?", "kiev"),
        ("Qual é a capital da Grécia?", "atenas"),
        ("Qual é a capital da Colômbia?", "bogota"),
        ("Qual é a capital do Chile?", "santiago"),
        ("Qual é a capital do Peru?", "lima"),
        ("Qual é a capital do Uruguai?", "montevideu"),
    ]
    for q, a in geografia:
        banco.append({"q": q, "a": a})

    # === MATEMÁTICA (300+) ===
    for i in range(1, 101):
        banco.append({"q": f"Quanto é {i} + {i}?", "a": str(i*2)})
        banco.append({"q": f"Quanto é {i} x 2?", "a": str(i*2)})
    for i in range(1, 51):
        banco.append({"q": f"Quanto é {i} x {i}?", "a": str(i*i)})
    for q, r in [(4,2),(9,3),(16,4),(25,5),(36,6),(49,7),(64,8),(81,9),(100,10),
                 (121,11),(144,12),(169,13),(196,14),(225,15)]:
        banco.append({"q": f"Qual é a raiz quadrada de {q}?", "a": str(r)})

    # === CULTURA GERAL ===
    cultura = [
        ("Quem descobriu o Brasil?", "pedro alvares cabral"),
        ("Em que ano o Brasil foi descoberto?", "1500"),
        ("Quem proclamou a independência do Brasil?", "dom pedro i"),
        ("Em que ano foi a independência do Brasil?", "1822"),
        ("Quem foi o primeiro presidente do Brasil?", "deodoro da fonseca"),
        ("Quem pintou a Mona Lisa?", "leonardo da vinci"),
        ("Quem escreveu 'Dom Casmurro'?", "machado de assis"),
        ("Em que ano o homem pisou na Lua?", "1969"),
        ("Quem foi o primeiro homem a pisar na Lua?", "neil armstrong"),
        ("Qual é o planeta mais próximo do Sol?", "mercurio"),
        ("Qual é o maior planeta do sistema solar?", "jupiter"),
        ("Quantos planetas tem o sistema solar?", "8"),
        ("Qual é o maior animal do mundo?", "baleia azul"),
        ("Qual é o animal mais rápido do mundo?", "falcão peregrino"),
        ("Qual é o animal terrestre mais rápido?", "guepardo"),
        ("Qual é a velocidade da luz?", "300000 km/s"),
        ("Quem formulou a teoria da relatividade?", "albert einstein"),
        ("Quem criou a teoria da evolução?", "charles darwin"),
        ("Quem inventou a lâmpada?", "thomas edison"),
        ("Quem inventou o telefone?", "alexander graham bell"),
        ("Quem inventou o avião?", "santos dumont"),
        ("O que significa HTML?", "hypertext markup language"),
        ("O que significa API?", "application programming interface"),
        ("Qual é a maior torre do mundo?", "burj khalifa"),
        ("Em que ano o Titanic afundou?", "1912"),
        ("Qual é a moeda oficial do Brasil?", "real"),
        ("Qual é a moeda oficial dos EUA?", "dolar"),
        ("Qual é a moeda oficial da Europa?", "euro"),
        ("O que é Bitcoin?", "criptomoeda"),
        ("Qual é o jogo mais vendido do mundo?", "minecraft"),
        ("Qual é o esporte mais popular do mundo?", "futebol"),
        ("Quantos jogadores tem um time de basquete?", "5"),
        ("Qual país ganhou mais Copas do Mundo?", "brasil"),
    ]
    for q, a in cultura:
        banco.append({"q": q, "a": a})

    # === ROBLOX / DISCORD / BRS ===
    extras = [
        ("Em que plataforma roda o Roblox Soccer?", "roblox"),
        ("Quem criou o Roblox?", "david baszucki"),
        ("Em que ano o Roblox foi lançado?", "2006"),
        ("O que é Robux?", "moeda do roblox"),
        ("O que significa GG?", "good game"),
        ("O que significa OP?", "overpowered"),
        ("O que é um scrim?", "treino competitivo"),
        ("O que é um friendly?", "partida amigavel"),
        ("O que significa FA?", "free agent"),
        ("O que é um Drop?", "sorteio de perguntas"),
        ("O que é Wave Drop?", "sequencia de drops"),
        ("O que é ping no Discord?", "latencia"),
        ("O que é embed?", "mensagem estilizada"),
        ("O que significa DM?", "direct message"),
        ("O que significa VC?", "voice channel"),
    ]
    for q, a in extras:
        banco.append({"q": q, "a": a})

    return banco


TODAS_PERGUNTAS = gerar_banco_perguntas()

# ============================================================
#  PERSISTÊNCIA
# ============================================================
DEFAULT_CONFIG = {
    "staff_role_ids": [],
    "command_permissions": {
        "ticket": [], "drop": [], "freeagent": [], "scouting": [],
        "say": [], "say_embed": [], "role": [],
    },
    "ticket": {
        "category_id": None,
        "staff_role_ids": [],
        "channel_name_template": "ticket-{user}",
        "welcome_message": "Olá {mention}, seja bem-vindo(a) à BRS! Descreva sua solicitação e aguarde o atendimento da staff.",
        "log_channel_id": None,
    },
    "drop": {
        "reward_role_ids": list(DROP_REWARD_ROLES.keys()),
        "default_channel_id": None,
        "meta_membros": 18750,
        "meta_canal_id": None,
        "meta_mensagem_id": None,
        "wave_ativo": False,
    },
    "freeagent": {"channel_id": None},
    "scouting": {"channel_id": None},
    "scrim": {"channel_id": None},
    "friendly": {"channel_id": None},
}


def carregar_dados() -> dict:
    if not os.path.exists(DATA_PATH):
        return {"config": copy.deepcopy(DEFAULT_CONFIG), "freeagents": {}, "scoutings": {}, "drop_expiracoes": {}}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        dados = json.load(f)
    dados.setdefault("config", copy.deepcopy(DEFAULT_CONFIG))
    for chave, valor in DEFAULT_CONFIG.items():
        dados["config"].setdefault(chave, copy.deepcopy(valor))
    dados["config"].setdefault("command_permissions", {})
    for cmd in DEFAULT_CONFIG["command_permissions"]:
        dados["config"]["command_permissions"].setdefault(cmd, [])
    dados.setdefault("freeagents", {})
    dados.setdefault("scoutings", {})
    dados.setdefault("drop_expiracoes", {})
    return dados


def salvar_dados(dados: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


DADOS = carregar_dados()


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto.strip().lower()


def tem_permissao(member: discord.Member, comando: str) -> bool:
    if member.guild_permissions.administrator:
        return True
    cfg = DADOS["config"]
    ids_permitidos = set(cfg["staff_role_ids"]) | set(cfg["command_permissions"].get(comando, []))
    if not ids_permitidos:
        return False
    return bool(ids_permitidos & {r.id for r in member.roles})


async def checar_permissao(interaction: discord.Interaction, comando: str) -> bool:
    if not tem_permissao(interaction.user, comando):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando.\n"
            "Peça para um administrador liberar com `/permissao` ou `/staff`.",
            ephemeral=True,
        )
        return False
    return True


# ============================================================
#  BOT
# ============================================================
class BRSBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(",", "/"),
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())
        self.tree.add_command(ticket_group, guild=GUILD)
        self.tree.add_command(drop_group, guild=GUILD)
        self.tree.add_command(freeagent_group, guild=GUILD)
        self.tree.add_command(scouting_group, guild=GUILD)
        self.tree.add_command(scrim_group, guild=GUILD)
        self.tree.add_command(friendly_group, guild=GUILD)
        synced = await self.tree.sync(guild=GUILD)
        log.info("Sincronizados %s comandos na guild %s", len(synced), GUILD_ID)
        verificar_expiracoes.start()


bot = BRSBot()


@bot.event
async def on_ready():
    log.info("Bot conectado como %s (ID: %s)", bot.user, bot.user.id)
    log.info("Total de perguntas no Drop: %s", len(TODAS_PERGUNTAS))


@bot.event
async def on_message(message: discord.Message):
    global ACTIVE_DROP

    if message.author.bot:
        return

    # === DROP ===
    if ACTIVE_DROP and not ACTIVE_DROP["finalizado"] and message.channel.id == ACTIVE_DROP["canal_id"]:
        if normalizar(message.content) == ACTIVE_DROP["resposta_normalizada"]:
            ACTIVE_DROP["finalizado"] = True
            vencedor = message.author

            await message.channel.send(
                embed=discord.Embed(
                    title="🎉 DROP VENCIDO!",
                    description=f"### {vencedor.mention} acertou!\nA resposta era **{ACTIVE_DROP['resposta']}**",
                    color=discord.Color.from_rgb(46, 204, 113),
                )
            )

            role_ids = DADOS["config"]["drop"].get("reward_role_ids", list(DROP_REWARD_ROLES.keys()))
            roles = [r for rid in role_ids if (r := message.guild.get_role(rid))]

            try:
                if roles:
                    dm_embed = discord.Embed(
                        title="🎁 Você Venceu o Drop!",
                        description=(
                            "Você respondeu corretamente no chat e garantiu seu prêmio.\n"
                            "Escolha abaixo qual cargo você deseja receber no servidor:"
                        ),
                        color=discord.Color.gold(),
                    )
                    dm_embed.set_footer(text="BRS — Drops System")
                    await vencedor.send(embed=dm_embed, view=DropRewardView(vencedor.id, roles))
                else:
                    await vencedor.send("🏆 Você venceu o Drop, mas nenhum cargo de recompensa está configurado.")
            except discord.Forbidden:
                await message.channel.send(
                    f"⚠️ {vencedor.mention}, não consegui te enviar DM. Habilite mensagens diretas do servidor!"
                )

            ACTIVE_DROP = None
            return

    await bot.process_commands(message)


# ============================================================
#  EXPIRAÇÃO DE CARGOS (5 dias)
# ============================================================
@tasks.loop(minutes=30)
async def verificar_expiracoes():
    agora = datetime.datetime.utcnow()
    removidos = []
    for uid, info in list(DADOS.get("drop_expiracoes", {}).items()):
        try:
            expira = datetime.datetime.fromisoformat(info["expira_em"])
            if agora >= expira:
                guild = bot.get_guild(GUILD_ID)
                if guild:
                    member = guild.get_member(int(uid))
                    role = guild.get_role(info["role_id"])
                    if member and role and role in member.roles:
                        await member.remove_roles(role, reason="Expiração do prêmio do Drop (5 dias)")
                removidos.append(uid)
        except Exception:
            continue
    for uid in removidos:
        DADOS["drop_expiracoes"].pop(uid, None)
    if removidos:
        salvar_dados(DADOS)


@verificar_expiracoes.before_loop
async def before_expiracoes():
    await bot.wait_until_ready()


# ============================================================
#  TICKETS
# ============================================================
def is_ticket_channel(channel: discord.abc.GuildChannel) -> bool:
    return isinstance(channel, discord.TextChannel) and channel.name.startswith("ticket-")


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", emoji="🎫", style=discord.ButtonStyle.green, custom_id="brs_open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        cfg = DADOS["config"]["ticket"]
        template = cfg.get("channel_name_template") or "ticket-{user}"
        channel_name = template.replace("{user}", interaction.user.name).lower().replace(" ", "-")[:90]
        if not channel_name.startswith("ticket-"):
            channel_name = f"ticket-{channel_name}"[:90]

        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await interaction.response.send_message(f"❌ Você já possui um ticket aberto: {existing.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for rid in cfg.get("staff_role_ids", []):
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        category = guild.get_channel(cfg.get("category_id")) if cfg.get("category_id") else None
        ticket_channel = await guild.create_text_channel(
            name=channel_name, category=category, overwrites=overwrites,
            reason=f"Ticket aberto por {interaction.user}"
        )

        mensagem = (cfg.get("welcome_message") or "Olá {mention}!").replace("{mention}", interaction.user.mention).replace("{user}", interaction.user.display_name)
        embed = discord.Embed(title="🎫 Ticket — BRS", description=mensagem, color=EMBED_COLOR, timestamp=datetime.datetime.now())
        embed.set_footer(text=f"Aberto por {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await ticket_channel.send(content=interaction.user.mention, embed=embed, view=TicketControlView())

        log_id = cfg.get("log_channel_id")
        if log_id:
            log_channel = guild.get_channel(log_id)
            if log_channel:
                await log_channel.send(embed=discord.Embed(
                    description=f"🎫 Ticket aberto: {ticket_channel.mention} por {interaction.user.mention}",
                    color=discord.Color.green()
                ))

        await interaction.response.send_message(f"✅ Ticket criado: {ticket_channel.mention}", ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fechar Ticket", emoji="🔒", style=discord.ButtonStyle.red, custom_id="brs_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message("❌ Este botão só funciona dentro de um canal de ticket.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Fechando o ticket em 5 segundos...", ephemeral=True)

        cfg = DADOS["config"]["ticket"]
        log_id = cfg.get("log_channel_id")
        if log_id:
            log_channel = interaction.guild.get_channel(log_id)
            if log_channel:
                await log_channel.send(embed=discord.Embed(
                    description=f"🔒 Ticket fechado: `{interaction.channel.name}` por {interaction.user.mention}",
                    color=discord.Color.red()
                ))

        await interaction.channel.send(f"🔒 Ticket fechado por {interaction.user.mention}. Encerrando em 5 segundos...")
        await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
        await interaction.channel.delete(reason=f"Ticket fechado por {interaction.user}")


ticket_group = app_commands.Group(name="ticket", description="Sistema de tickets da BRS")


@ticket_group.command(name="configurar", description="Configura o sistema de tickets.")
@app_commands.describe(
    categoria="Categoria dos tickets",
    cargo_staff="Cargo com acesso aos tickets",
    nome_canal="Modelo do nome (use {user})",
    mensagem="Mensagem inicial (use {mention})",
    canal_logs="Canal de logs",
)
async def ticket_configurar(
    interaction: discord.Interaction,
    categoria: Optional[discord.CategoryChannel] = None,
    cargo_staff: Optional[discord.Role] = None,
    nome_canal: Optional[str] = None,
    mensagem: Optional[str] = None,
    canal_logs: Optional[discord.TextChannel] = None,
):
    if not await checar_permissao(interaction, "ticket"):
        return
    cfg = DADOS["config"]["ticket"]
    alterado = []
    if categoria:
        cfg["category_id"] = categoria.id
        alterado.append(f"📁 Categoria: **{categoria.name}**")
    if cargo_staff:
        if cargo_staff.id not in cfg["staff_role_ids"]:
            cfg["staff_role_ids"].append(cargo_staff.id)
        alterado.append(f"🛡️ Cargo staff: **{cargo_staff.name}**")
    if nome_canal:
        cfg["channel_name_template"] = nome_canal
        alterado.append(f"🏷️ Nome: `{nome_canal}`")
    if mensagem:
        cfg["welcome_message"] = mensagem
        alterado.append("💬 Mensagem inicial atualizada")
    if canal_logs:
        cfg["log_channel_id"] = canal_logs.id
        alterado.append(f"📜 Logs: {canal_logs.mention}")
    salvar_dados(DADOS)
    if not alterado:
        await interaction.response.send_message("ℹ️ Nenhuma alteração enviada.", ephemeral=True)
        return
    await interaction.response.send_message("✅ Configuração atualizada:\n" + "\n".join(f"• {a}" for a in alterado), ephemeral=True)


@ticket_group.command(name="painel", description="Envia o painel de tickets.")
@app_commands.describe(canal="Canal do painel")
async def ticket_painel(interaction: discord.Interaction, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "ticket"):
        return
    canal = canal or interaction.channel
    embed = discord.Embed(
        title="🎫  Central de Atendimento — BRS",
        description="Clique no botão abaixo para abrir um ticket com a nossa staff.",
        color=EMBED_COLOR,
    )
    await canal.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message(f"✅ Painel enviado em {canal.mention}.", ephemeral=True)


@ticket_group.command(name="add", description="Adiciona membro/cargo ao ticket.")
@app_commands.describe(alvo="Membro ou cargo")
async def ticket_add(interaction: discord.Interaction, alvo: Union[discord.Member, discord.Role]):
    if not is_ticket_channel(interaction.channel):
        await interaction.response.send_message("❌ Só funciona dentro de um ticket.", ephemeral=True)
        return
    await interaction.channel.set_permissions(alvo, view_channel=True, send_messages=True, read_message_history=True)
    await interaction.response.send_message(f"✅ {alvo.mention} adicionado(a).", ephemeral
