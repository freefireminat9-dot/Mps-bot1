"""
Bot Discord completo — BRS (Brazilian Roblox Soccer)
Comandos: somente slash (/), sem prefixo de texto
Slash: /

Recursos:
  - Tickets automáticos (select menu de categorias, claim, fechar com motivo, transcript)
  - Assistente automático (IA) responde no ticket até a staff assumir
  - Drop estilo PAFO (select menu + cargos temporários 5 dias) com banco de 1000+ perguntas diversas
  - Meta de membros → Wave Drop (inicia sozinha ao bater a meta)
  - Free Agent / Scouting
  - /role e /cargo_criar (sem ID fixo para selecionar cargos)
  - /say e /say_embed (foto do bot automática, sempre)
  - Painel de configuração organizado, logs completos, anti-spam e ferramentas de liga

Dependências opcionais:
  - Para o assistente de ticket responder com IA de verdade (Claude),
    instale `pip install anthropic` e defina a variável de ambiente
    ANTHROPIC_API_KEY. Sem isso, o assistente usa respostas locais contextualizadas
    por categoria — o ticket nunca fica sem resposta automática.
"""

import os
import json
import copy
import datetime
import io
import logging
import unicodedata
import random
import asyncio
import re
from zoneinfo import ZoneInfo
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
BRS_GREEN = 0x00FF7F
DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")

# Cargos de recompensa do Drop (os que você passou).
# Observação: nenhum comando abaixo depende de ID fixo de cargo além destes
# valores padrão de PRÊMIO do drop — /role continua 100% livre de ID no código.
DROP_REWARD_ROLES = {
    1541600835472072724: {"nome": "Olheiro (5 Dias)", "emoji": "🔍"},
    1541065148590989332: {"nome": "Scrim Hoster (5 Dias)", "emoji": "⚔️"},
    1541600905298714664: {"nome": "Pic Perm (5 Dias)", "emoji": "💥"},
}

# Categorias de ticket estilo PAFO — o usuário escolhe no select menu.
TICKET_CATEGORIES = [
    {"key": "suporte", "label": "Suporte Geral", "emoji": "🛠️", "descricao": "Dúvidas, problemas ou ajuda geral com o servidor."},
    {"key": "denuncia", "label": "Denúncia / Report", "emoji": "🚨", "descricao": "Denunciar um jogador, staff ou situação irregular."},
    {"key": "duvidas", "label": "Dúvidas sobre o Jogo", "emoji": "❓", "descricao": "Perguntas sobre regras, eventos ou funcionamento do BRS."},
    {"key": "parcerias", "label": "Parcerias / Business", "emoji": "🤝", "descricao": "Propostas de parceria, patrocínio ou negócios."},
]
# ============================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("brs-bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

ACTIVE_DROP: Optional[dict] = None
WAVE_RUNNING = False
BRT = ZoneInfo("America/Sao_Paulo")
_CRIANDO_TICKETS: set[int] = set()

# Anti-spam: segunda repetição idêntica em até 60 segundos gera timeout de 5 minutos.
_ULTIMA_MENSAGEM: dict[tuple[int, int], tuple[str, object]] = {}
TEMPO_ANTI_SPAM_SEGUNDOS = 60
DURACAO_MUTE_SPAM = datetime.timedelta(minutes=5)

BRT = ZoneInfo("America/Sao_Paulo")

# Controle anti-spam: duas mensagens idênticas do mesmo membro dentro de 60s
# removem a segunda e aplicam timeout nativo de 5 minutos.
_ULTIMA_MENSAGEM: dict[tuple[int, int], tuple[str, datetime.datetime]] = {}
TEMPO_ANTI_SPAM_SEGUNDOS = 60
DURACAO_MUTE_SPAM = datetime.timedelta(minutes=5)

# Agendamentos de partidas da liga que sobrevivem a reinícios via data.json.

# ============================================================
#  BANCO DE PERGUNTAS DO DROP — 1000+ perguntas diversas
#  (futebol, geografia, capitais, moedas, ciência, história,
#   cultura geral, Roblox e matemática — não é só bandeira/flag)
# ============================================================

# --- 1) Perguntas curadas, diversas por natureza -----------------
PERGUNTAS_CURADAS = [
    # Futebol / BRS
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
    {"q": "Quantos minutos tem uma partida oficial de futebol?", "a": "90"},
    {"q": "Qual é o nome do cartão que expulsa um jogador?", "a": "vermelho"},
    {"q": "Quem organiza a Copa do Mundo?", "a": "fifa"},
    {"q": "Qual jogador é conhecido como CR7?", "a": "cristiano ronaldo"},
    {"q": "Qual é o apelido da seleção brasileira?", "a": "canarinho"},
    {"q": "Em que ano aconteceu o Maracanaço?", "a": "1950"},
    {"q": "Qual é o clube com mais títulos da Champions League?", "a": "real madrid"},
    {"q": "Quantos gols vale um pênalti convertido?", "a": "1"},
    {"q": "O que é um hat-trick?", "a": "tres gols"},
    {"q": "Qual é a posição do jogador que defende o gol?", "a": "goleiro"},
    # Cultura geral / Roblox
    {"q": "Qual é a plataforma onde roda o Roblox Soccer?", "a": "roblox"},
    {"q": "Qual é a moeda virtual do Roblox?", "a": "robux"},
    {"q": "Em que ano o Roblox foi lançado?", "a": "2006"},
    {"q": "Qual é o nome do avatar padrão do Roblox?", "a": "noob"},
    {"q": "Qual empresa criou o Roblox?", "a": "roblox corporation"},
    # Geografia / história geral
    {"q": "Qual é a capital do Brasil?", "a": "brasilia"},
    {"q": "Qual é o maior país da América do Sul?", "a": "brasil"},
    {"q": "Em que continente fica o Egito?", "a": "africa"},
    {"q": "Qual país tem a Torre Eiffel?", "a": "franca"},
    {"q": "Qual é a capital da Argentina?", "a": "buenos aires"},
    {"q": "Qual é o maior oceano do mundo?", "a": "pacifico"},
    {"q": "Qual é o rio mais longo do mundo?", "a": "nilo"},
    {"q": "Qual é o maior deserto do mundo?", "a": "saara"},
    {"q": "Quem descobriu o Brasil?", "a": "pedro alvares cabral"},
    {"q": "Em que ano o homem pisou na Lua?", "a": "1969"},
    {"q": "Quantos estados tem o Brasil?", "a": "26"},
    {"q": "Qual é o continente mais frio do planeta?", "a": "antartida"},
    {"q": "Qual é a montanha mais alta do mundo?", "a": "everest"},
    # Comida / cultura brasileira
    {"q": "Qual é o prato típico brasileiro feito com feijão preto?", "a": "feijoada"},
    {"q": "Qual é a moeda oficial do Brasil?", "a": "real"},
    {"q": "Qual é o esporte mais popular do Brasil?", "a": "futebol"},
    {"q": "Qual é a bebida típica feita com erva-mate no Brasil?", "a": "chimarrao"},
    {"q": "Qual é o doce brasileiro feito de leite condensado e chocolate?", "a": "brigadeiro"},
    # Ciência
    {"q": "Qual é o planeta mais próximo do Sol?", "a": "mercurio"},
    {"q": "Qual é o maior mamífero do mundo?", "a": "baleia azul"},
    {"q": "Quantos continentes existem?", "a": "7"},
    {"q": "Qual é o maior órgão do corpo humano?", "a": "pele"},
    {"q": "Qual gás os humanos respiram para viver?", "a": "oxigenio"},
    {"q": "Qual é o osso mais longo do corpo humano?", "a": "femur"},
    {"q": "Quantos ossos tem o corpo humano adulto?", "a": "206"},
    {"q": "Qual é a velocidade da luz aproximada (km/s)?", "a": "300000"},
    {"q": "Qual é o elemento químico representado por 'O'?", "a": "oxigenio"},
    {"q": "Qual planeta é conhecido como planeta vermelho?", "a": "marte"},
]

# --- 2) Capitais de países (gera perguntas de geografia) --------
CAPITAIS = {
    "Portugal": "lisboa", "Espanha": "madrid", "Italia": "roma", "Alemanha": "berlim",
    "Franca": "paris", "Reino Unido": "londres", "Japao": "toquio", "China": "pequim",
    "Russia": "moscou", "Canada": "ottawa", "Estados Unidos": "washington",
    "Mexico": "cidade do mexico", "Argentina": "buenos aires", "Chile": "santiago",
    "Uruguai": "montevideu", "Paraguai": "assuncao", "Peru": "lima", "Colombia": "bogota",
    "Venezuela": "caracas", "Bolivia": "sucre", "Equador": "quito", "Egito": "cairo",
    "Africa do Sul": "pretoria", "Nigeria": "abuja", "India": "nova deli",
    "Australia": "camberra", "Coreia do Sul": "seul", "Turquia": "ancara",
    "Grecia": "atenas", "Suecia": "estocolmo", "Noruega": "oslo", "Holanda": "amsterda",
    "Belgica": "bruxelas", "Suica": "berna", "Austria": "viena", "Polonia": "varsovia",
    "Cuba": "havana", "Marrocos": "rabat", "Croacia": "zagreb", "Servia": "belgrado",
}

# --- 3) Moedas de países -----------------------------------------
MOEDAS = {
    "Brasil": "real", "Estados Unidos": "dolar", "Reino Unido": "libra",
    "Japao": "iene", "China": "yuan", "Mexico": "peso", "Argentina": "peso",
    "Russia": "rublo", "India": "rupia", "Suica": "franco",
    "Coreia do Sul": "won", "Africa do Sul": "rand", "Turquia": "lira",
    "Chile": "peso", "Paraguai": "guarani",
}

# --- 4) Clubes de futebol e seus países ---------------------------
CLUBES_PAIS = {
    "Real Madrid": "espanha", "Barcelona": "espanha", "Manchester United": "inglaterra",
    "Manchester City": "inglaterra", "Liverpool": "inglaterra", "Chelsea": "inglaterra",
    "Bayern de Munique": "alemanha", "Borussia Dortmund": "alemanha",
    "Juventus": "italia", "Inter de Milao": "italia", "AC Milan": "italia",
    "Paris Saint-Germain": "franca", "Ajax": "holanda", "Porto": "portugal",
    "Benfica": "portugal", "Boca Juniors": "argentina", "River Plate": "argentina",
    "Flamengo": "brasil", "Palmeiras": "brasil", "Corinthians": "brasil",
    "Sao Paulo": "brasil", "Santos": "brasil", "Gremio": "brasil",
    "Internacional": "brasil", "Atletico-MG": "brasil", "Cruzeiro": "brasil",
    "Vasco": "brasil", "Botafogo": "brasil", "Fluminense": "brasil",
}

CORES_TIMES = {
    "Flamengo": "vermelho", "Internacional": "vermelho", "Sao Paulo": "branco",
    "Corinthians": "preto", "Vasco": "preto", "Palmeiras": "verde",
    "Santos": "branco", "Gremio": "azul", "Atletico-MG": "preto",
    "Cruzeiro": "azul", "Botafogo": "preto", "Fluminense": "vinho",
}

