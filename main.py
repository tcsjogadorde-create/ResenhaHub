from keep_alive import keep_alive
import discord
from discord.ext import commands
import os

# Liga o servidor web para manter o Render ativo
keep_alive()

# Configuração dos Intents do Bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot conectado com sucesso como {bot.user}!')

# Comando simples de teste
@bot.command()
async def ping(ctx):
    await ctx.send('Pong! O Resenha Hub está a funcionar!')

# Obtém o token das variáveis de ambiente do Render
TOKEN = os.getenv('DISCORD_TOKEN')

if TOKEN:
    bot.run(TOKEN)
else:
    print("ERRO: A variável de ambiente DISCORD_TOKEN não foi encontrada!")
  
