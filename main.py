import os
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
    
    # Servidores Autorizados
    cursor.execute('''CREATE TABLE IF NOT EXISTS guildas_autorizadas (
        guild_id INTEGER PRIMARY KEY
    )''')
    
    # Diários / Torneios
    cursor.execute('''CREATE TABLE IF NOT EXISTS diarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        tipo TEXT, -- Futecord ou Dream Team
        formato TEXT, -- 1v1, 2v2, 3v3, 4v4
        nome TEXT,
        descricao TEXT,
        tempo_wo TEXT,
        limite INTEGER,
        status TEXT DEFAULT 'Aberto', -- Aberto, Em Andamento, Finalizado
        canal_id INTEGER,
        mensagem_id INTEGER
    )''')
    
    # Participantes dos Diários
    cursor.execute('''CREATE TABLE IF NOT EXISTS participantes (
        diario_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (diario_id, user_id)
    )''')

    # Ranking (Futecord / Dream Team - Mensal e Anual)
    cursor.execute('''CREATE TABLE IF NOT EXISTS ranking (
        user_id INTEGER,
        categoria TEXT, -- Futecord_Mensal, Futecord_Anual, DT_Mensal, DT_Anual
        pontos INTEGER DEFAULT 0,
        titulos INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, categoria)
    )''')

    # Sistema VIP
    cursor.execute('''CREATE TABLE IF NOT EXISTS vips (
        user_id INTEGER PRIMARY KEY,
        guild_id INTEGER,
        role_id INTEGER,
        data_inicio TEXT,
        data_fim TEXT,
        status TEXT DEFAULT 'Ativo'
    )''')

    # Loja & Produtos
    cursor.execute('''CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        descricao TEXT,
        preco REAL,
        estoque INTEGER, -- -1 para Infinito
        imagem TEXT,
        cargo_id INTEGER,
        duracao_dias INTEGER
    )''')

    # Configurações do Bot
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

