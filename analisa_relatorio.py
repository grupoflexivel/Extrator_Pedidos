import pandas as pd
import numpy as np
from gerador_relatorio import preencher_datas
from pathlib import Path

def carregar_relatorio(relatorio):

    dataframe = pd.read_excel(relatorio,
                              parse_dates=["Prev. Embarque","Prev. Entrega"],
                              )
    return dataframe

def filtrar_pedidos_não_embarcados(dataframe: pd.DataFrame,coluna_embarcado:str,valor_padrão_coluna:str) -> pd.DataFrame:

    df = dataframe.copy()

    pedido_não_embarcado = df[coluna_embarcado].astype("string").str.contains(valor_padrão_coluna).fillna(False)

    return df[pedido_não_embarcado]

def filtrar_pedidos_atrasados(dataframe:pd.DataFrame,coluna_previsao_embarque: str) -> pd.DataFrame:

    df = dataframe.copy()

    _,_,hoje = preencher_datas()

    hoje_pandas = pd.to_datetime(hoje)

    pedido_atrasado = df[coluna_previsao_embarque] < hoje_pandas

    return df[pedido_atrasado]

def salvar_relatorio_modificado(dataframe: pd.DataFrame):

    _,_,hoje = preencher_datas()
    hoje_str = hoje.strftime("%d%m%Y")

    diretorio_atual = Path(__file__).parent
    nome_arquivo = f'Consulta de Pedidos Atrasados {hoje_str}.xlsx'

    dataframe = dataframe.drop(columns=["Unnamed: 0"])
    
    caminho_salvo = diretorio_atual / nome_arquivo

    with pd.ExcelWriter(caminho_salvo,engine="xlsxwriter", datetime_format="dd/mm/yyyy") as writer:
        dataframe.to_excel(
            writer,
            sheet_name="Pedidos Atrasados",
            index=False
        )
    return caminho_salvo




    
