import base64
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv
from gerador_relatorio import get_env

logger = logging.getLogger(__name__)

load_dotenv()

URL_FLOW = get_env("URL_FLOW", required=True)


def envia_email(caminho_arquivo):

    caminho_arquivo = Path(caminho_arquivo)
    logger.debug("Caminho do arquivo a anexar: %s", caminho_arquivo.resolve())

    if not caminho_arquivo.exists():
        logger.error("Arquivo de relatório não encontrado em: %s", caminho_arquivo.resolve())
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")

    tamanho_bytes = caminho_arquivo.stat().st_size
    logger.debug("Tamanho do arquivo: %d bytes", tamanho_bytes)

    with open(caminho_arquivo, "rb") as arquivo:
        arquivo_base64 = base64.b64encode(arquivo.read()).decode("utf-8")

    payload = {
        "assunto": "Relatório de pedidos gerado",
        "mensagem": (
            f"O relatório <strong>{caminho_arquivo.name}</strong> está anexo a este e-mail."
        ),
        "anexo_nome": caminho_arquivo.name,
        "anexo_conteudo": arquivo_base64,
        "anexo_tipo": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    logger.info("Chamando fluxo do Power Automate (%s)...", caminho_arquivo.name)
    try:
        response = requests.post(URL_FLOW, json=payload, timeout=30)
        logger.debug("Status HTTP retornado pelo Power Automate: %s", response.status_code)
        logger.debug("Corpo da resposta: %s", response.text[:2000])
        response.raise_for_status()
    except requests.exceptions.RequestException:
        logger.exception("Erro ao chamar o fluxo do Power Automate.")
        raise

    print("E-mail solicitado ao Power Automate com sucesso.")
    logger.info("E-mail solicitado ao Power Automate com sucesso.")
