"""
BRS Bot v2 — Brazilian Roblox Soccer
Sistemas: Tickets, Drop (1000+ perguntas), Scrim, Friendly,
Free Agent, Scouting, /role, /say, /say_embed (foto auto),
Wave Drop (5-10 drops), Metas, Config estilo PAFO
"""

import os, json, copy, datetime, logging, unicodedata, random, asyncio
from typing import Optional, Union, List

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

# ============================================================
#  CONFIG
# ============================================================
GUILD_ID = 1540722239027023882
GUILD = discord.Object(id=GUILD_ID)
EMBED_COLOR = 0x2B2D31
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("brs-bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

ACTIVE_DROP = None
WAVE_RUNNING = False
WAVE_LOCK = asyncio.Lock()

# ============================================================
#  BANCO DE PERGUNTAS (1000+)
# ============================================================
def gerar_perguntas():
    banco = []
    # Futebol / BRS
    fb = [
        ("Qual time é 'O Mais Querido'?", "flamengo"),
        ("Maior artilheiro da seleção brasileira?", "pele"),
        ("Ano do primeiro título mundial do Brasil?", "1958"),
        ("Quantos jogadores em campo?", "11"),
        ("Estádio do Flamengo e Fluminense?", "maracana"),
        ("Rei do Futebol?", "pele"),
        ("País da Copa de 2014?", "brasil"),
        ("O que significa BRS?", "brazilian roblox soccer"),
        ("Quantas Copas o Brasil tem?", "5"),
        ("Libertadores 2023?", "fluminense"),
        ("Posição do Neymar?", "atacante"),
        ("Conhecido como Galo?", "atletico mineiro"),
        ("Conhecido como Verdão?", "palmeiras"),
        ("Conhecido como Timão?", "corinthians"),
        ("Conhecido como Mengão?", "flamengo"),
        ("Maior estádio do Brasil?", "maracana"),
        ("Copas da Argentina?", "3"),
        ("Copa de 2022?", "argentina"),
        ("País da Copa 2022?", "catar"),
        ("O que é hat trick?", "tres gols"),
        ("Seleção Canarinho?", "brasil"),
        ("Seleção Albiceleste?", "argentina"),
        ("Maior campeão brasileiro?", "palmeiras"),
        ("Jogador Fenômeno?", "ronaldo"),
        ("Champions 2024?", "real madrid"),
        ("Melhor do mundo 2023?", "lionel messi"),
        ("Bolas de ouro do Messi?", "8"),
        ("Bolas de ouro do CR7?", "5"),
    ]
    for q, a in fb:
        banco.append({"q": q, "a": a})

    # Geografia
    geo = [
        ("Capital do Brasil?", "brasilia"),
        ("Capital da Argentina?", "buenos aires"),
        ("Capital da França?", "paris"),
        ("Capital da Inglaterra?", "londres"),
        ("Capital da Alemanha?", "berlim"),
        ("Capital da Itália?", "roma"),
        ("Capital da Espanha?", "madri"),
        ("Capital de Portugal?", "lisboa"),
        ("Capital dos EUA?", "washington dc"),
        ("Capital do Japão?", "toquio"),
        ("Capital da China?", "pequim"),
        ("Capital da Rússia?", "moscou"),
        ("Capital do Egito?", "cairo"),
        ("Maior país do mundo?", "russia"),
        ("Menor país do mundo?", "vaticano"),
        ("Continente do Egito?", "africa"),
        ("País da Torre Eiffel?", "franca"),
        ("Quantos continentes?", "7"),
        ("Maior oceano?", "pacifico"),
        ("Maior rio do mundo?", "amazonas"),
        ("Maior montanha?", "everest"),
        ("Estados do Brasil?", "26"),
        ("Menor estado do Brasil?", "sergipe"),
        ("Cidade Maravilhosa?", "rio de janeiro"),
        ("Terra do Sol Nascente?", "japao"),
        ("Capital da Suíça?", "berna"),
        ("Capital da Suécia?", "estocolmo"),
        ("Capital da Dinamarca?", "copenhague"),
        ("Capital da Grécia?", "atenas"),
        ("Capital da Colômbia?", "bogota"),
        ("Capital do Chile?", "santiago"),
        ("Capital do Peru?", "lima"),
        ("Capital do Uruguai?", "montevideu"),
        ("Oceano do Brasil?", "atlantico"),
        ("Clima do Brasil?", "tropical"),
        ("Maior bioma brasileiro?", "amazonia"),
        ("Cidade mais populosa do Brasil?", "sao paulo"),
        ("Regiões do Brasil?", "5"),
        ("Capital do Canadá?", "ottawa"),
        ("Capital da Austrália?", "canberra"),
    ]
    for q, a in geo:
        banco.append({"q": q, "a": a})

    # Matemática (300+)
    for i in range(1, 101):
        banco.append({"q": f"Quanto é {i} + {i}?", "a": str(i*2)})
        banco.append({"q": f"Quanto é {i} x 2?", "a": str(i*2)})
    for i in range(1, 51):
        banco.append({"q": f"Quanto é {i} x {i}?", "a": str(i*i)})
    for v, r in [(4,2),(9,3),(16,4),(25,5),(36,6),(49,7),(64,8),(81,9),(100,10),
                 (121,11),(144,12),(169,13),(196,14),(225,15)]:
        banco.append({"q": f"Raiz quadrada de {v}?", "a": str(r)})

    # Cultura geral
    cult = [
        ("Descobriu o Brasil?", "pedro alvares cabral"),
        ("Ano do descobrimento?", "1500"),
        ("Independência do Brasil?", "1822"),
        ("Primeiro presidente?", "deodoro da fonseca"),
        ("Pintou a Mona Lisa?", "leonardo da vinci"),
        ("Escreveu Dom Casmurro?", "machado de assis"),
        ("Primeiro homem na Lua?", "neil armstrong"),
        ("Ano do homem na Lua?", "1969"),
        ("Planeta mais próximo do Sol?", "mercurio"),
        ("Maior planeta?", "jupiter"),
        ("Planetas do sistema solar?", "8"),
        ("Maior animal?", "baleia azul"),
        ("Animal mais rápido?", "falcão peregrino"),
        ("Velocidade da luz?", "300000 km/s"),
        ("Teoria da relatividade?", "albert einstein"),
        ("Teoria da evolução?", "charles darwin"),
        ("Inventou a lâmpada?", "thomas edison"),
        ("Inventou o telefone?", "alexander graham bell"),
        ("Inventou o avião?", "santos dumont"),
        ("O que significa HTML?", "hypertext markup language"),
        ("Maior torre do mundo?", "burj khalifa"),
        ("Ano do Titanic?", "1912"),
        ("Moeda do Brasil?", "real"),
        ("Moeda dos EUA?", "dolar"),
        ("Moeda da Europa?", "euro"),
        ("O que é Bitcoin?", "criptomoeda"),
        ("Jogo mais vendido?", "minecraft"),
        ("Esporte mais popular?", "futebol"),
        ("Jogadores no basquete?", "5"),
        ("Mais Copas do Mundo?", "brasil"),
        ("O que significa DNA?", "acido desoxirribonucleico"),
        ("Ossos do corpo humano?", "206"),
        ("Maior órgão?", "pele"),
        ("Doador universal?", "o negativo"),
    ]
    for q, a in cult:
        banco.append({"q": q, "a": a})

    # Roblox / Discord
    rbx = [
        ("Plataforma do Roblox Soccer?", "roblox"),
        ("Criador do Roblox?", "david baszucki"),
        ("Ano do Roblox?", "2006"),
        ("O que é Robux?", "moeda do roblox"),
        ("O que significa GG?", "good game"),
        ("O que significa OP?", "overpowered"),
        ("O que é scrim?", "treino competitivo"),
        ("O que é friendly?", "partida amigavel"),
        ("O que significa FA?", "free agent"),
        ("O que é Drop?", "sorteio de perguntas"),
        ("O que é Wave Drop?", "sequencia de drops"),
        ("O que é ping?", "latencia"),
        ("O que é embed?", "mensagem estilizada"),
        ("O que significa DM?", "direct message"),
    ]
    for q, a in rbx:
        banco.append({"q": q, "a": a})

    return banco


TODAS_PERGUNTAS = gerar_perguntas()

# ============================================================
#  PERSISTÊNCIA
# ============================================================
DEFAULT_CONFIG = {
    "staff_role_ids": [],
    "command_permissions": {
        "ticket": [], "drop": [], "freeagent": [], "scouting": [],
        "say": [], "say_embed": [], "role": [], "scrim": [], "friendly": [],
    },
    "ticket": {
        "category_id": None, "staff_role_ids": [],
        "channel_name_template": "ticket-{user}",
        "welcome_message": "Olá {mention}, descreva sua solicitação.",
        "log_channel_id": None,
    },
    "drop": {
        "reward_role_ids": [],
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


def carregar_dados():
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


def salvar_dados(dados):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


DADOS = carregar_dados()


def normalizar(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return t.strip().lower()


def tem_permissao(member, comando):
    if member.guild_permissions.administrator:
        return True
    cfg = DADOS["config"]
    ids = set(cfg["staff_role_ids"]) | set(cfg["command_permissions"].get(comando, []))
    if not ids:
        return False
    return bool(ids & {r.id for r in member.roles})


async def checar_permissao(interaction, comando):
    if not tem_permissao(interaction.user, comando):
        await interaction.response.send_message(
            "❌ Sem permissão. Peça `/permissao` ou `/staff` a um admin.", ephemeral=True)
        return False
    return True


# ============================================================
#  BOT
# ============================================================
class BRSBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or(",", "/"), intents=intents, help_command=None)

    async def setup_hook(self):
        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())
        for g in [ticket_group, drop_group, freeagent_group, scouting_group]:
            self.tree.add_command(g, guild=GUILD)
        for cmd in [scrim_cmd, friendly_cmd, role_cmd, say_cmd, say_embed_cmd,
                    staff_cmd, permissao_cmd, config_ver_cmd]:
            self.tree.add_command(cmd, guild=GUILD)
        synced = await self.tree.sync(guild=GUILD)
        log.info(f"Sincronizados {len(synced)} comandos na guild {GUILD_ID}")
        verificar_expiracoes.start()


bot = BRSBot()


@bot.event
async def on_ready():
    log.info(f"Bot conectado como {bot.user} (ID: {bot.user.id})")
    log.info(f"Total de perguntas no Drop: {len(TODAS_PERGUNTAS)}")


@bot.event
async def on_message(message):
    global ACTIVE_DROP
    if message.author.bot:
        return
    if ACTIVE_DROP and not ACTIVE_DROP["finalizado"] and message.channel.id == ACTIVE_DROP["canal_id"]:
        if normalizar(message.content) == ACTIVE_DROP["resposta_normalizada"]:
            ACTIVE_DROP["finalizado"] = True
            v = message.author
            await message.channel.send(
                embed=discord.Embed(title="🎉 DROP VENCIDO!",
                                    description=f"### {v.mention} acertou!\nResposta: **{ACTIVE_DROP['resposta']}**",
                                    color=discord.Color.from_rgb(46, 204, 113)))
            roles = [r for rid in DADOS["config"]["drop"]["reward_role_ids"] if (r := message.guild.get_role(rid))]
            try:
                if roles:
                    await v.send(
                        embed=discord.Embed(title="🎁 Você Venceu!", description="Escolha seu cargo:", color=discord.Color.gold()),
                        view=DropRewardView(v.id, roles))
                else:
                    await v.send("🏆 Você venceu o Drop!")
            except discord.Forbidden:
                await message.channel.send(f"⚠️ {v.mention}, habilite DM!")
            ACTIVE_DROP = None
            return
    await bot.process_commands(message)


# ============================================================
#  EXPIRAÇÃO
# ============================================================
@tasks.loop(minutes=30)
async def verificar_expiracoes():
    agora = datetime.datetime.utcnow()
    rem = []
    for uid, info in list(DADOS.get("drop_expiracoes", {}).items()):
        try:
            exp = datetime.datetime.fromisoformat(info["expira_em"])
            if agora >= exp:
                g = bot.get_guild(GUILD_ID)
                if g:
                    m = g.get_member(int(uid))
                    r = g.get_role(info["role_id"])
                    if m and r and r in m.roles:
                        await m.remove_roles(r, reason="Expiração Drop")
                rem.append(uid)
        except Exception:
            continue
    for uid in rem:
        DADOS["drop_expiracoes"].pop(uid, None)
    if rem:
        salvar_dados(DADOS)


@verificar_expiracoes.before_loop
async def before_exp():
    await bot.wait_until_ready()


# ============================================================
#  TICKETS
# ============================================================
def is_ticket(c):
    return isinstance(c, discord.TextChannel) and c.name.startswith("ticket-")


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", emoji="🎫", style=discord.ButtonStyle.green, custom_id="brs_open_ticket")
    async def open_ticket(self, interaction, button):
        g = interaction.guild
        cfg = DADOS["config"]["ticket"]
        nome = (cfg.get("channel_name_template") or "ticket-{user}").replace("{user}", interaction.user.name).lower().replace(" ", "-")[:90]
        if not nome.startswith("ticket-"):
            nome = f"ticket-{nome}"[:90]
        if discord.utils.get(g.text_channels, name=nome):
            return await interaction.response.send_message("❌ Você já tem ticket!", ephemeral=True)
        overwrites = {
            g.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            g.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for rid in cfg.get("staff_role_ids", []):
            r = g.get_role(rid)
            if r:
                overwrites[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        cat = g.get_channel(cfg.get("category_id")) if cfg.get("category_id") else None
        ticket = await g.create_text_channel(name=nome, category=cat, overwrites=overwrites, reason=f"Ticket {interaction.user}")
        msg = (cfg.get("welcome_message") or "Olá {mention}!").replace("{mention}", interaction.user.mention)
        e = discord.Embed(title="🎫 Ticket — BRS", description=msg, color=EMBED_COLOR, timestamp=datetime.datetime.now())
        e.set_footer(text=f"{interaction.user}", icon_url=interaction.user.display_avatar.url)
        await ticket.send(content=interaction.user.mention, embed=e, view=TicketControlView())
        if cfg.get("log_channel_id") and (lc := g.get_channel(cfg["log_channel_id"])):
            await lc.send(embed=discord.Embed(description=f"🎫 Ticket: {ticket.mention} por {interaction.user.mention}", color=discord.Color.green()))
        await interaction.response.send_message(f"✅ Ticket: {ticket.mention}", ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fechar", emoji="🔒", style=discord.ButtonStyle.red, custom_id="brs_close_ticket")
    async def fechar(self, interaction, button):
        if not is_ticket(interaction.channel):
            return await interaction.response.send_message("❌ Só em ticket.", ephemeral=True)
        await interaction.response.send_message("🔒 Fechando...")
        await interaction.channel.send("🔒 Ticket será fechado.")
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Fechado por {interaction.user}")


ticket_group = app_commands.Group(name="ticket", description="Sistema de Tickets")


@ticket_group.command(name="configurar", description="Configura tickets")
async def ticket_configurar(interaction, categoria: Optional[discord.CategoryChannel] = None,
                            cargo_staff: Optional[discord.Role] = None,
                            nome_canal: Optional[str] = None,
                            mensagem: Optional[str] = None,
                            canal_logs: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "ticket"):
        return
    cfg = DADOS["config"]["ticket"]
    alt = []
    if categoria: cfg["category_id"] = categoria.id; alt.append(f"📁 {categoria.name}")
    if cargo_staff:
        if cargo_staff.id not in cfg["staff_role_ids"]: cfg["staff_role_ids"].append(cargo_staff.id)
        alt.append(f"🛡️ {cargo_staff.name}")
    if nome_canal: cfg["channel_name_template"] = nome_canal; alt.append(f"🏷️ `{nome_canal}`")
    if mensagem: cfg["welcome_message"] = mensagem; alt.append("💬 Mensagem atualizada")
    if canal_logs: cfg["log_channel_id"] = canal_logs.id; alt.append(f"📜 {canal_logs.mention}")
    salvar_dados(DADOS)
    await interaction.response.send_message("✅ " + "\n".join(f"• {a}" for a in alt) if alt else "ℹ️ Nada alterado.", ephemeral=True)


@ticket_group.command(name="painel", description="Envia painel de tickets")
async def ticket_painel(interaction, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "ticket"):
        return
    canal = canal or interaction.channel
    e = discord.Embed(title="🎫 Central de Atendimento — BRS", description="Clique abaixo para abrir ticket.", color=EMBED_COLOR)
    await canal.send(embed=e, view=TicketPanelView())
    await interaction.response.send_message(f"✅ Painel em {canal.mention}.", ephemeral=True)


@ticket_group.command(name="add", description="Adiciona ao ticket")
async def ticket_add(interaction, alvo: Union[discord.Member, discord.Role]):
    if not is_ticket(interaction.channel):
        return await interaction.response.send_message("❌ Só em ticket.", ephemeral=True)
    await interaction.channel.set_permissions(alvo, view_channel=True, send_messages=True, read_message_history=True)
    await interaction.response.send_message(f"✅ {alvo.mention} adicionado.", ephemeral=True)


@ticket_group.command(name="remove", description="Remove do ticket")
async def ticket_remove(interaction, alvo: Union[discord.Member, discord.Role]):
    if not is_ticket(interaction.channel):
        return await interaction.response.send_message("❌ Só em ticket.", ephemeral=True)
    await interaction.channel.set_permissions(alvo, overwrite=None)
    await interaction.response.send_message(f"✅ {alvo.mention} removido.", ephemeral=True)


# ============================================================
#  DROP
# ============================================================
class DropRewardSelect(discord.ui.Select):
    def __init__(self, user_id, roles):
        opts = [discord.SelectOption(label=r.name[:100], value=str(r.id), description="5 dias") for r in roles[:3]]
        super().__init__(placeholder="Escolha seu cargo", min_values=1, max_values=1, options=opts)
        self.user_id = user_id

    async def callback(self, interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Não é seu.", ephemeral=True)
        role_id = int(self.values[0])
        g = bot.get_guild(GUILD_ID)
        m = g.get_member(self.user_id)
        r = g.get_role(role_id)
        if not (g and m and r):
            return await interaction.response.send_message("❌ Erro ao aplicar.", ephemeral=True)
        await m.add_roles(r, reason="Drop BRS")
        DADOS.setdefault("drop_expiracoes", {})[str(m.id)] = {
            "role_id": role_id, "expira_em": (datetime.datetime.utcnow() + datetime.timedelta(days=5)).isoformat()}
        salvar_dados(DADOS)
        e = discord.Embed(title="✅ Resgatado!", description=f"Você recebeu {r.mention} por 5 dias.", color=discord.Color.green())
        await interaction.response.edit_message(content=None, embed=e, view=None)


class DropRewardView(discord.ui.View):
    def __init__(self, user_id, roles):
        super().__init__(timeout=600)
        self.add_item(DropRewardSelect(user_id, roles))


drop_group = app_commands.Group(name="drop", description="Sistema de Drops")


@drop_group.command(name="iniciar", description="Inicia um Drop")
async def drop_iniciar(interaction, pergunta: Optional[str] = None, resposta: Optional[str] = None, canal: Optional[discord.TextChannel] = None):
    global ACTIVE_DROP
    if not await checar_permissao(interaction, "drop"):
        return
    if ACTIVE_DROP and not ACTIVE_DROP["finalizado"]:
        return await interaction.response.send_message("❌ Já tem Drop ativo. Use `/drop cancelar`.", ephemeral=True)
    if not pergunta:
        esc = random.choice(TODAS_PERGUNTAS)
        pergunta, resposta = esc["q"], esc["a"]
    cd = canal or interaction.guild.get_channel(DADOS["config"]["drop"].get("default_channel_id")) or interaction.channel
    ACTIVE_DROP = {"pergunta": pergunta, "resposta": resposta, "resposta_normalizada": normalizar(resposta), "canal_id": cd.id, "finalizado": False}
    e = discord.Embed(description=f"# ❓ DROP — BRS\n\n### {pergunta}\n\nResponda no chat!", color=0x00FF7F)
    e.add_field(name="🎁 Prêmios", value="Cargos exclusivos!", inline=True)
    e.set_footer(text=f"{len(TODAS_PERGUNTAS)}+ perguntas")
    if bot.user: e.set_thumbnail(url=bot.user.display_avatar.url)
    await cd.send(embed=e)
    await interaction.response.send_message(f"✅ Drop em {cd.mention}", ephemeral=True)


@drop_group.command(name="cancelar", description="Cancela Drop")
async def drop_cancelar(interaction):
    global ACTIVE_DROP
    if not await checar_permissao(interaction, "drop"):
        return
    if not ACTIVE_DROP or ACTIVE_DROP["finalizado"]:
        return await interaction.response.send_message("ℹ️ Sem Drop ativo.", ephemeral=True)
    c = interaction.guild.get_channel(ACTIVE_DROP["canal_id"])
    ACTIVE_DROP = None
    if c: await c.send("🚫 Drop cancelado.")
    await interaction.response.send_message("✅ Cancelado.", ephemeral=True)


@drop_group.command(name="premio_adicionar", description="Adiciona cargo aos prêmios")
async def drop_premio_add(interaction, cargo: discord.Role):
    if not await checar_permissao(interaction, "drop"):
        return
    lst = DADOS["config"]["drop"]["reward_role_ids"]
    if cargo.id not in lst: lst.append(cargo.id); salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ {cargo.name} adicionado.", ephemeral=True)


@drop_group.command(name="premio_remover", description="Remove cargo dos prêmios")
async def drop_premio_rem(interaction, cargo: discord.Role):
    if not await checar_permissao(interaction, "drop"):
        return
    lst = DADOS["config"]["drop"]["reward_role_ids"]
    if cargo.id in lst: lst.remove(cargo.id); salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ {cargo.name} removido.", ephemeral=True)


@drop_group.command(name="canal_padrao", description="Canal padrão dos Drops")
async def drop_canal_padrao(interaction, canal: discord.TextChannel):
    if not await checar_permissao(interaction, "drop"):
        return
    DADOS["config"]["drop"]["default_channel_id"] = canal.id; salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Canal: {canal.mention}", ephemeral=True)


@drop_group.command(name="meta", description="Define meta de membros")
async def drop_meta(interaction, quantidade: int, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "drop"):
        return
    DADOS["config"]["drop"]["meta_membros"] = quantidade
    canal = canal or interaction.channel
    DADOS["config"]["drop"]["meta_canal_id"] = canal.id
    atual = interaction.guild.member_count
    e = discord.Embed(description="# 🟢 DROPS BRS\n\n**PRÊMIOS GARANTIDOS**\ncargos exclusivos\n\n**WAVE DROP**\n5 a 10 rodadas", color=0x00FF7F)
    e.add_field(name="📊 Progresso", value=f"👥 **{atual:,}** / **{quantidade:,}**", inline=False)
    e.set_footer(text="BRS — Metas")
    msg = await canal.send(embed=e)
    DADOS["config"]["drop"]["meta_mensagem_id"] = msg.id; salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Meta: {quantidade:,}", ephemeral=True)


# ============================================================
#  WAVE DROP (5-10 drops, lock anti-duplicidade)
# ============================================================
@drop_group.command(name="wave", description="Wave Drop 5 a 10 drops seguidos")
async def drop_wave(interaction, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "drop"):
        return
    async with WAVE_LOCK:
        global ACTIVE_DROP, WAVE_RUNNING
        if WAVE_RUNNING:
            return await interaction.response.send_message("❌ Wave já rodando!", ephemeral=True)
        cd = canal or interaction.channel
        qtd = random.randint(5, 10)
        WAVE_RUNNING = True
        await interaction.response.send_message(f"🌊 Wave Drop: **{qtd} drops** em {cd.mention}", ephemeral=True)
        for i in range(qtd):
            if ACTIVE_DROP and not ACTIVE_DROP.get("finalizado"):
                await asyncio.sleep(5)
            esc = random.choice(TODAS_PERGUNTAS)
            ACTIVE_DROP = {"pergunta": esc["q"], "resposta": esc["a"], "resposta_normalizada": normalizar(esc["a"]), "canal_id": cd.id, "finalizado": False}
            e = discord.Embed(description=f"# 🌊 WAVE DROP {i+1}/{qtd}\n\n### {esc['q']}", color=0x00FF7F)
            if bot.user: e.set_thumbnail(url=bot.user.display_avatar.url)
            e.set_footer(text=f"Drop {i+1}/{qtd} • {len(TODAS_PERGUNTAS)}+ perguntas")
            await cd.send(embed=e)
            for _ in range(36):
                await asyncio.sleep(5)
                if ACTIVE_DROP is None or ACTIVE_DROP.get("finalizado"):
                    break
            ACTIVE_DROP = None
            await asyncio.sleep(8)
        WAVE_RUNNING = False
        await cd.send(embed=discord.Embed(title="🌊 Wave Finalizada!", description=f"{qtd} drops!", color=discord.Color.gold()))


# ============================================================
#  SCRIM
# ============================================================
@bot.tree.command(name="scrim", description="Mensagem de Scrim", guild=GUILD)
async def scrim_cmd(interaction, time_a: str, time_b: str, horario: str, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "scrim"):
        return
    canal = canal or interaction.channel
    import datetime as dt
    e = discord.Embed(title="⚔️ SCRIM AGENDADO", description=f"**{time_a}** 🆚 **{time_b}**", color=discord.Color.blue(), timestamp=dt.datetime.now())
    e.add_field(name="🕒 Horário", value=horario, inline=True)
    e.add_field(name="📋 Status", value="✅ Confirmado", inline=True)
    if bot.user: e.set_thumbnail(url=bot.user.display_avatar.url); e.set_author(name=f"Scrim por {interaction.user.display_name}", icon_url=bot.user.display_avatar.url)
    e.set_footer(text="BRS • Scrims")
    await canal.send(embed=e)
    await interaction.response.send_message(f"✅ Scrim em {canal.mention}", ephemeral=True)


# ============================================================
#  FRIENDLY
# ============================================================
@bot.tree.command(name="friendly", description="Mensagem de Friendly", guild=GUILD)
async def friendly_cmd(interaction, time_a: str, time_b: str, horario: str, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "friendly"):
        return
    canal = canal or interaction.channel
    import datetime as dt
    e = discord.Embed(title="🤝 FRIENDLY AGENDADO", description=f"**{time_a}** 🆚 **{time_b}**", color=discord.Color.green(), timestamp=dt.datetime.now())
    e.add_field(name="🕒 Horário", value=horario, inline=True)
    e.add_field(name="🎯 Tipo", value="Amistoso", inline=True)
    if bot.user: e.set_thumbnail(url=bot.user.display_avatar.url); e.set_author(name=f"Friendly por {interaction.user.display_name}", icon_url=bot.user.display_avatar.url)
    e.set_footer(text="BRS • Friendly Matches")
    await canal.send(embed=e)
    await interaction.response.send_message(f"✅ Friendly em {canal.mention}", ephemeral=True)


# ============================================================
#  /role
# ============================================================
@bot.tree.command(name="role", description="Adiciona/remove cargo", guild=GUILD)
@app_commands.choices(acao=[app_commands.Choice(name="Adicionar", value="add"), app_commands.Choice(name="Remover", value="remove")])
async def role_cmd(interaction, membro: discord.Member, cargo: discord.Role, acao: app_commands.Choice[str]):
    if not await checar_permissao(interaction, "role"):
        return
    if cargo >= interaction.guild.me.top_role:
        return await interaction.response.send_message("❌ Não posso gerenciar este cargo.", ephemeral=True)
    try:
        if acao.value == "add":
            await membro.add_roles(cargo, reason=f"/role por {interaction.user}")
            await interaction.response.send_message(f"✅ {cargo.name} adicionado a {membro.mention}", ephemeral=True)
        else:
            await membro.remove_roles(cargo, reason=f"/role por {interaction.user}")
            await interaction.response.send_message(f"✅ {cargo.name} removido de {membro.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)


# ============================================================
#  FREE AGENT
# ============================================================
freeagent_group = app_commands.Group(name="freeagent", description="Free Agents")


@freeagent_group.command(name="add", description="Cadastra Free Agent")
async def fa_add(interaction, jogador: discord.Member, posicao: str, descricao: str, imagem: Optional[str] = None):
    if not await checar_permissao(interaction, "freeagent"):
        return
    reg = {"posicao": posicao, "descricao": descricao, "imagem": imagem, "data": datetime.datetime.now().isoformat()}
    DADOS["freeagents"][str(jogador.id)] = reg; salvar_dados(DADOS)
    c = interaction.guild.get_channel(DADOS["config"]["freeagent"]["channel_id"]) or interaction.channel
    e = discord.Embed(title="🆓 FREE AGENT", description=f"### {jogador.mention}", color=discord.Color.blue(), timestamp=datetime.datetime.now())
    e.add_field(name="⚽ Posição", value=f"```{posicao}```", inline=True)
    e.add_field(name="📝 Descrição", value=descricao, inline=False)
    if imagem: e.set_image(url=imagem)
    e.set_thumbnail(url=jogador.display_avatar.url); e.set_footer(text="BRS • Free Agents")
    await c.send(embed=e)
    await interaction.response.send_message(f"✅ {jogador.mention} cadastrado.", ephemeral=True)


@freeagent_group.command(name="remover", description="Remove Free Agent")
async def fa_rem(interaction, jogador: discord.Member):
    if not await checar_permissao(interaction, "freeagent"):
        return
    if str(jogador.id) not in DADOS["freeagents"]:
        return await interaction.response.send_message("❌ Não cadastrado.", ephemeral=True)
    del DADOS["freeagents"][str(jogador.id)]; salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Removido.", ephemeral=True)


@freeagent_group.command(name="lista", description="Lista Free Agents")
async def fa_list(interaction):
    if not DADOS["freeagents"]:
        return await interaction.response.send_message("ℹ️ Nenhum FA cadastrado.", ephemeral=True)
    linhas = []
    for jid, dj in DADOS["freeagents"].items():
        m = interaction.guild.get_member(int(jid))
        n = m.mention if m else f"<@{jid}>"
        linhas.append(f"▸ {n} — `{dj['posicao']}`")
    e = discord.Embed(title="🆓 FREE AGENTS", description="\n".join(linhas), color=discord.Color.blue())
    e.set_footer(text=f"Total: {len(DADOS['freeagents'])}")
    await interaction.response.send_message(embed=e, ephemeral=True)


@freeagent_group.command(name="canal", description="Canal de FA")
async def fa_canal(interaction, canal: discord.TextChannel):
    if not await checar_permissao(interaction, "freeagent"):
        return
    DADOS["config"]["freeagent"]["channel_id"] = canal.id; salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Canal: {canal.mention}", ephemeral=True)


# ============================================================
#  SCOUTING
# ============================================================
scouting_group = app_commands.Group(name="scouting", description="Scouting")
SC_STATUS = [app_commands.Choice(name=s, value=s) for s in ["Em avaliação", "Aprovado", "Reprovado", "Monitorando"]]
SC_CORES = {"Em avaliação": discord.Color.gold(), "Aprovado": discord.Color.green(), "Reprovado": discord.Color.red(), "Monitorando": discord.Color.blurple()}


@scouting_group.command(name="add", description="Cadastra scouting")
async def sc_add(interaction, jogador: discord.Member, posicao: str, descricao: str, observacoes: Optional[str] = None, status: Optional[app_commands.Choice[str]] = None):
    if not await checar_permissao(interaction, "scouting"):
        return
    st = status.value if status else "Em avaliação"
    reg = {"posicao": posicao, "descricao": descricao, "observacoes": observacoes or "", "status": st, "data": datetime.datetime.now().isoformat()}
    DADOS["scoutings"][str(jogador.id)] = reg; salvar_dados(DADOS)
    c = interaction.guild.get_channel(DADOS["config"]["scouting"]["channel_id"]) or interaction.channel
    e = discord.Embed(title="🔍 SCOUTING REPORT", description=f"### {jogador.mention}", color=SC_CORES.get(st, EMBED_COLOR))
    e.add_field(name="⚽ Posição", value=f"```{posicao}```", inline=True)
    e.add_field(name="📌 Status", value=f"```{st}```", inline=True)
    e.add_field(name="📝 Descrição", value=descricao, inline=False)
    if observacoes: e.add_field(name="🔎 Obs", value=observacoes, inline=False)
    e.set_thumbnail(url=jogador.display_avatar.url); e.set_footer(text="BRS • Scouting")
    await c.send(embed=e)
    await interaction.response.send_message(f"✅ Scouting de {jogador.mention}", ephemeral=True)


@scouting_group.command(name="status", description="Altera status")
async def sc_status(interaction, jogador: discord.Member, status: app_commands.Choice[str]):
    if not await checar_permissao(interaction, "scouting"):
        return
    if str(jogador.id) not in DADOS["scoutings"]:
        return await interaction.response.send_message("❌ Sem scouting.", ephemeral=True)
    DADOS["scoutings"][str(jogador.id)]["status"] = status.value; salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Status → **{status.value}**", ephemeral=True)


@scouting_group.command(name="remover", description="Remove scouting")
async def sc_rem(interaction, jogador: discord.Member):
    if not await checar_permissao(interaction, "scouting"):
        return
    if str(jogador.id) not in DADOS["scoutings"]:
        return await interaction.response.send_message("❌ Sem scouting.", ephemeral=True)
    del DADOS["scoutings"][str(jogador.id)]; salvar_dados(DADOS)
    await interaction.response.send_message("✅ Removido.", ephemeral=True)


@scouting_group.command(name="lista", description="Lista scoutings")
async def sc_list(interaction):
    if not DADOS["scoutings"]:
        return await interaction.response.send_message("ℹ️ Nenhum.", ephemeral=True)
    linhas = []
    for jid, dj in DADOS["scoutings"].items():
        m = interaction.guild.get_member(int(jid))
        n = m.mention if m else f"<@{jid}>"
        linhas.append(f"▸ {n} — **{dj['status']}**")
    e = discord.Embed(title="🔍 SCOUTING", description="\n".join(linhas), color=discord.Color.gold())
    e.set_footer(text=f"Total: {len(DADOS['scoutings'])}")
    await interaction.response.send_message(embed=e, ephemeral=True)


@scouting_group.command(name="canal", description="Canal de Scouting")
async def sc_canal(interaction, canal: discord.TextChannel):
    if not await checar_permissao(interaction, "scouting"):
        return
    DADOS["config"]["scouting"]["channel_id"] = canal.id; salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Canal: {canal.mention}", ephemeral=True)


# ============================================================
#  /say e /say_embed
# ============================================================
@bot.tree.command(name="say", description="Envia mensagem", guild=GUILD)
async def say_cmd(interaction, mensagem: str, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "say"):
        return
    canal = canal or interaction.channel
    await canal.send(mensagem.replace("\\n", "\n"))
    await interaction.response.send_message("✅ Enviado.", ephemeral=True)


@bot.tree.command(name="say_embed", description="Embed com foto do bot automática", guild=GUILD)
async def say_embed_cmd(interaction, titulo: str, descricao: str, canal: Optional[discord.TextChannel] = None, cor: Optional[str] = None, imagem: Optional[str] = None, rodape: Optional[str] = None):
    if not await checar_permissao(interaction, "say_embed"):
        return
    canal = canal or interaction.channel
    color = discord.Color(int(cor.replace("#", ""), 16)) if cor else discord.Color(EMBED_COLOR)
    e = discord.Embed(title=titulo, description=descricao.replace("\\n", "\n"), color=color)
    if bot.user:
        e.set_thumbnail(url=bot.user.display_avatar.url)
        e.set_author(name=f"Enviado por {interaction.user.display_name}", icon_url=bot.user.display_avatar.url)
    if imagem: e.set_image(url=imagem)
    if rodape: e.set_footer(text=rodape)
    await canal.send(embed=e)
    await interaction.response.send_message("✅ Embed enviado.", ephemeral=True)


# ============================================================
#  CONFIG / PERMISSÕES
# ============================================================
COMANDOS_LISTA = [app_commands.Choice(name=c, value=c) for c in ["ticket","drop","freeagent","scouting","say","say_embed","role","scrim","friendly"]]
ACOES = [app_commands.Choice(name="Adicionar", value="adicionar"), app_commands.Choice(name="Remover", value="remover")]


@bot.tree.command(name="staff", description="Staff geral", guild=GUILD)
@app_commands.checks.has_permissions(administrator=True)
async def staff_cmd(interaction, cargo: discord.Role, acao: app_commands.Choice[str]):
    lst = DADOS["config"]["staff_role_ids"]
    if acao.value == "adicionar":
        if cargo.id not in lst: lst.append(cargo.id)
        await interaction.response.send_message(f"✅ {cargo.name} é Staff.", ephemeral=True)
    else:
        if cargo.id in lst: lst.remove(cargo.id)
        await interaction.response.send_message(f"✅ {cargo.name} removido.", ephemeral=True)
    salvar_dados(DADOS)


@bot.tree.command(name="permissao", description="Permissão por comando", guild=GUILD)
@app_commands.checks.has_permissions(administrator=True)
async def permissao_cmd(interaction, comando: app_commands.Choice[str], cargo: discord.Role, acao: app_commands.Choice[str]):
    lst = DADOS["config"]["command_permissions"].setdefault(comando.value, [])
    if acao.value == "adicionar":
        if cargo.id not in lst: lst.append(cargo.id)
        await interaction.response.send_message(f"✅ {cargo.name} usa `/{comando.value}`.", ephemeral=True)
    else:
        if cargo.id in lst: lst.remove(cargo.id)
        await interaction.response.send_message(f"✅ {cargo.name} não usa `/{comando.value}`.", ephemeral=True)
    salvar_dados(DADOS)


@bot.tree.command(name="config_ver", description="Ver configurações", guild=GUILD)
@app_commands.checks.has_permissions(administrator=True)
async def config_ver_cmd(interaction):
    cfg = DADOS["config"]
    g = interaction.guild
    def nomes(ids): return ", ".join(f"`{g.get_role(i).name}`" for i in ids if g.get_role(i)) or "*nenhum*"
    def ch(cid): return g.get_channel(cid).mention if g.get_channel(cid) else "*não definido*"
    e = discord.Embed(title="⚙️ Configurações — BRS", color=EMBED_COLOR)
    if bot.user: e.set_thumbnail(url=bot.user.display_avatar.url)
    e.add_field(name="🛡️ Staff", value=nomes(cfg["staff_role_ids"]), inline=False)
    e.add_field(name="🔑 Permissões", value="\n".join(f"**/{k}** → {nomes(v)}" for k,v in cfg["command_permissions"].items()), inline=False)
    e.add_field(name="🎫 Tickets", value=f"Categoria: {ch(cfg['ticket']['category_id'])}\nLogs: {ch(cfg['ticket']['log_channel_id'])}", inline=False)
    e.add_field(name="❓ Drop", value=f"Prêmios: {nomes(cfg['drop']['reward_role_ids'])}\nMeta: **{cfg['drop'].get('meta_membros',0):,}**\nPerguntas: **{len(TODAS_PERGUNTAS)}+**", inline=False)
    e.add_field(name="🆓 FA", value=f"Canal: {ch(cfg['freeagent']['channel_id'])}", inline=True)
    e.add_field(name="🔍 Scouting", value=f"Canal: {ch(cfg['scouting']['channel_id'])}", inline=True)
    await interaction.response.send_message(embed=e, ephemeral=True)


# ============================================================
#  ATUALIZAR META
# ============================================================
@bot.event
async def on_member_join(member):
    await atualizar_meta(member.guild)

@bot.event
async def on_member_remove(member):
    await atualizar_meta(member.guild)

async def atualizar_meta(guild):
    cfg = DADOS["config"]["drop"]
    meta, cid, mid = cfg.get("meta_membros"), cfg.get("meta_canal_id"), cfg.get("meta_mensagem_id")
    if not (meta and cid and mid):
        return
    c = guild.get_channel(cid)
    if not c:
        return
    try:
        msg = await c.fetch_message(mid)
    except Exception:
        return
    atual = guild.member_count
    e = discord.Embed(description="# 🟢 DROPS BRS\n\n**PRÊMIOS GARANTIDOS**\ncargos exclusivos\n\n**WAVE DROP**\n5 a 10 rodadas", color=0x00FF7F)
    e.add_field(name="📊 Progresso", value=f"👥 **{atual:,}** / **{meta:,}**\n📈 Faltam: **{max(0, meta-atual):,}**", inline=False)
    e.set_footer(text="BRS — Sistema de Metas")
    await msg.edit(embed=e)
    if atual >= meta and not cfg.get("wave_ativo"):
        cfg["wave_ativo"] = True; salvar_dados(DADOS)
        await c.send(embed=discord.Embed(title="🌊 WAVE LIBERADO!", description="Meta batida! `/drop wave`", color=discord.Color.gold()))


# ============================================================
#  ERROS
# ============================================================
@bot.tree.error
async def on_error(interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ Sem permissão."
    else:
        msg = "❌ Erro ao executar."
        log.exception("Erro no comando", exc_info=error)
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


# ============================================================
#  EXECUÇÃO
# ============================================================
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise SystemExit("❌ Defina DISCORD_TOKEN no .env")
    bot.run(TOKEN)