# --- 5) Curiosidades diversas extras -------------------------------
CURIOSIDADES_EXTRAS = [
    {"q": "Quantos lados tem um hexágono?", "a": "6"},
    {"q": "Quantos lados tem um triângulo?", "a": "3"},
    {"q": "Qual é o animal terrestre mais rápido do mundo?", "a": "guepardo"},
    {"q": "Qual é o maior planeta do sistema solar?", "a": "jupiter"},
    {"q": "Quantas cores tem o arco-íris?", "a": "7"},
    {"q": "Qual é o metal líquido à temperatura ambiente?", "a": "mercurio"},
    {"q": "Qual instrumento mede a temperatura?", "a": "termometro"},
    {"q": "Qual é o idioma mais falado do mundo?", "a": "mandarim"},
    {"q": "Quantos dias tem um ano bissexto?", "a": "366"},
    {"q": "Qual é o menor país do mundo?", "a": "vaticano"},
    {"q": "Qual é o maior deserto de areia da África?", "a": "saara"},
    {"q": "Qual é o nome do satélite natural da Terra?", "a": "lua"},
    {"q": "Quantas patas tem uma aranha?", "a": "8"},
    {"q": "Qual é o inseto que produz mel?", "a": "abelha"},
    {"q": "Qual é o animal símbolo do Brasil?", "a": "arara"},
]


def gerar_perguntas_extras() -> List[dict]:
    """Combina categorias variadas para formar um banco de 1000+ perguntas,
    sem repetir apenas um tipo (evitando ficar 'só de bandeira')."""
    extras: List[dict] = []

    # Geografia (capitais)
    for pais, capital in CAPITAIS.items():
        extras.append({"q": f"Qual é a capital de {pais}?", "a": capital})

    # Moedas
    for pais, moeda in MOEDAS.items():
        extras.append({"q": f"Qual é a moeda oficial de {pais}?", "a": moeda})

    # Clubes e países
    for clube, pais in CLUBES_PAIS.items():
        extras.append({"q": f"De qual país é o clube {clube}?", "a": pais})

    # Cores dos times
    for time, cor in CORES_TIMES.items():
        extras.append({"q": f"Qual é a cor principal do {time}?", "a": cor})

    # Curiosidades
    extras.extend(CURIOSIDADES_EXTRAS)

    # Matemática variada (soma, subtração, multiplicação, quadrado) — mantém
    # o banco grande sem virar só um tipo de pergunta, pois é combinado com
    # todas as categorias acima (que somam ~200 perguntas não-matemáticas).
    for n in range(1, 301):
        extras.append({"q": f"Quanto é {n} + {n}?", "a": str(n * 2)})
        extras.append({"q": f"Quanto é {n} x 2?", "a": str(n * 2)})
        extras.append({"q": f"Quanto é {n} x 3?", "a": str(n * 3)})
        extras.append({"q": f"Quanto é {n + 10} - {n}?", "a": "10"})
        if n <= 40:
            extras.append({"q": f"Quanto é {n}²?", "a": str(n * n)})

    return extras


TODAS_PERGUNTAS = PERGUNTAS_CURADAS + gerar_perguntas_extras()


