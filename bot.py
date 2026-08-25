"""
Bot Discord completo — BRS (Brazilian Roblox Soccer)
Prefixo: ,
Slash: /

Recursos:
  - Tickets
  - Drop estilo PAFO (select menu + cargos 5 dias)
  - Meta de membros → Wave Drop
  - Free Agent / Scouting
  - /role
  - /say e /say_embed
  - Permissões e config
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

# Cargos de recompensa do Drop
DROP_REWARD_ROLES = {
    1541835699873914900: {"nome": "Olheiro (5 Dias)", "emoji": "🔍", "desc": "Cargo de Olheiro por 5 dias"},
    1541832115052871830: {"nome": "Scrim Hoster (5 Dias)", "emoji": "⚔️", "desc": "Pode hostear scrims por 5 dias"},
    1541836120382382100: {"nome": "Pic Perm (5 Dias)", "emoji": "💥", "desc": "Permissão de foto por 5 dias"},
}
# ============================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("brs-bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

ACTIVE_DROP: Optional[dict] = None
WAVE_RUNNING = False

# ============================================================
#  BANCO DE PERGUNTAS
# ============================================================
DROP_QUESTIONS = [
    {"q": "Qual time brasileiro é conhecido como 'O Mais Querido'?", "a": "flamengo"},
    {"q": "Quem é o maior artilheiro da história da seleção brasileira?", "a": "pele"},
    {"q": "Em que ano o Brasil ganhou a primeira Copa do Mundo?", "a": "1958"},
    {"q": "Quantos jogadores tem um time de futebol em campo?", "a": "11"},
    {"q": "Qual é o nome do estádio do Flamengo e Fluminense?", "a": "maracana"},
    {"q": "Quem é o Rei do Futebol?", "a": "pele"},
    {"q": "Qual país sediou a Copa de 2014?", "a": "brasil"},
    {"q": "Qual time tem as cores preto e branco e é de São Paulo?", "a": "corinthians"},
    {"q": "O que significa a sigla BRS?", "a": "brazilian roblox soccer"},
    {"q": "Quantos títulos de Copa do Mundo o Brasil tem?", "a": "5"},
    {"q": "Qual é a capital do Brasil?", "a": "brasilia"},
    {"q": "Qual é o maior país da América do Sul?", "a": "brasil"},
    {"q": "Em que continente fica o Egito?", "a": "africa"},
    {"q": "Qual país tem a Torre Eiffel?", "a": "franca"},
    {"q": "Qual é a capital da Argentina?", "a": "buenos aires"},
    {"q": "Qual é o prato típico brasileiro feito com feijão preto?", "a": "feijoada"},
    {"q": "Qual é a moeda oficial do Brasil?", "a": "real"},
    {"q": "Qual é o esporte mais popular do Brasil?", "a": "futebol"},
    {"q": "Qual é a plataforma onde roda o Roblox Soccer?", "a": "roblox"},
    {"q": "Quanto é 7 x 8?", "a": "56"},
    {"q": "Quanto é 15 + 27?", "a": "42"},
    {"q": "Qual é a raiz quadrada de 144?", "a": "12"},
    {"q": "Quanto é 9²?", "a": "81"},
    {"q": "Em que ano o homem pisou na Lua?", "a": "1969"},
    {"q": "Quem descobriu o Brasil?", "a": "pedro alvares cabral"},
    {"q": "Qual é o planeta mais próximo do Sol?", "a": "mercurio"},
    {"q": "Qual é o maior mamífero do mundo?", "a": "baleia azul"},
    {"q": "Quantos continentes existem?", "a": "7"},
    {"q": "Qual é o maior órgão do corpo humano?", "a": "pele"},
    {"q": "O que é um hat-trick?", "a": "tres gols"},
]

def gerar_perguntas_extras() -> List[dict]:
    extras = []
    times = ["Flamengo", "Corinthians", "Palmeiras", "São Paulo", "Santos", "Grêmio", "Internacional", "Atlético-MG", "Cruzeiro", "Vasco"]
    for t in times:
        extras.append({"q": f"Qual é a cor principal do {t}?", "a": "vermelho" if t in ["Flamengo", "Internacional"] else "preto" if t in ["Corinthians", "Vasco"] else "verde" if t == "Palmeiras" else "branco"})
    for n in range(1, 41):
        extras.append({"q": f"Quanto é {n} + {n}?", "a": str(n * 2)})
        extras.append({"q": f"Quanto é {n} x 2?", "a": str(n * 2)})
    return extras

TODAS_PERGUNTAS = DROP_QUESTIONS + gerar_perguntas_extras()

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
            command_prefix=commands.when_mentioned_or(","),  # só vírgula (não repete mais)
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
    if ACTIVE_DROP and not ACTIVE_DROP.get("finalizado") and message.channel.id == ACTIVE_DROP["canal_id"]:
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

            role_ids = DADOS["config"]["drop"].get("reward_role_ids") or list(DROP_REWARD_ROLES.keys())
            roles = []
            for rid in role_ids:
                role = message.guild.get_role(rid)
                if role:
                    roles.append(role)

            try:
                if roles:
                    dm_embed = discord.Embed(
                        title="🎁 Você Venceu o Drop!",
                        description=(
                            "Você respondeu corretamente e garantiu seu prêmio!\n\n"
                            "Escolha abaixo qual cargo VIP você deseja receber:"
                        ),
                        color=discord.Color.gold()
                    )
                    dm_embed.set_footer(text="BRS — Drops System • Válido por 5 dias")
                    await vencedor.send(embed=dm_embed, view=DropRewardView(vencedor.id, roles))
                else:
                    await vencedor.send(
                        "🏆 Você venceu o Drop!\n\n"
                        "Porém nenhum cargo de recompensa está disponível no momento.\n"
                        "Avise a staff para configurar os cargos corretamente."
                    )
            except discord.Forbidden:
                await message.channel.send(
                    f"⚠️ {vencedor.mention}, não consegui te enviar DM.\n"
                    "Habilite **Mensagens Diretas** nas configurações de privacidade do servidor!"
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
    await interaction.response.send_message(f"✅ {alvo.mention} adicionado(a).", ephemeral=True)
    await interaction.channel.send(f"➕ {alvo.mention} adicionado(a) por {interaction.user.mention}.")


@ticket_group.command(name="remove", description="Remove membro/cargo do ticket.")
@app_commands.describe(alvo="Membro ou cargo")
async def ticket_remove(interaction: discord.Interaction, alvo: Union[discord.Member, discord.Role]):
    if not is_ticket_channel(interaction.channel):
        await interaction.response.send_message("❌ Só funciona dentro de um ticket.", ephemeral=True)
        return
    await interaction.channel.set_permissions(alvo, overwrite=None)
    await interaction.response.send_message(f"✅ {alvo.mention} removido(a).", ephemeral=True)
    await interaction.channel.send(f"➖ {alvo.mention} removido(a) por {interaction.user.mention}.")


# ============================================================
#  DROP
# ============================================================
class DropRewardSelect(discord.ui.Select):
    def __init__(self, user_id: int, roles: list[discord.Role]):
        options = []
        for role in roles:
            info = DROP_REWARD_ROLES.get(role.id, {
                "nome": f"{role.name} (5 Dias)",
                "emoji": "🏅",
                "desc": "Recompensa do Drop"
            })
            options.append(discord.SelectOption(
                label=info["nome"][:100],
                value=str(role.id),
                emoji=info["emoji"],
                description=info.get("desc", "Válido por 5 dias")[:100]
            ))
        super().__init__(
            placeholder="🎁 Escolha seu cargo VIP (válido por 5 dias)",
            min_values=1,
            max_values=1,
            options=options[:25]
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Essa recompensa não é sua.", ephemeral=True)
            return

        role_id = int(self.values[0])
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            await interaction.response.send_message("❌ Erro interno. Fale com a staff.", ephemeral=True)
            return

        member = guild.get_member(self.user_id)
        role = guild.get_role(role_id)

        if not member or not role:
            await interaction.response.send_message(
                "❌ Não consegui encontrar o cargo ou o membro.\n"
                "Provavelmente o cargo foi deletado ou o bot perdeu permissão.",
                ephemeral=True
            )
            return

        try:
            await member.add_roles(role, reason="Recompensa do Drop BRS (5 dias)")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Não tenho permissão para dar esse cargo.\n"
                "Peça para a staff colocar o cargo do bot **acima** dos cargos de prêmio.",
                ephemeral=True
            )
            return

        expiracao = (datetime.datetime.utcnow() + datetime.timedelta(days=5)).isoformat()
        DADOS.setdefault("drop_expiracoes", {})[str(member.id)] = {
            "role_id": role_id,
            "expira_em": expiracao
        }
        salvar_dados(DADOS)

        embed = discord.Embed(
            title="✅ Drop Resgatado com Sucesso!",
            description=f"Você recebeu o cargo **{role.mention}**\n\nVálido por **5 dias**.",
            color=discord.Color.from_rgb(46, 204, 113)
        )
        embed.set_footer(text="BRS — Drops System")
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class DropRewardView(discord.ui.View):
    def __init__(self, user_id: int, roles: list[discord.Role]):
        super().__init__(timeout=600)
        if roles:
            self.add_item(DropRewardSelect(user_id, roles))


drop_group = app_commands.Group(name="drop", description="Sistema de Drops da BRS")


@drop_group.command(name="iniciar", description="Inicia um Drop (pergunta aleatória se não informar).")
@app_commands.describe(
    pergunta="Pergunta (deixe vazio = aleatória)",
    resposta="Resposta correta",
    canal="Canal do Drop"
)
async def drop_iniciar(
    interaction: discord.Interaction,
    pergunta: Optional[str] = None,
    resposta: Optional[str] = None,
    canal: Optional[discord.TextChannel] = None,
):
    if not await checar_permissao(interaction, "drop"):
        return

    global ACTIVE_DROP
    if ACTIVE_DROP and not ACTIVE_DROP.get("finalizado"):
        await interaction.response.send_message("❌ Já existe um Drop em andamento. Use `/drop cancelar`.", ephemeral=True)
        return

    if pergunta and not resposta:
        await interaction.response.send_message("❌ Se informar a pergunta, informe a resposta também.", ephemeral=True)
        return

    if not pergunta:
        escolha = random.choice(TODAS_PERGUNTAS)
        pergunta = escolha["q"]
        resposta = escolha["a"]

    canal_destino = canal
    if not canal_destino:
        canal_id = DADOS["config"]["drop"].get("default_channel_id")
        if canal_id:
            canal_destino = interaction.guild.get_channel(canal_id)
    canal_destino = canal_destino or interaction.channel

    ACTIVE_DROP = {
        "pergunta": pergunta,
        "resposta": resposta,
        "resposta_normalizada": normalizar(resposta),
        "canal_id": canal_destino.id,
        "finalizado": False,
    }

    embed = discord.Embed(
        description=(
            f"# ❓ DROP — BRS\n\n"
            f"### {pergunta}\n\n"
            f"Responda no chat! Quem acertar primeiro leva o prêmio 🏆"
        ),
        color=0x00FF7F
    )
    embed.add_field(name="🎁 Prêmios Garantidos", value="Cargos exclusivos a cada Drop vencido", inline=True)
    embed.add_field(name="⚡ Wave Drop", value="Vários drops seguidos quando a meta é batida", inline=True)
    embed.set_footer(text=f"Banco: {len(TODAS_PERGUNTAS)}+ perguntas • Boa sorte!")
    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    await canal_destino.send(embed=embed)
    await interaction.response.send_message(f"✅ Drop iniciado em {canal_destino.mention}.", ephemeral=True)


@drop_group.command(name="cancelar", description="Cancela o Drop em andamento.")
async def drop_cancelar(interaction: discord.Interaction):
    if not await checar_permissao(interaction, "drop"):
        return
    global ACTIVE_DROP
    if not ACTIVE_DROP or ACTIVE_DROP.get("finalizado"):
        await interaction.response.send_message("ℹ️ Não há Drop em andamento.", ephemeral=True)
        return
    canal = interaction.guild.get_channel(ACTIVE_DROP["canal_id"])
    ACTIVE_DROP = None
    if canal:
        await canal.send("🚫 O Drop foi cancelado pela staff.")
    await interaction.response.send_message("✅ Drop cancelado.", ephemeral=True)


@drop_group.command(name="premio_adicionar", description="Adiciona cargo aos prêmios.")
@app_commands.describe(cargo="Cargo")
async def drop_premio_adicionar(interaction: discord.Interaction, cargo: discord.Role):
    if not await checar_permissao(interaction, "drop"):
        return
    lst = DADOS["config"]["drop"]["reward_role_ids"]
    if cargo.id not in lst:
        lst.append(cargo.id)
        salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ **{cargo.name}** adicionado aos prêmios.", ephemeral=True)


@drop_group.command(name="premio_remover", description="Remove cargo dos prêmios.")
@app_commands.describe(cargo="Cargo")
async def drop_premio_remover(interaction: discord.Interaction, cargo: discord.Role):
    if not await checar_permissao(interaction, "drop"):
        return
    lst = DADOS["config"]["drop"]["reward_role_ids"]
    if cargo.id in lst:
        lst.remove(cargo.id)
        salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ **{cargo.name}** removido dos prêmios.", ephemeral=True)


@drop_group.command(name="canal_padrao", description="Define canal padrão dos Drops.")
@app_commands.describe(canal="Canal")
async def drop_canal_padrao(interaction: discord.Interaction, canal: discord.TextChannel):
    if not await checar_permissao(interaction, "drop"):
        return
    DADOS["config"]["drop"]["default_channel_id"] = canal.id
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Canal padrão: {canal.mention}", ephemeral=True)


@drop_group.command(name="meta", description="Define a meta de membros para Wave Drop.")
@app_commands.describe(quantidade="Quantidade de membros", canal="Canal da mensagem de progresso")
async def drop_meta(interaction: discord.Interaction, quantidade: int, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "drop"):
        return

    DADOS["config"]["drop"]["meta_membros"] = quantidade
    canal = canal or interaction.channel
    DADOS["config"]["drop"]["meta_canal_id"] = canal.id

    atual = interaction.guild.member_count
    faltam = max(0, quantidade - atual)

    embed = discord.Embed(
        description=(
            f"# 🟢 DROPS BRS\n\n"
            f"**PRÊMIOS GARANTIDOS**\n"
            f"cargos exclusivos a cada drop vencido\n\n"
            f"**VÁRIOS DROPS SEGUIDOS**\n"
            f"de 5 a 10 rodadas por meta batida\n\n"
            f"**CARGO PERMANENTE**\n"
            f"acumule vitórias e desbloqueie"
        ),
        color=0x00FF7F
    )
    embed.add_field(
        name="📊 Progresso atual",
        value=f"👥 Membros: **{atual:,}** / **{quantidade:,}**\n📈 Faltam: **{faltam:,}** membros",
        inline=False
    )
    embed.set_footer(text="Essa mensagem é atualizada automaticamente conforme o servidor cresce.\nBRS — Sistema de Metas")

    msg = await canal.send(embed=embed)
    DADOS["config"]["drop"]["meta_mensagem_id"] = msg.id
    salvar_dados(DADOS)

    await interaction.response.send_message(
        f"✅ Meta definida: **{quantidade:,}** membros\nMensagem em {canal.mention}",
        ephemeral=True
    )


@drop_group.command(name="wave", description="Inicia Wave Drop manualmente (5\~10 drops seguidos).")
@app_commands.describe(quantidade="Quantidade de drops (padrão 7)", canal="Canal")
async def drop_wave(interaction: discord.Interaction, quantidade: Optional[int] = 7, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "drop"):
        return

    global ACTIVE_DROP, WAVE_RUNNING

    if WAVE_RUNNING:
        await interaction.response.send_message("❌ Já existe uma Wave em andamento.", ephemeral=True)
        return

    canal_destino = canal or interaction.channel
    quantidade = max(3, min(quantidade or 7, 12))

    await interaction.response.send_message(
        f"🌊 Wave Drop iniciada! {quantidade} drops em {canal_destino.mention}",
        ephemeral=True
    )
    WAVE_RUNNING = True

    for i in range(quantidade):
        if ACTIVE_DROP and not ACTIVE_DROP.get("finalizado"):
            await asyncio.sleep(5)
            continue

        escolha = random.choice(TODAS_PERGUNTAS)
        ACTIVE_DROP = {
            "pergunta": escolha["q"],
            "resposta": escolha["a"],
            "resposta_normalizada": normalizar(escolha["a"]),
            "canal_id": canal_destino.id,
            "finalizado": False,
        }

        embed = discord.Embed(
            description=f"# 🌊 WAVE DROP {i+1}/{quantidade}\n\n### {escolha['q']}\n\nResponda no chat!",
            color=0x00FF7F
        )
        await canal_destino.send(embed=embed)

        for _ in range(36):
            await asyncio.sleep(5)
            if ACTIVE_DROP is None or ACTIVE_DROP.get("finalizado"):
                break

        ACTIVE_DROP = None
        await asyncio.sleep(8)

    WAVE_RUNNING = False
    await canal_destino.send(
        embed=discord.Embed(title="🌊 Wave Drop finalizada!", color=discord.Color.gold())
    )


@bot.event
async def on_member_join(member: discord.Member):
    await atualizar_meta(member.guild)


@bot.event
async def on_member_remove(member: discord.Member):
    await atualizar_meta(member.guild)


async def atualizar_meta(guild: discord.Guild):
    cfg = DADOS["config"]["drop"]
    meta = cfg.get("meta_membros")
    canal_id = cfg.get("meta_canal_id")
    msg_id = cfg.get("meta_mensagem_id")
    if not (meta and canal_id and msg_id):
        return
    canal = guild.get_channel(canal_id)
    if not canal:
        return
    try:
        msg = await canal.fetch_message(msg_id)
    except Exception:
        return

    atual = guild.member_count
    faltam = max(0, meta - atual)

    embed = discord.Embed(
        description=(
            f"# 🟢 DROPS BRS\n\n"
            f"**PRÊMIOS GARANTIDOS**\n"
            f"cargos exclusivos a cada drop vencido\n\n"
            f"**VÁRIOS DROPS SEGUIDOS**\n"
            f"de 5 a 10 rodadas por meta batida\n\n"
            f"**CARGO PERMANENTE**\n"
            f"acumule vitórias e desbloqueie"
        ),
        color=0x00FF7F
    )
    embed.add_field(
        name="📊 Progresso atual",
        value=f"👥 Membros: **{atual:,}** / **{meta:,}**\n📈 Faltam: **{faltam:,}** membros",
        inline=False
    )
    embed.set_footer(text="Essa mensagem é atualizada automaticamente conforme o servidor cresce.\nBRS — Sistema de Metas")
    await msg.edit(embed=embed)

    if atual >= meta and not cfg.get("wave_ativo"):
        cfg["wave_ativo"] = True
        salvar_dados(DADOS)
        await canal.send(embed=discord.Embed(
            title="🌊 WAVE DROP LIBERADO!",
            description=f"A meta de **{meta:,}** membros foi batida!\nUse `/drop wave` para iniciar.",
            color=discord.Color.gold()
        ))


# ============================================================
#  /role
# ============================================================
@bot.tree.command(name="role", description="Adiciona ou remove cargo de um membro.", guild=GUILD)
@app_commands.describe(membro="Membro", cargo="Cargo", acao="Adicionar ou Remover")
@app_commands.choices(acao=[
    app_commands.Choice(name="Adicionar", value="add"),
    app_commands.Choice(name="Remover", value="remove"),
])
async def role_cmd(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role, acao: app_commands.Choice[str]):
    if not await checar_permissao(interaction, "role"):
        return
    if cargo >= interaction.guild.me.top_role:
        await interaction.response.send_message("❌ Não posso gerenciar este cargo (acima do meu).", ephemeral=True)
        return
    if cargo >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Você não pode gerenciar um cargo igual/acima do seu.", ephemeral=True)
        return
    try:
        if acao.value == "add":
            await membro.add_roles(cargo, reason=f"/role por {interaction.user}")
            msg = f"✅ **{cargo.name}** adicionado a {membro.mention}."
        else:
            await membro.remove_roles(cargo, reason=f"/role por {interaction.user}")
            msg = f"✅ **{cargo.name}** removido de {membro.mention}."
        await interaction.response.send_message(msg, ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Sem permissão para gerenciar este cargo.", ephemeral=True)


# ============================================================
#  FREE AGENT
# ============================================================
def embed_freeagent(jogador_id: int, dados_jogador: dict, guild: discord.Guild) -> discord.Embed:
    membro = guild.get_member(jogador_id)
    embed = discord.Embed(
        title="🆓  FREE AGENT",
        description=f"### {membro.mention if membro else 'Jogador'}",
        color=discord.Color.from_rgb(52, 152, 219),
        timestamp=datetime.datetime.fromisoformat(dados_jogador["data"]),
    )
    embed.add_field(name="⚽ Posição", value=f"```{dados_jogador['posicao']}```", inline=True)
    embed.add_field(name="📝 Descrição", value=dados_jogador["descricao"], inline=False)
    if dados_jogador.get("imagem"):
        embed.set_image(url=dados_jogador["imagem"])
    if membro:
        embed.set_thumbnail(url=membro.display_avatar.url)
    embed.set_footer(text="BRS • Free Agents")
    return embed


freeagent_group = app_commands.Group(name="freeagent", description="Sistema de Free Agents")


@freeagent_group.command(name="add", description="Cadastra Free Agent.")
@app_commands.describe(jogador="Jogador", posicao="Posição", descricao="Descrição", imagem="URL imagem")
async def freeagent_add(interaction: discord.Interaction, jogador: discord.Member, posicao: str, descricao: str, imagem: Optional[str] = None):
    if not await checar_permissao(interaction, "freeagent"):
        return
    registro = {"posicao": posicao, "descricao": descricao, "imagem": imagem, "data": datetime.datetime.now().isoformat()}
    DADOS["freeagents"][str(jogador.id)] = registro
    salvar_dados(DADOS)
    canal_id = DADOS["config"]["freeagent"].get("channel_id")
    canal = interaction.guild.get_channel(canal_id) if canal_id else interaction.channel
    await canal.send(embed=embed_freeagent(jogador.id, registro, interaction.guild))
    await interaction.response.send_message(f"✅ {jogador.mention} cadastrado em {canal.mention}.", ephemeral=True)


@freeagent_group.command(name="remover", description="Remove Free Agent.")
@app_commands.describe(jogador="Jogador")
async def freeagent_remover(interaction: discord.Interaction, jogador: discord.Member):
    if not await checar_permissao(interaction, "freeagent"):
        return
    if str(jogador.id) not in DADOS["freeagents"]:
        await interaction.response.send_message("❌ Não está cadastrado.", ephemeral=True)
        return
    del DADOS["freeagents"][str(jogador.id)]
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ {jogador.mention} removido.", ephemeral=True)


@freeagent_group.command(name="editar", description="Edita Free Agent.")
@app_commands.describe(jogador="Jogador", posicao="Nova posição", descricao="Nova descrição", imagem="Nova imagem")
async def freeagent_editar(interaction: discord.Interaction, jogador: discord.Member, posicao: Optional[str] = None, descricao: Optional[str] = None, imagem: Optional[str] = None):
    if not await checar_permissao(interaction, "freeagent"):
        return
    registro = DADOS["freeagents"].get(str(jogador.id))
    if not registro:
        await interaction.response.send_message("❌ Não está cadastrado.", ephemeral=True)
        return
    if posicao: registro["posicao"] = posicao
    if descricao: registro["descricao"] = descricao
    if imagem: registro["imagem"] = imagem
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ {jogador.mention} atualizado.", ephemeral=True)


@freeagent_group.command(name="buscar", description="Busca Free Agent.")
@app_commands.describe(jogador="Jogador")
async def freeagent_buscar(interaction: discord.Interaction, jogador: discord.Member):
    registro = DADOS["freeagents"].get(str(jogador.id))
    if not registro:
        await interaction.response.send_message("❌ Não está cadastrado.", ephemeral=True)
        return
    await interaction.response.send_message(embed=embed_freeagent(jogador.id, registro, interaction.guild), ephemeral=True)


@freeagent_group.command(name="lista", description="Lista Free Agents.")
async def freeagent_lista(interaction: discord.Interaction):
    itens = DADOS["freeagents"]
    if not itens:
        await interaction.response.send_message("ℹ️ Nenhum Free Agent cadastrado.", ephemeral=True)
        return
    linhas = []
    for jid, dj in itens.items():
        m = interaction.guild.get_member(int(jid))
        nome = m.mention if m else f"<@{jid}>"
        linhas.append(f"▸ {nome} — `{dj['posicao']}`")
    embed = discord.Embed(title="🆓 FREE AGENTS — BRS", description="\n".join(linhas), color=discord.Color.from_rgb(52, 152, 219))
    embed.set_footer(text=f"Total: {len(itens)}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@freeagent_group.command(name="canal", description="Define canal de Free Agents.")
@app_commands.describe(canal="Canal")
async def freeagent_canal(interaction: discord.Interaction, canal: discord.TextChannel):
    if not await checar_permissao(interaction, "freeagent"):
        return
    DADOS["config"]["freeagent"]["channel_id"] = canal.id
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Canal: {canal.mention}", ephemeral=True)


# ============================================================
#  SCOUTING
# ============================================================
STATUS_CHOICES = [
    app_commands.Choice(name="Em avaliação", value="Em avaliação"),
    app_commands.Choice(name="Aprovado", value="Aprovado"),
    app_commands.Choice(name="Reprovado", value="Reprovado"),
    app_commands.Choice(name="Monitorando", value="Monitorando"),
]
STATUS_CORES = {
    "Em avaliação": discord.Color.gold(),
    "Aprovado": discord.Color.green(),
    "Reprovado": discord.Color.red(),
    "Monitorando": discord.Color.blurple(),
}


def embed_scouting(jogador_id: int, dj: dict, guild: discord.Guild) -> discord.Embed:
    membro = guild.get_member(jogador_id)
    embed = discord.Embed(
        title="🔍  SCOUTING REPORT",
        description=f"### {membro.mention if membro else 'Jogador'}",
        color=STATUS_CORES.get(dj["status"], discord.Color(EMBED_COLOR)),
        timestamp=datetime.datetime.fromisoformat(dj["data"]),
    )
    embed.add_field(name="⚽ Posição", value=f"```{dj['posicao']}```", inline=True)
    embed.add_field(name="📌 Status", value=f"```{dj['status']}```", inline=True)
    embed.add_field(name="📝 Descrição", value=dj["descricao"], inline=False)
    if dj.get("observacoes"):
        embed.add_field(name="🔎 Observações", value=dj["observacoes"], inline=False)
    if membro:
        embed.set_thumbnail(url=membro.display_avatar.url)
    embed.set_footer(text="BRS • Scouting")
    return embed


scouting_group = app_commands.Group(name="scouting", description="Sistema de Scouting")


@scouting_group.command(name="add", description="Cadastra scouting.")
@app_commands.describe(jogador="Jogador", posicao="Posição", descricao="Descrição", observacoes="Observações", status="Status")
@app_commands.choices(status=STATUS_CHOICES)
async def scouting_add(interaction: discord.Interaction, jogador: discord.Member, posicao: str, descricao: str, observacoes: Optional[str] = None, status: Optional[app_commands.Choice[str]] = None):
    if not await checar_permissao(interaction, "scouting"):
        return
    registro = {
        "posicao": posicao, "descricao": descricao, "observacoes": observacoes or "",
        "status": status.value if status else "Em avaliação", "data": datetime.datetime.now().isoformat(),
    }
    DADOS["scoutings"][str(jogador.id)] = registro
    salvar_dados(DADOS)
    canal_id = DADOS["config"]["scouting"].get("channel_id")
    canal = interaction.guild.get_channel(canal_id) if canal_id else interaction.channel
    await canal.send(embed=embed_scouting(jogador.id, registro, interaction.guild))
    await interaction.response.send_message(f"✅ Scouting de {jogador.mention} em {canal.mention}.", ephemeral=True)


@scouting_group.command(name="editar", description="Edita scouting.")
@app_commands.describe(jogador="Jogador", posicao="Posição", descricao="Descrição", observacoes="Observações")
async def scouting_editar(interaction: discord.Interaction, jogador: discord.Member, posicao: Optional[str] = None, descricao: Optional[str] = None, observacoes: Optional[str] = None):
    if not await checar_permissao(interaction, "scouting"):
        return
    registro = DADOS["scoutings"].get(str(jogador.id))
    if not registro:
        await interaction.response.send_message("❌ Sem scouting cadastrado.", ephemeral=True)
        return
    if posicao: registro["posicao"] = posicao
    if descricao: registro["descricao"] = descricao
    if observacoes: registro["observacoes"] = observacoes
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Scouting de {jogador.mention} atualizado.", ephemeral=True)


@scouting_group.command(name="status", description="Altera status do scouting.")
@app_commands.describe(jogador="Jogador", status="Novo status")
@app_commands.choices(status=STATUS_CHOICES)
async def scouting_status(interaction: discord.Interaction, jogador: discord.Member, status: app_commands.Choice[str]):
    if not await checar_permissao(interaction, "scouting"):
        return
    registro = DADOS["scoutings"].get(str(jogador.id))
    if not registro:
        await interaction.response.send_message("❌ Sem scouting cadastrado.", ephemeral=True)
        return
    registro["status"] = status.value
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Status de {jogador.mention} → **{status.value}**.", ephemeral=True)


@scouting_group.command(name="remover", description="Remove scouting.")
@app_commands.describe(jogador="Jogador")
async def scouting_remover(interaction: discord.Interaction, jogador: discord.Member):
    if not await checar_permissao(interaction, "scouting"):
        return
    if str(jogador.id) not in DADOS["scoutings"]:
        await interaction.response.send_message("❌ Sem scouting cadastrado.", ephemeral=True)
        return
    del DADOS["scoutings"][str(jogador.id)]
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Scouting de {jogador.mention} removido.", ephemeral=True)


@scouting_group.command(name="buscar", description="Busca scouting.")
@app_commands.describe(jogador="Jogador")
async def scouting_buscar(interaction: discord.Interaction, jogador: discord.Member):
    registro = DADOS["scoutings"].get(str(jogador.id))
    if not registro:
        await interaction.response.send_message("❌ Sem scouting cadastrado.", ephemeral=True)
        return
    await interaction.response.send_message(embed=embed_scouting(jogador.id, registro, interaction.guild), ephemeral=True)


@scouting_group.command(name="lista", description="Lista scoutings.")
async def scouting_lista(interaction: discord.Interaction):
    itens = DADOS["scoutings"]
    if not itens:
        await interaction.response.send_message("ℹ️ Nenhum scouting cadastrado.", ephemeral=True)
        return
    linhas = []
    for jid, dj in itens.items():
        m = interaction.guild.get_member(int(jid))
        nome = m.mention if m else f"<@{jid}>"
        linhas.append(f"▸ {nome} — `{dj['posicao']}` — **{dj['status']}**")
    embed = discord.Embed(title="🔍 SCOUTING — BRS", description="\n".join(linhas), color=discord.Color.from_rgb(241, 196, 15))
    embed.set_footer(text=f"Total: {len(itens)}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@scouting_group.command(name="canal", description="Define canal de Scouting.")
@app_commands.describe(canal="Canal")
async def scouting_canal(interaction: discord.Interaction, canal: discord.TextChannel):
    if not await checar_permissao(interaction, "scouting"):
        return
    DADOS["config"]["scouting"]["channel_id"] = canal.id
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Canal: {canal.mention}", ephemeral=True)


# ============================================================
#  /say e /say_embed
# ============================================================
@bot.tree.command(name="say", description="Envia mensagem pelo bot.", guild=GUILD)
@app_commands.describe(mensagem="Texto", canal="Canal")
async def say_cmd(interaction: discord.Interaction, mensagem: str, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "say"):
        return
    canal = canal or interaction.channel
    await canal.send(mensagem.replace("\\n", "\n"))
    await interaction.response.send_message(f"✅ Enviado em {canal.mention}.", ephemeral=True)


@bot.tree.command(name="say_embed", description="Envia embed pelo bot (foto do bot automática).", guild=GUILD)
@app_commands.describe(
    titulo="Título", descricao="Descrição (\\n para quebra)", canal="Canal",
    cor="Cor hex (#FF0000)", imagem="URL imagem grande", rodape="Rodapé", autor="Autor"
)
async def say_embed_cmd(
    interaction: discord.Interaction, titulo: str, descricao: str,
    canal: Optional[discord.TextChannel] = None, cor: Optional[str] = None,
    imagem: Optional[str] = None, rodape: Optional[str] = None, autor: Optional[str] = None,
):
    if not await checar_permissao(interaction, "say_embed"):
        return
    canal = canal or interaction.channel
    if cor:
        try:
            color = discord.Color(int(cor.replace("#", ""), 16))
        except ValueError:
            await interaction.response.send_message("❌ Cor inválida. Ex: #FF0000", ephemeral=True)
            return
    else:
        color = discord.Color(EMBED_COLOR)

    embed = discord.Embed(title=titulo, description=descricao.replace("\\n", "\n"), color=color)
    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    if imagem:
        embed.set_image(url=imagem)
    if rodape:
        embed.set_footer(text=rodape)
    if autor:
        embed.set_author(name=autor, icon_url=bot.user.display_avatar.url if bot.user else None)

    await canal.send(embed=embed)
    await interaction.response.send_message(f"✅ Embed enviado em {canal.mention}.", ephemeral=True)


# ============================================================
#  PERMISSÕES E CONFIG
# ============================================================
COMANDOS_CONFIGURAVEIS = [
    app_commands.Choice(name="ticket", value="ticket"),
    app_commands.Choice(name="drop", value="drop"),
    app_commands.Choice(name="freeagent", value="freeagent"),
    app_commands.Choice(name="scouting", value="scouting"),
    app_commands.Choice(name="say", value="say"),
    app_commands.Choice(name="say_embed", value="say_embed"),
    app_commands.Choice(name="role", value="role"),
]
ACAO_CHOICES = [
    app_commands.Choice(name="Adicionar", value="adicionar"),
    app_commands.Choice(name="Remover", value="remover"),
]


@bot.tree.command(name="staff", description="Define cargo como Staff geral.", guild=GUILD)
@app_commands.describe(cargo="Cargo", acao="Adicionar ou Remover")
@app_commands.choices(acao=ACAO_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def staff_cmd(interaction: discord.Interaction, cargo: discord.Role, acao: app_commands.Choice[str]):
    lst = DADOS["config"]["staff_role_ids"]
    if acao.value == "adicionar":
        if cargo.id not in lst:
            lst.append(cargo.id)
        msg = f"✅ **{cargo.name}** agora é Staff geral."
    else:
        if cargo.id in lst:
            lst.remove(cargo.id)
        msg = f"✅ **{cargo.name}** removido da Staff geral."
    salvar_dados(DADOS)
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="permissao", description="Libera/revoga cargo para um comando.", guild=GUILD)
@app_commands.describe(comando="Comando", cargo="Cargo", acao="Adicionar ou Remover")
@app_commands.choices(comando=COMANDOS_CONFIGURAVEIS, acao=ACAO_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def permissao_cmd(interaction: discord.Interaction, comando: app_commands.Choice[str], cargo: discord.Role, acao: app_commands.Choice[str]):
    lst = DADOS["config"]["command_permissions"].setdefault(comando.value, [])
    if acao.value == "adicionar":
        if cargo.id not in lst:
            lst.append(cargo.id)
        msg = f"✅ **{cargo.name}** pode usar `/{comando.value}`."
    else:
        if cargo.id in lst:
            lst.remove(cargo.id)
        msg = f"✅ **{cargo.name}** não pode mais usar `/{comando.value}`."
    salvar_dados(DADOS)
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="config_ver", description="Mostra configurações atuais.", guild=GUILD)
@app_commands.checks.has_permissions(administrator=True)
async def config_ver_cmd(interaction: discord.Interaction):
    cfg = DADOS["config"]
    guild = interaction.guild

    def nomes_cargos(ids):
        nomes = [guild.get_role(i).name for i in ids if guild.get_role(i)]
        return ", ".join(f"`{n}`" for n in nomes) if nomes else "*nenhum*"

    def nome_canal(cid):
        c = guild.get_channel(cid) if cid else None
        return c.mention if c else "*não definido*"

    embed = discord.Embed(
        title="⚙️ Configurações — BRS Bot",
        description="Visão geral das configurações atuais.",
        color=EMBED_COLOR,
        timestamp=datetime.datetime.now(),
    )
    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(name="🛡️ Staff Geral", value=nomes_cargos(cfg["staff_role_ids"]), inline=False)

    perms = "\n".join(f"**/{k}** → {nomes_cargos(v)}" for k, v in cfg["command_permissions"].items())
    embed.add_field(name="🔑 Permissões por Comando", value=perms or "*nenhuma*", inline=False)

    embed.add_field(
        name="🎫 Tickets",
        value=(
            f"Categoria: {nome_canal(cfg['ticket']['category_id'])}\n"
            f"Cargos: {nomes_cargos(cfg['ticket']['staff_role_ids'])}\n"
            f"Logs: {nome_canal(cfg['ticket']['log_channel_id'])}"
        ),
        inline=False,
    )
    embed.add_field(
        name="❓ Drop",
        value=(
            f"Prêmios: {nomes_cargos(cfg['drop']['reward_role_ids'])}\n"
            f"Canal padrão: {nome_canal(cfg['drop']['default_channel_id'])}\n"
            f"Meta: **{cfg['drop'].get('meta_membros', 0):,}** membros\n"
            f"Perguntas: **{len(TODAS_PERGUNTAS)}+**"
        ),
        inline=False,
    )
    embed.add_field(name="🆓 Free Agent", value=f"Canal: {nome_canal(cfg['freeagent']['channel_id'])}", inline=True)
    embed.add_field(name="🔍 Scouting", value=f"Canal: {nome_canal(cfg['scouting']['channel_id'])}", inline=True)
    embed.set_footer(text="BRS Bot • /staff e /permissao para gerenciar acessos")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
#  ERROS
# ============================================================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ Você não tem permissão para usar este comando."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Aguarde {error.retry_after:.1f}s."
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
        raise SystemExit("❌ Defina DISCORD_TOKEN no .env ou variável de ambiente.")
    bot.run(TOKEN)
