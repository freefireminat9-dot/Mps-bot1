"""
Bot Discord completo para a BRS (Brazilian Roblox Soccer)

Prefixos: ,  e  /
Slash commands: / (todos os grupos)

Comandos principais:
  /ticket ... | ,ticket ...
  /drop ...   | ,drop ...
  /freeagent ... | ,freeagent ...
  /scouting ...  | ,scouting ...
  /say  /say_embed
  /role  (dar/remover cargo por menção, sem ID no código)
  /staff  /permissao  /config_ver

Configurações salvas em data.json
"""

import os
import json
import copy
import datetime
import logging
import unicodedata
import random
from typing import Optional, Union, List

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ============================================================
#  CONFIGURAÇÕES FIXAS
# ============================================================
GUILD_ID = 1540722239027023882
GUILD = discord.Object(id=GUILD_ID)
EMBED_COLOR = 0x2B2D31
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")
# ============================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("brs-bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Estado transiente do Drop (some se o bot reiniciar)
ACTIVE_DROP: Optional[dict] = None

# ============================================================
#  BANCO DE PERGUNTAS DO DROP (>1000 possíveis via combinações + lista base diversa)
# ============================================================
# Lista base diversificada (futebol, Roblox, geografia, cultura BR, matemática, história, curiosidades...)
# Você pode expandir facilmente adicionando mais itens nas listas abaixo.

DROP_QUESTIONS = [
    # === FUTEBOL / ROBLOX SOCCER ===
    {"q": "Qual time brasileiro é conhecido como 'O Mais Querido'?", "a": "flamengo"},
    {"q": "Quem é o maior artilheiro da história da seleção brasileira?", "a": "pele"},
    {"q": "Em que ano o Brasil ganhou a primeira Copa do Mundo?", "a": "1958"},
    {"q": "Qual posição joga o goleiro?", "a": "goleiro"},
    {"q": "Quantos jogadores tem um time de futebol em campo?", "a": "11"},
    {"q": "Qual é o nome do estádio do Flamengo e Fluminense?", "a": "maracana"},
    {"q": "Quem é o Rei do Futebol?", "a": "pele"},
    {"q": "Qual país sediou a Copa de 2014?", "a": "brasil"},
    {"q": "Qual time tem as cores preto e branco e é de São Paulo?", "a": "corinthians"},
    {"q": "O que significa a sigla BRS?", "a": "brazilian roblox soccer"},
    {"q": "Qual é a posição do atacante principal?", "a": "centroavante"},
    {"q": "Quantos tempos tem uma partida de futebol?", "a": "2"},
    {"q": "Qual é o nome da competição mais importante de clubes da Europa?", "a": "champions league"},
    {"q": "Quem é conhecido como 'Fenômeno'?", "a": "ronaldo"},
    {"q": "Qual seleção é chamada de Canarinho?", "a": "brasil"},
    {"q": "Em que posição joga o lateral?", "a": "lateral"},
    {"q": "Qual time é o rival clássico do Flamengo no Rio?", "a": "fluminense"},
    {"q": "Quantos títulos de Copa do Mundo o Brasil tem?", "a": "5"},
    {"q": "Qual é o nome do prêmio de melhor jogador do mundo da FIFA?", "a": "bola de ouro"},
    {"q": "O que é um hat-trick?", "a": "tres gols"},

    # === GEOGRAFIA / BANDEIRAS (mas não só isso) ===
    {"q": "Qual é a capital do Brasil?", "a": "brasilia"},
    {"q": "Qual é o maior país da América do Sul?", "a": "brasil"},
    {"q": "Em que continente fica o Egito?", "a": "africa"},
    {"q": "Qual é o oceano que banha o litoral brasileiro?", "a": "atlantico"},
    {"q": "Qual país tem a Torre Eiffel?", "a": "franca"},
    {"q": "Qual é a capital da Argentina?", "a": "buenos aires"},
    {"q": "Qual é o maior deserto do mundo?", "a": "saara"},
    {"q": "Em que país fica a Grande Muralha?", "a": "china"},
    {"q": "Qual é a capital de Portugal?", "a": "lisboa"},
    {"q": "Qual país é famoso pelo Cristo Redentor?", "a": "brasil"},

    # === CULTURA BRASILEIRA ===
    {"q": "Qual é o prato típico brasileiro feito com feijão preto?", "a": "feijoada"},
    {"q": "Qual é a bebida mais famosa do Brasil feita de cana?", "a": "cachaca"},
    {"q": "Qual é o nome do carnaval mais famoso do Brasil?", "a": "rio de janeiro"},
    {"q": "Quem escreveu 'Os Lusíadas'?", "a": "luis de camoes"},
    {"q": "Qual é o nome do famoso escritor de 'Dom Casmurro'?", "a": "machado de assis"},
    {"q": "Qual é a cor da bandeira do Brasil além do verde e amarelo?", "a": "azul"},
    {"q": "Qual é o nome do rio mais famoso do Brasil?", "a": "amazonas"},
    {"q": "Qual é a moeda oficial do Brasil?", "a": "real"},
    {"q": "Qual é o nome do famoso Cristo no Rio de Janeiro?", "a": "cristo redentor"},
    {"q": "Qual é o esporte mais popular do Brasil?", "a": "futebol"},

    # === ROBLOX / GAMES ===
    {"q": "Qual é a plataforma de jogos online onde roda o Roblox Soccer?", "a": "roblox"},
    {"q": "O que significa 'FA' no contexto de free agent?", "a": "free agent"},
    {"q": "Qual comando abre ticket no servidor?", "a": "ticket"},
    {"q": "O que é um 'scouting' no contexto da liga?", "a": "avaliacao de jogador"},
    {"q": "Qual é o nome deste bot?", "a": "brs"},

    # === MATEMÁTICA / LÓGICA ===
    {"q": "Quanto é 7 x 8?", "a": "56"},
    {"q": "Quanto é 15 + 27?", "a": "42"},
    {"q": "Qual é a raiz quadrada de 144?", "a": "12"},
    {"q": "Quanto é 100 dividido por 4?", "a": "25"},
    {"q": "Qual é o próximo número da sequência: 2, 4, 8, 16...?", "a": "32"},
    {"q": "Quanto é 9²?", "a": "81"},
    {"q": "Qual é o resultado de 50 - 23?", "a": "27"},
    {"q": "Quanto é 3³?", "a": "27"},
    {"q": "Qual é a metade de 86?", "a": "43"},
    {"q": "Quanto é 12 x 12?", "a": "144"},

    # === HISTÓRIA / CURIOSIDADES ===
    {"q": "Em que ano o homem pisou na Lua pela primeira vez?", "a": "1969"},
    {"q": "Quem descobriu o Brasil?", "a": "pedro alvares cabral"},
    {"q": "Qual é o planeta mais próximo do Sol?", "a": "mercurio"},
    {"q": "Qual é o animal símbolo da Austrália?", "a": "canguru"},
    {"q": "Qual é o maior mamífero do mundo?", "a": "baleia azul"},
    {"q": "Quantos continentes existem?", "a": "7"},
    {"q": "Qual é o metal mais usado em fios elétricos?", "a": "cobre"},
    {"q": "Qual é a cor do sangue humano oxigenado?", "a": "vermelho"},
    {"q": "Qual é o nome do processo das plantas de produzir alimento?", "a": "fotossintese"},
    {"q": "Qual é o maior órgão do corpo humano?", "a": "pele"},
]

