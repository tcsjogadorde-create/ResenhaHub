import os
import re
import random
import sqlite3
import threading
from flask import Flask
import discord
from discord.ext import commands

# ---------------------------------------------------------
# 1. SERVIDOR FLASK (Keep Alive 24/7)
# ---------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot Resenha Hub + Nexus Store Online 24/7!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

# ---------------------------------------------------------
# 2. BANCO DE DADOS (SQLite - Diários e Loja)
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect('diarios.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ranking (
            user_id INTEGER PRIMARY KEY,
            pontos INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config_diario (
            id INTEGER PRIMARY KEY DEFAULT 1,
            imagem_padrao TEXT
        )
    ''')
    conn.commit()
    conn.close()

def salvar_imagem_padrao(url: str):
    conn = sqlite3.connect('diarios.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO config_diario (id, imagem_padrao) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET imagem_padrao = ?
    ''', (url, url))
    conn.commit()
    conn.close()

def obter_imagem_padrao():
    conn = sqlite3.connect('diarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT imagem_padrao FROM config_diario WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def init_loja_db():
    conn = sqlite3.connect('loja.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE,
            titulo TEXT,
            descricao TEXT,
            preco REAL DEFAULT 0.0,
            cor INTEGER DEFAULT 3447003,
            estoque INTEGER DEFAULT 0,
            imagem TEXT,
            termos TEXT,
            tipo TEXT DEFAULT 'unico'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itens_catalogo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER,
            nome TEXT,
            preco REAL,
            estoque INTEGER DEFAULT 0,
            FOREIGN KEY(produto_id) REFERENCES produtos(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cupons (
            codigo TEXT PRIMARY KEY,
            desconto REAL
        )
    ''')
    conn.commit()
    conn.close()

def adicionar_ponto_secretamente(user_id: int):
    conn = sqlite3.connect('diarios.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ranking (user_id, pontos) VALUES (?, 1)
        ON CONFLICT(user_id) DO UPDATE SET pontos = pontos + 1
    ''', (user_id,))
    conn.commit()
    conn.close()

def resetar_ranking_db():
    conn = sqlite3.connect('diarios.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM ranking')
    conn.commit()
    conn.close()

def obter_ranking():
    conn = sqlite3.connect('diarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, pontos FROM ranking ORDER BY pontos DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

# ---------------------------------------------------------
# 3. CONFIGURAÇÕES E FRASES DO DIÁRIO
# ---------------------------------------------------------
FRASES_CAMPEAO = [
    "Parabéns aos vencedores, até que enfim a sorte resolveu trabalhar por vocês. Jogaram nada e mesmo assim conseguiram ganhar, impressionante KKKKK.",
    "Os caras ganharam e até agora ninguém entendeu como. Jogaram mal pra caramba, mas a sorte tava do lado deles o jogo inteiro KKKKK.",
    "Parabéns pelo título, porque jogar bola mesmo vocês não jogaram. Dessa vez a sorte carregou vocês bonito KKKKK.",
    "Não vou mentir, vocês tiveram uma sorte absurda nessa. Porque se dependesse de habilidade, a história teria sido bem diferente KKKKK.",
    "Parabéns aos vencedores, que tiveram uma ajudinha pra chegar até aqui. Porque habilidade nunca existiu, então alguém tinha que ajudar KKKKK."
]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
BOTS_JOGOS = ["Dream Team", "Futecord"]
mata_mata_topicos = {}
  # ---------------------------------------------------------
# 4. PAINEL DE CONFIGURAÇÃO DA LOJA (/config_loja)
# ---------------------------------------------------------
class PainelConfigLojaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="O que deseja configurar?",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Configurar Loja", description="Categoria dos carrinhos e canais de logs", emoji="🔧", value="config_loja"),
            discord.SelectOption(label="Configurar Pagamentos", description="Defina as formas de pagamento aceitas", emoji="💳", value="config_pagamentos"),
            discord.SelectOption(label="Gerenciar Cupons", description="Crie cupons de desconto para seus clientes", emoji="✉️", value="gerenciar_cupons"),
            discord.SelectOption(label="Gerenciar Produtos", description="Crie, edite e remova produtos da loja", emoji="📁", value="gerenciar_produtos"),
            discord.SelectOption(label="Relatório de Vendas", description="Veja o desempenho de vendas da loja", emoji="🔲", value="relatorio_vendas"),
            discord.SelectOption(label="Enviar Produto", description="Envie o painel de um produto em um canal", emoji="🚀", value="enviar_produto"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        opcao = select.values[0]

        if opcao == "config_loja":
            embed = discord.Embed(title="🔧 | Canais da Loja", description="Defina onde os carrinhos são criados e para onde vão os registros da loja.", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed, view=VoltarView(), ephemeral=True)

        elif opcao == "config_pagamentos":
            embed = discord.Embed(title="💳 | Formas de Pagamento", description="Escolha e configure como os clientes poderão pagar pelos produtos.", color=discord.Color.gold())
            await interaction.response.send_message(embed=embed, view=VoltarView(), ephemeral=True)

        elif opcao == "gerenciar_cupons":
            conn = sqlite3.connect('loja.db')
            cursor = conn.cursor()
            cursor.execute('SELECT codigo, desconto FROM cupons')
            cupons = cursor.fetchall()
            conn.close()

            desc = "Crie códigos de desconto para seus clientes usarem na hora da compra.\n\n**Cupons cadastrados**\n\n"
            if not cupons:
                desc += "❗ **Nenhum cupom cadastrado ainda.**"
            else:
                for cod, desc_val in cupons:
                    desc += f"🎫 **{cod}** — Desconto: **{desc_val}%**\n"

            embed = discord.Embed(title="✉️ | Cupons", description=desc, color=discord.Color.blue())
            await interaction.response.send_message(embed=embed, view=CuponsView(), ephemeral=True)

        elif opcao == "gerenciar_produtos":
            await interaction.response.send_message(embed=get_embed_gerenciar_produtos(), view=GerenciarProdutosView(), ephemeral=True)

        elif opcao == "enviar_produto":
            await interaction.response.send_message(embed=get_embed_enviar_produto(), view=EnviarProdutoView(), ephemeral=True)

        else:
            await interaction.response.send_message("📊 **Relatório de Vendas:** Nenhuma venda registrada.", ephemeral=True)

class VoltarView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛒 Painel de Configuração da Loja", color=discord.Color.from_rgb(47, 49, 54))
        await interaction.response.send_message(embed=embed, view=PainelConfigLojaView(), ephemeral=True)

class CuponsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Criar Cupom", style=discord.ButtonStyle.success, emoji="➕")
    async def criar_cupom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalCriarCupom())

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛒 Painel de Configuração da Loja", color=discord.Color.from_rgb(47, 49, 54))
        await interaction.response.send_message(embed=embed, view=PainelConfigLojaView(), ephemeral=True)

class ModalCriarCupom(discord.ui.Modal, title="Criar Cupom"):
    codigo = discord.ui.TextInput(label="Código do Cupom", placeholder="Ex: DESCONTO10", required=True)
    desconto = discord.ui.TextInput(label="Porcentagem de Desconto (%)", placeholder="Ex: 10", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = float(self.desconto.value.replace(',', '.'))
            conn = sqlite3.connect('loja.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO cupons (codigo, desconto) VALUES (?, ?)', (self.codigo.value.upper(), val))
            conn.commit()
            conn.close()
            await interaction.response.send_message(f"✅ Cupom **{self.codigo.value.upper()}** criado!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao criar cupom: {e}", ephemeral=True)
          # ---------------------------------------------------------
# 5. GERENCIAMENTO E EDIÇÃO DE PRODUTOS
# ---------------------------------------------------------
def get_embed_gerenciar_produtos():
    conn = sqlite3.connect('loja.db')
    cursor = conn.cursor()
    cursor.execute('SELECT nome FROM produtos')
    prods = cursor.fetchall()
    conn.close()

    total = len(prods)
    desc = f"**{total} produto(s) cadastrado(s).**\n\n"
    if total == 0:
        desc += "❗ **Nenhum produto cadastrado ainda.**\nClique em **Criar Produto** para adicionar o primeiro."
    else:
        desc += "Adicione novos produtos ou edite os existentes abaixo:"

    return discord.Embed(title="📁 | Gerenciar Produtos", description=desc, color=discord.Color.blue())

class GerenciarProdutosView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Criar Produto", style=discord.ButtonStyle.success, emoji="➕")
    async def criar_produto(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📌 **Escolha o formato do novo produto:**", view=SelecionarTipoCriacaoView(), ephemeral=True)

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛒 Painel de Configuração da Loja", color=discord.Color.from_rgb(47, 49, 54))
        await interaction.response.send_message(embed=embed, view=PainelConfigLojaView(), ephemeral=True)

class SelecionarTipoCriacaoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        placeholder="Selecione o formato do produto...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Produto Único", description="Item simples com botão direto de compra", emoji="📦", value="unico"),
            discord.SelectOption(label="Catálogo (Múltiplas Opções)", description="Menu dropdown idêntico ao print", emoji="📂", value="catalogo")
        ]
    )
    async def select_tipo_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_modal(ModalCriarProdutoNome(tipo_produto=select.values[0]))

class ModalCriarProdutoNome(discord.ui.Modal, title="Criar Produto"):
    nome_produto = discord.ui.TextInput(label="Nome do produto", placeholder="Ex: CONTAS COM SANGUÍNE", required=True)

    def __init__(self, tipo_produto: str):
        super().__init__()
        self.tipo_produto = tipo_produto

    async def on_submit(self, interaction: discord.Interaction):
        nome = self.nome_produto.value.strip()
        conn = sqlite3.connect('loja.db')
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO produtos (nome, tipo) VALUES (?, ?)', (nome, self.tipo_produto))
            conn.commit()

            if self.tipo_produto == "catalogo":
                cursor.execute('SELECT id FROM produtos WHERE nome = ?', (nome,))
                prod_id = cursor.fetchone()[0]
                ex_items = [
                    ("GOD+SANGUINE+MAX", 6.00, 0),
                    ("GOD+CDK+SG+MAX", 4.50, 0),
                    ("GOD+MAX+CDK", 4.00, 0),
                    ("GOD+SG+MAX", 3.50, 0),
                    ("GOD+MAX", 1.00, 0)
                ]
                for item_nome, item_preco, item_est in ex_items:
                    cursor.execute('INSERT INTO itens_catalogo (produto_id, nome, preco, estoque) VALUES (?, ?, ?, ?)',
                                   (prod_id, item_nome, item_preco, item_est))
                conn.commit()

            conn.close()
            embed, view = get_painel_edicao_produto(nome)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except sqlite3.IntegrityError:
            conn.close()
            await interaction.response.send_message("❌ Já existe um produto cadastrado com esse nome!", ephemeral=True)

def get_painel_edicao_produto(nome_prod):
    conn = sqlite3.connect('loja.db')
    cursor = conn.cursor()
    cursor.execute('SELECT titulo, descricao, preco, estoque, tipo FROM produtos WHERE nome = ?', (nome_prod,))
    row = cursor.fetchone()
    conn.close()

    titulo = row[0] if row and row[0] else nome_prod
    desc = row[1] if row and row[1] else "Sem descrição configurada..."
    preco = row[2] if row else 0.00
    estoque = row[3] if row else 0
    tipo = row[4] if row and row[4] else "unico"

    tipo_str = "📦 Produto Único" if tipo == "unico" else "📂 Catálogo"

    embed = discord.Embed(
        title="✏️ | Edição de Produto",
        description=f"Selecione uma opção abaixo para editar ou configurar.\n\n🛍️ **{titulo}** `[{tipo_str}]`\n*{desc}*\n\n**R$ {preco:.2f}**\n{estoque} unidade(s) disponível(is)",
        color=discord.Color.blue()
    )
    return embed, EdicaoProdutoView(nome_prod)

class EdicaoProdutoView(discord.ui.View):
    def __init__(self, nome_prod):
        super().__init__(timeout=None)
        self.nome_prod = nome_prod

    @discord.ui.select(
        placeholder="O que vai editar?",
        options=[
            discord.SelectOption(label="Alterar Título", description="Personalizar título do produto", emoji="✏️", value="titulo"),
            discord.SelectOption(label="Alterar Descrição", description="Personalizar descrição do produto", emoji="💬", value="descricao"),
            discord.SelectOption(label="Alterar Valor", description="Personalizar valor do produto", emoji="💰", value="valor"),
            discord.SelectOption(label="Alterar Cor", description="Personalizar cor da borda", emoji="⭐", value="cor"),
            discord.SelectOption(label="Configurar Estoque", description="Entrega automática ou manual", emoji="📁", value="estoque"),
            discord.SelectOption(label="Configurar Imagem", description="Imagem exibida no produto", emoji="⬆️", value="imagem"),
            discord.SelectOption(label="Definir Termos de Compra", description="Termo aceito pelo cliente", emoji="💬", value="termos"),
            discord.SelectOption(label="Excluir Produto", description="Remove o produto permanentemente", emoji="🗑️", value="excluir"),
        ]
    )
    async def edit_select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        campo = select.values[0]

        if campo == "excluir":
            conn = sqlite3.connect('loja.db')
            cursor = conn.cursor()
            cursor.execute('DELETE FROM produtos WHERE nome = ?', (self.nome_prod,))
            conn.commit()
            conn.close()
            await interaction.response.send_message(f"🗑️ Produto **{self.nome_prod}** excluído!", ephemeral=True)
        else:
            await interaction.response.send_modal(ModalEditarCampo(nome_produto=self.nome_prod, campo=campo))

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=get_embed_gerenciar_produtos(), view=GerenciarProdutosView(), ephemeral=True)

class ModalEditarCampo(discord.ui.Modal, title="Editar Configuração do Produto"):
    valor_input = discord.ui.TextInput(label="Novo valor / Texto", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, nome_produto: str, campo: str):
        super().__init__()
        self.nome_produto = nome_produto
        self.campo = campo

    async def on_submit(self, interaction: discord.Interaction):
        novo_val = self.valor_input.value.strip()
        conn = sqlite3.connect('loja.db')
        cursor = conn.cursor()

        try:
            if self.campo == "titulo":
                cursor.execute('UPDATE produtos SET titulo = ? WHERE nome = ?', (novo_val, self.nome_produto))
            elif self.campo == "descricao":
                cursor.execute('UPDATE produtos SET descricao = ? WHERE nome = ?', (novo_val, self.nome_produto))
            elif self.campo == "valor":
                cursor.execute('UPDATE produtos SET preco = ? WHERE nome = ?', (float(novo_val.replace(',', '.')), self.nome_produto))
            elif self.campo == "estoque":
                cursor.execute('UPDATE produtos SET estoque = ? WHERE nome = ?', (int(novo_val), self.nome_produto))
            elif self.campo == "imagem":
                cursor.execute('UPDATE produtos SET imagem = ? WHERE nome = ?', (novo_val, self.nome_produto))
            elif self.campo == "termos":
                cursor.execute('UPDATE produtos SET termos = ? WHERE nome = ?', (novo_val, self.nome_produto))

            conn.commit()
            conn.close()

            embed, view = get_painel_edicao_produto(self.nome_produto)
            await interaction.response.send_message(content="✅ **Produto atualizado!**", embed=embed, view=view, ephemeral=True)
        except Exception as e:
            conn.close()
            await interaction.response.send_message(f"❌ Erro ao atualizar o campo: {e}", ephemeral=True)

# ---------------------------------------------------------
# 6. ENVIAR PRODUTO NO CANAL DO SERVIDOR
# ---------------------------------------------------------
def get_embed_enviar_produto():
    return discord.Embed(
        title="🚀 | Enviar Produto",
        description="Escolha um produto abaixo para enviar o painel de compra dele em um canal do servidor.",
        color=discord.Color.blue()
    )

class EnviarProdutoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Produto:", style=discord.ButtonStyle.secondary, emoji="🛍️")
    async def escolher_produto(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect('loja.db')
        cursor = conn.cursor()
        cursor.execute('SELECT nome, preco, estoque FROM produtos')
        prods = cursor.fetchall()
        conn.close()

        if not prods:
            await interaction.response.send_message("❌ Nenhum produto cadastrado para enviar!", ephemeral=True)
            return

        options = [
            discord.SelectOption(label=f"{i}. {nome}", description=f"R$ {preco:.2f} • Estoque: {estoque}", value=nome)
            for i, (nome, preco, estoque) in enumerate(prods, 1)
        ]

        select = discord.ui.Select(placeholder="Selecione um produto...", options=options)

        async def product_callback(i: discord.Interaction):
            prod_nome = i.data["values"][0]
            embed_canal = discord.Embed(title=f"📤 Selecione o canal onde deseja enviar o produto {prod_nome}:", color=discord.Color.blue())
            await i.response.send_message(embed=embed_canal, view=ViewCanalEnvio(prod_nome), ephemeral=True)

        select.callback = product_callback
        v = discord.ui.View()
        v.add_item(select)
        await interaction.response.send_message(embed=discord.Embed(title="Produto:"), view=v, ephemeral=True)

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛒 Painel de Configuração da Loja", color=discord.Color.from_rgb(47, 49, 54))
        await interaction.response.send_message(embed=embed, view=PainelConfigLojaView(), ephemeral=True)

class ViewCanalEnvio(discord.ui.View):
    def __init__(self, prod_nome):
        super().__init__(timeout=60)
        self.prod_nome = prod_nome
        self.add_item(discord.ui.ChannelSelect(placeholder="Selecione um canal...", channel_types=[discord.ChannelType.text]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        canal_id = interaction.data["values"][0]
        canal = interaction.guild.get_channel(int(canal_id))

        if canal:
            conn = sqlite3.connect('loja.db')
            cursor = conn.cursor()
            cursor.execute('SELECT id, titulo, descricao, preco, estoque, imagem, tipo FROM produtos WHERE nome = ?', (self.prod_nome,))
            row = cursor.fetchone()

            if not row:
                conn.close()
                await interaction.response.send_message("❌ Produto não encontrado!", ephemeral=True)
                return True

            p_id, titulo, desc, preco, estoque, imagem, tipo = row
            titulo = titulo if titulo else self.prod_nome
            desc = desc if desc else "Sem descrição configurada."

            embed_anuncio = discord.Embed(
                title=f"⚡ {titulo.upper()}",
                description=desc,
                color=discord.Color.red()
            )
            if imagem:
                embed_anuncio.set_image(url=imagem)
            embed_anuncio.set_footer(text=f"{interaction.guild.name} | Vendas Automáticas")

            if tipo == "catalogo":
                cursor.execute('SELECT nome, preco, estoque FROM itens_catalogo WHERE produto_id = ?', (p_id,))
                itens = cursor.fetchall()
                conn.close()

                opts = []
                for it_nome, it_preco, it_est in itens:
                    opts.append(discord.SelectOption(
                        label=it_nome,
                        description=f"Preço: R$ {it_preco:.2f} | Estoque: {it_est}",
                        value=f"buy_cat_{it_nome}"
                    ))

                if not opts:
                    opts.append(discord.SelectOption(label="Exemplo de Opção", description="R$ 0,00", value="buy_ex"))

                v = discord.ui.View(timeout=None)
                v.add_item(discord.ui.Select(placeholder="➡️ Clique aqui para ver as opções", options=opts, custom_id=f"catalogo_{p_id}"))
                await canal.send(embed=embed_anuncio, view=v)
            else:
                conn.close()
                v = discord.ui.View(timeout=None)
                v.add_item(discord.ui.Button(label="Comprar Produto", style=discord.ButtonStyle.green, emoji="🛒", custom_id=f"buy_single_{p_id}"))
                await canal.send(embed=embed_anuncio, view=v)

            await interaction.response.send_message(f"✅ Anúncio do produto enviado com sucesso em {canal.mention}!", ephemeral=True)
        return True

# ---------------------------------------------------------
# 7. PARSER AUTOMÁTICO DO MATA-MATA
# ---------------------------------------------------------
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    is_bot_jogo = message.author.bot and any(nome.lower() in message.author.name.lower() for nome in BOTS_JOGOS)

    if is_bot_jogo and message.embeds:
        mentions = message.mentions
        embed = message.embeds[0]
        
        texto_embed = f"{embed.title or ''} {embed.description or ''}"
        for field in embed.fields:
            texto_embed += f" {field.name} {field.value}"

        placar_match = re.search(r'(\d+)\s*[:xX-]\s*(\d+)', texto_embed)

        if placar_match and len(mentions) >= 2:
            gols_t1 = int(placar_match.group(1))
            gols_t2 = int(placar_match.group(2))

            metade = len(mentions) // 2
            time_1 = mentions[:metade]
            time_2 = mentions[metade:]

            mencoes_t1 = " ".join([u.mention for u in time_1])
            mencoes_t2 = " ".join([u.mention for u in time_2])

            await message.channel.send(
                f"⚽ **Resultado da Partida:**\n"
                f"🔴 **Time 1:** {mencoes_t1} (**{gols_t1}** gols)\n"
                f"🔵 **Time 2:** {mencoes_t2} (**{gols_t2}** gols)"
            )

            cid = message.channel.id
            if cid not in mata_mata_topicos:
                mata_mata_topicos[cid] = {}

            eh_final = any(p in texto_embed.lower() for p in ["final", "decisão", "decisao", "grande final"])

            if eh_final:
                vencedores = None
                if gols_t1 > gols_t2:
                    vencedores = time_1
                elif gols_t2 > gols_t1:
                    vencedores = time_2
                else:
                    await message.channel.send(
                        "⚠️ **EMPATE NA GRANDE FINAL!**\n"
                        "👉 **O saldo e o placar empataram. Façam a partida de desempate (confronto direto) para definir o campeão!**"
                    )
                    return

                if vencedores:
                    for jogador in vencedores:
                        adicionar_ponto_secretamente(jogador.id)

                    frase_sorteada = random.choice(FRASES_CAMPEAO)
                    mencoes_campeoes = " ".join([j.mention for j in vencedores])

                    embed_vitoria = discord.Embed(
                        title="🏆 TEMOS OS CAMPEÕES DO DIÁRIO! 🏆",
                        description=f"🎉 **Vencedores:** {mencoes_campeoes}\n\n{frase_sorteada}",
                        color=discord.Color.gold()
                    )

                    if isinstance(message.channel, discord.Thread):
                        canal_principal = message.channel.parent
                        try:
                            await message.channel.edit(archived=True, locked=True)
                        except Exception as e:
                            print(f"Erro ao fechar tópico da final: {e}")

                        if canal_principal:
                            await canal_principal.send(embed=embed_vitoria)
                    else:
                        await message.channel.send(embed=embed_vitoria)

                    if cid in mata_mata_topicos:
                        del mata_mata_topicos[cid]
              # ---------------------------------------------------------
# 8. COMANDOS SLASH (/iniciar_diario, /rank, /resetar_rank E /config_loja)
# ---------------------------------------------------------
class FormatoDiarioSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        placeholder="Selecione o formato do Diário...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="1v1", description="Partidas individuais", emoji="👤", value="1v1"),
            discord.SelectOption(label="2v2", description="Partidas em duplas", emoji="👥", value="2v2"),
            discord.SelectOption(label="3v3", description="Partidas em trios", emoji="⚔️", value="3v3"),
            discord.SelectOption(label="4v4", description="Partidas em squads", emoji="🛡️", value="4v4"),
        ]
    )
    async def select_formato(self, interaction: discord.Interaction, select: discord.ui.Select):
        formato = select.values[0]
        await interaction.response.send_modal(ModalOpcoesDiario(formato=formato))

class ModalOpcoesDiario(discord.ui.Modal, title="Configurações do Diário"):
    imagem_url = discord.ui.TextInput(
        label="URL da Imagem Banner (Opcional)",
        placeholder="Cole para salvar para sempre em todos os próximos diários...",
        required=False,
        style=discord.TextStyle.short
    )
    botao1_label = discord.ui.TextInput(label="Texto do Botão (Opcional)", placeholder="Ex: Regras", required=False)
    botao1_url = discord.ui.TextInput(label="Link do Botão (Opcional)", placeholder="https://...", required=False)

    def __init__(self, formato: str):
        super().__init__()
        self.formato = formato

    async def on_submit(self, interaction: discord.Interaction):
        url_informada = self.imagem_url.value.strip()
        if url_informada:
            salvar_imagem_padrao(url_informada)
            imagem_final = url_informada
        else:
            imagem_final = obter_imagem_padrao()

        embed_anuncio = discord.Embed(
            title=f"⚽ DIÁRIO INICIADO — {self.formato.upper()} 🏆",
            description=(
                f"🔥 **O Diário no formato `{self.formato}` está oficialmente aberto!**\n\n"
                f"📌 **Instruções:**\n"
                f"• Realizem as partidas no chat/tópico.\n"
                f"• Os placares e vitórias serão registrados automaticamente pelo bot.\n"
                f"• Boa sorte a todos os participantes!"
            ),
            color=discord.Color.green()
        )
        embed_anuncio.set_footer(text=f"Organizado por {interaction.user.display_name} • Resenha Hub")

        if imagem_final:
            embed_anuncio.set_image(url=imagem_final)

        view_botoes = discord.ui.View(timeout=None)
        
        b1_lbl = self.botao1_label.value.strip()
        b1_url = self.botao1_url.value.strip()
        if b1_lbl and b1_url.startswith("http"):
            view_botoes.add_item(discord.ui.Button(label=b1_lbl, url=b1_url, style=discord.ButtonStyle.link))

        if isinstance(interaction.channel, discord.TextChannel):
            topico = await interaction.channel.create_thread(
                name=f"🏆-diario-{self.formato}-{random.randint(100, 999)}",
                auto_archive_duration=1440
            )
            
            if len(view_botoes.children) > 0:
                await topico.send(content="@everyone", embed=embed_anuncio, view=view_botoes)
            else:
                await topico.send(content="@everyone", embed=embed_anuncio)

            await interaction.response.send_message(f"✅ Diário `{self.formato}` aberto em {topico.mention}!", ephemeral=True)
        else:
            if len(view_botoes.children) > 0:
                await interaction.response.send_message(embed=embed_anuncio, view=view_botoes)
            else:
                await interaction.response.send_message(embed=embed_anuncio)

@bot.tree.command(name="iniciar_diario", description="Inicia um novo torneio do Diário.")
@commands.has_permissions(administrator=True)
async def iniciar_diario(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚽ Iniciar Diário",
        description="Selecione abaixo o formato do campeonato. (Opcional: coloque uma imagem para salvar como padrão!)",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=FormatoDiarioSelectView(), ephemeral=True)

@bot.tree.command(name="rank", description="Exibe o ranking do diário (Nick — Pontos).")
async def rank(interaction: discord.Interaction):
    ranking_data = obter_ranking()

    if not ranking_data:
        await interaction.response.send_message("🏆 O ranking ainda está vazio!", ephemeral=True)
        return

    embed = discord.Embed(title="🏆 RANKING DE CAMPEÕES 🏆", color=discord.Color.gold())
    linhas = []
    medals = ["🥇", "🥈", "🥉"]

    for idx, (user_id, pontos) in enumerate(ranking_data, start=1):
        icon = medals[idx-1] if idx <= 3 else f"`#{idx}`"
        linhas.append(f"{icon} <@{user_id}> — **{pontos}**")

    embed.description = "\n".join(linhas)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="resetar_rank", description="Zera o ranking do campeonato (Apenas Admins).")
@commands.has_permissions(administrator=True)
async def resetar_rank(interaction: discord.Interaction):
    resetar_ranking_db()
    embed = discord.Embed(title="🔄 RANKING ZERADO!", description="O ranking do Diário foi resetado com sucesso.", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="config_loja", description="Abre o painel de configuração da loja.")
@commands.has_permissions(administrator=True)
async def config_loja(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛒 Painel de Configuração da Loja",
        description="Selecione abaixo a opção desejada para gerenciar a loja.",
        color=discord.Color.from_rgb(47, 49, 54)
    )
    await interaction.response.send_message(embed=embed, view=PainelConfigLojaView(), ephemeral=True)

# ---------------------------------------------------------
# 9. INICIALIZAÇÃO
# ---------------------------------------------------------
@bot.event
async def on_ready():
    init_db()
    init_loja_db()
    keep_alive()
    try:
        synced = await bot.tree.sync()
        print(f"Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")
    print(f'🤖 Bot ligado e 100% atualizado como: {bot.user.name}')

TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
                                
