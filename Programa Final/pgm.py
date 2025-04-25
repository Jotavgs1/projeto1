import pandas as pd
import os
import json
from tkinter import Tk, Label, Button, Checkbutton, IntVar, Radiobutton, StringVar, Text, Scrollbar, RIGHT, Y, END, filedialog, messagebox

# Caminho para arquivo de configuração
CONFIG_PATH = "config.json"
comparativo_atual = None  # Usado para exportações posteriores

# Salva os caminhos selecionados no arquivo config.json
def salvar_config(estoque_2, estoque_150):
    with open(CONFIG_PATH, "w") as f:
        json.dump({"estoque_2": estoque_2, "estoque_150": estoque_150}, f)

# Carrega os caminhos salvos ou retorna None
def carregar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {"estoque_2": None, "estoque_150": None}

# Permite selecionar arquivos manualmente e salva
def selecionar_arquivos():
    estoque_2 = filedialog.askopenfilename(title="Selecione o arquivo da empresa 2", filetypes=[["Arquivos Excel", "*.xlsx"]])
    estoque_150 = filedialog.askopenfilename(title="Selecione o arquivo da empresa 150", filetypes=[["Arquivos Excel", "*.xlsx"]])
    if estoque_2 and estoque_150:
        salvar_config(estoque_2, estoque_150)
        messagebox.showinfo("Arquivos Salvos", "Arquivos selecionados e salvos com sucesso.")

# Função principal de comparação
def comparar_estoques(base_path, comparada_path, filtrar_zerado, filtrar_positivo_base, text_area, contador_label, exportar_csv_btn, exportar_excel_btn):
    global comparativo_atual

    df_base = pd.read_excel(base_path)
    df_comparada = pd.read_excel(comparada_path)

    id_col_base = df_base.columns[0]
    id_col_comp = df_comparada.columns[0]

    def colunas_saldo(df):
        return [col for col in df.columns if not any(x in col.lower() for x in ['id', 'cor', 'descri', 'nome', 'sku', 'p', 'm', 'g', 'gg', 'eg', 'ex', 'tamanho']) and pd.api.types.is_numeric_dtype(df[col])]

    colunas_saldo_base = colunas_saldo(df_base)
    colunas_saldo_comp = colunas_saldo(df_comparada)

    if not colunas_saldo_base or not colunas_saldo_comp:
        messagebox.showerror("Erro", "Não foram encontradas colunas de saldo válidas nas planilhas.")
        return

    df_base['Saldo_Base'] = df_base[colunas_saldo_base].sum(axis=1)
    df_comparada['Saldo_Comparada'] = df_comparada[colunas_saldo_comp].sum(axis=1)

    df_base = df_base[[id_col_base, 'Saldo_Base']].groupby(id_col_base, as_index=False).sum()
    df_comparada = df_comparada[[id_col_comp, 'Saldo_Comparada']].groupby(id_col_comp, as_index=False).sum()

    df_base.columns = ['ID_Produto', 'Saldo_Base']
    df_comparada.columns = ['ID_Produto', 'Saldo_Comparada']

    comparativo = pd.merge(df_base, df_comparada, on='ID_Produto', how='outer').fillna(0)
    comparativo['Diferença'] = comparativo['Saldo_Base'] - comparativo['Saldo_Comparada']

    if filtrar_zerado:
        comparativo = comparativo[comparativo['Saldo_Comparada'] == 0]

    if filtrar_positivo_base:
        comparativo = comparativo[comparativo['Saldo_Base'] > 0]

    comparativo_atual = comparativo

    text_area.delete(1.0, END)
    text_area.insert(END, comparativo.to_string(index=False))
    contador_label.config(text=f"Total de produtos: {len(comparativo)}")

    exportar_csv_btn.config(state="normal")
    exportar_excel_btn.config(state="normal")

# Interface gráfica
def iniciar_interface():
    global comparativo_atual

    config = carregar_config()
    estoque_2 = config.get("estoque_2")
    estoque_150 = config.get("estoque_150")

    root = Tk()
    root.title("Comparativo de Estoque")
    root.geometry("900x600")

    def selecionar_arquivos_na_interface():
        selecionar_arquivos()
        novo_config = carregar_config()
        nonlocal estoque_2, estoque_150
        estoque_2 = novo_config.get("estoque_2")
        estoque_150 = novo_config.get("estoque_150")

    opcao_base = StringVar(value="150")
    opcao_comparada = StringVar(value="2")
    filtro_zerado = IntVar()
    filtro_positivo_base = IntVar()

    Label(root, text="Selecione a EMPRESA BASE:").pack(pady=5)
    Radiobutton(root, text="Empresa 150", variable=opcao_base, value="150").pack()
    Radiobutton(root, text="Empresa 2", variable=opcao_base, value="2").pack()

    Label(root, text="Selecione a EMPRESA COMPARADA:").pack(pady=5)
    Radiobutton(root, text="Empresa 150", variable=opcao_comparada, value="150").pack()
    Radiobutton(root, text="Empresa 2", variable=opcao_comparada, value="2").pack()

    Checkbutton(root, text="Mostrar apenas saldo zerado na empresa comparada", variable=filtro_zerado).pack(pady=5)
    Checkbutton(root, text="Mostrar apenas saldo positivo na empresa base", variable=filtro_positivo_base).pack(pady=5)

    Button(root, text="Executar Comparação", command=lambda: executar()).pack(pady=10)
    Button(root, text="Selecionar Arquivos", command=selecionar_arquivos_na_interface).pack(pady=5)

    contador_label = Label(root, text="Total de produtos: 0")
    contador_label.pack(pady=5)

    scrollbar = Scrollbar(root)
    scrollbar.pack(side=RIGHT, fill=Y)

    text_area = Text(root, height=20, wrap='none', yscrollcommand=scrollbar.set)
    text_area.pack(fill="both", expand=True)
    scrollbar.config(command=text_area.yview)

    exportar_csv_btn = Button(root, text="Exportar para CSV", state="disabled", command=lambda: salvar("csv"))
    exportar_excel_btn = Button(root, text="Exportar para Excel", state="disabled", command=lambda: salvar("xlsx"))
    exportar_csv_btn.pack(pady=2)
    exportar_excel_btn.pack(pady=2)

    def salvar(tipo):
        if comparativo_atual is None:
            messagebox.showerror("Erro", "Nenhum comparativo gerado ainda.")
            return
        ext = "csv" if tipo == "csv" else "xlsx"
        file_path = filedialog.asksaveasfilename(defaultextension=f".{ext}", filetypes=[["Arquivos", f"*.{ext}"]])
        if file_path:
            try:
                if tipo == "csv":
                    comparativo_atual.to_csv(file_path, index=False)
                else:
                    comparativo_atual.to_excel(file_path, index=False)
                messagebox.showinfo("Sucesso", f"Arquivo salvo com sucesso em:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar o arquivo:\n{e}")

    def executar():
        if not estoque_2 or not estoque_150:
            messagebox.showerror("Erro", "Arquivos ainda não foram selecionados. Clique em 'Selecionar Arquivos'.")
            return

        base = estoque_2 if opcao_base.get() == "2" else estoque_150
        comp = estoque_2 if opcao_comparada.get() == "2" else estoque_150

        if base == comp:
            messagebox.showwarning("Aviso", "Base e comparada não podem ser a mesma empresa.")
            return

        comparar_estoques(base, comp, filtro_zerado.get(), filtro_positivo_base.get(), text_area, contador_label, exportar_csv_btn, exportar_excel_btn)

    root.mainloop()

if __name__ == "__main__":
    iniciar_interface()
