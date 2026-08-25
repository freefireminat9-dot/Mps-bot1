"""
Bot Discord completo — BRS (Brazilian Roblox Soccer)
Comandos: somente slash (/), sem prefixo de texto
Slash: /

Recursos:
  - Tickets
  - Drop estilo PAFO (select menu + cargos temporários 5 dias)
  - Meta de membros → Wave Drop
  - Free Agent / Scouting
  - /role (sem ID no código)
  - /say e /say_embed (foto do bot automática)
  - Permissões e config organizada (/config ver e /config drop)
  - Wave com quantidade de Drops configurável
"""

import os
import json
import copy
import datetime
import logging
import unicodedata
import random
import asyncio
import re
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

# Os cargos de recompensa são cadastrados pelo comando /drop premio_adicionar.
# Nenhum ID de cargo fica gravado no código do comando /role.
# ============================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("brs-bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

ACTIVE_DROP: Optional[dict] = None
WAVE_RUNNING = False

# ============================================================
#  BANCO DE PERGUNTAS (diverso e com mais de 1.000 opções)
# ============================================================
def _normalizar_pergunta(texto: str) -> str:
    return " ".join(texto.strip().split())


def gerar_banco_perguntas() -> List[dict]:
    perguntas: list[dict] = []
    usadas: set[str] = set()

    def adicionar(pergunta: str, resposta: object, categoria: str):
        pergunta = _normalizar_pergunta(pergunta)
        if pergunta not in usadas:
            usadas.add(pergunta)
            perguntas.append({"q": pergunta, "a": str(resposta), "categoria": categoria})

    # BRS, futebol e esportes.
    futebol = [
        ("Qual time brasileiro é conhecido como O Mais Querido?", "Flamengo"),
        ("Quem é conhecido como o Rei do Futebol?", "Pelé"),
        ("Quantos jogadores cada time de futebol tem em campo no início de uma partida?", "11"),
        ("Qual é o nome do estádio conhecido como Maracanã?", "Estádio Jornalista Mário Filho"),
        ("Em que país surgiu o futebol moderno?", "Inglaterra"),
        ("Qual seleção tem mais títulos da Copa do Mundo masculina?", "Brasil"),
        ("Quantos minutos tem o tempo regulamentar de uma partida de futebol?", "90"),
        ("Quantos minutos dura cada tempo de uma partida de futebol?", "45"),
        ("O que é um hat-trick no futebol?", "Três gols do mesmo jogador"),
        ("Qual cartão indica expulsão no futebol?", "Vermelho"),
        ("Qual cartão indica advertência no futebol?", "Amarelo"),
        ("Quantos pontos vale uma vitória no futebol em pontos corridos?", "3"),
        ("Qual é a posição do jogador que protege o gol?", "Goleiro"),
        ("Qual é a principal competição de clubes da América do Sul?", "Copa Libertadores"),
        ("Qual é a principal competição de clubes da Europa?", "Liga dos Campeões"),
        ("Qual esporte usa uma cesta e uma bola laranja?", "Basquete"),
        ("Quantos jogadores formam uma equipe de vôlei em quadra?", "6"),
        ("Qual esporte é disputado em uma piscina e usa raias?", "Natação"),
        ("Em qual esporte se usa uma raquete e uma peteca?", "Badminton"),
        ("Qual esporte é associado ao torneio de Wimbledon?", "Tênis"),
        ("Quantos anéis há no símbolo olímpico?", "5"),
        ("Qual país sediou os Jogos Olímpicos de 2016?", "Brasil"),
        ("Qual é a pontuação máxima de uma cesta comum no basquete?", "3"),
        ("Qual peça do xadrez se move em formato de L?", "Cavalo"),
        ("Qual peça do xadrez vale mais, sem contar o rei?", "Dama"),
        ("Como se chama a jogada que derruba o rei no xadrez?", "Xeque-mate"),
        ("Qual esporte usa tacos e buracos em um campo?", "Golfe"),
        ("Qual esporte tem o cinturão como símbolo de campeão?", "Boxe"),
        ("Qual esporte é conhecido como esporte da bola oval?", "Rugby"),
        ("Qual é a distância oficial de uma maratona em quilômetros?", "42,195"),
    ]
    for pergunta, resposta in futebol:
        adicionar(pergunta, resposta, "Esportes")

    # Matemática: centenas de perguntas geradas, sem depender de perguntas de bandeiras.
    for a in range(2, 21):
        for b in range(2, 21):
            adicionar(f"Quanto é {a} × {b}?", a * b, "Matemática")
    for a in range(1, 51):
        for b in range(1, 6):
            adicionar(f"Quanto é {a} + {b}?", a + b, "Matemática")
    for a in range(10, 51):
        for b in range(1, 6):
            adicionar(f"Quanto é {a} − {b}?", a - b, "Matemática")
    for n in range(1, 31):
        adicionar(f"Qual é o quadrado de {n}?", n * n, "Matemática")
    for n in range(1, 16):
        adicionar(f"Qual é o cubo de {n}?", n ** 3, "Matemática")
    for n in range(1, 21):
        adicionar(f"Qual é a metade de {n * 2}?", n, "Matemática")
    for n in range(1, 21):
        adicionar(f"Qual é o dobro de {n}?", n * 2, "Matemática")

    # Geografia: capital e continente de países variados.
    paises = [
        ("Brasil", "Brasília", "América do Sul"), ("Argentina", "Buenos Aires", "América do Sul"),
        ("Chile", "Santiago", "América do Sul"), ("Uruguai", "Montevidéu", "América do Sul"),
        ("Paraguai", "Assunção", "América do Sul"), ("Bolívia", "Sucre", "América do Sul"),
        ("Peru", "Lima", "América do Sul"), ("Equador", "Quito", "América do Sul"),
        ("Colômbia", "Bogotá", "América do Sul"), ("Venezuela", "Caracas", "América do Sul"),
        ("Guiana", "Georgetown", "América do Sul"), ("Suriname", "Paramaribo", "América do Sul"),
        ("México", "Cidade do México", "América do Norte"), ("Canadá", "Ottawa", "América do Norte"),
        ("Estados Unidos", "Washington DC", "América do Norte"), ("Cuba", "Havana", "América do Norte"),
        ("Costa Rica", "San José", "América Central"), ("Panamá", "Cidade do Panamá", "América Central"),
        ("Guatemala", "Cidade da Guatemala", "América Central"), ("Jamaica", "Kingston", "América do Norte"),
        ("Reino Unido", "Londres", "Europa"), ("França", "Paris", "Europa"),
        ("Espanha", "Madri", "Europa"), ("Portugal", "Lisboa", "Europa"),
        ("Itália", "Roma", "Europa"), ("Alemanha", "Berlim", "Europa"),
        ("Países Baixos", "Amsterdã", "Europa"), ("Bélgica", "Bruxelas", "Europa"),
        ("Suíça", "Berna", "Europa"), ("Áustria", "Viena", "Europa"),
        ("Polônia", "Varsóvia", "Europa"), ("Grécia", "Atenas", "Europa"),
        ("Noruega", "Oslo", "Europa"), ("Suécia", "Estocolmo", "Europa"),
        ("Finlândia", "Helsinque", "Europa"), ("Dinamarca", "Copenhague", "Europa"),
        ("Islândia", "Reykjavik", "Europa"), ("Irlanda", "Dublin", "Europa"),
        ("Rússia", "Moscou", "Europa e Ásia"), ("Ucrânia", "Kiev", "Europa"),
        ("Turquia", "Ancara", "Ásia e Europa"), ("Romênia", "Bucareste", "Europa"),
        ("Bulgária", "Sófia", "Europa"), ("Croácia", "Zagreb", "Europa"),
        ("Sérvia", "Belgrado", "Europa"), ("Tchéquia", "Praga", "Europa"),
        ("Hungria", "Budapeste", "Europa"), ("Marrocos", "Rabat", "África"),
        ("Argélia", "Argel", "África"), ("Tunísia", "Túnis", "África"),
        ("Egito", "Cairo", "África"), ("Líbia", "Trípoli", "África"),
        ("Nigéria", "Abuja", "África"), ("Gana", "Acra", "África"),
        ("Senegal", "Dacar", "África"), ("Quênia", "Nairóbi", "África"),
        ("Etiópia", "Adis Abeba", "África"), ("Tanzânia", "Dodoma", "África"),
        ("África do Sul", "Pretória", "África"), ("Angola", "Luanda", "África"),
        ("Moçambique", "Maputo", "África"), ("Madagascar", "Antananarivo", "África"),
        ("Austrália", "Camberra", "Oceania"), ("Nova Zelândia", "Wellington", "Oceania"),
        ("Fiji", "Suva", "Oceania"), ("China", "Pequim", "Ásia"),
        ("Japão", "Tóquio", "Ásia"), ("Coreia do Sul", "Seul", "Ásia"),
        ("Mongólia", "Ulan Bator", "Ásia"), ("Índia", "Nova Délhi", "Ásia"),
        ("Paquistão", "Islamabad", "Ásia"), ("Nepal", "Catmandu", "Ásia"),
        ("Bangladesh", "Daca", "Ásia"), ("Sri Lanka", "Sri Jayawardenepura Kotte", "Ásia"),
        ("Tailândia", "Bangcoc", "Ásia"), ("Vietnã", "Hanói", "Ásia"),
        ("Filipinas", "Manila", "Ásia"), ("Indonésia", "Jacarta", "Ásia"),
        ("Malásia", "Kuala Lumpur", "Ásia"), ("Singapura", "Singapura", "Ásia"),
        ("Mianmar", "Naypyidaw", "Ásia"), ("Irã", "Teerã", "Ásia"),
        ("Iraque", "Bagdá", "Ásia"), ("Israel", "Jerusalém", "Ásia"),
        ("Jordânia", "Amã", "Ásia"), ("Arábia Saudita", "Riade", "Ásia"),
        ("Emirados Árabes Unidos", "Abu Dhabi", "Ásia"), ("Catar", "Doha", "Ásia"),
        ("Afeganistão", "Cabul", "Ásia"), ("Cazaquistão", "Astana", "Ásia"),
    ]
    for pais, capital, continente in paises:
        adicionar(f"Qual é a capital de {pais}?", capital, "Geografia")
        adicionar(f"Em qual continente fica {pais}?", continente, "Geografia")

    moedas = [
        ("Brasil", "real"), ("Estados Unidos", "dólar"), ("Reino Unido", "libra esterlina"),
        ("Japão", "iene"), ("China", "yuan"), ("Índia", "rúpia"), ("Rússia", "rublo"),
        ("México", "peso mexicano"), ("Argentina", "peso argentino"), ("Chile", "peso chileno"),
        ("Colômbia", "peso colombiano"), ("Peru", "sol"), ("Uruguai", "peso uruguaio"),
        ("Paraguai", "guarani"), ("Suíça", "franco suíço"), ("Austrália", "dólar australiano"),
        ("Canadá", "dólar canadense"), ("Coreia do Sul", "won"), ("Turquia", "lira turca"),
        ("África do Sul", "rand"),
    ]
    for pais, moeda in moedas:
        adicionar(f"Qual é a moeda oficial de {pais}?", moeda, "Geografia")

    # Ciências naturais e corpo humano.
    elementos = [
        ("Hidrogênio", "H", 1), ("Hélio", "He", 2), ("Lítio", "Li", 3), ("Berílio", "Be", 4),
        ("Boro", "B", 5), ("Carbono", "C", 6), ("Nitrogênio", "N", 7), ("Oxigênio", "O", 8),
        ("Flúor", "F", 9), ("Neônio", "Ne", 10), ("Sódio", "Na", 11), ("Magnésio", "Mg", 12),
        ("Alumínio", "Al", 13), ("Silício", "Si", 14), ("Fósforo", "P", 15), ("Enxofre", "S", 16),
        ("Cloro", "Cl", 17), ("Argônio", "Ar", 18), ("Potássio", "K", 19), ("Cálcio", "Ca", 20),
        ("Ferro", "Fe", 26), ("Cobre", "Cu", 29), ("Zinco", "Zn", 30), ("Prata", "Ag", 47),
        ("Ouro", "Au", 79), ("Mercúrio", "Hg", 80), ("Chumbo", "Pb", 82), ("Urânio", "U", 92),
    ]
    for nome, simbolo, numero in elementos:
        adicionar(f"Qual é o símbolo químico do elemento {nome}?", simbolo, "Ciências")
        adicionar(f"Qual é o número atômico do elemento {nome}?", numero, "Ciências")

    planetas = [
        ("Mercúrio", "mais próximo do Sol"), ("Vênus", "mais quente do Sistema Solar"),
        ("Terra", "onde vivemos"), ("Marte", "conhecido como planeta vermelho"),
        ("Júpiter", "maior planeta do Sistema Solar"), ("Saturno", "famoso por seus anéis"),
        ("Urano", "tem rotação bastante inclinada"), ("Netuno", "mais distante do Sol entre os oito planetas"),
    ]
    for planeta, descricao in planetas:
        adicionar(f"Qual planeta é {descricao}?", planeta, "Ciências")
    adicionar("Quantos planetas há no Sistema Solar?", 8, "Ciências")
    adicionar("Qual é a estrela do Sistema Solar?", "Sol", "Ciências")
    adicionar("Qual é o satélite natural da Terra?", "Lua", "Ciências")
    adicionar("Qual gás os seres humanos precisam respirar para viver?", "Oxigênio", "Ciências")
    adicionar("Qual gás as plantas absorvem na fotossíntese?", "Gás carbônico", "Ciências")
    adicionar("Como se chama a passagem da água líquida para vapor?", "Evaporação", "Ciências")
    adicionar("Como se chama a passagem do vapor para o estado líquido?", "Condensação", "Ciências")
    adicionar("Qual é a unidade básica da vida?", "Célula", "Ciências")
    adicionar("Qual órgão bombeia o sangue pelo corpo?", "Coração", "Ciências")
    adicionar("Qual órgão é responsável principalmente pelas trocas gasosas?", "Pulmão", "Ciências")
    adicionar("Qual é o maior órgão do corpo humano?", "Pele", "Ciências")
    adicionar("Qual substância dá cor verde às plantas?", "Clorofila", "Ciências")
    adicionar("Qual força nos mantém atraídos à Terra?", "Gravidade", "Ciências")
    adicionar("A que temperatura a água congela em Celsius ao nível do mar?", "0", "Ciências")
    adicionar("A que temperatura a água ferve em Celsius ao nível do mar?", "100", "Ciências")
    adicionar("Qual é o animal terrestre mais veloz?", "Guepardo", "Ciências")
    adicionar("Qual é o maior mamífero do mundo?", "Baleia azul", "Ciências")
    adicionar("Qual é o maior animal terrestre?", "Elefante africano", "Ciências")
    adicionar("Como se chama o estudo dos seres vivos?", "Biologia", "Ciências")
    adicionar("Como se chama o estudo dos astros?", "Astronomia", "Ciências")

    # História, sociedade, cultura e língua portuguesa.
    historia = [
        ("Em que ano o ser humano pisou na Lua pela primeira vez?", "1969"),
        ("Quem foi o primeiro ser humano a pisar na Lua?", "Neil Armstrong"),
        ("Em que ano o Brasil declarou sua independência?", "1822"),
        ("Quem proclamou a independência do Brasil?", "Dom Pedro I"),
        ("Em que ano foi proclamada a República no Brasil?", "1889"),
        ("Qual cidade foi a primeira capital do Brasil?", "Salvador"),
        ("Qual é a atual capital do Brasil?", "Brasília"),
        ("Quem foi conhecido como Tiradentes?", "Joaquim José da Silva Xavier"),
        ("Qual civilização construiu Machu Picchu?", "Inca"),
        ("Qual povo construiu as pirâmides de Gizé?", "Egípcios"),
        ("Qual era o idioma principal do Império Romano?", "Latim"),
        ("Quem escreveu a Ilíada e a Odisseia?", "Homero"),
        ("Em que país começou a Revolução Industrial?", "Inglaterra"),
        ("Qual muro caiu em 1989 e simbolizava a divisão de Berlim?", "Muro de Berlim"),
        ("Qual foi o conflito mundial encerrado em 1945?", "Segunda Guerra Mundial"),
        ("Qual organização internacional foi criada em 1945 para promover a cooperação entre países?", "ONU"),
        ("Qual documento inglês de 1215 limitou o poder do rei?", "Magna Carta"),
        ("Quem pintou a Mona Lisa?", "Leonardo da Vinci"),
        ("Quem pintou o teto da Capela Sistina?", "Michelangelo"),
        ("Quem escreveu Dom Quixote?", "Miguel de Cervantes"),
        ("Quem escreveu Os Lusíadas?", "Luís de Camões"),
        ("Quem escreveu Dom Casmurro?", "Machado de Assis"),
        ("Quem escreveu O Auto da Compadecida?", "Ariano Suassuna"),
        ("Qual é o idioma oficial do Brasil?", "Português"),
        ("Qual é o plural de cidadão?", "Cidadãos"),
        ("Qual é o antônimo de claro?", "Escuro"),
        ("Qual é o sinônimo de feliz?", "Alegre"),
        ("Quantas letras tem o alfabeto português brasileiro?", "26"),
        ("Como se chama a palavra que indica uma ação?", "Verbo"),
        ("Como se chama a palavra que caracteriza um substantivo?", "Adjetivo"),
        ("Qual sinal encerra normalmente uma pergunta?", "Ponto de interrogação"),
        ("Qual sinal indica uma pausa breve?", "Vírgula"),
    ]
    for pergunta, resposta in historia:
        adicionar(pergunta, resposta, "História e Cultura")

    # Tecnologia, internet, Roblox e jogos.
    tecnologia = [
        ("Qual empresa desenvolve o sistema operacional Windows?", "Microsoft"),
        ("Qual empresa criou o iPhone?", "Apple"),
        ("Qual empresa mantém o Android?", "Google"),
        ("O que significa a sigla CPU?", "Unidade central de processamento"),
        ("O que significa a sigla GPU?", "Unidade de processamento gráfico"),
        ("Qual linguagem é usada para estruturar páginas web?", "HTML"),
        ("Qual linguagem é usada para estilizar páginas web?", "CSS"),
        ("Qual linguagem é muito usada para interatividade em páginas web?", "JavaScript"),
        ("O que significa a sigla URL?", "Localizador uniforme de recursos"),
        ("O que significa a sigla HTTP?", "Protocolo de transferência de hipertexto"),
        ("Qual dispositivo distribui uma conexão de internet em uma rede local?", "Roteador"),
        ("Como se chama o armazenamento temporário usado para acelerar acessos?", "Cache"),
        ("Qual unidade costuma medir a capacidade de armazenamento digital?", "Byte"),
        ("Qual é a base numérica usada pelos computadores?", "Binária"),
        ("O que é um programa malicioso?", "Malware"),
        ("O que significa fazer uma cópia de segurança?", "Backup"),
        ("Qual empresa é responsável pelo Roblox?", "Roblox Corporation"),
        ("Em qual plataforma é possível jogar Roblox?", "Roblox"),
        ("Qual jogo popular tem blocos e mineração?", "Minecraft"),
        ("Qual jogo tem personagens chamados tripulantes e impostores?", "Among Us"),
        ("Qual empresa criou o jogo Minecraft?", "Mojang"),
        ("Qual é o nome do encanador famoso dos jogos da Nintendo?", "Mario"),
        ("Qual personagem da Nintendo é um ouriço azul?", "Sonic"),
        ("Qual empresa criou o PlayStation?", "Sony"),
        ("Qual empresa criou o Xbox?", "Microsoft"),
        ("Qual empresa criou o Nintendo Switch?", "Nintendo"),
        ("Qual formato de imagem suporta transparência e é muito usado na web?", "PNG"),
        ("Qual formato costuma ser usado para documentos portáteis?", "PDF"),
        ("O que significa a sigla Wi-Fi?", "Wireless Fidelity"),
        ("Qual tecnologia permite comunicação sem fio de curto alcance entre dispositivos?", "Bluetooth"),
    ]
    for pergunta, resposta in tecnologia:
        adicionar(pergunta, resposta, "Tecnologia e Jogos")

    # Conhecimentos gerais, cotidiano e natureza.
    gerais = [
        ("Qual é a capital da França?", "Paris"), ("Qual é a capital da Itália?", "Roma"),
        ("Qual é a capital do Japão?", "Tóquio"), ("Qual é a capital de Portugal?", "Lisboa"),
        ("Qual é o maior país da América do Sul?", "Brasil"),
        ("Qual é o maior oceano do planeta?", "Pacífico"),
        ("Qual é o menor oceano do planeta?", "Ártico"),
        ("Qual é o rio mais extenso frequentemente citado em livros didáticos?", "Nilo"),
        ("Qual é a montanha mais alta do mundo?", "Everest"),
        ("Qual é o deserto quente mais extenso do mundo?", "Saara"),
        ("Quantos dias tem um ano comum?", "365"),
        ("Quantos dias tem um ano bissexto?", "366"),
        ("Quantos meses tem um ano?", "12"),
        ("Quantas horas tem um dia?", "24"),
        ("Quantos minutos tem uma hora?", "60"),
        ("Quantos segundos tem um minuto?", "60"),
        ("Qual é o primeiro mês do ano?", "Janeiro"),
        ("Qual é o último mês do ano?", "Dezembro"),
        ("Qual estação vem depois do inverno no Brasil?", "Primavera"),
        ("Qual é a cor formada pela mistura de azul e amarelo?", "Verde"),
        ("Qual é a cor formada pela mistura de vermelho e branco?", "Rosa"),
        ("Qual é o ingrediente principal da feijoada?", "Feijão preto"),
        ("Qual alimento é usado para fazer pão?", "Farinha de trigo"),
        ("Qual bebida é feita tradicionalmente com grãos torrados?", "Café"),
        ("Qual animal é conhecido por produzir mel?", "Abelha"),
        ("Qual animal é conhecido por mudar de cor e mover os olhos de forma independente?", "Camaleão"),
        ("Qual mamífero é famoso por dormir de cabeça para baixo?", "Morcego"),
        ("Qual ave não voa e vive naturalmente na Antártida?", "Pinguim"),
        ("Qual instrumento tem teclas brancas e pretas?", "Piano"),
        ("Qual instrumento de cordas é muito usado no samba?", "Cavaquinho"),
        ("Qual gênero musical brasileiro nasceu no Rio de Janeiro e tem forte presença de percussão?", "Samba"),
        ("Qual dança brasileira é associada a Pernambuco e a pequenos guarda-chuvas?", "Frevo"),
        ("Qual feriado brasileiro é celebrado em 7 de setembro?", "Independência do Brasil"),
        ("Qual feriado é celebrado em 25 de dezembro?", "Natal"),
        ("Qual é o símbolo químico da água?", "H2O"),
        ("Qual é o formato geométrico com três lados?", "Triângulo"),
        ("Quantos lados tem um hexágono?", "6"),
        ("Quantos graus tem um ângulo reto?", "90"),
        ("Qual é o número que vem depois de 99?", "100"),
        ("Qual é o dobro de 50?", "100"),
    ]
    for pergunta, resposta in gerais:
        adicionar(pergunta, resposta, "Conhecimentos Gerais")

    # Pequeno conjunto de bandeiras, mantendo o banco claramente diversificado.
    bandeiras = [
        ("Qual país tem uma folha de bordo em sua bandeira?", "Canadá"),
        ("Qual país tem um círculo vermelho no centro de sua bandeira?", "Japão"),
        ("Qual país tem uma cruz branca sobre fundo vermelho em sua bandeira?", "Suíça"),
        ("Qual país tem uma folha de bordo como símbolo nacional?", "Canadá"),
        ("Qual país tem uma bandeira verde, amarela e azul com uma esfera ao centro?", "Brasil"),
        ("Qual país tem uma cruz nórdica azul em fundo branco e vermelho?", "Islândia"),
        ("Qual país tem uma estrela de Davi em sua bandeira?", "Israel"),
        ("Qual país tem uma bandeira com um cedro no centro?", "Líbano"),
        ("Qual país tem uma bandeira com um dragão?", "Butão"),
        ("Qual país tem uma bandeira com uma águia dourada?", "Cazaquistão"),
        ("Qual país é representado por uma bandeira tricolor vertical verde, branca e vermelha?", "Itália"),
        ("Qual país é representado por uma bandeira azul, branca e vermelha em faixas horizontais?", "Rússia"),
    ]
    for pergunta, resposta in bandeiras:
        adicionar(pergunta, resposta, "Bandeiras")

    random.shuffle(perguntas)
    if len(perguntas) < 1000:
        raise RuntimeError(f"Banco de perguntas insuficiente: {len(perguntas)}")
    return perguntas


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
        "reward_role_ids": [],
        "default_channel_id": None,
        "quantidade_drops": 7,
        "intervalo_drops_segundos": 8,
        "tempo_resposta_segundos": 180,
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
    dados["config"]["drop"].setdefault("reward_role_ids", [])
    dados["config"]["drop"].setdefault("quantidade_drops", 7)
    dados["config"]["drop"].setdefault("intervalo_drops_segundos", 8)
    dados["config"]["drop"].setdefault("tempo_resposta_segundos", 180)
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
    texto = re.sub(r"[^a-zA-Z0-9\s]", "", texto).lower()
    return " ".join(texto.split())


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
            command_prefix=commands.when_mentioned,
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
        self.tree.add_command(config_group, guild=GUILD)
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

            role_ids = DADOS["config"]["drop"].get("reward_role_ids", [])
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
#  DROP — estilo PAFO
# ============================================================
class DropRewardSelect(discord.ui.Select):
    def __init__(self, user_id: int, roles: list[discord.Role]):
        options = []
        for role in roles[:3]:
            info = {"nome": f"{role.name} (5 Dias)", "emoji": "🏅"}
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