# Check de Autorização de Servidor
def eh_servidor_autorizado(guild_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT guild_id FROM guildas_autorizadas WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

# ==========================================
# 4. BOTÕES E INTERFACES (DIÁRIOS & LOJA)
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

        total = self.obter_total_participantes()
        if total < 2:
            await interaction.response.send_message("⚠️ É necessário pelo menos 2 participantes para iniciar!", ephemeral=True)
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE diarios SET status = 'Em Andamento' WHERE id = ?", (self.diario_id,))
        conn.commit()
        conn.close()

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(content="🔒 **Inscrições Encerradas! Sorteando times...**", view=self)
        
        await interaction.response.send_message(f"🚀 **Diário #{self.diario_id} iniciado com sucesso por {interaction.user.mention}!**\nTotal de Participantes: **{total}**")

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

@bot.tree.command(name="autorizar_servidor", description="[Dono] Autoriza este servidor a usar o Resenha Hub")
@app_commands.checks.has_permissions(administrator=True)
async def autorizar_servidor(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO guildas_autorizadas (guild_id) VALUES (?)", (interaction.guild_id,))
    conn.commit()
    conn.close()
    await interaction.response.send_message("✅ **Servidor Autorizado com Sucesso!** O Resenha Hub já pode ser utilizado aqui.", ephemeral=True)

@bot.tree.command(name="iniciar_diario", description="Abre as inscrições para um novo Diário (Futecord / Dream Team)")
@app_commands.describe(
    tipo="Tipo de Diário",
    formato="Formato dos times",
    nome="Nome do Diário",
    tempo_wo="Tempo limite de W.O. (ex: 15min)"
)
@app_commands.choices(
    tipo=[
        app_commands.Choice(name="Futecord", value="Futecord"),
        app_commands.Choice(name="Dream Team", value="Dream Team")
    ],
    formato=[
        app_commands.Choice(name="1v1", value="1v1"),
        app_commands.Choice(name="2v2", value="2v2"),
        app_commands.Choice(name="3v3", value="3v3"),
        app_commands.Choice(name="4v4", value="4v4")
    ]
)
async def iniciar_diario(interaction: discord.Interaction, tipo: str, formato: str, nome: str, tempo_wo: str = "15 minutos"):
    if not eh_servidor_autorizado(interaction.guild_id):
        await interaction.response.send_message("⛔ Este servidor não está autorizado a utilizar o Resenha Hub!", ephemeral=True)
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO diarios (guild_id, tipo, formato, nome, descricao, tempo_wo, status, canal_id)
        VALUES (?, ?, ?, ?, ?, ?, 'Aberto', ?)
    """, (interaction.guild_id, tipo, formato, nome, f"Diário {tipo} {formato}", tempo_wo, interaction.channel_id))
    
    diario_id = cursor.lastrowid
    conn.commit()
    conn.close()

    embed = discord.Embed(
        title=f"🏆 {nome.upper()} — INSCRIÇÕES ABERTAS!",
        description=f"**Tipo:** {tipo}\n**Formato:** {formato}\n**Tempo de W.O.:** {tempo_wo}\n\nClique no botão abaixo para se inscrever!",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"Resenha Hub • ID do Diário: #{diario_id}")

    view = InscricaoDiarioView(diario_id=diario_id)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="rank", description="Exibe o ranking do Diário Futecord ou Dream Team")
@app_commands.choices(
    periodo=[
        app_commands.Choice(name="Mensal", value="Mensal"),
        app_commands.Choice(name="Anual", value="Anual")
    ],
    modalidade=[
        app_commands.Choice(name="Futecord", value="Futecord"),
        app_commands.Choice(name="Dream Team", value="Dream Team")
    ]
)
async def rank(interaction: discord.Interaction, periodo: str, modalidade: str):
    categoria = f"{modalidade}_{periodo}"
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, pontos FROM ranking WHERE categoria = ? ORDER BY pontos DESC LIMIT 5", (categoria,))
    top5 = cursor.fetchall()
    conn.close()

    embed = discord.Embed(
        title=f"📊 TOP 5 RANKING — {modalidade.upper()} ({periodo.upper()})",
        color=discord.Color.blue()
    )

    if not top5:
        embed.description = "Nenhum jogador pontuou nesta categoria ainda!"
    else:
        texto = ""
        medalias = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for idx, (user_id, pontos) in enumerate(top5):
            texto += f"{medalias[idx]} <@{user_id}> — **{pontos} Ponto(s)**\n"
        embed.description = texto

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vip_adicionar", description="Concede plano VIP a um usuário")
@app_commands.choices(
    duracao=[
        app_commands.Choice(name="15 Dias", value=15),
        app_commands.Choice(name="30 Dias", value=30),
        app_commands.Choice(name="60 Dias", value=60)
    ]
)
@app_commands.checks.has_permissions(administrator=True)
async def vip_adicionar(interaction: discord.Interaction, usuario: discord.Member, cargo: discord.Role, duracao: int):
    inicio = datetime.now()
    fim = inicio + timedelta(dias=duracao)
    
    inicio_str = inicio.strftime("%Y-%m-%d %H:%M:%S")
    fim_str = fim.strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO vips (user_id, guild_id, role_id, data_inicio, data_fim, status)
        VALUES (?, ?, ?, ?, ?, 'Ativo')
    """, (usuario.id, interaction.guild_id, cargo.id, inicio_str, fim_str))
    conn.commit()
    conn.close()

    try:
        await usuario.add_roles(cargo)
        await usuario.send(f"🎉 **Parabéns!** Seu VIP foi ativado!\n**Duração:** {duracao} Dias\n**Validade:** até {fim.strftime('%d/%m/%Y às %H:%M')}")
    except Exception as e:
        print(f"Erro ao enviar DM/Cargo VIP: {e}")

    await interaction.response.send_message(f"✅ VIP concedido com sucesso para {usuario.mention} por {duracao} dias!", ephemeral=True)

# ==========================================
# 7. INICIALIZAÇÃO
# ==========================================
keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ ERRO: A variável de ambiente DISCORD_TOKEN não foi configurada!")
  
