import os
import discord
from discord.ext import commands

# Configuração das permissões (Intents)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Inicialização do Bot
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot online como {bot.user.name} ({bot.user.id})")
    print("Resenha Hub pronto para operar!")

# Comando simples de teste
@bot.command()
async def ping(ctx):
    await ctx.send("Pong! 🏓 O Resenha Hub está online!")

# Lê o token diretamente das variáveis de ambiente da Discloud
TOKEN = os.getenv("DISCORD_TOKEN")

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERRO: O DISCORD_TOKEN não foi encontrado nas variáveis de ambiente!")
