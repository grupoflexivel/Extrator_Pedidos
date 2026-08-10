import logging
import os
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from pathlib import Path
from dotenv import load_dotenv
import time

load_dotenv()

REPORTS_DIR = Path(r"C:\Automacoes\Gerador_Relatorio_Pedidos\reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DIAG_DIR = Path(r"C:\Automacoes\Gerador_Relatorio_Pedidos\logs\diagnostico")
DIAG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


def captura_diagnostico(page, etapa: str) -> None:
    """Salva print e HTML da página para inspeção posterior de falhas."""
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = DIAG_DIR / f"{etapa}_{carimbo}"
    try:
        page.screenshot(path=f"{destino}.png", full_page=True)
        Path(f"{destino}.html").write_text(page.content(), encoding="utf-8")
        logger.error("Diagnóstico salvo em %s.png e %s.html", destino, destino)
    except Exception:
        logger.exception("Não foi possível capturar o diagnóstico da página.")

def get_env(name: str, required: bool = False) -> str:
    value = os.getenv(name)
    if required and not value:
        raise ValueError(f"Variavel obrigatoria ausente: {name}")
    return value


CSW_URL = get_env("CSW_URL", required=True)
CSW_USER = get_env("CSW_USER", required=True)
CSW_PASS = get_env("CSW_PASS", required=True)

SELECTOR_USER = 'input[placeholder="Usuário"]'
SELECTOR_PASS = 'input[placeholder="Senha"]'
SELECTOR_BUTTON = 'button.loginButton:has-text("Acessar")'
SELECTOR_SIDEBAR_ITEM = '#root div.csw_page_sidebar_item'

# Varredura ampla usada só em caminho de erro: o popup que bloqueia o CSW ainda
# não teve sua marcação identificada, então procuramos qualquer sobreposição.
SELETORES_OVERLAY = [
    ".ui.modal",
    ".ui.dimmer",
    "[role='dialog']",
    "[role='alertdialog']",
    ".modal",
    ".ui.popup",
    ".ui.message",
    ".ui.toast",
    ".ui.confirm",
]


def descreve_overlays(page) -> None:
    """Loga toda sobreposição visível na tela, para identificar popups desconhecidos."""
    encontrou = False

    for seletor in SELETORES_OVERLAY:
        try:
            elementos = page.locator(seletor)
            total = elementos.count()
        except Exception:
            continue

        for indice in range(min(total, 5)):
            item = elementos.nth(indice)
            try:
                if not item.is_visible():
                    continue
                classe = (item.get_attribute("class") or "")[:150]
                texto = (item.inner_text() or "").strip().replace("\n", " | ")[:300]
                logger.error(
                    "Overlay visível [%s #%d] class=%r texto=%r", seletor, indice, classe, texto
                )
                encontrou = True
            except Exception:
                continue

    if not encontrou:
        logger.error("Nenhuma sobreposição conhecida visível na tela.")

def preencher_datas():
    hoje = datetime.now().date()

    data_passada = hoje - timedelta(days=30)
    data_amanha = hoje + timedelta(days=1)

    # 3. Formatar as datas como DDMMYYYY (ex: "09062026" e "25062026")
    str_data_passada = data_passada.strftime("%d%m%Y")
    str_data_amanha = data_amanha.strftime("%d%m%Y")
    

    return str_data_passada, str_data_amanha, hoje

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

    fechar_popups(page)

    # networkidle numa SPA retorna de imediato (não há navegação de página), então
    # só a presença do shell do ERP confirma que o login realmente passou.
    try:
        page.locator(SELECTOR_SIDEBAR_ITEM).first.wait_for(state="visible", timeout=60000)
    except PlaywrightTimeoutError:
        logger.error("Shell do ERP não carregou após o login.")
        descreve_overlays(page)
        captura_diagnostico(page, "pos_login")
        raise RuntimeError("Login não concluiu: barra lateral do ERP não apareceu.")

    print("Login realizado com sucesso.")
    logger.info("Login realizado com sucesso.")

POPUP_SELECTOR = ".ui.modal.visible.active, .ui.modal.active"
DIMMER_SELECTOR = ".ui.dimmer.active, .ui.dimmer.visible"


def _tenta_fechar_modal(page, modal) -> bool:
    """Tenta fechar um modal pelos caminhos usuais do Semantic UI."""
    candidatos = [
        modal.locator("i.close.icon"),
        modal.locator(".actions button.ok, .actions button.primary, .actions button.positive"),
        modal.locator(".actions button"),
        modal.locator(
            "button:has-text('OK'), button:has-text('Ok'), "
            "button:has-text('Fechar'), button:has-text('Confirmar'), "
            "button:has-text('Continuar'), button:has-text('Ciente')"
        ),
    ]

    for candidato in candidatos:
        alvo = candidato.first
        if alvo.count() and alvo.is_visible():
            logger.debug("Fechando popup via: %s", alvo.inner_text().strip() or "ícone de fechar")
            alvo.click(timeout=5000, no_wait_after=True)
            return True

    logger.debug("Nenhum botão de fechar encontrado, tentando Escape...")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    try:
        return not modal.is_visible()
    except Exception:
        return True  # modal saiu do DOM


def fechar_popups(page, tentativas: int = 5) -> int:
    """Fecha os avisos que o CSW exibe ao entrar. Retorna quantos foram fechados."""
    fechados = 0

    for _ in range(tentativas):
        modal = page.locator(POPUP_SELECTOR).last
        try:
            modal.wait_for(state="visible", timeout=3000)
        except PlaywrightTimeoutError:
            break

        texto = (modal.inner_text() or "").strip().replace("\n", " | ")
        logger.warning("Popup detectado no CSW: %s", texto[:300])

        if not _tenta_fechar_modal(page, modal):
            logger.error("Não foi possível fechar o popup automaticamente.")
            captura_diagnostico(page, "popup_nao_fechado")
            raise RuntimeError(f"Popup bloqueando o fluxo: {texto[:200]}")

        fechados += 1
        page.wait_for_timeout(1000)

    # O dimmer continua interceptando cliques mesmo depois do modal sumir.
    try:
        page.locator(DIMMER_SELECTOR).last.wait_for(state="hidden", timeout=10000)
    except PlaywrightTimeoutError:
        logger.warning("Dimmer ainda ativo; cliques podem ser interceptados.")
    except Exception:
        pass

    if fechados:
        logger.info("%d popup(s) fechado(s) antes de seguir o fluxo.", fechados)

    return fechados


def interagir_csw(page,codigo_rotina: str, data_inicial: str, data_final: str) -> str:
    print("Inicio de interação com CSW")
    logger.info("Início de interação com CSW (rotina=%s)", codigo_rotina)

    page.wait_for_timeout(1000)
    fechar_popups(page)

    logger.debug("Clicando no item da barra lateral...")
    itens_sidebar = page.locator(SELECTOR_SIDEBAR_ITEM)

    # A barra lateral só renderiza depois que o shell do ERP monta; sem esta
    # espera o count() abaixo pode ler 0 e mascarar o motivo real da falha.
    try:
        itens_sidebar.first.wait_for(state="visible", timeout=30000)
    except PlaywrightTimeoutError:
        logger.error("Barra lateral não renderizou nenhum item.")
        descreve_overlays(page)
        captura_diagnostico(page, "sidebar_ausente")
        raise

    total_itens = itens_sidebar.count()
    logger.debug("Itens encontrados na barra lateral: %d", total_itens)

    if total_itens <= 4:
        logger.error(
            "Barra lateral com apenas %d item(ns); o índice 4 não existe. "
            "Layout do CSW pode ter mudado ou o menu está recolhido.",
            total_itens,
        )
        captura_diagnostico(page, "sidebar_itens_insuficientes")
        raise RuntimeError(f"Barra lateral com {total_itens} itens; esperado ao menos 5.")

    sidebar_item = itens_sidebar.nth(4)
    try:
        sidebar_item.wait_for(state="visible", timeout=30000)
    except PlaywrightTimeoutError:
        logger.error("Item 4 da barra lateral existe mas não ficou visível.")
        captura_diagnostico(page, "sidebar_item_invisivel")
        raise

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

    logger.debug("Abas ativas encontradas: %d", aba_ativa.count())

    botao_exportar = aba_ativa.locator("button:has(i.share.square.icon)").last

    logger.debug("Aguardando botão de exportação aparecer...")
    try:
        botao_exportar.wait_for(state="visible", timeout=60000)
    except PlaywrightTimeoutError:
        bloqueio = page.locator(POPUP_SELECTOR).last
        if bloqueio.count() and bloqueio.is_visible():
            texto = (bloqueio.inner_text() or "").strip().replace("\n", " | ")
            logger.error("Botão de exportação não apareceu: popup bloqueando a tela: %s", texto[:300])
        else:
            logger.error(
                "Botão de exportação não apareceu — o relatório não chegou a ser carregado."
            )
        captura_diagnostico(page, "botao_ausente")
        raise

    logger.debug("Botão visível, aguardando habilitar...")
    for _ in range(120):  # até 60s
        classe = botao_exportar.get_attribute("class") or ""
        if "disabled" not in classe and botao_exportar.is_enabled():
            break
        page.wait_for_timeout(500)
    else:
        logger.error("Botão de exportação apareceu mas permaneceu desabilitado por 60s.")
        captura_diagnostico(page, "botao_desabilitado")
        raise RuntimeError("Botão de exportação não habilitou.")

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
