import logging
import os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from pathlib import Path
from dotenv import load_dotenv
import time

load_dotenv()

REPORTS_DIR = Path(r"C:\Automacoes\Gerador_Relatorio_Pedidos\reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

def get_env(name: str, required: bool = False) -> str:
    value = os.getenv(name)
    if required and not value:
        raise ValueError(f"Variavel obrigatoria ausente: {name}")
    return value


CSW_URL = get_env("CSW_URL", required=True)
CSW_USER = get_env("CSW_USER", required=True)
CSW_PASS = get_env("CSW_PASS", required=True)

# CSW_URL="http://10.1.1.220/"
# CSW_USER='rpa.flexivel'
# CSW_PASS='Flex@123'

SELECTOR_USER = 'input[placeholder="Usuário"]'
SELECTOR_PASS = 'input[placeholder="Senha"]'
SELECTOR_BUTTON = 'button.loginButton:has-text("Acessar")'

def preencher_datas():
    hoje = datetime.now()

    data_passada = hoje - timedelta(days=30)
    data_amanha = hoje + timedelta(days=1)

    # 3. Formatar as datas como DDMMYYYY (ex: "09062026" e "25062026")
    str_data_passada = data_passada.strftime("%d%m%Y")
    str_data_amanha = data_amanha.strftime("%d%m%Y")

    return str_data_passada, str_data_amanha

def tempo_espera(s: int):
    time.sleep(s)

def pressiona_tecla_e_espera(page,tecla: str, espera: float = 1):
    page.keyboard.press(tecla)
    tempo_espera(espera)

def fazer_login(page) -> None:
    logger.debug("Navegando para %s", CSW_URL)
    page.goto(CSW_URL, wait_until="networkidle", timeout=300000)

    logger.debug("Aguardando campo de usuário...")
    page.wait_for_selector(SELECTOR_USER)
    page.click(SELECTOR_USER)
    page.keyboard.type(CSW_USER)

    logger.debug("Aguardando campo de senha...")
    page.wait_for_selector(SELECTOR_PASS)
    page.click(SELECTOR_PASS)
    page.keyboard.type(CSW_PASS)

    button = page.locator(SELECTOR_BUTTON)
    button.wait_for(state="visible", timeout=30000)

    # espera botão habilitar
    logger.debug("Aguardando botão de login habilitar...")
    for _ in range(50):  # ~10 segundos
        if not button.is_disabled():
            break
        page.wait_for_timeout(200)

    if button.is_disabled():
        logger.error("Botão de login não habilitou após o tempo de espera.")
        raise RuntimeError("Botão de login não habilitou.")

    button.click()
    logger.debug("Botão de login clicado, aguardando carregamento...")

    page.wait_for_load_state("networkidle", timeout=120000)

    print("Login realizado com sucesso.")
    logger.info("Login realizado com sucesso.")

def interagir_csw(page,codigo_rotina: str, data_inicial: str, data_final: str) -> str:
    print("Inicio de interação com CSW")
    logger.info("Início de interação com CSW (rotina=%s)", codigo_rotina)

    page.wait_for_timeout(1000)
    page.locator("body").click()
    page.keyboard.press("Escape")

    logger.debug("Clicando no item da barra lateral...")
    sidebar_item = page.locator('#root div.csw_page_sidebar_item').nth(4)
    sidebar_item.wait_for(state="visible")
    sidebar_item.click()

    tempo_espera(3)

    logger.debug("Digitando código da rotina: %s", codigo_rotina)
    page.keyboard.type(codigo_rotina)
    tempo_espera(1)
    pressiona_tecla_e_espera(page,"Enter")

    tempo_espera(2)
    logger.debug("Digitando data inicial: %s", data_inicial)
    page.keyboard.type(data_inicial)
    pressiona_tecla_e_espera(page,"Enter")

    logger.debug("Digitando data final: %s", data_final)
    page.keyboard.type(data_final)
    pressiona_tecla_e_espera(page,"Enter")

    for contagem in range(4):
        pressiona_tecla_e_espera(page,"Enter")

    logger.debug("Aguardando 20s pelo carregamento do relatório...")
    tempo_espera(20)

    # aba_ativa = page.locator(".ui.bottom.attached.segment.active.tab")

    # # Abre o menu de exportação
    # logger.debug("Abrindo menu de exportação...")
    # botao_exportar = aba_ativa.locator("button:has(i.share.square.icon)").last
    # botao_exportar.wait_for(state="visible", timeout=30000)
    # botao_exportar.click(timeout=5000, no_wait_after=True)

    # page.wait_for_timeout(500)

    aba_ativa = page.locator(".ui.bottom.attached.segment.active.tab")

    logger.debug("Aguardando botão de exportação habilitado...")

    botao_exportar = aba_ativa.locator(
        "button:has(i.share.square.icon):not(.disabled):not([disabled])"
    ).last

    botao_exportar.wait_for(state="visible", timeout=60000)

    logger.debug("Abrindo menu de exportação...")
    botao_exportar.click(timeout=10000, no_wait_after=True)

    page.wait_for_timeout(500)

    opcao_excel = page.locator(".csw_table_toolbar_popup_item").filter(
    has_text="Exportar em Excel"
    ).last

    # Clica em Exportar em Excel e captura o download
    logger.debug("Clicando em 'Exportar em Excel' e aguardando download...")
    with page.expect_download() as download_info:
        opcao_excel.click(timeout=5000, no_wait_after=True)

    download = download_info.value

    nome_arquivo = f"Pedidos {data_inicial} ate {data_final}"
    caminho_arquivo = REPORTS_DIR / f"{nome_arquivo}.xlsx"

    download.save_as(caminho_arquivo)
    logger.info("Download salvo em: %s", caminho_arquivo.resolve())

    return caminho_arquivo, nome_arquivo