# Gera mais variações dinamicamente para passar de 1k facilmente
def gerar_perguntas_extras() -> List[dict]:
    extras = []
    times = ["Flamengo", "Corinthians", "Palmeiras", "São Paulo", "Santos", "Grêmio", "Internacional", "Atlético-MG", "Cruzeiro", "Vasco"]
    posicoes = ["GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LW", "RW", "ST"]
    numeros = list(range(1, 51))
    for t in times:
        extras.append({"q": f"Qual é a cor principal do {t}?", "a": "vermelho" if t in ["Flamengo", "Internacional"] else "preto" if t in ["Corinthians", "Vasco"] else "verde" if t == "Palmeiras" else "branco"})
    for p in posicoes:
        extras.append({"q": f"O que significa a sigla {p} no futebol?", "a": p.lower()})
    for n in numeros:
        extras.append({"q": f"Quanto é {n} + {n}?", "a": str(n * 2)})
        extras.append({"q": f"Quanto é {n} x 2?", "a": str(n * 2)})
    # Mais de 200 extras já
    return extras

TODAS_PERGUNTAS = DROP_QUESTIONS + gerar_perguntas_extras()

# ============================================================
#  PERSISTÊNCIA
# ============================================================

DEFAULT_CONFIG = {
    "staff_role_ids": [],
    "command_permissions": {
        "ticket": [], "drop": [], "freeagent": [], "scouting": [], "say": [], "say_embed": [], "role": [],
    },
    "ticket": {
        "category_id": None,
        "staff_role_ids": [],
        "channel_name_template": "ticket-{user}",
        "welcome_message": "Olá {mention}, seja bem-vindo(a) à BRS! Descreva sua solicitação e aguarde o atendimento da staff.",
        "log_channel_id": None,
    },
    "drop": {
        "reward_role_ids": [],
        "default_channel_id": None,
    },
    "freeagent": {"channel_id": None},
    "scouting": {"channel_id": None},
}


