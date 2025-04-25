import pandas as pd
import os

# Caminhos
entrada = r"C:\Users\joao.silva\Desktop\Projetos\Extrator Atacado\entrada.xlsx"
estoque_path = r"C:\Users\joao.silva\Desktop\Projetos\Extrator Atacado\estoque2.xlsx"
saida = r"C:\Users\joao.silva\Desktop\Projetos\Extrator Atacado\saida2.xlsx"

# Lê as planilhas
df = pd.read_excel(entrada)
estoque_df = pd.read_excel(estoque_path)

# Renomeia colunas de forma mais clara
df.columns = ["_IDSKU", "_NomeSKU", "_IDProduto", "_DataLancamentoProduto", "_TituloSite"]
estoque_df.columns = ["_IDSKU", "Estoque"]

# Extrai tamanho e cor
df["Tamanho"] = df["_NomeSKU"].str.extract(r"-(\w+)$")
df["Cor"] = df["_NomeSKU"].str.extract(r"^(.*?)-").fillna("")
df["Cor"] = df["Cor"].str.strip("-")

# Junta com o estoque
df = df.merge(estoque_df, on="_IDSKU", how="left")
df["Estoque"] = df["Estoque"].fillna(0)

# Substitui "Tem"/"Não tem" pela quantidade real ou 0
df["Quantidade"] = df["Estoque"]

# Tabela dinâmica com quantidade real
tabela = df.pivot_table(
    index=["_IDProduto", "Cor"],
    columns="Tamanho",
    values="Quantidade",
    aggfunc="first",
    fill_value=0
).reset_index()

# Reordena colunas
ordem_tamanhos = ["P", "M", "G", "GG", "XG", "G1", "G2", "G3", "G4", "2", "4", "6", "8", "10", "12"]
colunas_finais = ["_IDProduto", "Cor"] + [t for t in ordem_tamanhos if t in tabela.columns]
tabela = tabela[colunas_finais]

# Salva o resultado
tabela.to_excel(saida, index=False)
print("Finalizado com sucesso. Planilha salva em:", saida)