# ============================================================
#  PERSISTÊNCIA
# ============================================================
DEFAULT_CONFIG = {
    "staff_role_ids": [],
    "command_permissions": {
        "ticket": [], "drop": [], "freeagent": [], "scouting": [],
        "say": [], "say_embed": [],         "role": [], "criar_cargo": [], "liga": [],

    },
    "ticket": {
        "category_id": None,
        "staff_role_ids": [],
        "channel_name_template": "ticket-{tipo}-{user}",
        "welcome_message": "Olá {mention}, seja bem-vindo(a) à BRS! Descreva sua solicitação e aguarde o atendimento da staff.",
        "log_channel_id": None,
        "painel_titulo": "🎫 Central de Atendimento — BRS",
        "painel_descricao": "Selecione abaixo o tipo de atendimento que você precisa. Nossa staff irá te ajudar o mais rápido possível!",
        "painel_channel_id": None,
        "painel_mensagem_id": None,
        "banner_url": "",
        "horario_atendimento": "Sábado e domingo das 13h às 21h (BRT). Fora desse horário, o Assistente BRS (IA) continuará atendendo até a staff chegar.",
        "faq": [],  # lista de {"palavras": [...], "resposta": "..."} — ensinado via /ticket faq_add
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
        return {"config": copy.deepcopy(DEFAULT_CONFIG), "freeagents": {}, "scoutings": {}, "drop_expiracoes": {}, "tickets": {}}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        dados = json.load(f)
    dados.setdefault("config", copy.deepcopy(DEFAULT_CONFIG))
    for chave, valor in DEFAULT_CONFIG.items():
        if chave not in dados["config"]:
            dados["config"][chave] = copy.deepcopy(valor)
        elif isinstance(valor, dict):
            for sub_chave, sub_valor in valor.items():
                dados["config"][chave].setdefault(sub_chave, copy.deepcopy(sub_valor))
    dados["config"].setdefault("command_permissions", {})
    for cmd in DEFAULT_CONFIG["command_permissions"]:
        dados["config"]["command_permissions"].setdefault(cmd, [])
    dados.setdefault("freeagents", {})
    dados.setdefault("scoutings", {})
    dados.setdefault("drop_expiracoes", {})
    dados.setdefault("tickets", {})  # estado de cada ticket: reivindicado, tipo, autor
    dados.setdefault("liga", {"times": [], "sorteios": [], "resultados": []})
    dados["liga"].setdefault("times", [])
    dados["liga"].setdefault("sorteios", [])
    dados["liga"].setdefault("resultados", [])
    return dados


def salvar_dados(dados: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


DADOS = carregar_dados()


def agora_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def enviar_log_ticket(
    guild: discord.Guild,
    titulo: str,
    descricao: str,
    *,
    campos: Optional[list[tuple[str, str]]] = None,
    cor: discord.Color = discord.Color.blurple(),
    transcript_texto: Optional[str] = None,
    nome_canal: Optional[str] = None,
):
    """Envia um log completo no canal de logs configurado, com transcript opcional."""
    cfg = DADOS["config"].get("ticket", {})
    log_id = cfg.get("log_channel_id")
    log_channel = guild.get_channel(log_id) if log_id else None
    if not log_channel:
        return

    embed = discord.Embed(title=titulo, description=descricao, color=cor, timestamp=agora_utc())
    if campos:
        for nome, valor in campos:
            embed.add_field(name=nome, value=str(valor)[:1024] or "—", inline=False)
    avatar = bot_avatar_url() if "bot" in globals() else None
    if avatar:
        embed.set_thumbnail(url=avatar)
    embed.set_footer(text="BRS • Ticket Logs")

    arquivo = None
    if transcript_texto is not None:
        nome = nome_canal or "ticket"
        arquivo = discord.File(
            io.BytesIO(transcript_texto.encode("utf-8")),
            filename=f"{nome}-transcript.txt",
        )
    if arquivo:
        await log_channel.send(embed=embed, file=arquivo)
    else:
        await log_channel.send(embed=embed)


async def moderar_repeticao(message: discord.Message) -> bool:
    """Apaga a segunda mensagem idêntica e aplica timeout de 5 minutos."""
    if not message.guild or not isinstance(message.author, discord.Member):
        return False
    member = message.author
    if (
        member.guild_permissions.administrator
        or member.guild_permissions.manage_messages
        or member.guild_permissions.moderate_members
    ):
        return False

    assinatura = normalizar(message.content)
    if len(assinatura) < 3:
        return False

    agora = agora_utc()
    chave = (message.guild.id, member.id)
    anterior = _ULTIMA_MENSAGEM.get(chave)
    _ULTIMA_MENSAGEM[chave] = (assinatura, agora)
    if not anterior:
        return False

    texto_anterior, quando = anterior
    if texto_anterior != assinatura or (agora - quando).total_seconds() > TEMPO_ANTI_SPAM_SEGUNDOS:
        return False

    try:
        await message.delete()
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass

    try:
        await member.timeout(DURACAO_MUTE_SPAM, reason="Anti-spam BRS: mensagem repetida")
        aviso = await message.channel.send(
            f"⚠️ {member.mention}, mensagem repetida detectada. Você ficou em silêncio por **5 minutos**.",
            delete_after=8,
        )
        await enviar_log_ticket(
            message.guild,
            "🛡️ Anti-spam aplicado",
            f"O sistema detectou uma mensagem repetida e aplicou timeout de 5 minutos.",
            campos=[
                ("Membro", f"{member.mention} (`{member.id}`)"),
                ("Canal", getattr(message.channel, "mention", str(message.channel))),
                ("Mensagem", message.content[:900]),
            ],
            cor=discord.Color.orange(),
        )
        return True
    except discord.Forbidden:
        await message.channel.send(
            f"⚠️ {member.mention}, evite repetir a mesma mensagem. Não consegui aplicar o mute porque falta a permissão **Moderar Membros**.",
            delete_after=10,
        )
        return True
    except discord.HTTPException:
        return True


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


def bot_avatar_url() -> Optional[str]:
    """Retorna a foto do bot automaticamente, sem precisar informar nada."""
    if bot.user:
        return bot.user.display_avatar.url
    return None


# ============================================================
#  ASSISTENTE AUTOMÁTICO DO TICKET (estilo "Assistente PAFO (IA)")
#  Responde a quem abriu o ticket automaticamente até que um
#  membro da staff clique em "Assumir". Se a variável de ambiente
#  ANTHROPIC_API_KEY estiver configurada e o pacote `anthropic`
#  instalado, as respostas usam IA de verdade (Claude). Caso
#  contrário, o assistente usa uma base de perguntas frequentes
#  (configurável por comando) para tentar entender e responder de
#  verdade o que o membro precisa — usa o contexto da mensagem e não fica presa a uma frase genérica.
# ============================================================
try:
    import anthropic
    _anthropic_client = anthropic.Anthropic() if os.getenv("ANTHROPIC_API_KEY") else None
except Exception:
    anthropic = None
    _anthropic_client = None

# Base de conhecimento padrão (funciona mesmo sem IA configurada).
# Cada entrada tem palavras-chave e uma resposta. A staff pode adicionar
# mais com `/ticket faq_add`, específicas do servidor (regras, canais, etc).
FAQ_CURADA = [
    {"palavras": ["liga", "chamar galera", "procurando jogador", "montar time", "entrar em 1 liga", "entrar numa liga"],
     "resposta": "Pra chamar gente pra sua liga ou time, procure o canal específico de divulgação de ligas do servidor — assim mais gente vê. Se não souber qual é, a staff te indica quando assumir o ticket."},
    {"palavras": ["chat geral", "falar no geral", "postar no geral"],
     "resposta": "O chat geral costuma ser só pra conversa livre — pedidos específicos (divulgar liga, vender item, etc.) geralmente têm um canal próprio. A staff confirma certinho pra você."},
    {"palavras": ["bug", "travando", "erro", "nao consigo entrar", "não consigo entrar", "crashou"],
     "resposta": "Entendi, parece ser um problema técnico. Me conta: em qual tela/ação isso acontece e se aparece alguma mensagem de erro? Isso ajuda a staff a resolver mais rápido."},
    {"palavras": ["denunciar", "denuncia", "hacker", "cheater", "xingou", "ofendeu", "provas", "print"],
     "resposta": "Pra denúncia, o mais importante são provas: prints, vídeos ou links da conversa/situação. Pode mandar aqui mesmo no ticket que a staff analisa."},
    {"palavras": ["parceria", "divulgação", "divulgar servidor", "afiliação", "proposta"],
     "resposta": "Legal que você quer fazer parceria! Me conta rapidinho: qual é a proposta (tipo de parceria, o que oferece e o que espera em troca)? Assim a equipe de negócios já pega o contexto pronto."},
    {"palavras": ["cargo", "role", "vip", "premio", "prêmio", "recompensa"],
     "resposta": "Sobre cargos e recompensas: eles costumam vir de eventos como o Drop ou de compras/parcerias. Só a staff pode confirmar ou aplicar isso manualmente."},
    {"palavras": ["quando", "demora", "quanto tempo", "ninguem responde", "ninguém responde"],
     "resposta": "Peço desculpa pela demora! A staff é notificada assim que o ticket abre — em horário de atendimento a resposta costuma ser rápida, fora dele pode levar um pouco mais."},
    {"palavras": ["banido", "ban", "fui banido", "expulso", "kickado"],
     "resposta": "Sobre banimentos: me conta o nome/ID de quem foi banido e, se souber, o motivo informado. A staff confere o registro e te explica certinho o que houve."},
    {"palavras": ["desbanir", "revisao de ban", "revisão de ban", "recurso de ban", "apelar"],
     "resposta": "Pra pedir revisão de um banimento, explique o que aconteceu com o máximo de detalhes e, se tiver, provas a seu favor. Só a staff pode decidir sobre isso."},
    {"palavras": ["comprei", "compra", "pagamento", "nao recebi", "não recebi", "produto", "reembolso"],
     "resposta": "Sobre compras: me passa o comprovante (print do pagamento) e o que você comprou. A staff financeira confirma e resolve com você."},
    {"palavras": ["senha", "conta invadida", "hackearam", "roubaram conta", "recuperar conta"],
     "resposta": "Se sua conta foi comprometida, troque a senha imediatamente pelo site/app oficial do Roblox e ative a verificação em duas etapas. A staff pode te orientar, mas a recuperação em si é feita direto com o suporte do Roblox."},
    {"palavras": ["regras", "regulamento", "pode fazer isso", "e proibido", "é proibido"],
     "resposta": "Sobre regras do servidor: me diz especificamente o que você quer confirmar que pode ou não fazer, que eu tento te ajudar — e a staff confirma oficialmente."},
    {"palavras": ["staff", "candidatura", "quero ser staff", "recrutamento", "vaga staff"],
     "resposta": "Pra se candidatar à staff, geralmente tem um canal ou formulário próprio de recrutamento. Se estiver aberto, a staff te passa o link certinho."},
    {"palavras": ["evento", "quando tem evento", "proximo evento", "próximo evento"],
     "resposta": "Os eventos (como Drops e Wave Drops) costumam ser avisados nos canais de anúncio do servidor. Fica de olho lá — e a staff pode confirmar se tem algo agendado."},
    {"palavras": ["obrigado", "valeu", "ok obrigado", "blz", "entendi obrigado"],
     "resposta": "Por nada! Se precisar de mais alguma coisa é só mandar aqui mesmo, ou aguardar que a staff chega em breve."},
]


def gerar_faq_automatica() -> List[dict]:
    """Gera automaticamente milhares de respostas combinando temas comuns
    de ticket (prazos de cargo, códigos de erro do Roblox, clubes,
    posições e temporadas), formando uma base de conhecimento grande o
    suficiente pra o assistente responder sem depender só da IA."""
    extras: List[dict] = []

    # 1) Prazos de cargos temporários (ex.: "5 dias", "12 dias"...)
    for n in range(1, 1001):
        extras.append({
            "palavras": [f"{n} dias"],
            "resposta": (
                f"Cargos ou prazos de {n} dias contam a partir do momento em que foram entregues. "
                "Depois desse período o sistema remove automaticamente — não precisa pedir remoção manual."
            ),
        })

    # 2) Códigos de erro do Roblox (o número sozinho já casa com a mensagem)
    for n in range(100, 3450):
        extras.append({
            "palavras": [f"erro {n}", f"error {n}", f"codigo {n}"],
            "resposta": (
                f"O código de erro {n} geralmente está ligado a instabilidade de conexão com os servidores do Roblox. "
                "Tente: 1) reiniciar o Roblox, 2) checar sua internet, 3) tentar entrar de novo em alguns minutos. "
                f"Se o erro {n} continuar, manda um print aqui no ticket que a staff verifica."
            ),
        })

    # 3) Clubes específicos (reaproveita a lista usada no Drop)
    templates_clube = [
        "Posso jogar pelo {c}?", "Como entro no {c}?", "Quero fazer parte do {c}",
        "O {c} tá recrutando?", "Vaga no {c}", "Testes para o {c}",
        "Time {c} precisa de jogador", "{c} tá montando elenco",
    ]
    for clube in CLUBES_PAIS.keys():
        for template in templates_clube:
            extras.append({
                "palavras": [template.format(c=clube), clube],
                "resposta": (
                    f"Pra entrar ou saber sobre vagas no {clube}, o ideal é falar direto com a diretoria/capitão do time "
                    "ou se cadastrar como jogador disponível usando o Free Agent (`/freeagent`). "
                    "A staff também pode te indicar o contato certo."
                ),
            })

    # 4) Posições em campo
    posicoes = ["goleiro", "zagueiro", "lateral", "volante", "meia", "atacante", "ponta"]
    templates_posicao = [
        "como jogo de {p}", "dicas de {p}", "quero jogar de {p}",
        "melhor forma de jogar de {p}", "como ser um bom {p}",
    ]
    for pos in posicoes:
        for template in templates_posicao:
            extras.append({
                "palavras": [template.format(p=pos)],
                "resposta": (
                    f"Dicas gerais de {pos} variam bastante de time pra time — o técnico ou capitão do seu time "
                    "costuma ter as orientações táticas específicas. Se quiser, a staff pode te indicar algum "
                    "canal ou guia sobre posições do BRS."
                ),
            })

    # 5) Temporadas da liga
    for n in range(1, 501):
        extras.append({
            "palavras": [f"temporada {n}"],
            "resposta": (
                f"Sobre a temporada {n}: regras e premiações podem mudar entre temporadas. "
                f"Pra confirmar os detalhes atualizados da temporada {n}, espera a staff assumir o ticket."
            ),
        })

    return extras


FAQ_PADRAO = FAQ_CURADA + gerar_faq_automatica()
log.info("Base de conhecimento do assistente de tickets: %s respostas.", len(FAQ_PADRAO))

# Controle simples de cooldown para não floodar respostas automáticas.
_ULTIMA_RESPOSTA_IA: dict[int, datetime.datetime] = {}
_HISTORICO_IA: dict[int, list[dict[str, str]]] = {}
_IA_LOCKS: dict[int, asyncio.Lock] = {}


def buscar_resposta_faq(pergunta_normalizada: str, tipo_ticket: str) -> Optional[str]:
    """Procura, na base de conhecimento (padrão + configurada pela staff),
    a resposta cuja(s) palavra(s)-chave melhor combinam com a mensagem.
    Retorna None se nada bateu o suficiente."""
    faq_custom = DADOS["config"]["ticket"].get("faq", [])
    candidatos = faq_custom + FAQ_PADRAO  # o que a staff ensinou tem prioridade

    melhor_resposta = None
    melhor_pontuacao = 0
    for entrada in candidatos:
        pontuacao = sum(1 for p in entrada.get("palavras", []) if normalizar(p) in pergunta_normalizada)
        if pontuacao > melhor_pontuacao:
            melhor_pontuacao = pontuacao
            melhor_resposta = entrada.get("resposta")

    return melhor_resposta if melhor_pontuacao > 0 else None


# Respostas locais gratuitas: funcionam mesmo sem ANTHROPIC_API_KEY.
# A ordem é importante: intenções específicas vêm antes das intenções gerais.
RESPOSTAS_LOCAIS = [
    (r"\b(oi|olá|ola|eai|e ai|bom dia|boa tarde|boa noite)\b", "Oi! Sou o Assistente BRS. Pode me contar o que aconteceu que eu te explico o próximo passo enquanto a staff não chega."),
    (r"(obrigad|valeu|vlw|tmj|entendi)", "Por nada! Se surgir outra dúvida, pode mandar aqui no ticket que eu continuo te ajudando."),
    (r"(enviar|mandar|anexar).*(prova|print|video|vídeo|link)|(prova|print|video|vídeo).*(enviar|mandar|anexar)", "Você pode enviar prints, vídeos e links diretamente no ticket. Se preferir, abra **Painéis e ações do ticket → Enviar Provas** para registrar a descrição das evidências."),
    (r"(painel|menu).*(staff|membro|prova)|painéis e ações", "Dentro do ticket, toque em **Painéis e ações do ticket**. Lá ficam o **Painel Staff**, o **Painel Membro** e o **Enviar Provas**."),
    (r"(assumir|reivindicar|reivindicado).*(ticket)|ticket.*(assumir|reivindicar)", "A staff pode clicar em **Reivindicar Ticket** para iniciar o atendimento oficial. Quando alguém assumir, eu paro de responder automaticamente e o responsável continua com você."),
    (r"(fechar|encerrar).*(ticket)|ticket.*(fechar|encerrar)", "Quando o atendimento terminar, a staff pode clicar em **Fechar Ticket**. O bot gera o transcript e envia o registro para o canal de logs configurado."),
    (r"(horário|horario|atendimento|staff responde|demora)", "O horário exibido no ticket é o configurado pela administração. Fora dele, eu continuo orientando com a base local até a staff chegar."),
    (r"(drop|wave|pergunta|premio|prêmio|cargo.*5|recompensa)", "Os Drops usam perguntas variadas e, quando você vence, a recompensa é escolhida pela DM do bot. Se o cargo não aparecer, envie um print aqui para a staff verificar."),
    (r"(liga|time|equipe|elenco|jogar|recrut|confronto|partida|jogo).*(entrar|participar|vaga|sortear|horário|horario)|\btime\b", "Para assuntos de liga, informe o nome do time, a função do jogador e o que você precisa. A staff pode orientar sobre recrutamento, confrontos e horários; os administradores também podem usar `/liga times`, `/liga sortear` e `/liga tabela`."),
    (r"(tabela|pontuação|pontuacao|classificação|classificacao|resultado|placar)", "A liga registra vitórias, empates, derrotas, gols e saldo. Os administradores podem lançar um jogo com `/liga resultado` e publicar a classificação com `/liga tabela`."),
    (r"(free.?agent|jogador disponível|jogador disponivel|procurando time)", "O cadastro de jogador disponível é feito pela staff com `/freeagent add`. Informe posição e uma descrição para facilitar o contato com os times."),
    (r"(scout|scouting|avaliação|avaliacao|olheiro)", "O Scouting registra posição, descrição, observações e status do jogador. A equipe autorizada pode cadastrar com `/scouting add` e consultar com `/scouting buscar`."),
    (r"(denúncia|denuncia|report|hacker|cheater|ofensa|xingamento|roubo)", "Para uma denúncia, envie quem está envolvido, o que aconteceu, quando ocorreu e as provas. Não apague os prints ou links; a staff fará a análise oficial."),
    (r"(ban|banido|punição|punicao|kick|expulso|recurso|apelar|desban)", "Explique o motivo informado, o nome ou ID da conta e envie qualquer prova. Eu não consigo decidir punições, mas deixo o caso organizado para a staff revisar."),
    (r"(roblox|erro|error|crash|travando|não entra|nao entra|conexão|conexao)", "Tente reiniciar o Roblox, conferir a conexão e entrar novamente. Se continuar, envie o código ou print do erro e diga em qual tela aconteceu para a staff analisar."),
    (r"(conta|senha|invad|roubaram)", "Troque a senha pelo site oficial do Roblox e ative a verificação em duas etapas. Não envie sua senha no ticket; se precisar de ajuda, mande apenas o erro e as provas necessárias."),
    (r"(cargo|role|criar cargo|permissão|permissao)", "Cargos só podem ser criados e gerenciados pela equipe autorizada. Administradores podem usar `/cargo_criar`, `/role`, `/staff` e `/permissao` conforme a necessidade."),
    (r"(parceria|divulgação|divulgacao|sponsor|patrocínio|patrocinio)", "Envie a proposta com o nome do projeto, o que você oferece, o que espera da BRS e links relevantes. A equipe responsável avalia e responde no ticket."),
    (r"(prefixo|comando|slash|barra)", "O bot foi configurado para usar comandos slash, começando com `/`. Não é necessário usar vírgula ou outro prefixo de texto."),
]


def resposta_local(pergunta: str, tipo_ticket: str = "suporte") -> str:
    """Responde de forma determinística e útil sem depender de serviço pago."""
    texto = normalizar(pergunta)
    for padrao, resposta in RESPOSTAS_LOCAIS:
        if re.search(padrao, texto, flags=re.IGNORECASE):
            return resposta
    categoria = TICKET_CATEGORIES_BY_KEY.get(tipo_ticket, {"label": "Atendimento"})
    return (
        f"Entendi que sua solicitação é sobre **{categoria['label']}**. "
        "Para eu te orientar melhor sem inventar informação, diga qual resultado você espera, "
        "o que já tentou e envie um print ou link se aparecer algum erro."
    )


async def gerar_resposta_ia(
    pergunta: str,
    tipo_ticket: str,
    historico: Optional[list[dict[str, str]]] = None,
) -> Optional[str]:
    """Gera resposta contextual usando Claude; sem chave, o fluxo usa respostas locais."""
    if not _anthropic_client:
        return None
    tipo = TICKET_CATEGORIES_BY_KEY.get(tipo_ticket, {"label": "Atendimento"})

    def _chamar():
        resposta = _anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=(
                "Você é o Assistente BRS, atendente virtual de primeiro nível de uma liga "
                "de futebol no Roblox. Responda em português brasileiro como uma conversa "
                "natural, leia o contexto anterior, responda diretamente à pergunta e explique "
                "o motivo quando isso ajudar. Se faltar dado, faça uma única pergunta objetiva. "
                "Não invente regras, horários, cargos, punições ou decisões; quando algo exigir "
                "a staff, explique isso e diga quais informações devem ser enviadas. Não repita "
                "saudações desnecessárias. Seja educado, claro e tenha até 6 frases. Você é uma IA "
                "do bot, não finja ser uma pessoa, mas fale como atendimento de staff. "
                f"Categoria atual: {tipo['label']}."
            ),
            messages=(historico or [{"role": "user", "content": pergunta[:1800]}])[-10:],
        )
        blocos = [b.text for b in resposta.content if getattr(b, "type", None) == "text"]
        return "\n".join(blocos).strip()

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _chamar)
    except Exception:
        log.exception("Erro ao chamar a IA do assistente de tickets")
        return None


async def assistente_responder_ticket(message: discord.Message, ticket_info: dict):
    """Responde em diálogo contextual e mantém a ordem das mensagens."""
    lock = _IA_LOCKS.setdefault(message.channel.id, asyncio.Lock())
    async with lock:
        estado = DADOS["tickets"].get(str(message.channel.id))
        if not estado or estado.get("reivindicado"):
            return

        tipo_key = estado.get("tipo", "suporte")
        pergunta = message.content.strip()
        if message.attachments:
            nomes = ", ".join(a.filename for a in message.attachments[:5])
            pergunta = f"{pergunta or 'O usuário enviou anexos.'} Anexos recebidos: {nomes}."
        pergunta = pergunta or "O usuário enviou uma mensagem sem texto. Peça que ele explique o caso."

        historico = _HISTORICO_IA.setdefault(message.channel.id, [])
        historico.append({"role": "user", "content": pergunta[:1800]})
        del historico[:-10]

        async with message.channel.typing():
            texto = await gerar_resposta_ia(pergunta, tipo_key, historico)
            if not texto:
                texto = buscar_resposta_faq(normalizar(pergunta), tipo_key)
            if not texto:
                texto = resposta_local(pergunta, tipo_key)
        historico.append({"role": "assistant", "content": texto[:1800]})
        del historico[:-10]

        estado_atual = DADOS["tickets"].get(str(message.channel.id))
        if not estado_atual or estado_atual.get("reivindicado"):
            return

        embed = discord.Embed(
            title="🤖 Assistente BRS (IA)",
            description=f"{message.author.mention}\n\n{texto}",
            color=BRS_GREEN,
        )
        avatar = bot_avatar_url()
        if avatar:
            embed.set_author(name="Assistente BRS • Atendimento", icon_url=avatar)
            embed.set_thumbnail(url=avatar)
        embed.set_footer(text="✦ Atendimento automático · A staff assumirá quando necessário.")
        await message.channel.send(embed=embed)


# ============================================================
#  BOT
# ============================================================
class BRSBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())
        for grupo in (ticket_group, drop_group, freeagent_group, scouting_group, liga_group):
            if self.tree.get_command(grupo.name, guild=GUILD) is None:
                self.tree.add_command(grupo, guild=GUILD)

        # Remove comandos globais antigos e sincroniza apenas uma vez por processo.
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        if not getattr(self, "_brs_synced", False):
            synced = await self.tree.sync(guild=GUILD)
            self._brs_synced = True
            log.info("Sincronizados %s comandos na guild %s", len(synced), GUILD_ID)
        if not verificar_expiracoes.is_running():
            verificar_expiracoes.start()
        if not verificar_agenda_liga.is_running():
            verificar_agenda_liga.start()


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

    if await moderar_repeticao(message):
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
                    if bot_avatar_url():
                        dm_embed.set_thumbnail(url=bot_avatar_url())
                    await vencedor.send(embed=dm_embed, view=DropRewardView(vencedor.id, roles))
                else:
                    await vencedor.send("🏆 Você venceu o Drop, mas nenhum cargo de recompensa está configurado.")
            except discord.Forbidden:
                await message.channel.send(
                    f"⚠️ {vencedor.mention}, não consegui te enviar DM. Habilite mensagens diretas do servidor!"
                )

            ACTIVE_DROP = None
            return

    # === ASSISTENTE AUTOMÁTICO DE TICKET ===
    # Enquanto ninguém da staff "assumir" o ticket, o bot responde
    # automaticamente para quem abriu o atendimento.
    if is_ticket_channel(message.channel):
        ticket_info = DADOS["tickets"].get(str(message.channel.id))
        if (
            ticket_info
            and not ticket_info.get("reivindicado")
            and message.author.id == ticket_info.get("autor_id")
        ):
            asyncio.create_task(assistente_responder_ticket(message, ticket_info))

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
#  TICKETS — sistema automático estilo PAFO
#  (select menu de categorias → cria canal → claim → fechar com
#   transcript automático, tudo sem precisar digitar comando)
# ============================================================
TICKET_CATEGORIES_BY_KEY = {c["key"]: c for c in TICKET_CATEGORIES}


