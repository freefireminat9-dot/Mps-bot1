"""
Bot Discord para liga de MPS (Modified Professional Soccer / Ro-Soccer)

Comandos:
  /say            - envia uma mensagem de texto pelo bot
  /say_embed      - envia uma mensagem em embed pelo bot
  /freeagent      - anuncia um jogador como free agent
  /scouting       - anuncia que um time está procurando jogadores
  /contract       - anuncia a assinatura de contrato de um jogador
  /release        - anuncia a liberação/dispensa de um jogador
  /elenco         - mostra o elenco de um time (baseado em cargo)
  /friendly       - anuncia/agenda um amistoso entre dois times
  /setup          - cria o painel de abertura de tickets
  /add            - adiciona membro/cargo a um ticket
  /remove         - remove membro/cargo de um ticket

Todas as respostas de interação são ephemeral (visíveis apenas para quem usou o
comando). Comandos de anúncio (freeagent, scouting, contract, release, friendly,
say, say_embed) publicam o conteúdo no canal normalmente (para a liga ver), mas
a confirmação do comando em si só aparece para quem executou.
"""

import os
import datetime
import logging
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

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

SCRIM_HOSTER_ROLE_ID: Optional[int] = 1541065148590989332
PIC_PERM_ROLE_ID: Optional[int] = 1541600905298714664
SCOUTING_ROLE_ID: Optional[int] = 1541600835472072724

# Cor padrão usada nos embeds quando nenhuma cor é especificada.
EMBED_COLOR = 0x2B2D31
# ============================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mps-bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class MPSBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Views persistentes (os botões continuam funcionando mesmo depois
        # de reiniciar o bot).
        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())

        # Sincroniza os slash commands apenas na guild da liga (fica
        # disponível instantaneamente, sem esperar a propagação global).
        synced = await self.tree.sync(guild=GUILD)
        log.info("Sincronizados %s comandos na guild %s", len(synced), GUILD_ID)


bot = MPSBot()


@bot.event
async def on_ready():
    log.info("Bot conectado como %s (ID: %s)", bot.user, bot.user.id)