@drop_group.command(name="configurar", description="Configura quantidade e tempo dos Drops.")
@app_commands.describe(
    quantidade="Quantidade padrão de Drops seguidos (1 a 25)",
    tempo_resposta="Tempo para responder cada pergunta, em segundos (30 a 600)",
    intervalo="Intervalo entre Drops, em segundos (0 a 120)",
    canal="Canal padrão dos Drops",
)
async def drop_configurar(
    interaction: discord.Interaction,
    quantidade: Optional[int] = None,
    tempo_resposta: Optional[int] = None,
    intervalo: Optional[int] = None,
    canal: Optional[discord.TextChannel] = None,
):
    if not await checar_permissao(interaction, "drop"):
        return

    cfg = DADOS["config"]["drop"]
    alteracoes = []
    if quantidade is not None:
        if not 1 <= quantidade <= 25:
            await interaction.response.send_message("❌ A quantidade deve ficar entre 1 e 25 Drops.", ephemeral=True)
            return
        cfg["quantidade_drops"] = quantidade
        alteracoes.append(f"Drops seguidos: **{quantidade}**")
    if tempo_resposta is not None:
        if not 30 <= tempo_resposta <= 600:
            await interaction.response.send_message("❌ O tempo de resposta deve ficar entre 30 e 600 segundos.", ephemeral=True)
            return
        cfg["tempo_resposta_segundos"] = tempo_resposta
        alteracoes.append(f"Tempo por pergunta: **{tempo_resposta}s**")
    if intervalo is not None:
        if not 0 <= intervalo <= 120:
            await interaction.response.send_message("❌ O intervalo deve ficar entre 0 e 120 segundos.", ephemeral=True)
            return
        cfg["intervalo_drops_segundos"] = intervalo
        alteracoes.append(f"Intervalo: **{intervalo}s**")
    if canal is not None:
        cfg["default_channel_id"] = canal.id
        alteracoes.append(f"Canal: {canal.mention}")

    if not alteracoes:
        await interaction.response.send_message(
            "ℹ️ Configuração atual:\n"
            f"Drops seguidos: **{cfg.get('quantidade_drops', 7)}**\n"
            f"Tempo por pergunta: **{cfg.get('tempo_resposta_segundos', 180)}s**\n"
            f"Intervalo: **{cfg.get('intervalo_drops_segundos', 8)}s**",
            ephemeral=True,
        )
        return

    salvar_dados(DADOS)
    await interaction.response.send_message("✅ Configuração dos Drops atualizada:\n" + "\n".join(alteracoes), ephemeral=True)


