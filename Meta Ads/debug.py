import requests
from datetime import datetime
import pytz

# Função para buscar campanhas ativas durante o mês de abril de 2024
def buscar_campanhas_ativas(token, ad_account):
    # Definir o período de abril de 2024
    data_inicial = datetime(2024, 4, 1, 0, 0, 0, tzinfo=pytz.timezone('America/Sao_Paulo'))
    data_final = datetime(2024, 4, 30, 23, 59, 59, tzinfo=pytz.timezone('America/Sao_Paulo'))

    # URL para buscar as campanhas
    url_campanhas = f"https://graph.facebook.com/v19.0/{ad_account}/campaigns"
    params_campanhas = {
        'fields': 'name,status,start_time,end_time',
        'access_token': token
    }

    # Requisição para pegar as campanhas
    response = requests.get(url_campanhas, params=params_campanhas)

    if response.status_code == 200:
        campanhas = response.json().get('data', [])
        print("Campanhas retornadas:", len(campanhas))
        
        if not campanhas:
            print("Nenhuma campanha encontrada.")
            return

        # Verificar campanhas ativas no mês de abril de 2024
        for campanha in campanhas:
            nome = campanha.get('name')
            status = campanha.get('status')
            start_time = campanha.get('start_time')
            end_time = campanha.get('end_time')

            # Exibir todas as campanhas com seus dados
            print(f"Campanha: {nome}, Status: {status}, Início: {start_time}, Fim: {end_time}")

            # Transformar as datas para comparar
            start_time = datetime.fromisoformat(start_time) if start_time else None
            end_time = datetime.fromisoformat(end_time) if end_time else None

            # Adicionar o fuso horário nas datas se não tiver
            if start_time and start_time.tzinfo is None:
                start_time = pytz.timezone('America/Sao_Paulo').localize(start_time)
            if end_time and end_time.tzinfo is None:
                end_time = pytz.timezone('America/Sao_Paulo').localize(end_time)

            # Verificar se a campanha estava ativa em algum momento durante abril de 2024
            if start_time and end_time:
                # A campanha estava ativa se iniciou antes de 30-04-2024 e terminou depois ou é indefinida
                if start_time <= data_final and (end_time >= data_inicial or not end_time):
                    print(f"{nome} | Status: {status} | Início: {start_time} | Fim: {end_time}")
            elif start_time and not end_time:  # Caso a campanha não tenha data de término
                if start_time <= data_final:
                    print(f"{nome} | Status: {status} | Início: {start_time} | Fim: {end_time}")
            elif not start_time and not end_time:  # Caso a campanha não tenha datas
                print(f"{nome} não tinha datas definidas e pode ter estado ativa.")
    else:
        print("Erro ao buscar campanhas:", response.text)

# Seu Access Token e Ad Account ID
token = 'EAAmVctN4znUBOxRCCzfjcmCSC1dwYJ7hivV0k5bwmlZAYcwtvp2ZBCCkqKb5koZAHZC1vYAyV4vGSwHXM2T5Tvk8mZCzlhB2DTQF4ZCUKf8FsKXDgzTjw9JHFJboOKNZA8HKZBYjBtQ76Om7ns6zMc5rZATE5UFsufqeapEj229a4PwWsn3F8psOnLdHzyZC60JE1hT78sHYqn4LLk6OaDiFvNrkRAgyLBWgmZBeH2zOmsmlzgZD'
ad_account = 'act_1083214178355433'

# Chamar a função
buscar_campanhas_ativas(token, ad_account)