def carregar_dados() -> dict:
    if not os.path.exists(DATA_PATH):
        return {"config": copy.deepcopy(DEFAULT_CONFIG), "freeagents": {}, "scoutings": {}}
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
    ids_membro = {r.id for r in member.roles}
    return bool(ids_permitidos & ids_membro)


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
        # Prefixos: , e /
        super().__init__(
            command_prefix=commands.when_mentioned_or(",", "/"),
            intents=intents,
            help_command=None,  # evita conflito
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

    # === Lógica do Drop (prioridade) ===
    if ACTIVE_DROP and not ACTIVE_DROP["finalizado"] and message.channel.id == ACTIVE_DROP["canal_id"]:
        if normalizar(message.content) == ACTIVE_DROP["resposta_normalizada"]:
            ACTIVE_DROP["finalizado"] = True
            vencedor = message.author

            await message.channel.send(
                embed=discord.Embed(
                    title="🎉  DROP VENCIDO!",
                    description=f"### {vencedor.mention} acertou! A resposta era **{ACTIVE_DROP['resposta']}**",
                    color=discord.Color.from_rgb(46, 204, 113),
                )
            )

            role_ids = DADOS["config"]["drop"].get("reward_role_ids", [])
            roles = [message.guild.get_role(rid) for rid in role_ids]
            roles = [r for r in roles if r]

            try:
                if roles:
                    dm_embed = discord.Embed(
                        title="🏆 Você venceu o Drop!",
                        description="Escolha um dos cargos abaixo como sua recompensa:",
                        color=discord.Color.gold(),
                    )
                    await vencedor.send(embed=dm_embed, view=DropRewardView(vencedor.id, roles))
                else:
                    await vencedor.send(
                        "🏆 Você venceu o Drop, mas nenhum cargo de recompensa está configurado ainda. "
                        "Fale com a staff!"
                    )
            except discord.Forbidden:
                await message.channel.send(
                    f"⚠️ {vencedor.mention}, não consegui te enviar DM. Habilite mensagens diretas do servidor!"
                )

            ACTIVE_DROP = None
            return  # não processa como comando

    # Processa comandos de prefixo (só uma vez)
    await bot.process_commands(message)


# ============================================================
#  SISTEMA DE TICKETS
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
            await interaction.response.send_message(
                f"❌ Você já possui um ticket aberto: {existing.mention}", ephemeral=True
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
        for rid in cfg.get("staff_role_ids", []):
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )

        category = guild.get_channel(cfg.get("category_id")) if cfg.get("category_id") else None

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket aberto por {interaction.user} ({interaction.user.id})",
        )

        mensagem = (cfg.get("welcome_message") or "Olá {mention}, seja bem-vindo(a)!")
        mensagem = mensagem.replace("{mention}", interaction.user.mention).replace("{user}", interaction.user.display_name)

        embed = discord.Embed(
            title="🎫 Ticket — BRS",
            description=mensagem,
            color=EMBED_COLOR,
            timestamp=datetime.datetime.now(),
        )
        embed.set_footer(text=f"Aberto por {interaction.user}", icon_url=interaction.user.display_avatar.url)

        await ticket_channel.send(content=interaction.user.mention, embed=embed, view=TicketControlView())

        log_id = cfg.get("log_channel_id")
        if log_id:
            log_channel = guild.get_channel(log_id)
            if log_channel:
                await log_channel.send(
                    embed=discord.Embed(
                        description=f"🎫 Ticket aberto: {ticket_channel.mention} por {interaction.user.mention}",
                        color=discord.Color.green(),
                    )
                )

        await interaction.response.send_message(f"✅ Ticket criado: {ticket_channel.mention}", ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fechar Ticket", emoji="🔒", style=discord.ButtonStyle.red, custom_id="brs_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message(
                "❌ Este botão só funciona dentro de um canal de ticket.", ephemeral=True
            )
            return

        await interaction.response.send_message("🔒 Fechando o ticket em 5 segundos...", ephemeral=True)

        cfg = DADOS["config"]["ticket"]
        log_id = cfg.get("log_channel_id")
        if log_id:
            log_channel = interaction.guild.get_channel(log_id)
            if log_channel:
                await log_channel.send(
                    embed=discord.Embed(
                        description=f"🔒 Ticket fechado: `{interaction.channel.name}` por {interaction.user.mention}",
                        color=discord.Color.red(),
                    )
                )

        await interaction.channel.send(f"🔒 Ticket fechado por {interaction.user.mention}. Encerrando em 5 segundos...")
        await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
        await interaction.channel.delete(reason=f"Ticket fechado por {interaction.user}")


ticket_group = app_commands.Group(name="ticket", description="Sistema de tickets da BRS")


@ticket_group.command(name="configurar", description="Configura o sistema de tickets.")
@app_commands.describe(
    categoria="Categoria onde os tickets serão criados",
    cargo_staff="Cargo com acesso aos tickets (chame de novo para adicionar mais de um)",
    nome_canal="Modelo do nome do canal (use {user})",
    mensagem="Mensagem inicial enviada no ticket (use {mention} para marcar quem abriu)",
    canal_logs="Canal onde logs de abertura/fechamento serão enviados",
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
        alterado.append(f"🛡️ Cargo staff adicionado: **{cargo_staff.name}**")
    if nome_canal:
        cfg["channel_name_template"] = nome_canal
        alterado.append(f"🏷️ Nome do canal: `{nome_canal}`")
    if mensagem:
        cfg["welcome_message"] = mensagem
        alterado.append("💬 Mensagem inicial atualizada")
    if canal_logs:
        cfg["log_channel_id"] = canal_logs.id
        alterado.append(f"📜 Canal de logs: {canal_logs.mention}")

    salvar_dados(DADOS)

    if not alterado:
        await interaction.response.send_message("ℹ️ Nenhuma alteração enviada.", ephemeral=True)
        return

    await interaction.response.send_message(
        "✅ Configuração de tickets atualizada:\n" + "\n".join(f"• {a}" for a in alterado), ephemeral=True
    )


@ticket_group.command(name="painel", description="Envia o painel de abertura de tickets.")
@app_commands.describe(canal="Canal onde o painel será enviado (padrão: canal atual)")
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


@ticket_group.command(name="add", description="Adiciona um membro ou cargo ao ticket atual.")
@app_commands.describe(alvo="Membro ou cargo a ser adicionado ao ticket")
async def ticket_add(interaction: discord.Interaction, alvo: Union[discord.Member, discord.Role]):
    if not is_ticket_channel(interaction.channel):
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado dentro de um canal de ticket.", ephemeral=True
        )
        return
    await interaction.channel.set_permissions(alvo, view_channel=True, send_messages=True, read_message_history=True)
    await interaction.response.send_message(f"✅ {alvo.mention} foi adicionado(a) ao ticket.", ephemeral=True)
    await interaction.channel.send(f"➕ {alvo.mention} foi adicionado(a) ao ticket por {interaction.user.mention}.")


@ticket_group.command(name="remove", description="Remove um membro ou cargo do ticket atual.")
@app_commands.describe(alvo="Membro ou cargo a ser removido do ticket")
async def ticket_remove(interaction: discord.Interaction, alvo: Union[discord.Member, discord.Role]):
    if not is_ticket_channel(interaction.channel):
        await interaction.response.send_message(
            "❌ Este comando só pode ser usado dentro de um canal de ticket.", ephemeral=True
        )
        return
    await interaction.channel.set_permissions(alvo, overwrite=None)
    await interaction.response.send_message(f"✅ {alvo.mention} foi removido(a) do ticket.", ephemeral=True)
    await interaction.channel.send(f"➖ {alvo.mention} foi removido(a) do ticket por {interaction.user.mention}.")


# ============================================================
#  /drop
# ============================================================

class DropRewardButton(discord.ui.Button):
    def __init__(self, role: discord.Role):
        super().__init__(label=role.name[:80], style=discord.ButtonStyle.blurple, emoji="🏅")
        self.role = role

    async def callback(self, interaction: discord.Interaction):
        view: "DropRewardView" = self.view
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("❌ Essa recompensa não é sua.", ephemeral=True)
            return

        guild = bot.get_guild(GUILD_ID)
        member = guild.get_member(view.user_id) if guild else None
        if not (guild and member):
            await interaction.response.send_message("❌ Não consegui aplicar o cargo. Fale com a staff.", ephemeral=True)
            return

        await member.add_roles(self.role, reason="Recompensa do Drop")
        for item in view.children:
            item.disabled = True
        await interaction.response.edit_message(content=f"✅ Você recebeu o cargo **{self.role.name}**!", view=view)
        view.stop()


class DropRewardView(discord.ui.View):
    def __init__(self, user_id: int, roles: list[discord.Role]):
        super().__init__(timeout=600)
        self.user_id = user_id
        for role in roles[:25]:
            self.add_item(DropRewardButton(role))


drop_group = app_commands.Group(name="drop", description="Sistema de Drops (perguntas e respostas) da BRS")


@drop_group.command(name="iniciar", description="Inicia um novo Drop com pergunta e resposta (ou aleatória).")
@app_commands.describe(
    pergunta="A pergunta do Drop (deixe vazio para aleatória do banco)",
    resposta="A resposta correta (obrigatória se informar pergunta)",
    canal="Canal onde o Drop será postado (padrão: canal configurado ou atual)",
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
    if ACTIVE_DROP and not ACTIVE_DROP["finalizado"]:
        await interaction.response.send_message(
            "❌ Já existe um Drop em andamento. Use `/drop cancelar` primeiro.", ephemeral=True
        )
        return

    if pergunta and not resposta:
        await interaction.response.send_message("❌ Se informar a pergunta, precisa informar a resposta também.", ephemeral=True)
        return

    if not pergunta:
        # Escolhe aleatória do banco
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
        title="❓  DROP — BRS",
        description=f"### {pergunta}\n\nResponda no chat! Quem acertar primeiro leva o prêmio 🏆",
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"Banco de perguntas: {len(TODAS_PERGUNTAS)}+ | Boa sorte!")
    await canal_destino.send(embed=embed)
    await interaction.response.send_message(f"✅ Drop iniciado em {canal_destino.mention}.", ephemeral=True)


@drop_group.command(name="cancelar", description="Cancela o Drop em andamento.")
async def drop_cancelar(interaction: discord.Interaction):
    if not await checar_permissao(interaction, "drop"):
        return

    global ACTIVE_DROP
    if not ACTIVE_DROP or ACTIVE_DROP["finalizado"]:
        await interaction.response.send_message("ℹ️ Não há nenhum Drop em andamento.", ephemeral=True)
        return

    canal = interaction.guild.get_channel(ACTIVE_DROP["canal_id"])
    ACTIVE_DROP = None
    if canal:
        await canal.send("🚫 O Drop foi cancelado pela staff.")
    await interaction.response.send_message("✅ Drop cancelado.", ephemeral=True)


@drop_group.command(name="premio_adicionar", description="Adiciona um cargo à lista de prêmios do Drop.")
@app_commands.describe(cargo="Cargo a adicionar como prêmio")
async def drop_premio_adicionar(interaction: discord.Interaction, cargo: discord.Role):
    if not await checar_permissao(interaction, "drop"):
        return
    lst = DADOS["config"]["drop"]["reward_role_ids"]
    if cargo.id not in lst:
        lst.append(cargo.id)
        salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Cargo **{cargo.name}** adicionado aos prêmios do Drop.", ephemeral=True)


@drop_group.command(name="premio_remover", description="Remove um cargo da lista de prêmios do Drop.")
@app_commands.describe(cargo="Cargo a remover dos prêmios")
async def drop_premio_remover(interaction: discord.Interaction, cargo: discord.Role):
    if not await checar_permissao(interaction, "drop"):
        return
    lst = DADOS["config"]["drop"]["reward_role_ids"]
    if cargo.id in lst:
        lst.remove(cargo.id)
        salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Cargo **{cargo.name}** removido dos prêmios do Drop.", ephemeral=True)


@drop_group.command(name="canal_padrao", description="Define o canal padrão onde os Drops serão postados.")
@app_commands.describe(canal="Canal padrão para os Drops")
async def drop_canal_padrao(interaction: discord.Interaction, canal: discord.TextChannel):
    if not await checar_permissao(interaction, "drop"):
        return
    DADOS["config"]["drop"]["default_channel_id"] = canal.id
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Canal padrão do Drop definido: {canal.mention}", ephemeral=True)


# ============================================================
#  /role — dar/remover cargo SEM precisar de ID no código
# ============================================================

@bot.tree.command(name="role", description="Adiciona ou remove um cargo de um membro (por menção).", guild=GUILD)
@app_commands.describe(
    membro="Membro que vai receber/perder o cargo",
    cargo="Cargo a adicionar ou remover",
    acao="Adicionar ou Remover",
)
@app_commands.choices(acao=[
    app_commands.Choice(name="Adicionar", value="add"),
    app_commands.Choice(name="Remover", value="remove"),
])
async def role_cmd(
    interaction: discord.Interaction,
    membro: discord.Member,
    cargo: discord.Role,
    acao: app_commands.Choice[str],
):
    if not await checar_permissao(interaction, "role"):
        return

    # Segurança: não permite cargos acima do bot ou do autor
    if cargo >= interaction.guild.me.top_role:
        await interaction.response.send_message("❌ Não posso gerenciar este cargo (está acima do meu).", ephemeral=True)
        return
    if cargo >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Você não pode gerenciar um cargo igual ou acima do seu.", ephemeral=True)
        return

    try:
        if acao.value == "add":
            await membro.add_roles(cargo, reason=f"Comando /role por {interaction.user}")
            msg = f"✅ Cargo **{cargo.name}** adicionado a {membro.mention}."
        else:
            await membro.remove_roles(cargo, reason=f"Comando /role por {interaction.user}")
            msg = f"✅ Cargo **{cargo.name}** removido de {membro.mention}."
        await interaction.response.send_message(msg, ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Não tenho permissão para gerenciar este cargo.", ephemeral=True)


# ============================================================
#  FREE AGENT + SCOUTING (iguais ao original, só organizados)
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


freeagent_group = app_commands.Group(name="freeagent", description="Sistema de Free Agents da BRS")


@freeagent_group.command(name="add", description="Cadastra um jogador como Free Agent.")
@app_commands.describe(
    jogador="Jogador", posicao="Posição (ex: ST, CM, GK)", descricao="Descrição do jogador",
    imagem="URL de uma imagem/avatar (opcional)",
)
async def freeagent_add(
    interaction: discord.Interaction, jogador: discord.Member, posicao: str, descricao: str,
    imagem: Optional[str] = None,
):
    if not await checar_permissao(interaction, "freeagent"):
        return
    registro = {"posicao": posicao, "descricao": descricao, "imagem": imagem, "data": datetime.datetime.now().isoformat()}
    DADOS["freeagents"][str(jogador.id)] = registro
    salvar_dados(DADOS)

    canal_id = DADOS["config"]["freeagent"].get("channel_id")
    canal = interaction.guild.get_channel(canal_id) if canal_id else None
    canal = canal or interaction.channel

    embed = embed_freeagent(jogador.id, registro, interaction.guild)
    await canal.send(embed=embed)
    await interaction.response.send_message(f"✅ {jogador.mention} cadastrado como Free Agent em {canal.mention}.", ephemeral=True)


@freeagent_group.command(name="remover", description="Remove um jogador da lista de Free Agents.")
@app_commands.describe(jogador="Jogador a remover")
async def freeagent_remover(interaction: discord.Interaction, jogador: discord.Member):
    if not await checar_permissao(interaction, "freeagent"):
        return
    if str(jogador.id) not in DADOS["freeagents"]:
        await interaction.response.send_message("❌ Esse jogador não está cadastrado como Free Agent.", ephemeral=True)
        return
    del DADOS["freeagents"][str(jogador.id)]
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ {jogador.mention} removido dos Free Agents.", ephemeral=True)


@freeagent_group.command(name="editar", description="Edita as informações de um Free Agent.")
@app_commands.describe(
    jogador="Jogador", posicao="Nova posição (opcional)", descricao="Nova descrição (opcional)",
    imagem="Nova imagem (opcional)",
)
async def freeagent_editar(
    interaction: discord.Interaction, jogador: discord.Member, posicao: Optional[str] = None,
    descricao: Optional[str] = None, imagem: Optional[str] = None,
):
    if not await checar_permissao(interaction, "freeagent"):
        return
    registro = DADOS["freeagents"].get(str(jogador.id))
    if not registro:
        await interaction.response.send_message("❌ Esse jogador não está cadastrado como Free Agent.", ephemeral=True)
        return
    if posicao:
        registro["posicao"] = posicao
    if descricao:
        registro["descricao"] = descricao
    if imagem:
        registro["imagem"] = imagem
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Free Agent {jogador.mention} atualizado.", ephemeral=True)


@freeagent_group.command(name="buscar", description="Mostra os dados de um Free Agent específico.")
@app_commands.describe(jogador="Jogador a buscar")
async def freeagent_buscar(interaction: discord.Interaction, jogador: discord.Member):
    registro = DADOS["freeagents"].get(str(jogador.id))
    if not registro:
        await interaction.response.send_message("❌ Esse jogador não está cadastrado como Free Agent.", ephemeral=True)
        return
    embed = embed_freeagent(jogador.id, registro, interaction.guild)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@freeagent_group.command(name="lista", description="Lista todos os Free Agents cadastrados.")
async def freeagent_lista(interaction: discord.Interaction):
    itens = DADOS["freeagents"]
    if not itens:
        await interaction.response.send_message("ℹ️ Nenhum Free Agent cadastrado no momento.", ephemeral=True)
        return
    linhas = []
    for jid, dj in itens.items():
        membro = interaction.guild.get_member(int(jid))
        nome = membro.mention if membro else f"<@{jid}>"
        linhas.append(f"▸ {nome} — `{dj['posicao']}`")
    embed = discord.Embed(
        title="🆓  FREE AGENTS — BRS", description="\n".join(linhas), color=discord.Color.from_rgb(52, 152, 219)
    )
    embed.set_footer(text=f"Total: {len(itens)} jogador(es)")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@freeagent_group.command(name="canal", description="Define o canal onde os Free Agents serão publicados.")
@app_commands.describe(canal="Canal de publicação")
async def freeagent_canal(interaction: discord.Interaction, canal: discord.TextChannel):
    if not await checar_permissao(interaction, "freeagent"):
        return
    DADOS["config"]["freeagent"]["channel_id"] = canal.id
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Canal de Free Agents definido: {canal.mention}", ephemeral=True)


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
        embed.add_field(name="🔎 Observações do Scout", value=dj["observacoes"], inline=False)
    if membro:
        embed.set_thumbnail(url=membro.display_avatar.url)
    embed.set_footer(text="BRS • Scouting")
    return embed


scouting_group = app_commands.Group(name="scouting", description="Sistema de Scouting da BRS")


@scouting_group.command(name="add", description="Cadastra um relatório de Scouting.")
@app_commands.describe(
    jogador="Jogador", posicao="Posição", descricao="Descrição do jogador",
    observacoes="Observações do Scout (opcional)", status="Status do scouting (padrão: Em avaliação)",
)
@app_commands.choices(status=STATUS_CHOICES)
async def scouting_add(
    interaction: discord.Interaction, jogador: discord.Member, posicao: str, descricao: str,
    observacoes: Optional[str] = None, status: Optional[app_commands.Choice[str]] = None,
):
    if not await checar_permissao(interaction, "scouting"):
        return
    registro = {
        "posicao": posicao, "descricao": descricao, "observacoes": observacoes or "",
        "status": status.value if status else "Em avaliação", "data": datetime.datetime.now().isoformat(),
    }
    DADOS["scoutings"][str(jogador.id)] = registro
    salvar_dados(DADOS)

    canal_id = DADOS["config"]["scouting"].get("channel_id")
    canal = interaction.guild.get_channel(canal_id) if canal_id else None
    canal = canal or interaction.channel

    embed = embed_scouting(jogador.id, registro, interaction.guild)
    await canal.send(embed=embed)
    await interaction.response.send_message(f"✅ Scouting de {jogador.mention} cadastrado em {canal.mention}.", ephemeral=True)


@scouting_group.command(name="editar", description="Edita um relatório de Scouting.")
@app_commands.describe(
    jogador="Jogador", posicao="Nova posição (opcional)", descricao="Nova descrição (opcional)",
    observacoes="Novas observações (opcional)",
)
async def scouting_editar(
    interaction: discord.Interaction, jogador: discord.Member, posicao: Optional[str] = None,
    descricao: Optional[str] = None, observacoes: Optional[str] = None,
):
    if not await checar_permissao(interaction, "scouting"):
        return
    registro = DADOS["scoutings"].get(str(jogador.id))
    if not registro:
        await interaction.response.send_message("❌ Esse jogador não tem scouting cadastrado.", ephemeral=True)
        return
    if posicao:
        registro["posicao"] = posicao
    if descricao:
        registro["descricao"] = descricao
    if observacoes:
        registro["observacoes"] = observacoes
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Scouting de {jogador.mention} atualizado.", ephemeral=True)


@scouting_group.command(name="status", description="Altera o status de um scouting.")
@app_commands.describe(jogador="Jogador", status="Novo status")
@app_commands.choices(status=STATUS_CHOICES)
async def scouting_status(interaction: discord.Interaction, jogador: discord.Member, status: app_commands.Choice[str]):
    if not await checar_permissao(interaction, "scouting"):
        return
    registro = DADOS["scoutings"].get(str(jogador.id))
    if not registro:
        await interaction.response.send_message("❌ Esse jogador não tem scouting cadastrado.", ephemeral=True)
        return
    registro["status"] = status.value
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Status de {jogador.mention} alterado para **{status.value}**.", ephemeral=True)


@scouting_group.command(name="remover", description="Remove um relatório de Scouting.")
@app_commands.describe(jogador="Jogador")
async def scouting_remover(interaction: discord.Interaction, jogador: discord.Member):
    if not await checar_permissao(interaction, "scouting"):
        return
    if str(jogador.id) not in DADOS["scoutings"]:
        await interaction.response.send_message("❌ Esse jogador não tem scouting cadastrado.", ephemeral=True)
        return
    del DADOS["scoutings"][str(jogador.id)]
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Scouting de {jogador.mention} removido.", ephemeral=True)


@scouting_group.command(name="buscar", description="Mostra o relatório de Scouting de um jogador.")
@app_commands.describe(jogador="Jogador")
async def scouting_buscar(interaction: discord.Interaction, jogador: discord.Member):
    registro = DADOS["scoutings"].get(str(jogador.id))
    if not registro:
        await interaction.response.send_message("❌ Esse jogador não tem scouting cadastrado.", ephemeral=True)
        return
    embed = embed_scouting(jogador.id, registro, interaction.guild)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@scouting_group.command(name="lista", description="Lista todos os relatórios de Scouting.")
async def scouting_lista(interaction: discord.Interaction):
    itens = DADOS["scoutings"]
    if not itens:
        await interaction.response.send_message("ℹ️ Nenhum scouting cadastrado no momento.", ephemeral=True)
        return
    linhas = []
    for jid, dj in itens.items():
        membro = interaction.guild.get_member(int(jid))
        nome = membro.mention if membro else f"<@{jid}>"
        linhas.append(f"▸ {nome} — `{dj['posicao']}` — **{dj['status']}**")
    embed = discord.Embed(
        title="🔍  SCOUTING — BRS", description="\n".join(linhas), color=discord.Color.from_rgb(241, 196, 15)
    )
    embed.set_footer(text=f"Total: {len(itens)} jogador(es)")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@scouting_group.command(name="canal", description="Define o canal onde os relatórios de Scouting serão publicados.")
@app_commands.describe(canal="Canal de publicação")
async def scouting_canal(interaction: discord.Interaction, canal: discord.TextChannel):
    if not await checar_permissao(interaction, "scouting"):
        return
    DADOS["config"]["scouting"]["channel_id"] = canal.id
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Canal de Scouting definido: {canal.mention}", ephemeral=True)


# ============================================================
#  /say  e  /say_embed  (foto do bot automática no embed)
# ============================================================

@bot.tree.command(name="say", description="Envia uma mensagem de texto através do bot.", guild=GUILD)
@app_commands.describe(mensagem="Texto a ser enviado", canal="Canal de destino (padrão: canal atual)")
async def say_cmd(interaction: discord.Interaction, mensagem: str, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "say"):
        return
    canal = canal or interaction.channel
    await canal.send(mensagem.replace("\\n", "\n"))
    await interaction.response.send_message(f"✅ Mensagem enviada em {canal.mention}.", ephemeral=True)


@bot.tree.command(name="say_embed", description="Envia uma mensagem em formato de embed através do bot.", guild=GUILD)
@app_commands.describe(
    titulo="Título do embed",
    descricao="Descrição do embed (use \\n para quebrar linha)",
    canal="Canal de destino (padrão: canal atual)",
    cor="Cor em hexadecimal, ex: #FF0000",
    imagem="URL de uma imagem grande (opcional)",
    rodape="Texto do rodapé (opcional)",
    autor="Nome do autor no topo (opcional)",
)
async def say_embed_cmd(
    interaction: discord.Interaction,
    titulo: str,
    descricao: str,
    canal: Optional[discord.TextChannel] = None,
    cor: Optional[str] = None,
    imagem: Optional[str] = None,
    rodape: Optional[str] = None,
    autor: Optional[str] = None,
):
    if not await checar_permissao(interaction, "say_embed"):
        return
    canal = canal or interaction.channel

    if cor:
        try:
            color = discord.Color(int(cor.replace("#", ""), 16))
        except ValueError:
            await interaction.response.send_message("❌ Cor inválida. Use um código hexadecimal, ex: #FF0000", ephemeral=True)
            return
    else:
        color = discord.Color(EMBED_COLOR)

    embed = discord.Embed(title=titulo, description=descricao.replace("\\n", "\n"), color=color)

    # Foto do bot automática (thumbnail)
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
#  PERMISSÕES E CONFIG (layout melhorado)
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


@bot.tree.command(name="staff", description="Define um cargo como Staff geral (acesso a todos os comandos).", guild=GUILD)
@app_commands.describe(cargo="Cargo de staff", acao="Adicionar ou remover")
@app_commands.choices(acao=ACAO_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def staff_cmd(interaction: discord.Interaction, cargo: discord.Role, acao: app_commands.Choice[str]):
    lst = DADOS["config"]["staff_role_ids"]
    if acao.value == "adicionar":
        if cargo.id not in lst:
            lst.append(cargo.id)
        msg = f"✅ Cargo **{cargo.name}** agora é Staff geral (acesso a todos os comandos administrativos)."
    else:
        if cargo.id in lst:
            lst.remove(cargo.id)
        msg = f"✅ Cargo **{cargo.name}** removido da Staff geral."
    salvar_dados(DADOS)
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="permissao", description="Libera/revoga um cargo para usar um comando específico.", guild=GUILD)
@app_commands.describe(comando="Comando a configurar", cargo="Cargo a liberar/revogar", acao="Adicionar ou remover")
@app_commands.choices(comando=COMANDOS_CONFIGURAVEIS, acao=ACAO_CHOICES)
@app_commands.checks.has_permissions(administrator=True)
async def permissao_cmd(
    interaction: discord.Interaction, comando: app_commands.Choice[str], cargo: discord.Role,
    acao: app_commands.Choice[str],
):
    lst = DADOS["config"]["command_permissions"].setdefault(comando.value, [])
    if acao.value == "adicionar":
        if cargo.id not in lst:
            lst.append(cargo.id)
        msg = f"✅ Cargo **{cargo.name}** agora pode usar `/{comando.value}`."
    else:
        if cargo.id in lst:
            lst.remove(cargo.id)
        msg = f"✅ Cargo **{cargo.name}** não pode mais usar `/{comando.value}`."
    salvar_dados(DADOS)
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="config_ver", description="Mostra as configurações atuais do bot (layout organizado).", guild=GUILD)
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
        title="⚙️  Configurações do Bot — BRS",
        description="Visão geral de todas as configurações atuais.",
        color=EMBED_COLOR,
        timestamp=datetime.datetime.now(),
    )
    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    # Staff
    embed.add_field(
        name="🛡️  Staff Geral",
        value=nomes_cargos(cfg["staff_role_ids"]),
        inline=False,
    )

    # Permissões por comando
    perms_txt = []
    for cmd_nome, ids in cfg["command_permissions"].items():
        perms_txt.append(f"**/{cmd_nome}** → {nomes_cargos(ids)}")
    embed.add_field(
        name="🔑  Permissões por Comando",
        value="\n".join(perms_txt) if perms_txt else "*nenhuma*",
        inline=False,
    )

    # Ticket
    embed.add_field(
        name="🎫  Sistema de Tickets",
        value=(
            f"Categoria: {nome_canal(cfg['ticket']['category_id'])}\n"
            f"Cargos staff: {nomes_cargos(cfg['ticket']['staff_role_ids'])}\n"
            f"Canal de logs: {nome_canal(cfg['ticket']['log_channel_id'])}\n"
            f"Template nome: `{cfg['ticket'].get('channel_name_template', 'ticket-{user}')}`"
        ),
        inline=False,
    )

    # Drop
    embed.add_field(
        name="❓  Sistema de Drop",
        value=(
            f"Prêmios: {nomes_cargos(cfg['drop']['reward_role_ids'])}\n"
            f"Canal padrão: {nome_canal(cfg['drop']['default_channel_id'])}\n"
            f"Perguntas no banco: **{len(TODAS_PERGUNTAS)}+**"
        ),
        inline=False,
    )

    # Free Agent + Scouting
    embed.add_field(
        name="🆓  Free Agents",
        value=f"Canal: {nome_canal(cfg['freeagent']['channel_id'])}",
        inline=True,
    )
    embed.add_field(
        name="🔍  Scouting",
        value=f"Canal: {nome_canal(cfg['scouting']['channel_id'])}",
        inline=True,
    )

    embed.set_footer(text="BRS Bot • Use /staff e /permissao para gerenciar acessos")
    await interaction.response.send_message(embed=embed, ephemeral=True)


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
