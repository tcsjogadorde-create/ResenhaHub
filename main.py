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
# 2. BANCO DE DADOS (SQLite - Diários, Loja e Configurações)
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS confrontos_ativos (
            thread_id INTEGER PRIMARY KEY,
            confronto_num INTEGER,
            time1_id TEXT,
            time2_id TEXT,
            gols_t1 INTEGER DEFAULT 0,
            gols_t2 INTEGER DEFAULT 0,
            vitorias_t1 INTEGER DEFAULT 0,
            vitorias_t2 INTEGER DEFAULT 0,
            partidas_jogadas INTEGER DEFAULT 0
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
        CREATE TABLE IF NOT EXISTS config_loja_canais (
            id INTEGER PRIMARY KEY DEFAULT 1,
            categoria_carrinhos INTEGER,
            log_compras INTEGER,
            log_avaliacoes INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config_pagamento_pix (
            id INTEGER PRIMARY KEY DEFAULT 1,
            tipo_chave TEXT,
            chave_pix TEXT
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
BOTS_JOGOS = ["Dream Team", "Futecord", "DreamDaily"]
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
            discord.SelectOption(label="Configurar Pagamentos", description="Defina a chave PIX de recebimento", emoji="💳", value="config_pagamentos"),
            discord.SelectOption(label="Gerenciar Cupons", description="Crie cupons de desconto para seus clientes", emoji="✉️", value="gerenciar_cupons"),
            discord.SelectOption(label="Gerenciar Produtos", description="Crie, edite e remova produtos da loja", emoji="📁", value="gerenciar_produtos"),
            discord.SelectOption(label="Relatório de Vendas", description="Veja o desempenho de vendas da loja", emoji="🔲", value="relatorio_vendas"),
            discord.SelectOption(label="Enviar Produto", description="Envie o painel de um produto em um canal", emoji="🚀", value="enviar_produto"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        opcao = select.values[0]

        if opcao == "config_loja":
            conn = sqlite3.connect('loja.db')
            cursor = conn.cursor()
            cursor.execute('SELECT categoria_carrinhos, log_compras, log_avaliacoes FROM config_loja_canais WHERE id = 1')
            row = cursor.fetchone()
            conn.close()

            cat_id, l_comp, l_av = row if row else (None, None, None)
            c_txt = f"<#:{cat_id}>" if cat_id else "não definido"
            lc_txt = f"<#{l_comp}>" if l_comp else "não definido"
            la_txt = f"<#{l_av}>" if l_av else "não definido"

            embed = discord.Embed(
                title="🔧 | Canais da Loja",
                description=(
                    f"Defina onde os carrinhos são criados e para onde vão os registros da loja.\n\n"
                    f"❗ **Categoria dos Carrinhos:** {c_txt}\n"
                    f"❗ **Logs de Compras Concluídas:** {lc_txt}\n"
                    f"❗ **Logs de Avaliações:** {la_txt}"
                ),
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, view=CanaisLojaConfigView(), ephemeral=True)

        elif opcao == "config_pagamentos":
            conn = sqlite3.connect('loja.db')
            cursor = conn.cursor()
            cursor.execute('SELECT tipo_chave, chave_pix FROM config_pagamento_pix WHERE id = 1')
            row = cursor.fetchone()
            conn.close()

            t_chave, c_pix = row if row else ("Não configurado", "Nenhuma chave salva")
            embed = discord.Embed(
                title="💳 | Configurar Pagamento (PIX)",
                description=f"Configure a chave PIX que aparecerá para os clientes realizarem o pagamento.\n\n📌 **Tipo:** {t_chave}\n🔑 **Chave:** `{c_pix}`",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, view=ConfigPixView(), ephemeral=True)

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

class CanaisLojaConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Definir Categoria Carrinhos", style=discord.ButtonStyle.primary, emoji="📁")
    async def def_cat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(content="Selecione a categoria para os carrinhos abaixo:", view=ViewSelecionarCategoriaCarrinho(), ephemeral=True)

    @discord.ui.button(label="Definir Logs de Compras", style=discord.ButtonStyle.primary, emoji="📋")
    async def def_log_comp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(content="Selecione o canal de logs de compras:", view=ViewSelecionarCanalLogComp(), ephemeral=True)

    @discord.ui.button(label="Definir Logs de Avaliações", style=discord.ButtonStyle.primary, emoji="⭐")
    async def def_log_av(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(content="Selecione o canal de logs de avaliações:", view=ViewSelecionarCanalLogAv(), ephemeral=True)

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛒 Painel de Configuração da Loja", color=discord.Color.from_rgb(47, 49, 54))
        await interaction.response.send_message(embed=embed, view=PainelConfigLojaView(), ephemeral=True)

class ViewSelecionarCategoriaCarrinho(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(discord.ui.ChannelSelect(placeholder="Selecione a categoria...", channel_types=[discord.ChannelType.category]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cat_id = interaction.data["values"][0]
        conn = sqlite3.connect('loja.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO config_loja_canais (id, categoria_carrinhos) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET categoria_carrinhos = ?
        ''', (int(cat_id), int(cat_id)))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"✅ Categoria de carrinhos definida com sucesso!", ephemeral=True)
        return True

class ViewSelecionarCanalLogComp(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(discord.ui.ChannelSelect(placeholder="Selecione o canal de logs...", channel_types=[discord.ChannelType.text]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        chan_id = interaction.data["values"][0]
        conn = sqlite3.connect('loja.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO config_loja_canais (id, log_compras) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET log_compras = ?
        ''', (int(chan_id), int(chan_id)))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"✅ Canal de logs de compras definido com sucesso!", ephemeral=True)
        return True

class ViewSelecionarCanalLogAv(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(discord.ui.ChannelSelect(placeholder="Selecione o canal de avaliações...", channel_types=[discord.ChannelType.text]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        chan_id = interaction.data["values"][0]
        conn = sqlite3.connect('loja.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO config_loja_canais (id, log_avaliacoes) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET log_avaliacoes = ?
        ''', (int(chan_id), int(chan_id)))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"✅ Canal de logs de avaliações definido com sucesso!", ephemeral=True)
        return True

class ConfigPixView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Definir / Alterar Chave PIX", style=discord.ButtonStyle.success, emoji="🔑")
    async def definir_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalConfigPix())

    @discord.ui.button(label="Voltar", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🛒 Painel de Configuração da Loja", color=discord.Color.from_rgb(47, 49, 54))
        await interaction.response.send_message(embed=embed, view=PainelConfigLojaView(), ephemeral=True)

class ModalConfigPix(discord.ui.Modal, title="Configurar Chave PIX"):
    tipo_chave = discord.ui.TextInput(label="Tipo de Chave (CPF, Telefone, Email, Aleatória)", placeholder="Ex: CPF ou Telefone", required=True)
    chave = discord.ui.TextInput(label="Chave PIX", placeholder="Digite a sua chave...", required=True, style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        t = self.tipo_chave.value.strip()
        c = self.chave.value.strip()
        conn = sqlite3.connect('loja.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO config_pagamento_pix (id, tipo_chave, chave_pix) VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET tipo_chave = ?, chave_pix = ?
        ''', (t, c, t, c))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"✅ Chave PIX salva com sucesso!\n**Tipo:** {t}\n**Chave:** `{c}`", ephemeral=True)

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

    @discord.ui.button(label="Gerenciar Existente", style=discord.ButtonStyle.primary, emoji="✏️")
    async def ger_existente(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect('loja.db')
        cursor = conn.cursor()
        cursor.execute('SELECT nome FROM produtos')
        prods = cursor.fetchall()
        conn.close()

        if not prods:
            await interaction.response.send_message("❌ Nenhum produto cadastrado para editar!", ephemeral=True)
            return

        options = [discord.SelectOption(label=p[0], value=p[0]) for p in prods]
        select = discord.ui.Select(placeholder="Selecione o produto para editar...", options=options)

        async def callback_sel(i: discord.Interaction):
            prod_escolhido = i.data["values"][0]
            embed, view = get_painel_edicao_produto(prod_escolhido)
            await i.response.send_message(embed=embed, view=view, ephemeral=True)

        select.callback = callback_sel
        v = discord.ui.View()
        v.add_item(select)
        await interaction.response.send_message(embed=discord.Embed(title="Selecione o produto:"), view=v, ephemeral=True)

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
            discord.SelectOption(label="Catálogo (Múltiplas Opções)", description="Menu dropdown personalizado", emoji="📂", value="catalogo")
        ]
    )
    async def select_tipo_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_modal(ModalCriarProdutoNome(tipo_produto=select.values[0]))

class ModalCriarProdutoNome(discord.ui.Modal, title="Criar Produto"):
    nome_produto = discord.ui.TextInput(label="Nome do produto", placeholder="Ex: CONTA VIP", required=True)

    def __init__(self, tipo_produto: str):
        super().__init__()
        self.tipo_produto = tipo_produto

    async def on_submit(self, interaction: discord.Interaction):
        nome = self.nome_produto.value.strip()
        conn = sqlite3.connect('loja.db')
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO produtos (nome, titulo, tipo, estoque, preco) VALUES (?, ?, ?, 0, 0.0)', (nome, nome, self.tipo_produto))
            conn.commit()

            if self.tipo_produto == "catalogo":
                cursor.execute('SELECT id FROM produtos WHERE nome = ?', (nome,))
                prod_id = cursor.fetchone()[0]
                cursor.execute('INSERT INTO itens_catalogo (produto_id, nome, preco, estoque) VALUES (?, ?, ?, ?)',
                               (prod_id, "Opção Exemplo 1", 10.00, 10))
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
            discord.SelectOption(label="Configurar Estoque", description="Definir estoque disponível", emoji="📁", value="estoque"),
            discord.SelectOption(label="Configurar Imagem", description="Imagem exibida no produto", emoji="⬆️", value="imagem"),
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

            conn.commit()
            conn.close()

            embed, view = get_painel_edicao_produto(self.nome_produto)
            await interaction.response.send_message(content="✅ **Produto atualizado com sucesso!**", embed=embed, view=view, ephemeral=True)
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

    @discord.ui.button(label="Escolher Produto", style=discord.ButtonStyle.secondary, emoji="🛍️")
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
            discord.SelectOption(label=f"{nome}", description=f"R$ {preco:.2f} • Estoque: {estoque}", value=nome)
            for nome, preco, estoque in prods
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
                    opts.append(discord.SelectOption(label="Padrão", description="R$ 0,00", value="buy_ex"))

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

            if isinstance(message.channel, discord.Thread):
                conn = sqlite3.connect('diarios.db')
                cursor = conn.cursor()
                cursor.execute('SELECT time1_id, time2_id, gols_t1, gols_t2, vitorias_t1, vitorias_t2, partidas_jogadas FROM confrontos_ativos WHERE thread_id = ?', (message.channel.id,))
                row = cursor.fetchone()
                
                if row:
                    t1_db, t2_db, gt1, gt2, vt1, vt2, pj = row
                    
                    if time_1[0].id == int(t1_db):
                        pt1_gols, pt2_gols = gols_t1, gols_t2
                    else:
                        pt1_gols, pt2_gols = gols_t2, gols_t1

                    novo_gt1 = gt1 + pt1_gols
                    novo_gt2 = gt2 + pt2_gols
                    novo_pj = pj + 1
                    
                    if pt1_gols > pt2_gols:
                        vt1 += 1
                    elif pt2_gols > pt1_gols:
                        vt2 += 1

                    cursor.execute('''
                        UPDATE confrontos_ativos 
                        SET gols_t1 = ?, gols_t2 = ?, vitorias_t1 = ?, vitorias_t2 = ?, partidas_jogadas = ?
                        WHERE thread_id = ?
                    ''', (novo_gt1, novo_gt2, vt1, vt2, novo_pj, message.channel.id))
                    conn.commit()

                    u1 = message.guild.get_member(int(t1_db))
                    u2 = message.guild.get_member(int(t2_db))
                    
                    await message.channel.send(
                        f"✅ **Placar salvo:**\n"
                        f"{u1.mention} {pt1_gols} x {pt2_gols} {u2.mention}\n\n"
                        f"Ainda faltam partidas desse confronto. Aguarde o bot processar."
                    )

                    if novo_pj >= 2:
                        if vt1 > vt2:
                            vencedor = u1
                        elif vt2 > vt1:
                            vencedor = u2
                        elif novo_gt1 > novo_gt2:
                            vencedor = u1
                        elif novo_gt2 > novo_gt1:
                            vencedor = u2
                        else:
                            vencedor = None

                        if vencedor:
                            for jogador in [u1, u2]:
                                if jogador and jogador.id == vencedor.id:
                                    adicionar_ponto_secretamente(jogador.id)

                            frase_sorteada = random.choice(FRASES_CAMPEAO)
                            embed_vitoria = discord.Embed(
                                title="🏆 VENCEDOR DO CONFRONTO DEFINIDO! 🏆",
                                description=f"🎉 **Vencedor:** {vencedor.mention}\n\n{frase_sorteada}",
                                color=discord.Color.gold()
                            )
                            await message.channel.parent.send(embed=embed_vitoria)
                            cursor.execute('DELETE FROM confrontos_ativos WHERE thread_id = ?', (message.channel.id,))
                            conn.commit()
                            await message.channel.edit(archived=True, locked=True)
                conn.close()
      # ---------------------------------------------------------
# 8. COMANDOS SLASH E VIEWS DE INSCRIÇÃO DO DIÁRIO
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
    titulo_diario = discord.ui.TextInput(
        label="Título / Nome do Torneio",
        placeholder="Ex: Diário Resenha Hub 🏆",
        required=True,
        style=discord.TextStyle.short
    )
    descricao_diario = discord.ui.TextInput(
        label="Descrição do Torneio",
        placeholder="Ex: Participe e garanta sua vaga!",
        required=True,
        style=discord.TextStyle.paragraph
    )
    imagem_url = discord.ui.TextInput(
        label="URL da Imagem Banner (Opcional)",
        placeholder="Cole a URL da imagem...",
        required=False,
        style=discord.TextStyle.short
    )

    def __init__(self, formato: str):
        super().__init__()
        self.formato = formato

    async def on_submit(self, interaction: discord.Interaction):
        t_txt = self.titulo_diario.value.strip()
        d_txt = self.descricao_diario.value.strip()
        url_informada = self.imagem_url.value.strip()

        if url_informada:
            salvar_imagem_padrao(url_informada)
            imagem_final = url_informada
        else:
            imagem_final = obter_imagem_padrao()

        embed_anuncio = discord.Embed(
            title=f"{t_txt}",
            description=f"{d_txt}\n\nClique abaixo para participar! 🔴",
            color=discord.Color.red()
        )
        if imagem_final:
            embed_anuncio.set_image(url=imagem_final)

        view = InskricaoDiarioView(formato=self.formato, titulo=t_txt, desc=d_txt)
        await interaction.response.send_message(embed=embed_anuncio, view=view)

class InskricaoDiarioView(discord.ui.View):
    def __init__(self, formato: str, titulo: str, desc: str):
        super().__init__(timeout=None)
        self.formato = formato
        self.titulo = titulo
        self.desc = desc
        self.participantes = set()

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green, emoji="✅")
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.participantes:
            await interaction.response.send_message("⚠️ Você já está inscrito neste diário!", ephemeral=True)
        else:
            self.participantes.add(interaction.user)
            await interaction.response.send_message("✅ Inscrição realizada com sucesso!", ephemeral=True)
            await self.atualizar_mensagem(interaction)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red, emoji="🚪")
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.participantes:
            self.participantes.remove(interaction.user)
            await interaction.response.send_message("🚪 Você saiu da lista de participantes.", ephemeral=True)
            await self.atualizar_mensagem(interaction)
        else:
            await interaction.response.send_message("⚠️ Você não está inscrito!", ephemeral=True)

    @discord.ui.button(label="Iniciar (0)", style=discord.ButtonStyle.blurple, emoji="🏆")
    async def iniciar_torneio(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem iniciar o torneio!", ephemeral=True)
            return

        if len(self.participantes) < 2:
            await interaction.response.send_message("❌ É preciso ter pelo menos 2 participantes inscritos para iniciar!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        button.label = f"Finalizado! ({len(self.participantes)})"
        button.style = discord.ButtonStyle.grey
        await interaction.message.edit(view=self)

        membros = list(self.participantes)
        random.shuffle(membros)
        canal_chat = interaction.channel

        conn = sqlite3.connect('diarios.db')
        cursor = conn.cursor()

        confronto_num = 1
        for i in range(0, len(membros) - 1, 2):
            t1 = membros[i]
            t2 = membros[i+1]

            nome_thread = f"confronto-{confronto_num}"
            topico = await canal_chat.create_thread(name=nome_thread, auto_archive_duration=1440)

            cursor.execute('''
                INSERT INTO confrontos_ativos (thread_id, confronto_num, time1_id, time2_id)
                VALUES (?, ?, ?, ?)
            ''', (topico.id, confronto_num, str(t1.id), str(t2.id)))
            conn.commit()

            msg_confronto = f"Confronto #{confronto_num:02d} {t1.mention} vs {t2.mention}"
            await canal_chat.send(msg_confronto)

            msg_topico = (
                f"🔍 **Ida e volta**\n"
                f"1. {t1.mention} x {t2.mention}\n"
                f"2. {t2.mention} x {t1.mention}\n\n"
                f"As partidas podem acontecer em qualquer ordem; cada vaga é identificada pelo mandante. "
                f"O critério é mais vitórias e depois o agregado de gols. Persistindo empate total, abre-se outro par completo de ida e volta."
            )
            await topico.send(msg_topico)

            confronto_num += 1

        conn.close()
        await interaction.response.send_message(f"🚀 Torneio iniciado! {len(membros)} participantes divididos em confrontos.", ephemeral=True)

    async def atualizar_mensagem(self, interaction: discord.Interaction):
        for child in self.children:
            if child.label.startswith("Iniciar"):
                child.label = f"Iniciar ({len(self.participantes)})"
        
        embed = interaction.message.embeds[0]
        embed.description = f"{self.desc}\n\nClique abaixo para participar! 🔴\n\n👥 **Inscritos ({len(self.participantes)}):** " + ", ".join([u.mention for u in self.participantes])
        await interaction.message.edit(embed=embed, view=self)

@bot.tree.command(name="iniciar_diario", description="Inicia um novo torneio do Diário.")
@commands.has_permissions(administrator=True)
async def iniciar_diario(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚽ Iniciar Diário",
        description="Selecione abaixo o formato do campeonato e configure o título e a descrição.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=FormatoDiarioSelectView(), ephemeral=True)

@bot.tree.command(name="parciais", description="Mostra o resumo automático do confronto atual.")
@commands.has_permissions(administrator=True)
async def parciais(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message("❌ Este comando deve ser usado dentro de um tópico de **confronto**!", ephemeral=True)
        return

    conn = sqlite3.connect('diarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT confronto_num, time1_id, time2_id, gols_t1, gols_t2, vitorias_t1, vitorias_t2, partidas_jogadas FROM confrontos_ativos WHERE thread_id = ?', (interaction.channel.id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        await interaction.response.send_message("❌ Nenhum confronto ativo encontrado neste tópico.", ephemeral=True)
        return

    c_num, t1_id, t2_id, g_t1, g_t2, v_t1, v_t2, p_jogadas = row
    u1 = interaction.guild.get_member(int(t1_id))
    u2 = interaction.guild.get_member(int(t2_id))

    nome_t1 = u1.mention if u1 else "Time 1"
    nome_t2 = u2.mention if u2 else "Time 2"

    if v_t1 > v_t2:
        sugestao = nome_t1
    elif v_t2 > v_t1:
        sugestao = nome_t2
    elif g_t1 > g_t2:
        sugestao = nome_t1
    elif g_t2 > g_t1:
        sugestao = nome_t2
    else:
        sugestao = "Empate Técnico"

    embed = discord.Embed(
        title=f"📊 **Parciais Automáticas — Confronto #{c_num:02d}**",
        description=(
            f"🎮 **Progresso:** {p_jogadas}/2 jogos concluídos\n\n"
            f"⚽ **Vitórias:** Time 1 ({v_t1}) x ({v_t2}) Time 2\n"
            f"🎯 **Gols:** Time 1 ({g_t1}) x ({g_t2}) Time 2\n\n"
            f"🏆 **Vencedor sugerido:** {sugestao}"
        ),
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vencedor", description="Define manualmente o vencedor do confronto atual.")
@commands.has_permissions(administrator=True)
async def vencedor(interaction: discord.Interaction, escolha: str):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message("❌ Este comando deve ser usado dentro de um tópico de **confronto**!", ephemeral=True)
        return

    if escolha.lower() not in ["1", "2", "time 1", "time 2"]:
        await interaction.response.send_message("❌ Escolha inválida! Digite '1' para Time 1 ou '2' para Time 2.", ephemeral=True)
        return

    conn = sqlite3.connect('diarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT confronto_num, time1_id, time2_id FROM confrontos_ativos WHERE thread_id = ?', (interaction.channel.id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        await interaction.response.send_message("❌ Nenhum confronto ativo neste tópico.", ephemeral=True)
        return

    c_num, t1_id, t2_id = row
    u1 = interaction.guild.get_member(int(t1_id))
    u2 = interaction.guild.get_member(int(t2_id))

    vencedor_obj = u1 if escolha.lower() in ["1", "time 1"] else u2

    if vencedor_obj:
        adicionar_ponto_secretamente(vencedor_obj.id)

    frase_sorteada = random.choice(FRASES_CAMPEAO)
    embed_vitoria = discord.Embed(
        title="🏆 VENCEDOR DO CONFRONTO DEFINIDO (ADMIN) 🏆",
        description=f"🎉 **Vencedor:** {vencedor_obj.mention if vencedor_obj else 'Desconhecido'}\n\n{frase_sorteada}",
        color=discord.Color.gold()
    )
    await interaction.channel.parent.send(embed=embed_vitoria)
    
    cursor.execute('DELETE FROM confrontos_ativos WHERE thread_id = ?', (interaction.channel.id,))
    conn.commit()
    conn.close()

    await interaction.response.send_message(f"✅ Vencedor definido com sucesso!", ephemeral=True)
    await interaction.channel.edit(archived=True, locked=True)

@bot.tree.command(name="rank", description="Exibe o ranking do diário.")
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
  
