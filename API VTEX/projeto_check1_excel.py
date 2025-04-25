import requests
import json
import os
import time
import pandas as pd
from dateutil import parser
from datetime import datetime
import pytz

def load_config():
    """Carrega configurações do config.json"""
    config_file = "config.json"
    if not os.path.exists(config_file):
        print("Erro: Arquivo config.json não encontrado")
        return {}
    with open(config_file, "r") as f:
        config = json.load(f)
        required_keys = ["vtex_account", "app_key", "app_token"]
        if not all(key in config for key in required_keys):
            print(f"Erro: config.json deve conter {required_keys}")
            return {}
        return config

def is_date_in_brazil_day(dt, target_date="2025-04-24"):
    """Verifica se a data está em 24/04/2025 no horário de Brasília"""
    brazil_tz = pytz.timezone("America/Sao_Paulo")
    dt_brazil = dt.astimezone(brazil_tz)
    return dt_brazil.strftime("%Y-%m-%d") == target_date

def fetch_orders():
    """Busca pedidos da VTEX com status 'ready-for-handling' para 24/04/2025 (Brasília) e exporta IDs, datas, status e valores para Excel"""
    config = load_config()
    if not config:
        return

    # Configuração da API para lista de pedidos
    url = f"https://{config['vtex_account']}.vtexcommercestable.com.br/api/oms/pvt/orders"
    headers = {
        "X-VTEX-API-AppKey": config["app_key"],
        "X-VTEX-API-AppToken": config["app_token"],
    }

    # Filtro de data para 24/04/2025 em horário de Brasília (UTC-3)
    date_filter = "creationDate:[2025-04-24T03:00:00.000Z TO 2025-04-25T02:59:59.999Z]"
    
    params = {
        "per_page": 100,
        "page": 1,
        "f_creationDate": date_filter,
        "orderStatus": "ready-for-handling",
        "orderBy": "creationDate,asc"  # Ordenar por data de criação, do mais antigo ao mais atual
    }

    orders = []
    total_expected = 0
    max_retries = 3

    try:
        while True:
            for attempt in range(max_retries):
                print(f"\nBuscando página {params['page']} (Tentativa {attempt + 1}/{max_retries})...")
                print(f"Parâmetros: {params}")
                try:
                    response = requests.get(url, headers=headers, params=params, timeout=10)
                    if response.status_code == 429:
                        wait_time = 2 ** attempt
                        print(f"Erro 429: Rate limit atingido. Aguardando {wait_time} segundos...")
                        time.sleep(wait_time)
                        continue
                    response.raise_for_status()
                    break
                except requests.RequestException as e:
                    print(f"Erro na requisição: {e}")
                    if attempt == max_retries - 1:
                        print("Número máximo de tentativas atingido. Abortando...")
                        return
                    time.sleep(2 ** attempt)

            data = response.json()
            print(f"Resposta completa: {json.dumps(data, indent=2)}")

            # Verificar estrutura da resposta
            if "paging" not in data or "list" not in data:
                print("Erro: Resposta da API não contém 'paging' ou 'list'")
                return

            total_expected = data["paging"].get("total", 0)
            print(f"Total esperado (API): {total_expected}")
            page_orders = data["list"]
            print(f"\nPedidos encontrados na página {params['page']}:")
            for order in page_orders:
                print(f" - Pedido {order['orderId']}: Status {order['status']}, Data {order['creationDate']}, Valor {order.get('totalValue', 0)}")
            orders.extend(page_orders)
            print(f"Página {params['page']}: {len(page_orders)} pedidos")

            # Parar se não houver mais pedidos ou a página estiver vazia
            if not page_orders or len(page_orders) < params["per_page"]:
                break

            params["page"] += 1

    except Exception as e:
        print(f"Erro inesperado: {e}")
        return

    # Resumo dos pedidos
    print(f"\nTotal de pedidos carregados: {len(orders)} (Esperado: {total_expected})")
    
    # Verificar pedidos ausentes específicos
    missing_orders = [
        "1527370727164-01",
        "1527370727166-01",
        "1527380727170-01"
    ]
    found_orders = [order['orderId'] for order in orders]
    for missing_id in missing_orders:
        if missing_id not in found_orders:
            print(f"Aviso: Pedido {missing_id} não encontrado na resposta da API")
        else:
            print(f"Confirmado: Pedido {missing_id} encontrado")

    # Preparar dados para exportação (ID do pedido, data de criação, status e valor)
    orders_data = []
    if orders:
        print("\nPreparando dados dos pedidos para exportação...")
        for order in orders:
            try:
                creation_date = parser.isoparse(order['creationDate'])
                # Verificar se a data está em 24/04/2025 no horário de Brasília
                if not is_date_in_brazil_day(creation_date):
                    print(f"Pedido {order['orderId']} ignorado: Data {creation_date} fora de 24/04/2025 em Brasília")
                    continue
                orders_data.append({
                    "ID do Pedido": order['orderId'],
                    "Data de Criação": creation_date.astimezone(pytz.timezone("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S"),
                    "Status": order['status'],
                    "Valor do Pedido (R$)": order.get('totalValue', 0) / 100,  # Converter de centavos para reais
                    "creation_date_raw": creation_date  # Para ordenação
                })
            except ValueError as e:
                print(f"Erro ao parsear data do pedido {order['orderId']}: {e}")
                continue

        # Ordenar por data de criação
        orders_data.sort(key=lambda x: x["creation_date_raw"])

        # Remover a coluna auxiliar de ordenação
        orders_data = [
            {
                "ID do Pedido": order["ID do Pedido"],
                "Data de Criação": order["Data de Criação"],
                "Status": order["Status"],
                "Valor do Pedido (R$)": order["Valor do Pedido (R$)"]
            }
            for order in orders_data
        ]

        # Exportar para Excel
        if orders_data:
            print("\nExportando pedidos para 'pedidos_pronto_manuseio_24_04_2025.xlsx'...")
            df = pd.DataFrame(orders_data)
            df.to_excel("pedidos_pronto_manuseio_24_04_2025.xlsx", index=False, engine='openpyxl')
            print("Exportação concluída com sucesso!")
        else:
            print("\nNenhum pedido encontrado para exportar.")

    print(f"\nResumo:")
    print(f"Total de Pedidos Exportados: {len(orders_data)}")
    status_counts = {}
    for order in orders:
        status = order["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    print("Por Status (todos os pedidos retornados):")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")

if __name__ == "__main__":
    fetch_orders()