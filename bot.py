import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

load_dotenv() # Garante que as variáveis do .env sejam carregadas

# --- Configurações e Variáveis Globais ---
VOTOS_PARA_MUTAR = 5
VOTOS_PARA_DESMUTAR = 3
DURACAO_VOTACAO_SEGUNDOS = 20

# --- Configuração do Bot ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- Funções Auxiliares ---
async def get_or_create_mute_role(guild: discord.Guild) -> discord.Role:
    """Verifica se o cargo 'Mutado' existe. Se não, cria e configura as permissões."""
    mute_role = discord.utils.get(guild.roles, name="Mutado")
    if not mute_role:
        try:
            # Bot admin tem permissão para criar cargos, a menos que algo muito estranho aconteça.
            mute_role = await guild.create_role(name="Mutado", reason="Cargo para mutar usuários via bot.")
            for channel in guild.text_channels:
                await channel.set_permissions(mute_role, send_messages=False)
            for channel in guild.voice_channels:
                await channel.set_permissions(mute_role, speak=False)
            print(f"Cargo 'Mutado' criado e configurado no servidor {guild.name}.")
        except discord.HTTPException as e:
            print(f"Erro de API ao tentar criar/configurar o cargo 'Mutado': {e}")
            return None
    return mute_role

async def contar_votos(message: discord.Message, emoji: str, user_to_exclude: discord.User = None):
    """Conta os votos de uma reação, excluindo o próprio bot e, opcionalmente, um usuário específico."""
    try:
        message = await message.channel.fetch_message(message.id)
    except discord.NotFound:
        return 0 # A mensagem de votação foi deletada
    
    for reaction in message.reactions:
        if str(reaction.emoji) == emoji:
            users = [user async for user in reaction.users() if not user.bot]
            if user_to_exclude:
                users = [user for user in users if user.id != user_to_exclude.id]
            return len(users)
    return 0

# --- Eventos do Bot ---
@bot.event
async def on_ready():
    print(f'✅ Bot está online como {bot.user}')

# --- Comando Principal ---
@bot.command()
# 🛡️ ESSA VERIFICAÇÃO CONTINUA SENDO ESSENCIAL!
# Define que apenas moderadores (com permissão de expulsar) podem iniciar a votação.
@commands.has_permissions(kick_members=True)
async def b(ctx, member: discord.Member, action: str):
    
    # 🛡️ Verificações de segurança sobre o usuário e o alvo, continuam cruciais.
    if member == ctx.author:
        await ctx.send("❌ Você não pode iniciar uma votação contra si mesmo.")
        return
        
    if member.guild_permissions.administrator:
        await ctx.send("❌ Você não pode mutar um administrador.")
        return

    if member.top_role >= ctx.author.top_role and ctx.guild.owner != ctx.author:
        await ctx.send("❌ Você não pode iniciar uma votação contra um membro com cargo igual ou superior ao seu.")
        return

    mute_role = await get_or_create_mute_role(ctx.guild)
    if not mute_role:
        await ctx.send("❌ Ocorreu um erro ao buscar/criar o cargo 'Mutado'. Verifique os logs do bot.")
        return

    action = action.lower()

    # --- Lógica para MUTE ---
    if action == "mute":
        # ... (a lógica interna de mute permanece a mesma) ...
        # ... (código da votação, sleep, contagem, add_roles, etc.) ...
        vote_msg = await ctx.send(f"🗳️ **VOTAÇÃO PARA MUTAR** {member.mention}...\n(Necessários {VOTOS_PARA_MUTAR} votos em {DURACAO_VOTACAO_SEGUNDOS}s)")
        await vote_msg.add_reaction("✅")
        await asyncio.sleep(DURACAO_VOTACAO_SEGUNDOS)
        votos_sim = await contar_votos(vote_msg, "✅", user_to_exclude=member)
        if votos_sim >= VOTOS_PARA_MUTAR:
            await member.add_roles(mute_role, reason=f"Mutado por votação ({votos_sim} votos)")
            await ctx.send(f"🔇 **Votação Aprovada!** {member.mention} foi mutado.")
            if member.voice:
                await member.move_to(None, reason="Mutado por votação.")
                await ctx.send(f"📤 {member.display_name} foi desconectado do canal de voz.")
        else:
            await ctx.send(f"❌ **Votação Falhou.** Apenas {votos_sim} de {VOTOS_PARA_MUTAR} votos.")

    # --- Lógica para UNMUTE ---
    elif action == "unmute":
        # ... (a lógica interna de unmute permanece a mesma) ...
        vote_msg = await ctx.send(f"🗳️ **VOTAÇÃO PARA DESMUTAR** {member.mention}...\n(Necessários {VOTOS_PARA_DESMUTAR} votos em {DURACAO_VOTACAO_SEGUNDOS}s)")
        await vote_msg.add_reaction("✅")
        await asyncio.sleep(DURACAO_VOTACAO_SEGUNDOS)
        votos_sim = await contar_votos(vote_msg, "✅")
        if votos_sim >= VOTOS_PARA_DESMUTAR:
            await member.remove_roles(mute_role, reason=f"Desmutado por votação ({votos_sim} votos)")
            await ctx.send(f"🔊 **Votação Aprovada!** {member.mention} foi desmutado.")
        else:
            await ctx.send(f"❌ **Votação Falhou.** Apenas {votos_sim} de {VOTOS_PARA_DESMUTAR} votos.")

    else:
        await ctx.send("Ação inválida. Use `mute` ou `unmute`.")

# 💡 Tratamento de erros focado no USUÁRIO.
@b.error
async def b_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument) or isinstance(error, commands.BadArgument):
        await ctx.send("Uso incorreto. Tente: `!b @usuário mute` ou `!b @usuário unmute`")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para usar este comando.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(f"❌ Não encontrei o membro `{error.argument}`.")
    else:
        # Erros inesperados ainda são impressos no console para depuração.
        print(f"Erro inesperado no comando 'b': {error}")
        await ctx.send("Ocorreu um erro inesperado ao executar o comando.")

# --- Execução do Bot ---
bot.run(os.getenv("TOKEN"))