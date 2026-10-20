import os
import random
import asyncio
import sqlite3
from datetime import datetime, timedelta
import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask
import threading

# ==========================================
# 1. FLASK KEEP-ALIVE (PARA O RENDER)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Resenha Hub Bot está Ativo e Online!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 2. CONFIGURAÇÃO DO BANCO DE DADOS (SQLITE)
# ==========================================
DB_FILE = "resenha_hub.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS guildas_autorizadas (
        guild_id INTEGER PRIMARY KEY
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS diarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        tipo TEXT,
        formato TEXT,
        nome TEXT,
        descricao TEXT,
        tempo_wo TEXT,
        limite INTEGER,
        imagem_banner TEXT,
        status TEXT DEFAULT 'Aberto',
        canal_id INTEGER,
        mensagem_id INTEGER
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS participantes (
        diario_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (diario_id, user_id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ranking (
        user_id INTEGER,
        categoria TEXT,
        pontos INTEGER DEFAULT 0,
        titulos INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, categoria)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS vips (
        user_id INTEGER PRIMARY KEY,
        guild_id INTEGER,
        role_id INTEGER,
        data_inicio TEXT,
        data_fim TEXT,
        status TEXT DEFAULT 'Ativo'
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        descricao TEXT,
        preco REAL,
        estoque INTEGER,
        imagem TEXT,
        categoria TEXT DEFAULT 'Solo',
        cargo_id INTEGER,
        duracao_dias INTEGER
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS configs (
        guild_id INTEGER PRIMARY KEY,
        canal_loja INTEGER,
        canal_logs INTEGER,
        canal_pedidos INTEGER,
        cargo_atendimento INTEGER,
        cargo_admin INTEGER
    )''')

    conn.commit()
    conn.close()

init_db()

# ==========================================
# 3. SETUP DO BOT DISCORD
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

def eh_servidor_autorizado(guild_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT guild_id FROM guildas_autorizadas WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def adicionar_pontos_ranking(user_id: int, categoria: str, pontos: int = 3, e_titulo: bool = False):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT pontos, titulos FROM ranking WHERE user_id = ? AND categoria = ?", (user_id, categoria))
    row = cursor.fetchone()
    
    if row:
        novos_pontos = row[0] + pontos
        novos_titulos = row[1] + (1 if e_titulo else 0)
        cursor.execute("UPDATE ranking SET pontos = ?, titulos = ? WHERE user_id = ? AND categoria = ?", 
                       (novos_pontos, novos_titulos, user_id, categoria))
    else:
        cursor.execute("INSERT INTO ranking (user_id, categoria, pontos, titulos) VALUES (?, ?, ?, ?)", 
                       (user_id, categoria, pontos, 1 if e_titulo else 0))
        
    conn.commit()
    conn.close()

# ==========================================
# 4. BOTÕES E INTERFACES (DIÁRIOS)
# ==========================================
class InscricaoDiarioView(discord.ui.View):
    def __init__(self, diario_id: int):
        super().__init__(timeout=None)
        self.diario_id = diario_id
        self.atualizar_contador()

    def obter_total_participantes(self) -> int:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM participantes WHERE diario_id = ?", (self.diario_id,))
        total = cursor.fetchone()[0]
        conn.close()
        return total

    def atualizar_contador(self):
        total = self.obter_total_participantes()
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == "btn_iniciar":
                item.label = f"Iniciar ({total})"

    @discord.ui.button(label="Participar", style=discord.ButtonStyle.green, custom_id="btn_participar")
    async def participar(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO participantes (diario_id, user_id) VALUES (?, ?)", (self.diario_id, interaction.user.id))
            conn.commit()
            await interaction.response.send_message("✅ Você entrou no Diário com sucesso!", ephemeral=True)
        except sqlite3.IntegrityError:
            await interaction.response.send_message("⚠️ Você já está inscrito neste Diário!", ephemeral=True)
        finally:
            conn.close()
            
        self.atualizar_contador()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red, custom_id="btn_sair")
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM participantes WHERE diario_id = ? AND user_id = ?", (self.diario_id, interaction.user.id))
        conn.commit()
        conn.close()
        
        await interaction.response.send_message("❌ Você saiu do Diário.", ephemeral=True)
        self.atualizar_contador()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Iniciar (0)", style=discord.ButtonStyle.blurple, custom_id="btn_iniciar")
    async def iniciar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("⛔ Apenas administradores podem iniciar o Diário!", ephemeral=True)
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM participantes WHERE diario_id = ?", (self.diario_id,))
        jogadores = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT tipo, formato FROM diarios WHERE id = ?", (self.diario_id,))
        diario_info = cursor.fetchone()
        conn.close()

        if len(jogadores) < 2:
            await interaction.response.send_message("⚠️ É necessário pelo menos 2 participantes para iniciar!", ephemeral=True)
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE diarios SET status = 'Em Andamento' WHERE id = ?", (self.diario_id,))
        conn.commit()
        conn.close()

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(content="🔒 **Inscrições Encerradas! Sorteando confrontos...**", view=self)

        random.shuffle(jogadores)
        confrontos = []
        for i in range(0, len(jogadores) - 1, 2):
            confrontos.append((jogadores[i], jogadores[i+1]))

        embed = discord.Embed(
            title=f"⚔️ CONFRONTOS SORTEADOS — DIÁRIO #{self.diario_id}",
            description=f"**Modalidade:** {diario_info[0]} ({diario_info[1]})\n\n",
            color=discord.Color.green()
        )

        for idx, (j1, j2) in enumerate(confrontos, 1):
            embed.description += f"**Jogo {idx}:** <@{j1}> 🆚 <@{j2}>\n"

        if len(jogadores) % 2 != 0:
            embed.description += f"\n🏆 **Folga na Rodada:** <@{jogadores[-1]}> (Avança automaticamente)"

        await interaction.response.send_message(embed=embed)

# ==========================================
# 5. EVENTOS DO BOT & REPETIDORES DE TASK
# ==========================================
@bot.event
async def on_ready():
    print(f"🤖 [RESENHA HUB] Logado com sucesso como {bot.user}!")
    try:
        synced = await bot.tree.sync()
        print(f"⚡ [SLASH COMMANDS] {len(synced)} comandos sincronizados globalmente!")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")
    
    verificar_vips_expirados.start()

@tasks.loop(minutes=1)
async def verificar_vips_expirados():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("SELECT user_id, guild_id, role_id FROM vips WHERE status = 'Ativo' AND data_fim <= ?", (agora_str,))
    expirados = cursor.fetchall()
    
    for user_id, guild_id, role_id in expirados:
        guild = bot.get_guild(guild_id)
        if guild:
            member = guild.get_member(user_id)
            role = guild.get_role(role_id)
            if member and role:
                try:
                    await member.remove_roles(role)
                    await member.send("⚠️ **Seu plano VIP no Resenha Hub expirou!** Esperamos ter você de volta em breve.")
                except Exception as e:
                    print(f"Erro ao remover cargo VIP: {e}")
                    
        cursor.execute("UPDATE vips SET status = 'Expirado' WHERE user_id = ?", (user_id,))
    
    conn.commit()
    conn.close()

# ==========================================
# 6. COMANDOS SLASH (APP COMMANDS)
# ==========================================

# --- GESTÃO E ADMINISTRAÇÃO DE LOJA