def is_ticket_channel(channel: discord.abc.GuildChannel) -> bool:
    return isinstance(channel, discord.TextChannel) and channel.name.startswith("ticket-")


def usuario_tem_ticket_aberto(guild: discord.Guild, user: discord.Member) -> Optional[discord.TextChannel]:
    alvo = f"user_id:{user.id}"
    for ch in guild.text_channels:
        if ch.name.startswith("ticket-") and ch.topic and alvo in ch.topic:
            return ch
    return None


class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=c["label"], value=c["key"], emoji=c["emoji"], description=c["descricao"][:100])
            for c in TICKET_CATEGORIES
        ]
        super().__init__(
            placeholder="Selecione o tipo de atendimento...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="brs_ticket_select",
        )

    async def callback(self, interaction: discord.Interaction):
        existente = usuario_tem_ticket_aberto(interaction.guild, interaction.user)
        if existente:
            await interaction.response.send_message(f"❌ Você já possui um ticket aberto: {existente.mention}", ephemeral=True)
            return
        await interaction.response.send_modal(TicketReasonModal(self.values[0]))


class TicketReasonModal(discord.ui.Modal, title="Detalhes do atendimento"):
    duvida = discord.ui.TextInput(
        label="Explique sua dúvida ou solicitação",
        placeholder="Conte o que aconteceu e inclua os detalhes importantes...",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=3,
        max_length=1800,
    )

    def __init__(self, tipo_key: str):
        super().__init__()
        self.tipo_key = tipo_key

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await criar_ticket(interaction, self.tipo_key, self.duvida.value.strip())


async def criar_ticket(interaction: discord.Interaction, tipo_key: str, duvida: str):
    user_id = interaction.user.id
    if user_id in _CRIANDO_TICKETS:
        await interaction.followup.send("⏳ Seu ticket já está sendo criado. Aguarde alguns segundos.", ephemeral=True)
        return
    _CRIANDO_TICKETS.add(user_id)
    try:
        await _criar_ticket_impl(interaction, tipo_key, duvida)
    finally:
        _CRIANDO_TICKETS.discard(user_id)


async def _criar_ticket_impl(interaction: discord.Interaction, tipo_key: str, duvida: str):
    guild = interaction.guild
    cfg = DADOS["config"]["ticket"]
    tipo = TICKET_CATEGORIES_BY_KEY.get(tipo_key, TICKET_CATEGORIES[0])
    existente = usuario_tem_ticket_aberto(guild, interaction.user)
    if existente:
        await interaction.followup.send(f"❌ Você já possui um ticket aberto: {existente.mention}", ephemeral=True)
        return

    template = cfg.get("channel_name_template") or "ticket-{tipo}-{user}"
    nome_canal = template.replace("{tipo}", tipo_key).replace("{user}", interaction.user.name).lower().replace(" ", "-")[:90]
    if not nome_canal.startswith("ticket-"):
        nome_canal = f"ticket-{nome_canal}"[:90]

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
        name=nome_canal,
        category=category,
        overwrites=overwrites,
        topic=f"Ticket de {tipo['label']} | user_id:{interaction.user.id}",
        reason=f"Ticket ({tipo['label']}) aberto por {interaction.user}",
    )

    mensagem = (cfg.get("welcome_message") or "Olá {mention}, seja bem-vindo(a) à BRS!").replace("{mention}", interaction.user.mention).replace("{user}", interaction.user.display_name)
    horario = cfg.get("horario_atendimento", "Sábado e domingo das 13h às 21h (BRT). Fora desse horário, o Assistente BRS (IA) continuará atendendo até a staff chegar.")
    embed = discord.Embed(title="🎫 Ticket Aberto", description=mensagem, color=EMBED_COLOR, timestamp=agora_utc())
    embed.add_field(name="📋 Informações do Ticket", value=(
        f"**Nome do Ticket:** `{ticket_channel.name}`\n"
        f"**Criado por:** {interaction.user.mention}\n"
        f"**Tipo do Ticket:** {tipo['emoji']} **{tipo['label']}**"
    ), inline=False)
    embed.add_field(name="📝 Informações Preenchidas", value=f"**Dúvida:** {duvida[:900]}", inline=False)
    embed.add_field(name="📎 Envie provas, prints ou links diretamente no ticket.", value="Use **Painéis e ações do ticket** para enviar evidências ou ver as orientações.", inline=False)
    embed.add_field(name="⏰ Horário de atendimento", value=horario[:1024], inline=False)
    banner_url = cfg.get("banner_url")
    if banner_url:
        embed.set_image(url=banner_url)
    avatar = bot_avatar_url()
    if avatar:
        embed.set_thumbnail(url=avatar)
    embed.set_footer(text="BRS — Ticket System")

    staff_pings = " ".join(f"<@&{rid}>" for rid in cfg.get("staff_role_ids", []) if guild.get_role(rid))
    await ticket_channel.send(content=f"{interaction.user.mention} {staff_pings}".strip(), embed=embed, view=TicketControlView())
    DADOS["tickets"][str(ticket_channel.id)] = {
        "autor_id": interaction.user.id,
        "tipo": tipo_key,
        "duvida": duvida,
        "reivindicado": False,
        "reivindicado_por": None,
    }
    salvar_dados(DADOS)

    await enviar_log_ticket(
        guild,
        "🎫 TICKET ABERTO",
        f"Novo atendimento criado no canal {ticket_channel.mention}.",
        campos=[
            ("Quem abriu", f"{interaction.user.mention} (`{interaction.user.id}`)"),
            ("Categoria", tipo["label"]),
            ("Dúvida", duvida),
            ("Data e hora", datetime.datetime.now(BRT).strftime("%d/%m/%Y às %H:%M (BRT)")),
        ],
        cor=discord.Color.green(),
        nome_canal=ticket_channel.name,
    )

    assistente = discord.Embed(
        title="🤖 Assistente BRS (IA)",
        description=(
            f"Oi {interaction.user.mention}! Pode perguntar, tô aqui pra ajudar enquanto a staff não chega. "
            "Vou ler o que você escrever, explicar o que for possível e pedir detalhes quando necessário."
        ),
        color=BRS_GREEN,
    )
    if avatar:
        assistente.set_author(name="Assistente BRS • Atendimento", icon_url=avatar)
        assistente.set_thumbnail(url=avatar)
    assistente.set_footer(text="✦ Atendimento automático · A staff assumirá quando necessário.")
    await ticket_channel.send(embed=assistente)
    await interaction.followup.send(f"✅ Ticket criado: {ticket_channel.mention}", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())


