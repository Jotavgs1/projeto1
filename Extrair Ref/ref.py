import pandas as pd
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json

CONFIG_PATH = "config.json"
pasta_padrao = ""
df_entrada = None
df_estoque = None

# ---------------- Funções de Config ----------------
def carregar_config():
    global pasta_padrao
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
            pasta_padrao = config.get("pasta_padrao", "")

def salvar_config():
    with open(CONFIG_PATH, 'w') as f:
        json.dump({"pasta_padrao": pasta_padrao}, f)

# ---------------- Funções de Processamento ----------------
def extrair_codigo(texto):
    if pd.isna(texto):
        return None
    padrao = r'[A-Za-z]+\d+'
    resultado = re.findall(padrao, texto)
    return ', '.join(resultado) if resultado else None

def normalizar_colunas(df):
    df.columns = [col.strip().lower() for col in df.columns]
    return df

def carregar_entrada(caminho):
    global df_entrada
    df_entrada = pd.read_excel(caminho)
    df_entrada = normalizar_colunas(df_entrada)
    df_entrada['codigo extraído'] = df_entrada['_titulosite'].apply(extrair_codigo)

def carregar_estoque(caminho):
    global df_estoque
    df_estoque = pd.read_excel(caminho)
    df_estoque = normalizar_colunas(df_estoque)

def carregar_automaticamente():
    if not pasta_padrao:
        messagebox.showinfo("Defina a pasta", "Selecione a pasta onde estão os arquivos.")
        return

    entrada_path = os.path.join(pasta_padrao, "entrada.xlsx")
    estoque_path = os.path.join(pasta_padrao, "estoque150.xlsx")

    if not os.path.exists(entrada_path) or not os.path.exists(estoque_path):
        messagebox.showwarning("Arquivos não encontrados", f"Certifique-se de que 'entrada.xlsx' e 'estoque150.xlsx' estão na pasta:\n{pasta_padrao}")
        return

    try:
        carregar_entrada(entrada_path)
        carregar_estoque(estoque_path)
        salvar_config()
        status_label.config(text="✅ Planilhas carregadas com sucesso!", foreground="green")
    except Exception as e:
        messagebox.showerror("Erro ao carregar arquivos", str(e))

def atualizar_dados():
    if df_entrada is None or df_estoque is None:
        messagebox.showwarning("Dados insuficientes", "As planilhas ainda não foram carregadas.")
        return

    try:
        df_entrada['_idsku (não alterável)'] = df_entrada['_idsku (não alterável)'].astype(str)
        df_estoque['skuid'] = df_estoque['skuid'].astype(str)
        dicionario_estoque = dict(zip(df_estoque['skuid'], df_estoque['estoque']))
        df_entrada['estoque'] = df_entrada['_idsku (não alterável)'].map(dicionario_estoque).fillna(0).astype(int)

        atualizar_lista(df_entrada)
        status_label.config(text="✔️ Dados atualizados com sucesso.", foreground="blue")
    except Exception as e:
        messagebox.showerror("Erro ao atualizar dados", str(e))

def atualizar_lista(df):
    lista.delete(0, tk.END)
    mostrar_zerado = filtro_zerado.get()
    mostrar_positivo = filtro_positivo.get()

    agrupado = df.groupby('codigo extraído', as_index=False).agg({
        'estoque': 'sum',
        '_titulosite': 'first'
    })

    for _, row in agrupado.iterrows():
        codigo = row['codigo extraído']
        estoque = row['estoque']
        titulo = str(row['_titulosite'])[:40]

        if not codigo:
            continue

        if mostrar_zerado and estoque != 0:
            continue
        if mostrar_positivo and estoque <= 0:
            continue

        texto = f"{titulo:<42} | Código: {codigo:<15} | Estoque: {estoque}"
        lista.insert(tk.END, texto)

def exportar_resultado():
    if df_entrada is None:
        messagebox.showwarning("Nada para exportar", "Os dados ainda não foram processados.")
        return
    try:
        df_entrada.to_excel("resultado.xlsx", index=False)
        messagebox.showinfo("Exportado", "Resultado salvo como 'resultado.xlsx'")
    except Exception as e:
        messagebox.showerror("Erro ao exportar", str(e))

def selecionar_pasta():
    global pasta_padrao
    nova_pasta = filedialog.askdirectory()
    if nova_pasta:
        pasta_padrao = nova_pasta
        salvar_config()
        carregar_automaticamente()

# ---------------- Interface ----------------
carregar_config()

root = tk.Tk()
root.title("Extrator de Códigos + Estoque")
root.geometry("1000x600")

frame_topo = ttk.Frame(root, padding=10)
frame_topo.pack(fill='x')

btn_pasta = ttk.Button(frame_topo, text="📂 Selecionar Pasta", command=selecionar_pasta)
btn_pasta.pack(side='left', padx=5)

btn_atualizar = ttk.Button(frame_topo, text="🔁 Atualizar Dados", command=atualizar_dados)
btn_atualizar.pack(side='left', padx=5)

btn_exportar = ttk.Button(frame_topo, text="📤 Exportar Resultado", command=exportar_resultado)
btn_exportar.pack(side='left', padx=5)

filtro_zerado = tk.BooleanVar()
filtro_positivo = tk.BooleanVar()

ttk.Checkbutton(frame_topo, text="Mostrar quantidade zerada", variable=filtro_zerado).pack(side='left', padx=10)
ttk.Checkbutton(frame_topo, text="Mostrar somente saldo positivo", variable=filtro_positivo).pack(side='left', padx=10)

status_label = ttk.Label(root, text="ℹ️ Selecione uma pasta contendo os arquivos.", foreground="gray")
status_label.pack(pady=(0,10))

lista = tk.Listbox(root, font=('Courier New', 10), width=150, height=30)
lista.pack(padx=10, pady=10)

root.mainloop()