import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import requests
import csv
import json
import os
from datetime import datetime
from dateutil import parser
from tkcalendar import Calendar
import pytz  # Importando pytz para manipulação de fusos horários

CONFIG_FILE = "config_meta_ads.json"
campanhas_global = []

# Função para garantir que todas as datas sejam cientes do fuso horário (aware)
def ajustar_data_com_fuso(data):
    fuso_horario = pytz.timezone("America/Sao_Paulo")  # Definindo o fuso horário
    return data.astimezone(fuso_horario) if data.tzinfo else data.replace(tzinfo=fuso_horario)

def carregar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            token_entry.insert(0, config.get("token", ""))
            ad_account_entry.insert(0, config.get("ad_account", ""))

def salvar_config(token, ad_account):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"token": token, "ad_account": ad_account}, f)

def buscar_campanhas():
    global campanhas_global
    token = token_entry.get()
    ad_account = ad_account_entry.get()

    if not token or not ad_account:
        messagebox.showerror("Erro", "Preencha o Access Token e o Ad Account ID.")
        return

    salvar_config(token, ad_account)

    # Pega as campanhas
    url_campanhas = f"https://graph.facebook.com/v19.0/{ad_account}/campaigns"
    params_campanhas = {
        'fields': 'name,status,objective,start_time,end_time',
        'access_token': token
    }

    try:
        resp = requests.get(url_campanhas, params=params_campanhas)
        dados = resp.json()

        if 'error' in dados:
            messagebox.showerror("Erro", dados['error']['message'])
            return

        campanhas = dados.get('data', [])
        campanhas_global = []
        resultado_text.delete('1.0', tk.END)

        # Agora, vamos pegar a data de início e fim, considerando apenas a parte de ano, mês e dia
        try:
            data_inicial = datetime.strptime(calendario_inicial.get_date(), "%m/%d/%Y")
            data_final = datetime.strptime(calendario_final.get_date(), "%m/%d/%Y")
        except ValueError:
            messagebox.showerror("Erro", "Formato de data inválido. Use o formato MM/DD/YYYY.")
            return

        # Garantindo que as datas sejam cientes do fuso horário
        data_inicial = ajustar_data_com_fuso(data_inicial)
        data_final = ajustar_data_com_fuso(data_final)

        for c in campanhas:
            camp_id = c.get('id')
            nome = c.get('name')
            status = c.get('status')
            objetivo = c.get('objective', 'N/A')
            start_time = parser.parse(c.get('start_time', "1970-01-01T00:00:00"))
            end_time = parser.parse(c.get('end_time', "1970-01-01T00:00:00"))

            # Ajustando as datas para o fuso horário
            start_time = ajustar_data_com_fuso(start_time)
            end_time = ajustar_data_com_fuso(end_time)

            if start_time > data_final or end_time < data_inicial:
                continue  # pula campanhas fora do intervalo

            # Pega métricas da campanha
            url_insights = f"https://graph.facebook.com/v19.0/{camp_id}/insights"
            params_insights = {
                'access_token': token,
                'fields': 'impressions,clicks,ctr,spend,cpc,reach,actions',
                'date_preset': 'lifetime',  # Vamos pegar o total de dados para a campanha
                'time_range': {
                    'since': data_inicial.strftime("%Y-%m-%d"),
                    'until': data_final.strftime("%Y-%m-%d")
                }
            }
            r_insights = requests.get(url_insights, params=params_insights).json()
            metrics = r_insights.get('data', [{}])[0]

            # Processa ações (ex: compras)
            actions = metrics.get('actions', [])
            purchases = next((a['value'] for a in actions if a['action_type'] == 'purchase'), 0)

            campanha_info = {
                'name': nome,
                'status': status,
                'objective': objetivo,
                'impressions': metrics.get('impressions', 0),
                'clicks': metrics.get('clicks', 0),
                'ctr': metrics.get('ctr', 0),
                'cpc': metrics.get('cpc', 0),
                'reach': metrics.get('reach', 0),
                'spend': metrics.get('spend', 0),
                'purchases': purchases
            }

            campanhas_global.append(campanha_info)

            status_icon = "✅" if status == "ACTIVE" else "⏸️"
            resultado_text.insert(
                tk.END,
                f"{status_icon} {nome} | Status: {status} | Objetivo: {objetivo}\n"
                f"➡️ Alcance: {campanha_info['reach']} | Cliques: {campanha_info['clicks']} | "
                f"CTR: {campanha_info['ctr']} | CPC: {campanha_info['cpc']} | Compras: {purchases} | Gasto: R${campanha_info['spend']}\n\n"
            )

    except Exception as e:
        messagebox.showerror("Erro", str(e))

def exportar_csv():
    if not campanhas_global:
        messagebox.showinfo("Sem dados", "Nenhuma campanha para exportar.")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV files", "*.csv")],
                                             title="Salvar como")
    if not file_path:
        return

    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=campanhas_global[0].keys())
            writer.writeheader()
            writer.writerows(campanhas_global)
        messagebox.showinfo("Sucesso", f"Campanhas exportadas para:\n{file_path}")
    except Exception as e:
        messagebox.showerror("Erro ao salvar", str(e))


# Interface
janela = tk.Tk()
janela.title("Painel Meta Ads - Campanhas e Métricas")
janela.geometry("800x600")

# Campos
ttk.Label(janela, text="Access Token:").pack(pady=5)
token_entry = ttk.Entry(janela, width=100, show="*")
token_entry.pack()

ttk.Label(janela, text="Ad Account ID (ex: act_1234567890):").pack(pady=5)
ad_account_entry = ttk.Entry(janela, width=40)
ad_account_entry.pack()

# Campos de Data usando o tkcalendar
ttk.Label(janela, text="Data Inicial:").pack(pady=5)
calendario_inicial = Calendar(janela, selectmode='day', date_pattern='mm/dd/yyyy')
calendario_inicial.pack()

ttk.Label(janela, text="Data Final:").pack(pady=5)
calendario_final = Calendar(janela, selectmode='day', date_pattern='mm/dd/yyyy')
calendario_final.pack()

# Filtro
filtro_var = tk.BooleanVar()
filtro_checkbox = ttk.Checkbutton(janela, text="Mostrar apenas campanhas ativas", variable=filtro_var)
filtro_checkbox.pack(pady=5)

# Botões
btn_frame = ttk.Frame(janela)
btn_frame.pack(pady=10)

ttk.Button(btn_frame, text="Buscar Campanhas", command=buscar_campanhas).grid(row=0, column=0, padx=5)
ttk.Button(btn_frame, text="Exportar CSV", command=exportar_csv).grid(row=0, column=1, padx=5)

# Área de resultado
resultado_text = scrolledtext.ScrolledText(janela, width=100, height=25)
resultado_text.pack(padx=10, pady=10)

# Carregar configs anteriores
carregar_config()

janela.mainloop()