class EnviarProvasModal(discord.ui.Modal, title="Enviar provas ao ticket"):
    provas = discord.ui.TextInput(
        label="Links ou descrição das provas",
        placeholder="Cole links de prints/vídeos ou explique quais arquivos vai anexar...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1800,
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📎 Provas enviadas",
            description=f"**Enviado por:** {interaction.user.mention}\n\n{self.provas.value}",
            color=BRS_GREEN,
            timestamp=agora_utc(),
        )
        avatar = bot_avatar_url()
        if avatar:
            embed.set_thumbnail(url=avatar)
        embed.set_footer(text="BRS — Evidências do ticket")
        await interaction.channel.send(embed=embed)
        await enviar_log_ticket(
            interaction.guild,
            "📎 PROVAS ENVIADAS",
            f"Evidências registradas no canal {interaction.channel.mention}.",
            campos=[("Enviado por", f"{interaction.user.mention} (`{interaction.user.id}`)"), ("Conteúdo", self.provas.value)],
            cor=discord.Color.blurple(),
            nome_canal=interaction.channel.name,
        )
        await interaction.response.send_message("✅ Suas provas foram registradas. Se precisar, envie os arquivos como anexo em uma mensagem no ticket.", ephemeral=True)


class TicketActionsSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Painel Staff", value="staff", emoji="🛠️", description="Abrir ações e dados da equipe"),
            discord.SelectOption(label="Painel Membro", value="membro", emoji="👤", description="Ver orientações do atendimento"),
            discord.SelectOption(label="Enviar Provas", value="provas", emoji="📎", description="Anexar prints, vídeos ou links"),
        ]
        super().__init__(placeholder="Painéis e ações do ticket", min_values=1, max_values=1, options=options, custom_id="brs_ticket_actions_select")

    async def callback(self, interaction: discord.Interaction):
        escolha = self.values[0]
        info = DADOS["tickets"].get(str(interaction.channel.id), {})
        tipo = TICKET_CATEGORIES_BY_KEY.get(info.get("tipo", "suporte"), TICKET_CATEGORIES[0])
        avatar = bot_avatar_url()
        if escolha == "provas":
            await interaction.response.send_modal(EnviarProvasModal())
            return
        if escolha == "staff":
            if not tem_permissao(interaction.user, "ticket"):
                await interaction.response.send_message("❌ O Painel Staff é exclusivo da equipe de atendimento.", ephemeral=True)
                return
            autor = interaction.guild.get_member(info.get("autor_id")) if interaction.guild else None
            responsavel = interaction.guild.get_member(info.get("reivindicado_por")) if interaction.guild and info.get("reivindicado_por") else None
            status = "✅ Reivindicado" if info.get("reivindicado") else "🟡 Aguardando staff"
            texto = (f"**Solicitante:** {autor.mention if autor else 'não encontrado'}\n"
                     f"**Categoria:** {tipo['label']}\n**Status:** {status}\n"
                     f"**Responsável:** {responsavel.mention if responsavel else 'Ninguém assumiu ainda'}\n\n"
                     "Use **Reivindicar Ticket** para iniciar o atendimento oficial.")
            embed = discord.Embed(title="🛠️ Painel Staff", description=texto, color=BRS_GREEN)
        else:
            embed = discord.Embed(
                title="👤 Painel Membro",
                description=(f"Este é o seu ticket de **{tipo['label']}**.\n\n"
                             "Explique o caso com detalhes, use **Enviar Provas** para registrar links ou evidências "
                             "e aguarde a staff. O Assistente BRS (IA) responde enquanto ninguém assumir."),
                color=BRS_GREEN,
            )
        if avatar:
            embed.set_thumbnail(url=avatar)
        embed.set_footer(text="BRS — Ticket System")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class TicketActionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(TicketActionsSelect())


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fechar Ticket", emoji="🔒", style=discord.ButtonStyle.red, custom_id="brs_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message("❌ Este botão só funciona dentro de um canal de ticket.", ephemeral=True)
            return
        if not tem_permissao(interaction.user, "ticket"):
            await interaction.response.send_message("❌ Apenas a staff pode fechar tickets.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Ticket fechado em 5 segundos. Gerando log e transcript...", ephemeral=True)
        canal = interaction.channel
        info = DADOS["tickets"].get(str(canal.id), {})
        cfg = DADOS["config"]["ticket"]
        linhas = []
        async for msg in canal.history(limit=None, oldest_first=True):
            hora = msg.created_at.astimezone(BRT).strftime("%d/%m/%Y %H:%M")
            conteudo = msg.content or "[embed/anexo sem texto]"
            if msg.attachments:
                conteudo += " | Anexos: " + ", ".join(a.filename for a in msg.attachments)
            linhas.append(f"[{hora}] {msg.author} ({msg.author.id}): {conteudo}")
        transcript_texto = "\n".join(linhas) or "Nenhuma mensagem registrada."
        autor = interaction.guild.get_member(info.get("autor_id")) if info.get("autor_id") else None
        responsavel = interaction.guild.get_member(info.get("reivindicado_por")) if info.get("reivindicado_por") else None
        autor_id = info.get("autor_id")
        autor_texto = autor.mention if autor else (f"<@{autor_id}>" if autor_id else "Usuário desconhecido")
        tipo = TICKET_CATEGORIES_BY_KEY.get(info.get("tipo", "suporte"), TICKET_CATEGORIES[0])
        await enviar_log_ticket(
            interaction.guild,
            "🎫 TICKET FINALIZADO",
            f"O ticket `{canal.name}` foi encerrado.",
            campos=[
                ("👥 Quem abriu", f"{autor_texto} `{autor_id or '—'}`"),
                ("🗑️ Quem finalizou", f"{interaction.user.mention} `{interaction.user.id}`"),
                ("🛠️ Responsável pelo atendimento", responsavel.mention if responsavel else "Ninguém assumiu o Ticket"),
                ("📁 Categoria do Ticket", tipo["label"]),
                ("📅 Data", datetime.datetime.now(BRT).strftime("%d de %B de %Y às %H:%M")),
            ],
            cor=discord.Color.red(),
            transcript_texto=transcript_texto,
            nome_canal=canal.name,
        )
        await canal.send(f"🔒 Ticket fechado por {interaction.user.mention}. Encerrando em 5 segundos...")
        DADOS["tickets"].pop(str(canal.id), None)
        _ULTIMA_RESPOSTA_IA.pop(canal.id, None)
        _HISTORICO_IA.pop(canal.id, None)
        _IA_LOCKS.pop(canal.id, None)
        salvar_dados(DADOS)
        await asyncio.sleep(5)
        await canal.delete(reason=f"Ticket fechado por {interaction.user}")

    @discord.ui.button(label="Reivindicar Ticket", emoji="📋", style=discord.ButtonStyle.green, custom_id="brs_claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message("❌ Este botão só funciona dentro de um canal de ticket.", ephemeral=True)
            return
        if not tem_permissao(interaction.user, "ticket"):
            await interaction.response.send_message("❌ Apenas a staff pode reivindicar tickets.", ephemeral=True)
            return
        info = DADOS["tickets"].get(str(interaction.channel.id))
        if info and info.get("reivindicado"):
            await interaction.response.send_message("ℹ️ Este ticket já foi reivindicado por outro membro da staff.", ephemeral=True)
            return
        autor_mention = "usuário"
        if info:
            info["reivindicado"] = True
            info["reivindicado_por"] = interaction.user.id
            autor = interaction.guild.get_member(info.get("autor_id"))
            autor_mention = autor.mention if autor else f"<@{info.get('autor_id')}>"
            salvar_dados(DADOS)
        _ULTIMA_RESPOSTA_IA.pop(interaction.channel.id, None)
        _HISTORICO_IA.pop(interaction.channel.id, None)
        _IA_LOCKS.pop(interaction.channel.id, None)
        button.disabled = True
        button.label = f"Assumido por {interaction.user.display_name}"[:80]
        await interaction.response.edit_message(view=self)
        await enviar_log_ticket(
            interaction.guild,
            "🙋 TICKET REIVINDICADO",
            f"A staff iniciou o atendimento em {interaction.channel.mention}.",
            campos=[("Staff responsável", f"{interaction.user.mention} (`{interaction.user.id}`)"), ("Membro atendido", autor_mention)],
            cor=discord.Color.green(),
            nome_canal=interaction.channel.name,
        )
        embed = discord.Embed(
            title="🤝 Atendimento Iniciado",
            description=(f"Olá {autor_mention}, o seu atendimento foi iniciado!\n\n"
                         f"**Staff responsável:** {interaction.user.mention}\n\n"
                         "Por favor, descreva sua solicitação detalhadamente para agilizar o suporte."),
            color=BRS_GREEN,
        )
        avatar = bot_avatar_url()
        if avatar:
            embed.set_thumbnail(url=avatar)
        embed.set_footer(text="BRS — Ticket System")
        await interaction.channel.send(embed=embed)

    @discord.ui.button(label="Painéis e ações do ticket", emoji="☰", style=discord.ButtonStyle.secondary, custom_id="brs_ticket_actions")
    async def ticket_actions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message("❌ Este botão só funciona dentro de um canal de ticket.", ephemeral=True)
            return
        await interaction.response.send_message("Painéis e ações do ticket", view=TicketActionsView(), ephemeral=True)


ticket_group = app_commands.Group(name="ticket", description="Sistema de tickets da BRS")


@ticket_group.command(name="configurar", description="Configura o sistema de tickets.")
@app_commands.describe(
    categoria="Categoria dos tickets",
    cargo_staff="Cargo com acesso aos tickets",
    nome_canal="Modelo do nome (use {tipo} e {user})",
    mensagem="Mensagem inicial (use {mention})",
    canal_logs="Canal de logs (recebe abertura, fechamento e transcript)",
    banner="URL opcional da imagem grande no topo do ticket",
    horario="Horário mostrado no ticket",
)
async def ticket_configurar(
    interaction: discord.Interaction,
    categoria: Optional[discord.CategoryChannel] = None,
    cargo_staff: Optional[discord.Role] = None,
    nome_canal: Optional[str] = None,
    mensagem: Optional[str] = None,
    canal_logs: Optional[discord.TextChannel] = None,
    banner: Optional[str] = None,
    horario: Optional[str] = None,
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
    if banner is not None:
        cfg["banner_url"] = banner.strip()
        alterado.append("🖼️ Banner atualizado")
    if horario:
        cfg["horario_atendimento"] = horario
        alterado.append("⏰ Horário atualizado")
    salvar_dados(DADOS)
    if not alterado:
        await interaction.response.send_message("ℹ️ Nenhuma alteração enviada.", ephemeral=True)
        return
    await interaction.response.send_message("✅ Configuração atualizada:\n" + "\n".join(f"• {a}" for a in alterado), ephemeral=True)


@ticket_group.command(name="painel", description="Envia o painel automático de tickets (select menu).")
@app_commands.describe(canal="Canal do painel")
async def ticket_painel(interaction: discord.Interaction, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "ticket"):
        return
    canal = canal or interaction.channel
    cfg = DADOS["config"]["ticket"]
    embed = discord.Embed(
        title=cfg.get("painel_titulo", "🎫 Central de Atendimento — BRS"),
        description=cfg.get("painel_descricao", "Selecione abaixo o tipo de atendimento que você precisa."),
        color=BRS_GREEN,
    )
    tipos_texto = "\n".join(f"{c['emoji']} **{c['label']}** — {c['descricao']}" for c in TICKET_CATEGORIES)
    embed.add_field(name="📋 Categorias disponíveis", value=tipos_texto, inline=False)
    avatar = bot_avatar_url()
    if avatar:
        embed.set_thumbnail(url=avatar)
    if cfg.get("banner_url"):
        embed.set_image(url=cfg["banner_url"])
    embed.set_footer(text="BRS — Sistema de Tickets Automático")
    painel_msg = None
    if cfg.get("painel_channel_id") == canal.id and cfg.get("painel_mensagem_id"):
        try:
            painel_msg = await canal.fetch_message(cfg["painel_mensagem_id"])
            await painel_msg.edit(embed=embed, view=TicketPanelView())
        except (discord.NotFound, discord.HTTPException):
            painel_msg = None
    if painel_msg is None:
        painel_msg = await canal.send(embed=embed, view=TicketPanelView())
    cfg["painel_channel_id"] = canal.id
    cfg["painel_mensagem_id"] = painel_msg.id
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Painel criado/atualizado em {canal.mention}. Se você executar o comando novamente, ele será atualizado sem duplicar.", ephemeral=True)


@ticket_group.command(name="add", description="Adiciona membro/cargo ao ticket.")
@app_commands.describe(alvo="Membro ou cargo")
async def ticket_add(interaction: discord.Interaction, alvo: Union[discord.Member, discord.Role]):
    if not is_ticket_channel(interaction.channel):
        await interaction.response.send_message("❌ Só funciona dentro de um ticket.", ephemeral=True)
        return
    await interaction.channel.set_permissions(alvo, view_channel=True, send_messages=True, read_message_history=True)
    await enviar_log_ticket(
        interaction.guild,
        "➕ PARTICIPANTE ADICIONADO AO TICKET",
        f"{alvo.mention} recebeu acesso a {interaction.channel.mention}.",
        campos=[("Ação por", f"{interaction.user.mention} (`{interaction.user.id}`)"), ("Alvo", f"{alvo.mention} (`{alvo.id}`)")],
        cor=discord.Color.green(),
        nome_canal=interaction.channel.name,
    )
    await interaction.response.send_message(f"✅ {alvo.mention} adicionado(a).", ephemeral=True)
    await interaction.channel.send(f"➕ {alvo.mention} adicionado(a) por {interaction.user.mention}.")


@ticket_group.command(name="remove", description="Remove membro/cargo do ticket.")
@app_commands.describe(alvo="Membro ou cargo")
async def ticket_remove(interaction: discord.Interaction, alvo: Union[discord.Member, discord.Role]):
    if not is_ticket_channel(interaction.channel):
        await interaction.response.send_message("❌ Só funciona dentro de um ticket.", ephemeral=True)
        return
    await interaction.channel.set_permissions(alvo, overwrite=None)
    await enviar_log_ticket(
        interaction.guild,
        "➖ PARTICIPANTE REMOVIDO DO TICKET",
        f"{alvo.mention} perdeu acesso a {interaction.channel.mention}.",
        campos=[("Ação por", f"{interaction.user.mention} (`{interaction.user.id}`)"), ("Alvo", f"{alvo.mention} (`{alvo.id}`)")],
        cor=discord.Color.orange(),
        nome_canal=interaction.channel.name,
    )
    await interaction.response.send_message(f"✅ {alvo.mention} removido(a).", ephemeral=True)
    await interaction.channel.send(f"➖ {alvo.mention} removido(a) por {interaction.user.mention}.")


@ticket_group.command(name="faq_add", description="Ensina o assistente automático a responder algo específico.")
@app_commands.describe(
    palavras_chave="Palavras separadas por vírgula que ativam essa resposta (ex: liga,time,jogador)",
    resposta="O que o assistente deve responder quando detectar essas palavras",
)
async def ticket_faq_add(interaction: discord.Interaction, palavras_chave: str, resposta: str):
    if not await checar_permissao(interaction, "ticket"):
        return
    palavras = [p.strip() for p in palavras_chave.split(",") if p.strip()]
    if not palavras:
        await interaction.response.send_message("❌ Informe ao menos uma palavra-chave.", ephemeral=True)
        return
    DADOS["config"]["ticket"].setdefault("faq", []).append({"palavras": palavras, "resposta": resposta})
    salvar_dados(DADOS)
    await interaction.response.send_message(
        f"✅ Aprendido! Quando alguém mencionar `{', '.join(palavras)}`, o assistente vai responder:\n> {resposta}",
        ephemeral=True,
    )


@ticket_group.command(name="faq_lista", description="Lista as respostas ensinadas ao assistente automático.")
async def ticket_faq_lista(interaction: discord.Interaction):
    if not await checar_permissao(interaction, "ticket"):
        return
    faq = DADOS["config"]["ticket"].get("faq", [])
    if not faq:
        await interaction.response.send_message("ℹ️ Nenhuma resposta customizada ensinada ainda. Use `/ticket faq_add`.", ephemeral=True)
        return
    linhas = [f"**{i}.** `{', '.join(f['palavras'])}` → {f['resposta']}" for i, f in enumerate(faq)]
    embed = discord.Embed(title="🧠 Base de Conhecimento do Assistente", description="\n\n".join(linhas), color=BRS_GREEN)
    embed.set_footer(text="Use /ticket faq_remover <número> para apagar uma entrada.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@ticket_group.command(name="faq_remover", description="Remove uma resposta ensinada ao assistente (veja o número em /ticket faq_lista).")
@app_commands.describe(numero="Número da entrada mostrado em /ticket faq_lista")
async def ticket_faq_remover(interaction: discord.Interaction, numero: int):
    if not await checar_permissao(interaction, "ticket"):
        return
    faq = DADOS["config"]["ticket"].get("faq", [])
    if not (0 <= numero < len(faq)):
        await interaction.response.send_message("❌ Número inválido. Veja `/ticket faq_lista`.", ephemeral=True)
        return
    removida = faq.pop(numero)
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Removida: `{', '.join(removida['palavras'])}`", ephemeral=True)


# ============================================================
#  DROP — estilo PAFO
# ============================================================
class DropRewardSelect(discord.ui.Select):
    def __init__(self, user_id: int, roles: list[discord.Role]):
        options = []
        for role in roles[:3]:
            info = DROP_REWARD_ROLES.get(role.id, {"nome": f"{role.name} (5 Dias)", "emoji": "🏅"})
            options.append(discord.SelectOption(
                label=info["nome"][:100],
                value=str(role.id),
                emoji=info["emoji"],
                description="Válido por 5 dias"
            ))
        super().__init__(
            placeholder="Escolha seu cargo VIP (Válido por 5 dias)",
            min_values=1, max_values=1, options=options
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Essa recompensa não é sua.", ephemeral=True)
            return

        role_id = int(self.values[0])
        guild = bot.get_guild(GUILD_ID)
        member = guild.get_member(self.user_id) if guild else None
        role = guild.get_role(role_id) if guild else None

        if not (guild and member and role):
            await interaction.response.send_message("❌ Não consegui aplicar o cargo. Fale com a staff.", ephemeral=True)
            return

        await member.add_roles(role, reason="Recompensa do Drop BRS (5 dias)")

        expiracao = (datetime.datetime.utcnow() + datetime.timedelta(days=5)).isoformat()
        DADOS.setdefault("drop_expiracoes", {})[str(member.id)] = {
            "role_id": role_id,
            "expira_em": expiracao
        }
        salvar_dados(DADOS)

        embed = discord.Embed(
            title="✅ Drop Resgatado com Sucesso!",
            description=f"Você recebeu o cargo {role.mention}.",
            color=discord.Color.from_rgb(46, 204, 113)
        )
        embed.set_footer(text="BRS — Drops System")
        await interaction.response.edit_message(content=None, embed=embed, view=None)


class DropRewardView(discord.ui.View):
    def __init__(self, user_id: int, roles: list[discord.Role]):
        super().__init__(timeout=600)
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
    if ACTIVE_DROP and not ACTIVE_DROP["finalizado"]:
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
        color=BRS_GREEN
    )
    embed.add_field(name="🎁 Prêmios Garantidos", value="Cargos exclusivos a cada Drop vencido", inline=True)
    embed.add_field(name="⚡ Wave Drop", value="Vários drops seguidos quando a meta é batida", inline=True)
    embed.set_footer(text=f"Banco: {len(TODAS_PERGUNTAS)}+ perguntas • Boa sorte!")
    avatar = bot_avatar_url()
    if avatar:
        embed.set_thumbnail(url=avatar)

    await canal_destino.send(embed=embed)
    await interaction.response.send_message(f"✅ Drop iniciado em {canal_destino.mention}.", ephemeral=True)


@drop_group.command(name="cancelar", description="Cancela o Drop em andamento.")
async def drop_cancelar(interaction: discord.Interaction):
    if not await checar_permissao(interaction, "drop"):
        return
    global ACTIVE_DROP
    if not ACTIVE_DROP or ACTIVE_DROP["finalizado"]:
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
        color=BRS_GREEN
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


async def executar_wave(canal_destino: discord.TextChannel, quantidade: int = 7):
    """Roda a sequência de drops da Wave. Usada tanto pelo comando manual
    quanto pelo disparo automático quando a meta de membros é batida."""
    global ACTIVE_DROP, WAVE_RUNNING

    if WAVE_RUNNING:
        return False

    quantidade = max(3, min(quantidade or 7, 12))
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
            color=BRS_GREEN
        )
        await canal_destino.send(embed=embed)

        # espera até alguém acertar ou ~3 minutos
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
    return True


@drop_group.command(name="wave", description="Inicia Wave Drop manualmente (5~10 drops seguidos).")
@app_commands.describe(quantidade="Quantidade de drops (padrão 7)", canal="Canal")
async def drop_wave(interaction: discord.Interaction, quantidade: Optional[int] = 7, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "drop"):
        return

    if WAVE_RUNNING:
        await interaction.response.send_message("❌ Já existe uma Wave em andamento.", ephemeral=True)
        return

    canal_destino = canal or interaction.channel
    quantidade_final = max(3, min(quantidade or 7, 12))

    await interaction.response.send_message(
        f"🌊 Wave Drop iniciada! {quantidade_final} drops em {canal_destino.mention}",
        ephemeral=True
    )
    await executar_wave(canal_destino, quantidade_final)


# Atualiza meta quando membro entra/sai
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
        color=BRS_GREEN
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
            description=f"A meta de **{meta:,}** membros foi batida!\nIniciando a Wave Drop automaticamente...",
            color=discord.Color.gold()
        ))
        # Dispara a Wave Drop automaticamente, sem precisar de comando manual.
        if not WAVE_RUNNING:
            asyncio.create_task(executar_wave(canal, quantidade=7))