# ============================================================
#  FUNÇÃO AUXILIAR DE PERMISSÃO POR CARGO
# ============================================================
def tem_cargo(*role_ids: Optional[int]):
    """Verifica se o usuário possui pelo menos um dos cargos especificados ou é Administrador."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        user_roles = [role.id for role in interaction.user.roles]
        if any(rid in user_roles for rid in role_ids if rid is not None):
            return True
        raise app_commands.MissingPermissions([])
    return app_commands.check(predicate)


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
    overall="Overall/nível do jogador (opcional)",
    plataforma="Plataforma (PC, Console, Mobile) (opcional)",
    observacoes="Observações adicionais (opcional)",
)
async def freeagent_cmd(
    interaction: discord.Interaction,
    jogador: discord.Member,
    posicao: str,
    overall: Optional[str] = None,
    plataforma: Optional[str] = None,
    observacoes: Optional[str] = None,
):
    embed = discord.Embed(
        title="🆓 FREE AGENT",
        description=f"{jogador.mention} está disponível no mercado!",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(),
    )
    embed.add_field(name="Posição", value=posicao, inline=True)
    if overall:
        embed.add_field(name="Overall", value=overall, inline=True)
    if plataforma:
        embed.add_field(name="Plataforma", value=plataforma, inline=True)
    if observacoes:
        embed.add_field(name="Observações", value=observacoes, inline=False)
    embed.set_thumbnail(url=jogador.display_avatar.url)
    embed.set_footer(text="Interessados, entrem em contato!")

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Anúncio de free agent enviado.", ephemeral=True)


@bot.tree.command(name="scouting", description="Anuncia que um time está procurando jogadores.", guild=GUILD)
@tem_cargo(SCOUTING_ROLE_ID)
@app_commands.describe(
    time="Nome do time que está scoutando",
    posicao="Posição desejada",
    requisitos="Requisitos para o jogador (overall mínimo, disponibilidade, etc.)",
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
        title="🔍 SCOUTING",
        description=f"O time **{time}** está em busca de novos talentos!",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(),
    )
    embed.add_field(name="Posição desejada", value=posicao, inline=True)
    if requisitos:
        embed.add_field(name="Requisitos", value=requisitos, inline=False)
    if contato:
        embed.add_field(name="Contato", value=contato.mention, inline=True)
    embed.set_footer(text="Fique de olho, sua chance pode estar aqui!")

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Anúncio de scouting enviado.", ephemeral=True)


@bot.tree.command(name="contract", description="Anuncia a assinatura de contrato de um jogador com um time.", guild=GUILD)
async def contract_cmd(
    interaction: discord.Interaction,
    jogador: discord.Member,
    time: str,
    posicao: Optional[str] = None,
    valor: Optional[str] = None,
    temporadas: Optional[str] = None,
):
    embed = discord.Embed(
        title="✍️ CONTRATO ASSINADO",
        description=f"{jogador.mention} agora faz parte do **{time}**! 🎉",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(),
    )
    if posicao:
        embed.add_field(name="Posição", value=posicao, inline=True)
    if valor:
        embed.add_field(name="Valor", value=valor, inline=True)
    if temporadas:
        embed.add_field(name="Duração", value=temporadas, inline=True)
    embed.set_thumbnail(url=jogador.display_avatar.url)
    embed.set_footer(text=f"Assinado por {interaction.user}", icon_url=interaction.user.display_avatar.url)

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Anúncio de contrato enviado.", ephemeral=True)


@bot.tree.command(name="release", description="Anuncia a liberação/dispensa de um jogador de um time.", guild=GUILD)
async def release_cmd(
    interaction: discord.Interaction,
    jogador: discord.Member,
    time: str,
    motivo: Optional[str] = None,
):
    embed = discord.Embed(
        title="❌ JOGADOR LIBERADO",
        description=f"{jogador.mention} foi liberado(a) do **{time}**.",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(),
    )
    if motivo:
        embed.add_field(name="Motivo", value=motivo, inline=False)
    embed.set_thumbnail(url=jogador.display_avatar.url)
    embed.set_footer(text=f"Liberado por {interaction.user}", icon_url=interaction.user.display_avatar.url)

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Anúncio de liberação enviado.", ephemeral=True)


@bot.tree.command(name="elenco", description="Mostra o elenco de um time com base em um cargo.", guild=GUILD)
async def elenco_cmd(interaction: discord.Interaction, cargo: discord.Role):
    membros = [m for m in cargo.members if not m.bot]

    embed = discord.Embed(
        title=f"📋 Elenco — {cargo.name}",
        color=cargo.color if cargo.color.value != 0 else discord.Color(EMBED_COLOR),
        timestamp=datetime.datetime.now(),
    )
    embed.description = "\n".join(f"• {m.mention}" for m in membros) if membros else "Nenhum jogador encontrado com este cargo."
    embed.set_footer(text=f"Total: {len(membros)} jogador(es)")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="friendly", description="Anuncia/agenda um amistoso entre dois times.", guild=GUILD)
@tem_cargo(SCRIM_HOSTER_ROLE_ID, PIC_PERM_ROLE_ID)
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
        title="🤝 AMISTOSO CONFIRMADO",
        description=f"**{time1}**   🆚   **{time2}**",
        color=discord.Color.purple(),
        timestamp=datetime.datetime.now(),
    )
    embed.add_field(name="📅 Data", value=data, inline=True)
    embed.add_field(name="⏰ Horário", value=horario, inline=True)
    if observacoes:
        embed.add_field(name="Observações", value=observacoes, inline=False)
    embed.set_footer(text=f"Agendado por {interaction.user}", icon_url=interaction.user.display_avatar.url)

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Amistoso anunciado.", ephemeral=True)


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
