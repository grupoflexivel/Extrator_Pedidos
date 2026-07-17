import logging
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from gerador_relatorio import fazer_login, interagir_csw, preencher_datas
from notificador import envia_email



REPORTS_DIR = Path(r"C:\Automacoes\Gerador_Relatorio_Pedidos\reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "rpa_pedidos.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("===== Início da execução =====")

    try:
        data_inicial, data_final = preencher_datas()
        logger.info("Período definido: %s até %s", data_inicial, data_final)

        with sync_playwright() as p:
            logger.debug("Iniciando browser Chromium (headless=True)")
            browser = p.chromium.launch(
                headless=True,
                args=["--ignore-certificate-errors"]
            )

            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            logger.info("Realizando login no CSW...")
            fazer_login(page)
            logger.info("Login concluído.")

            logger.info("Interagindo com rotina GCFEPVC600...")
            relatorio, nome_relatorio = interagir_csw(page, "GCFEPVC600", data_inicial, data_final)
            logger.info("Arquivo gerado: %s", nome_relatorio)

            context.close()
            browser.close()
            logger.debug("Browser encerrado.")

        logger.info("Enviando e-mail via Power Automate...")
        envia_email(relatorio)
        logger.info("E-mail enviado com sucesso.")

    except Exception:
        logger.exception("Falha na execução do RPA.")
        raise

    logger.info("===== Fim da execução =====")


if __name__ == "__main__":
    main()