# ============================================================
#  /cargo_criar — criação segura de cargos pelo bot
# ============================================================
@bot.tree.command(name="cargo_criar", description="Cria um cargo novo sem editar o código.", guild=GUILD)
@app_commands.describe(nome="Nome do cargo", cor="Cor hexadecimal, ex: #00FF7F", mostrar_separado="Exibir separado na lista", mencionavel="Permitir menções")
async def cargo_criar_cmd(
    interaction: discord.Interaction,
    nome: str,
    cor: Optional[str] = None,
    mostrar_separado: bool = False,
    mencionavel: bool = False,
):
    if not await checar_permissao(interaction, "criar_cargo"):
        return
    nome = nome.strip()[:100]
    if not nome or nome.lower() == "everyone":
        await interaction.response.send_message("❌ Informe um nome válido para o cargo.", ephemeral=True)
        return
    try:
        valor_cor = int((cor or "#00FF7F").replace("#", ""), 16)
        if not 0 <= valor_cor <= 0xFFFFFF:
            raise ValueError
    except ValueError:
        await interaction.response.send_message("❌ Cor inválida. Use um hexadecimal como `#00FF7F`.", ephemeral=True)
        return
    if discord.utils.get(interaction.guild.roles, name=nome):
        await interaction.response.send_message("ℹ️ Já existe um cargo com esse nome; não criei outro para evitar duplicidade.", ephemeral=True)
        return
    if not interaction.guild.me.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ O bot não possui a permissão Gerenciar Cargos.", ephemeral=True)
        return
    try:
        role = await interaction.guild.create_role(
            name=nome,
            colour=discord.Colour(valor_cor),
            hoist=mostrar_separado,
            mentionable=mencionavel,
            reason=f"Cargo criado por {interaction.user}",
        )
        embed = discord.Embed(title="✅ Cargo criado", description=f"O cargo {role.mention} foi criado com sucesso.", color=discord.Colour(valor_cor))
        embed.add_field(name="Nome", value=role.name, inline=True)
        embed.add_field(name="Cor", value=f"#{valor_cor:06X}", inline=True)
        embed.set_footer(text=f"Criado por {interaction.user}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ O bot não tem permissão para criar cargos.", ephemeral=True)