@drop_group.command(name="wave", description="Inicia vários Drops seguidos.")
@app_commands.describe(quantidade="Quantidade de Drops; vazio usa a configuração salva", canal="Canal")
async def drop_wave(interaction: discord.Interaction, quantidade: Optional[int] = None, canal: Optional[discord.TextChannel] = None):
    if not await checar_permissao(interaction, "drop"):
        return

    global ACTIVE_DROP, WAVE_RUNNING
    if WAVE_RUNNING:
        await interaction.response.send_message("❌ Já existe uma Wave em andamento.", ephemeral=True)
        return
    if ACTIVE_DROP and not ACTIVE_DROP.get("finalizado"):
        await interaction.response.send_message("❌ Já existe um Drop em andamento. Cancele-o antes de iniciar a Wave.", ephemeral=True)
        return

    cfg = DADOS["config"]["drop"]
    if quantidade is None:
        quantidade = int(cfg.get("quantidade_drops", 7))
    if not 1 <= quantidade <= 25:
        await interaction.response.send_message("❌ A quantidade deve ficar entre 1 e 25 Drops.", ephemeral=True)
        return

    canal_destino = canal
    if canal_destino is None:
        canal_id = cfg.get("default_channel_id")
        canal_destino = interaction.guild.get_channel(canal_id) if canal_id else None
    canal_destino = canal_destino or interaction.channel
    tempo_resposta = max(30, min(int(cfg.get("tempo_resposta_segundos", 180)), 600))
    intervalo = max(0, min(int(cfg.get("intervalo_drops_segundos", 8)), 120))

    await interaction.response.send_message(
        f"🌊 Wave iniciada com **{quantidade} Drops** em {canal_destino.mention}.",
        ephemeral=True,
    )
    WAVE_RUNNING = True
    try:
        for indice in range(quantidade):
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
                description=(
                    f"# 🌊 WAVE DROP {indice + 1}/{quantidade}\n\n"
                    f"### {escolha['q']}\n\nResponda no chat!"
                ),
                color=0x00FF7F,
            )
            if bot.user:
                embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(text=f"Categoria: {escolha.get('categoria', 'Geral')} • BRS Drops")
            await canal_destino.send(embed=embed)

            limite = max(1, (tempo_resposta + 4) // 5)
            for _ in range(limite):
                await asyncio.sleep(5)
                if ACTIVE_DROP is None or ACTIVE_DROP.get("finalizado"):
                    break

            ACTIVE_DROP = None
            if indice < quantidade - 1 and intervalo:
                await asyncio.sleep(intervalo)

        await canal_destino.send(
            embed=discord.Embed(
                title="🌊 Wave Drop finalizada!",
                description=f"Foram executados **{quantidade} Drops**.",
                color=discord.Color.gold(),
            )
        )
    finally:
        ACTIVE_DROP = None
        WAVE_RUNNING = False


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
    avatar_url = bot.user.display_avatar.url if bot.user else None
    if bot.user:
        # Identidade visual automática: não é necessário colar URL ou código da foto.
        embed.set_author(name=autor or bot.user.name, icon_url=avatar_url)
        embed.set_thumbnail(url=avatar_url)
    elif autor:
        embed.set_author(name=autor)
    if imagem:
        embed.set_image(url=imagem)
    embed.set_footer(text=rodape or "BRS • Mensagem oficial", icon_url=avatar_url)

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


async def enviar_configuracao(interaction: discord.Interaction):
    cfg = DADOS["config"]
    guild = interaction.guild

    def nomes_cargos(ids):
        nomes = [guild.get_role(i).name for i in ids if guild.get_role(i)]
        texto = ", ".join(f"`{n}`" for n in nomes) if nomes else "*nenhum*"
        return texto[:1024]

    def nome_canal(cid):
        c = guild.get_channel(cid) if cid else None
        if not c:
            return "*não definido*"
        return getattr(c, "mention", f"`{c.name}`")

    embed = discord.Embed(
        title="⚙️ Configurações — BRS",
        description="Painel geral de configuração do servidor. Use `/config drop` para ajustar a Wave e `/permissao` para acessos.",
        color=EMBED_COLOR,
        timestamp=datetime.datetime.now(),
    )
    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(
        name="🔐 Acessos",
        value=(
            f"**Staff geral:** {nomes_cargos(cfg['staff_role_ids'])}\n"
            f"**Permissões específicas:** {len(cfg['command_permissions'])} comandos configuráveis"
        ),
        inline=False,
    )
    embed.add_field(
        name="🎫 Tickets",
        value=(
            f"**Categoria:** {nome_canal(cfg['ticket']['category_id'])}\n"
            f"**Cargos staff:** {nomes_cargos(cfg['ticket']['staff_role_ids'])}\n"
            f"**Logs:** {nome_canal(cfg['ticket']['log_channel_id'])}"
        ),
        inline=False,
    )
    embed.add_field(
        name="🌊 Drops",
        value=(
            f"**Canal padrão:** {nome_canal(cfg['drop']['default_channel_id'])}\n"
            f"**Drops seguidos:** `{cfg['drop'].get('quantidade_drops', 7)}`\n"
            f"**Tempo de resposta:** `{cfg['drop'].get('tempo_resposta_segundos', 180)}s`\n"
            f"**Intervalo:** `{cfg['drop'].get('intervalo_drops_segundos', 8)}s`\n"
            f"**Prêmios cadastrados:** `{len(cfg['drop'].get('reward_role_ids', []))}`\n"
            f"**Banco:** `{len(TODAS_PERGUNTAS)}` perguntas em várias categorias"
        ),
        inline=False,
    )
    embed.add_field(
        name="📈 Meta de membros",
        value=(
            f"**Meta:** `{cfg['drop'].get('meta_membros', 0):,}` membros\n"
            f"**Canal:** {nome_canal(cfg['drop'].get('meta_canal_id'))}\n"
            f"**Wave liberada:** `{('sim' if cfg['drop'].get('wave_ativo') else 'não')}`"
        ),
        inline=True,
    )
    embed.add_field(
        name="📣 Publicações",
        value=(
            f"**Free Agent:** {nome_canal(cfg['freeagent']['channel_id'])}\n"
            f"**Scouting:** {nome_canal(cfg['scouting']['channel_id'])}"
        ),
        inline=True,
    )
    embed.set_footer(text="BRS Bot • Configuração em português do Brasil")
    await interaction.response.send_message(embed=embed, ephemeral=True)


config_group = app_commands.Group(name="config", description="Configurações organizadas do bot BRS")


@config_group.command(name="ver", description="Mostra o painel completo de configurações.")
@app_commands.checks.has_permissions(administrator=True)
async def config_ver_subcmd(interaction: discord.Interaction):
    await enviar_configuracao(interaction)


@config_group.command(name="drop", description="Mostra como estão configurados os Drops.")
async def config_drop_subcmd(interaction: discord.Interaction):
    if not await checar_permissao(interaction, "drop"):
        return
    cfg = DADOS["config"]["drop"]
    embed = discord.Embed(title="🌊 Configuração dos Drops — BRS", color=0x00FF7F)
    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(name="Drops seguidos", value=f"`{cfg.get('quantidade_drops', 7)}`", inline=True)
    embed.add_field(name="Tempo por pergunta", value=f"`{cfg.get('tempo_resposta_segundos', 180)}s`", inline=True)
    embed.add_field(name="Intervalo", value=f"`{cfg.get('intervalo_drops_segundos', 8)}s`", inline=True)
    embed.add_field(name="Banco de perguntas", value=f"`{len(TODAS_PERGUNTAS)}` perguntas", inline=False)
    embed.set_footer(text="Para alterar: /drop configurar")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="config_ver", description="Mostra configurações atuais.", guild=GUILD)
@app_commands.checks.has_permissions(administrator=True)
async def config_ver_cmd(interaction: discord.Interaction):
    await enviar_configuracao(interaction)


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
