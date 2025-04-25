import pandas as pd
import os
from tkinter import Tk, filedialog, Button, Frame, ttk, Label, Scrollbar, RIGHT, Y, LEFT, BOTH

# Mapeamento das UFs para suas regiões
regioes = {
    'Norte': ['AC', 'AM', 'AP', 'PA', 'RO', 'RR', 'TO'],
    'Nordeste': ['AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE'],
    'Centro-Oeste': ['DF', 'GO', 'MS', 'MT'],
    'Sudeste': ['ES', 'MG', 'RJ', 'SP'],
    'Sul': ['PR', 'RS', 'SC']
}

def selecionar_arquivo():
    caminho = filedialog.askopenfilename(
        title="Selecione a planilha",
        filetypes=[("Arquivos Excel", "*.xlsx *.xls")]
    )
    if caminho:
        processar_planilha(caminho)

def formatar_valor(valor):
    try:
        return f"R$ {valor:,.2f}".replace('.', ',')
    except:
        return valor

def adicionar_regiao(df):
    # Função para atribuir a região com base na UF
    def obter_regiao(uf):
        for regiao, ufs in regioes.items():
            if uf in ufs:
                return regiao
        return "Desconhecida"
    
    # Aplicar a função 'obter_regiao' para adicionar a coluna "Região"
    df['Região'] = df['UF'].apply(obter_regiao)
    return df

def processar_planilha(caminho):
    try:
        df = pd.read_excel(caminho)

        colunas_necessarias = ['Postal Code', 'UF', 'Shipping List Price', 'Order']
        for col in colunas_necessarias:
            if col not in df.columns:
                raise ValueError(f"A coluna '{col}' não foi encontrada na planilha.")

        df = df[colunas_necessarias].copy()
        df = df.dropna(subset=['Postal Code', 'UF', 'Shipping List Price', 'Order'])

        df['Postal Code'] = df['Postal Code'].astype(str).str.extract(r'(\d{5})')
        df['Shipping List Price'] = pd.to_numeric(df['Shipping List Price'], errors='coerce')
        df = df.dropna(subset=['Postal Code', 'Shipping List Price'])

        df['Postal Code'] = df['Postal Code'].astype(int)
        df['Faixa de CEP'] = df['Postal Code'].apply(
            lambda x: f"{(x // 500) * 500:05d}-000 a {(x // 500) * 500 + 499:05d}-000"
        )

        # Cálculo da média considerando apenas valores de frete > 0
        df_frete = df[df['Shipping List Price'] > 0]  # Somente para o cálculo da média de frete

        frete = df_frete.groupby(['UF', 'Faixa de CEP'])['Shipping List Price'].mean().reset_index()
        frete['Shipping List Price'] = frete['Shipping List Price'].round(2)

        pedidos_unicos = df.drop_duplicates(subset='Order')
        total_pedidos_unicos = pedidos_unicos['Order'].nunique()

        pedidos_com_frete = df[df['Shipping List Price'] > 0].drop_duplicates(subset='Order')
        total_pedidos_com_frete = pedidos_com_frete['Order'].nunique()

        total_pedidos = df['Order'].nunique()

        pedidos = pedidos_unicos.groupby(['UF', 'Faixa de CEP'])['Order'].count().reset_index()
        pedidos.rename(columns={'Order': 'Pedidos'}, inplace=True)

        resultado = pd.merge(frete, pedidos, on=['UF', 'Faixa de CEP'])
        resultado['Valor do Frete'] = resultado['Shipping List Price'].apply(formatar_valor)
        resultado = resultado[['UF', 'Faixa de CEP', 'Valor do Frete', 'Pedidos']]

        # Adiciona a coluna "Região"
        resultado = adicionar_regiao(resultado)

        exibir_tabela(resultado, total_pedidos_unicos, total_pedidos, total_pedidos_com_frete)
        global df_resultado
        df_resultado = resultado  # Armazenar o resultado globalmente para exportação posterior

    except Exception as e:
        print(f"Erro ao processar planilha: {e}")

def exibir_tabela(df_resultado, total_pedidos_unicos, total_pedidos, total_pedidos_com_frete):
    for widget in frame_tabela.winfo_children():
        widget.destroy()
    
    label_total_pedidos.config(text=f"Total de pedidos únicos: {total_pedidos_unicos}")
    label_total_pedidos_geral.config(text=f"Total de pedidos: {total_pedidos}")
    label_pedidos_com_frete.config(text=f"Pedidos com frete: {total_pedidos_com_frete}")

    scrollbar = Scrollbar(frame_tabela)
    scrollbar.pack(side=RIGHT, fill=Y)

    tree = ttk.Treeview(frame_tabela, yscrollcommand=scrollbar.set)
    tree.pack(side=LEFT, fill=BOTH, expand=True)
    scrollbar.config(command=tree.yview)

    tree["columns"] = list(df_resultado.columns)
    tree["show"] = "headings"

    # Dicionário para controlar a direção de ordenação (True = Crescente, False = Decrescente)
    column_sort_direction = {col: True for col in df_resultado.columns}

    def sort_column(event, col):
        nonlocal df_resultado
        if column_sort_direction[col]:
            # Ordenar de forma crescente
            df_resultado = df_resultado.sort_values(by=col, ascending=True)
            column_sort_direction[col] = False
        else:
            # Ordenar de forma decrescente
            df_resultado = df_resultado.sort_values(by=col, ascending=False)
            column_sort_direction[col] = True
        exibir_tabela(df_resultado, label_total_pedidos.cget("text").split(":")[1].strip(), label_total_pedidos_geral.cget("text").split(":")[1].strip(), label_pedidos_com_frete.cget("text").split(":")[1].strip())

    # Definir os cabeçalhos e ligar à função de ordenação
    for col in df_resultado.columns:
        tree.heading(col, text=col, command=lambda col=col: sort_column(None, col))
        tree.column(col, anchor="center")

    for _, row in df_resultado.iterrows():
        tree.insert("", "end", values=list(row))

def exportar_planilha():
    if 'df_resultado' in globals():
        # Salvar o arquivo com a versão atual filtrada e ordenada
        saida = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Planilha Excel", "*.xlsx")],
            title="Salvar planilha como",
            initialfile="frete_e_pedidos_por_faixa_cep.xlsx"
        )
        if saida:
            df_resultado.to_excel(saida, index=False)
            print(f"✅ Resultado salvo em: {saida}")
    else:
        print("⚠️ Nenhuma planilha foi processada ainda.")

# Interface principal
root = Tk()
root.title("Frete e Pedidos por Faixa de CEP")
root.geometry("740x640")

btn_selecionar = Button(root, text="Selecionar Planilha", command=selecionar_arquivo)
btn_selecionar.pack(pady=10)

frame_tabela = Frame(root)
frame_tabela.pack(fill=BOTH, expand=True, padx=10, pady=10)

label_info = Label(root, text="Agrupamento por UF e Faixa de CEP | Valor Médio do Frete + Pedidos Únicos")
label_info.pack(pady=5)

label_total_pedidos = Label(root, text="Total de pedidos únicos: 0", font=("Arial", 10, "bold"))
label_total_pedidos.pack(pady=5)

label_total_pedidos_geral = Label(root, text="Total de pedidos: 0", font=("Arial", 10, "bold"))
label_total_pedidos_geral.pack(pady=5)

label_pedidos_com_frete = Label(root, text="Pedidos com frete: 0", font=("Arial", 10, "bold"))
label_pedidos_com_frete.pack(pady=5)

btn_exportar = Button(root, text="Exportar Planilha", command=exportar_planilha)
btn_exportar.pack(pady=10)

root.mainloop()