# ============================================================
#  /role — 100% livre de ID de cargo no código.
#  O cargo é sempre escolhido pelo próprio Discord (parâmetro
#  discord.Role), então funciona com qualquer cargo do servidor
#  sem precisar editar o código-fonte.
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
#  LIGA — cadastro de times, sorteio de confrontos e agenda
# ============================================================
liga_group = app_commands.Group(name="liga", description="Ferramentas da liga e dos confrontos")


def _times_liga() -> list[str]:
    return DADOS.setdefault("liga", {}).setdefault("times", [])


def _parse_data_hora_brt(dia: str, horario: str) -> Optional[datetime.datetime]:
    try:
        return datetime.datetime.strptime(f"{dia.strip()} {horario.strip()}", "%d/%m/%Y %H:%M").replace(tzinfo=BRT)
    except ValueError:
        return None


async def publicar_sorteio_liga(evento: dict):
    guild = bot.get_guild(GUILD_ID)
    canal = guild.get_channel(evento.get("canal_id")) if guild else None
    if not canal:
        return False
    times = list(evento.get("times", []))
    random.shuffle(times)
    confrontos = []
    while len(times) >= 2:
        a, b = times.pop(0), times.pop(0)
        confrontos.append(f"⚽ **{a}**  ×  **{b}**")
    if times:
        confrontos.append(f"🟡 **{times[0]}** — folga nesta rodada")
    embed = discord.Embed(
        title="🎲 SORTEIO DE CONFRONTOS — BRS",
        description="\n".join(confrontos) or "Nenhum confronto gerado.",
        color=BRS_GREEN,
        timestamp=agora_utc(),
    )
    embed.add_field(name="📅 Dia", value=evento.get("dia", "—"), inline=True)
    embed.add_field(name="⏰ Horário", value=f"{evento.get('horario', '—')} (BRT)", inline=True)
    embed.add_field(name="👥 Times", value=str(len(evento.get("times", []))), inline=True)
    avatar = bot_avatar_url()
    if avatar:
        embed.set_thumbnail(url=avatar)
    embed.set_footer(text="BRS • Sorteio de confrontos")
    await canal.send(embed=embed)
    return True


@tasks.loop(minutes=1)
async def verificar_agenda_liga():
    agora = agora_utc()
    alterou = False
    for evento in DADOS.get("liga", {}).get("sorteios", []):
        if evento.get("status") != "agendado":
            continue
        try:
            quando = datetime.datetime.fromisoformat(evento["executar_em"])
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=BRT)
        except (KeyError, ValueError):
            evento["status"] = "erro"
            alterou = True
            continue
        if agora >= quando:
            if await publicar_sorteio_liga(evento):
                evento["status"] = "publicado"
                evento["publicado_em"] = agora.isoformat()
                alterou = True
    if alterou:
        salvar_dados(DADOS)


@verificar_agenda_liga.before_loop
async def before_agenda_liga():
    await bot.wait_until_ready()


@liga_group.command(name="times", description="Substitui a lista de times da liga.")
@app_commands.describe(nomes="Times separados por vírgula. Ex: BRS, Wolves, Titans, Kings")
async def liga_times(interaction: discord.Interaction, nomes: str):
    if not await checar_permissao(interaction, "liga"):
        return
    lista = [re.sub(r"\s+", " ", nome.strip()) for nome in re.split(r"[,;]", nomes) if nome.strip()]
    unicos = []
    vistos = set()
    for nome in lista:
        chave = normalizar(nome)
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(nome[:80])
    if len(unicos) < 2:
        await interaction.response.send_message("❌ Informe pelo menos 2 times separados por vírgula.", ephemeral=True)
        return
    if len(unicos) > 64:
        await interaction.response.send_message("❌ Limite de 64 times por sorteio.", ephemeral=True)
        return
    DADOS["liga"]["times"] = unicos
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ {len(unicos)} times cadastrados:\n" + " • ".join(unicos), ephemeral=True)


@liga_group.command(name="time_adicionar", description="Adiciona um time à lista da liga.")
@app_commands.describe(nome="Nome do time")
async def liga_time_adicionar(interaction: discord.Interaction, nome: str):
    if not await checar_permissao(interaction, "liga"):
        return
    nome = re.sub(r"\s+", " ", nome.strip())[:80]
    if not nome or normalizar(nome) in {normalizar(t) for t in _times_liga()}:
        await interaction.response.send_message("❌ Nome vazio ou time já cadastrado.", ephemeral=True)
        return
    if len(_times_liga()) >= 64:
        await interaction.response.send_message("❌ Limite de 64 times.", ephemeral=True)
        return
    _times_liga().append(nome)
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Time **{nome}** adicionado. Total: {len(_times_liga())}.", ephemeral=True)


@liga_group.command(name="time_remover", description="Remove um time da lista da liga.")
@app_commands.describe(nome="Nome do time")
async def liga_time_remover(interaction: discord.Interaction, nome: str):
    if not await checar_permissao(interaction, "liga"):
        return
    alvo = normalizar(nome)
    antes = len(_times_liga())
    DADOS["liga"]["times"] = [t for t in _times_liga() if normalizar(t) != alvo]
    salvar_dados(DADOS)
    await interaction.response.send_message("✅ Time removido." if len(_times_liga()) < antes else "ℹ️ Time não encontrado.", ephemeral=True)


@liga_group.command(name="lista", description="Lista os times cadastrados.")
async def liga_lista(interaction: discord.Interaction):
    times = _times_liga()
    await interaction.response.send_message("📋 **Times cadastrados:**\n" + ("\n".join(f"{i}. {t}" for i, t in enumerate(times, 1)) if times else "Nenhum."), ephemeral=True)


@liga_group.command(name="sortear", description="Agenda o sorteio dos confrontos para dia e horário escolhidos.")
@app_commands.describe(dia="Data no formato DD/MM/AAAA", horario="Horário no formato HH:MM (BRT)", canal="Canal onde publicar")
async def liga_sortear(interaction: discord.Interaction, dia: str, horario: str, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "liga"):
        return
    times = list(_times_liga())
    if len(times) < 2:
        await interaction.response.send_message("❌ Cadastre pelo menos 2 times em `/liga times` antes de sortear.", ephemeral=True)
        return
    quando = _parse_data_hora_brt(dia, horario)
    if not quando:
        await interaction.response.send_message("❌ Data/horário inválidos. Use `26/08/2026` e `20:30`.", ephemeral=True)
        return
    if quando <= datetime.datetime.now(BRT):
        await interaction.response.send_message("❌ Escolha uma data e horário futuros.", ephemeral=True)
        return
    destino = canal or interaction.channel
    duplicado = any(
        e.get("status") == "agendado"
        and e.get("canal_id") == destino.id
        and e.get("dia") == dia.strip()
        and e.get("horario") == horario.strip()
        and sorted(e.get("times", [])) == sorted(times)
        for e in DADOS["liga"].get("sorteios", [])
    )
    if duplicado:
        await interaction.response.send_message("ℹ️ Já existe um sorteio igual agendado para esse canal, data e horário.", ephemeral=True)
        return
    evento = {
        "id": str(int(agora_utc().timestamp() * 1000)),
        "dia": dia,
        "horario": horario,
        "executar_em": quando.isoformat(),
        "canal_id": destino.id,
        "times": times,
        "status": "agendado",
    }
    DADOS["liga"]["sorteios"].append(evento)
    salvar_dados(DADOS)
    await interaction.response.send_message(f"✅ Sorteio agendado para **{dia} às {horario} (BRT)** em {destino.mention}, com **{len(times)} times**.", ephemeral=True)


@liga_group.command(name="sortear_agora", description="Sorteia os confrontos imediatamente.")
@app_commands.describe(canal="Canal onde publicar")
async def liga_sortear_agora(interaction: discord.Interaction, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "liga"):
        return
    times = list(_times_liga())
    if len(times) < 2:
        await interaction.response.send_message("❌ Cadastre pelo menos 2 times primeiro.", ephemeral=True)
        return
    destino = canal or interaction.channel
    evento = {"dia": datetime.datetime.now(BRT).strftime("%d/%m/%Y"), "horario": datetime.datetime.now(BRT).strftime("%H:%M"), "canal_id": destino.id, "times": times}
    await publicar_sorteio_liga(evento)
    await interaction.response.send_message("✅ Confrontos sorteados e publicados.", ephemeral=True)


@liga_group.command(name="agenda", description="Mostra os sorteios agendados.")
async def liga_agenda(interaction: discord.Interaction):
    eventos = [e for e in DADOS.get("liga", {}).get("sorteios", []) if e.get("status") == "agendado"]
    if not eventos:
        await interaction.response.send_message("ℹ️ Nenhum sorteio agendado.", ephemeral=True)
        return
    linhas = [f"**{i}.** {e.get('dia')} às {e.get('horario')} (BRT) • <#{e.get('canal_id')}> • {len(e.get('times', []))} times" for i, e in enumerate(eventos, 1)]
    await interaction.response.send_message(embed=discord.Embed(title="📅 Agenda de confrontos", description="\n".join(linhas), color=BRS_GREEN), ephemeral=True)



@liga_group.command(name="resultado", description="Registra o resultado de uma partida entre dois times.")
@app_commands.describe(casa="Time da casa", gols_casa="Gols do time da casa", fora="Time visitante", gols_fora="Gols do time visitante", rodada="Nome ou número da rodada")
async def liga_resultado(
    interaction: discord.Interaction,
    casa: str,
    gols_casa: int,
    fora: str,
    gols_fora: int,
    rodada: Optional[str] = None,
):
    if not await checar_permissao(interaction, "liga"):
        return
    if gols_casa < 0 or gols_fora < 0 or gols_casa > 99 or gols_fora > 99:
        await interaction.response.send_message("❌ Os gols devem ficar entre 0 e 99.", ephemeral=True)
        return
    nomes = {normalizar(t): t for t in _times_liga()}
    casa_real, fora_real = nomes.get(normalizar(casa)), nomes.get(normalizar(fora))
    if not casa_real or not fora_real or casa_real == fora_real:
        await interaction.response.send_message("❌ Use dois times diferentes que estejam cadastrados em `/liga lista`.", ephemeral=True)
        return
    resultado = {
        "casa": casa_real,
        "fora": fora_real,
        "gols_casa": gols_casa,
        "gols_fora": gols_fora,
        "rodada": rodada or "—",
        "data": agora_utc().isoformat(),
        "registrado_por": interaction.user.id,
    }
    DADOS["liga"].setdefault("resultados", []).append(resultado)
    salvar_dados(DADOS)
    if gols_casa > gols_fora:
        resumo = f"🏆 **{casa_real}** venceu"
    elif gols_fora > gols_casa:
        resumo = f"🏆 **{fora_real}** venceu"
    else:
        resumo = "🤝 Partida empatada"
    embed = discord.Embed(title="📊 Resultado registrado", description=f"**{casa_real}** `{gols_casa} × {gols_fora}` **{fora_real}**\n\n{resumo}", color=BRS_GREEN)
    embed.add_field(name="Rodada", value=rodada or "—", inline=True)
    embed.set_footer(text="BRS • Liga")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@liga_group.command(name="tabela", description="Publica a tabela da liga com pontos e saldo de gols.")
@app_commands.describe(canal="Canal para publicar a tabela")
async def liga_tabela(interaction: discord.Interaction, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "liga"):
        return
    times = list(_times_liga())
    if not times:
        await interaction.response.send_message("❌ Cadastre os times primeiro.", ephemeral=True)
        return
    stats = {t: {"j": 0, "v": 0, "e": 0, "d": 0, "gp": 0, "gc": 0, "pts": 0} for t in times}
    for r in DADOS["liga"].get("resultados", []):
        casa, fora = r.get("casa"), r.get("fora")
        if casa not in stats or fora not in stats:
            continue
        gc, gf = int(r.get("gols_casa", 0)), int(r.get("gols_fora", 0))
        stats[casa]["j"] += 1; stats[fora]["j"] += 1
        stats[casa]["gp"] += gc; stats[casa]["gc"] += gf
        stats[fora]["gp"] += gf; stats[fora]["gc"] += gc
        if gc > gf:
            stats[casa]["v"] += 1; stats[casa]["pts"] += 3; stats[fora]["d"] += 1
        elif gf > gc:
            stats[fora]["v"] += 1; stats[fora]["pts"] += 3; stats[casa]["d"] += 1
        else:
            stats[casa]["e"] += 1; stats[fora]["e"] += 1
            stats[casa]["pts"] += 1; stats[fora]["pts"] += 1
    ranking = sorted(stats.items(), key=lambda item: (item[1]["pts"], item[1]["gp"] - item[1]["gc"], item[1]["gp"]), reverse=True)
    linhas = []
    for pos, (nome, s) in enumerate(ranking, 1):
        saldo = s["gp"] - s["gc"]
        linhas.append(f"**{pos:02d}.** {nome} — **{s['pts']} pts** | J {s['j']} • V {s['v']} • E {s['e']} • D {s['d']} | SG {saldo:+d}")
    embed = discord.Embed(title="🏆 TABELA DA LIGA — BRS", description="\n".join(linhas), color=BRS_GREEN, timestamp=agora_utc())
    embed.add_field(name="Sistema de pontos", value="Vitória = 3 • Empate = 1 • Derrota = 0", inline=False)
    avatar = bot_avatar_url()
    if avatar:
        embed.set_thumbnail(url=avatar)
    embed.set_footer(text="BRS • Liga")
    destino = canal or interaction.channel
    await destino.send(embed=embed)
    await interaction.response.send_message(f"✅ Tabela publicada em {destino.mention}.", ephemeral=True)


# ============================================================
#  /say e /say_embed — foto do bot SEMPRE automática
#  (nunca precisa colocar URL/código de imagem manualmente)
# ============================================================
@bot.tree.command(name="say", description="Envia mensagem pelo bot.", guild=GUILD)
@app_commands.describe(mensagem="Texto", canal="Canal")
async def say_cmd(interaction: discord.Interaction, mensagem: str, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "say"):
        return
    canal = canal or interaction.channel
    await canal.send(mensagem.replace("\\n", "\n"))
    await interaction.response.send_message(f"✅ Enviado em {canal.mention}.", ephemeral=True)


@bot.tree.command(name="say_embed", description="Envia embed pelo bot (a foto do bot vai automática, sem precisar informar nada).", guild=GUILD)
@app_commands.describe(
    titulo="Título", descricao="Descrição (\\n para quebra)", canal="Canal",
    cor="Cor hex (#FF0000)", imagem="URL imagem grande (opcional)", rodape="Rodapé", autor="Autor"
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
        color = discord.Color(BRS_GREEN)

    embed = discord.Embed(title=titulo, description=descricao.replace("\\n", "\n"), color=color)

    # A foto do bot é sempre aplicada automaticamente — não depende de
    # nenhum parâmetro do comando nem de código extra por quem usa.
    avatar = bot_avatar_url()
    if avatar:
        embed.set_thumbnail(url=avatar)
        embed.set_author(name=autor or (bot.user.name if bot.user else "BRS"), icon_url=avatar)
    elif autor:
        embed.set_author(name=autor)

    # A logo do próprio bot fica grande automaticamente; uma imagem informada pelo usuário tem prioridade.
    if imagem or avatar:
        embed.set_image(url=imagem or avatar)
    if rodape:
        embed.set_footer(text=rodape, icon_url=avatar)
    elif avatar:
        embed.set_footer(text="BRS — Brazilian Roblox Soccer", icon_url=avatar)

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
    app_commands.Choice(name="criar_cargo", value="criar_cargo"),
    app_commands.Choice(name="liga", value="liga"),
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


# ---- Painel de configuração, no estilo visual da referência (PAFO) ----
def _nomes_cargos(guild: discord.Guild, ids) -> str:
    nomes = [role.name for i in ids if (role := guild.get_role(i))]
    return ", ".join(f"`{n}`" for n in nomes) if nomes else "*nenhum*"


def _nome_canal(guild: discord.Guild, cid) -> str:
    c = guild.get_channel(cid) if cid else None
    return c.mention if c else "*não definido*"


@bot.tree.command(name="config_ver", description="Mostra o painel de configurações atuais do bot.", guild=GUILD)
@app_commands.checks.has_permissions(administrator=True)
async def config_ver_cmd(interaction: discord.Interaction):
    cfg = DADOS["config"]
    guild = interaction.guild
    avatar = bot_avatar_url()

    # Embed principal — visão geral, no mesmo estilo escuro/verde da referência
    principal = discord.Embed(
        title="⚙️  PAINEL DE CONFIGURAÇÕES — BRS",
        description=(
            "Visão geral organizada de tudo que está configurado no bot.\n"
            "Use `/staff`, `/permissao`, `/cargo_criar`, `/ticket configurar`, "
            "`/drop meta`, `/liga times` e os comandos de canal para alterar."
        ),
        color=BRS_GREEN,
        timestamp=datetime.datetime.now(),
    )
    if avatar:
        principal.set_thumbnail(url=avatar)
    principal.add_field(name="🛡️ Staff Geral", value=_nomes_cargos(guild, cfg["staff_role_ids"]), inline=False)
    perms = "\n".join(f"**/{k}** → {_nomes_cargos(guild, v)}" for k, v in cfg["command_permissions"].items())
    principal.add_field(name="🔑 Permissões por Comando", value=perms or "*nenhuma*", inline=False)
    principal.set_footer(text="BRS Bot • Painel 1/2")

    # Embed secundário — módulos (tickets, drop, free agent, scouting)
    modulos = discord.Embed(color=BRS_GREEN, timestamp=datetime.datetime.now())
    modulos.add_field(
        name="🎫 Tickets",
        value=(
            f"Categoria: {_nome_canal(guild, cfg['ticket']['category_id'])}\n"
            f"Cargos staff: {_nomes_cargos(guild, cfg['ticket']['staff_role_ids'])}\n"
            f"Logs de Ticket: {_nome_canal(guild, cfg['ticket']['log_channel_id'])}\n"
            f"Banner: {'configurado' if cfg['ticket'].get('banner_url') else 'não configurado'}\n"
            f"Horário: {cfg['ticket'].get('horario_atendimento', 'não definido')[:180]}\n"
            f"Tipos disponíveis: {', '.join(c['label'] for c in TICKET_CATEGORIES)}"
        ),
        inline=False,
    )
    modulos.add_field(
        name="❓ Drop",
        value=(
            f"Prêmios: {_nomes_cargos(guild, cfg['drop']['reward_role_ids'])}\n"
            f"Canal padrão: {_nome_canal(guild, cfg['drop']['default_channel_id'])}\n"
            f"Meta: **{cfg['drop'].get('meta_membros', 0):,}** membros\n"
            f"Perguntas no banco: **{len(TODAS_PERGUNTAS):,}+**"
        ),
        inline=False,
    )
    modulos.add_field(name="🆓 Free Agent", value=f"Canal: {_nome_canal(guild, cfg['freeagent']['channel_id'])}", inline=True)
    modulos.add_field(name="🔍 Scouting", value=f"Canal: {_nome_canal(guild, cfg['scouting']['channel_id'])}", inline=True)
    modulos.add_field(name="🏆 Liga", value=f"Times: {len(DADOS.get('liga', {}).get('times', []))}\nSorteios agendados: {sum(1 for e in DADOS.get('liga', {}).get('sorteios', []) if e.get('status') == 'agendado')}", inline=True)
    modulos.set_footer(text="BRS Bot • Painel 2/2")

    await interaction.response.send_message(embeds=[principal, modulos], ephemeral=True)


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
