from scrapling.fetchers import StealthyFetcher
import random
import concurrent.futures
import json
import sys
import os
import logging
from pythonjsonlogger import jsonlogger
import time 


companies = ["pix", "sefaz", "nota-fiscal-eletronica",
             "cielo", "rede", "pagseguro",
             "mercadopago", "aws-amazon-web-services", "windows-azure",
             "cloudflare", "ifood", "99", "telegram"]


JSON_FILE = "/app/data/downdetector_status.json"

css_script = 'script[type="text/javascript"]:contains("{ x:")::text'

downdetector = []

def setup_logger():
    logger = logging.getLogger("downdetector")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

logger = setup_logger()

def get_site(url):
    css_script = 'script[type="text/javascript"]:contains("{ x:")'
    max_attempts = 5
    attempts = 0
    browser = None

    while attempts < max_attempts:
        attempts += 1

        try:
            browser = StealthyFetcher.fetch(
                f'https://downdetector.com.br/fora-do-ar/{url}/',
                solve_cloudflare=True,
                block_webrtc=True,
                real_chrome=False,
                hide_canvas=True,
                google_search=True,
                headless=True,
                allow_webgl=False,
                wait=2000,
                wait_selector='script[type="text/javascript"]',
                wait_selector_state='attached',
                timeout=20000
            )
        except Exception as e:
            logger.error("erro no fetch", extra={
                "url": url,
                "tentativa": attempts,
                "error": str(e),
                "event": "fetch_error"
            })
            continue

        if browser.status != 200:
            logger.error("status http invalido", extra={
                "url": url,
                "status_http": browser.status,
                "tentativa": attempts,
                "event": "fetch_error"
            })
            continue

        if not browser.css(css_script):
            logger.error("script de dados nao encontrado", extra={
                "url": url,
                "tentativa": attempts,
                "event": "script_not_found"
            })
            continue

        return browser

    raise Exception(f"falha apos {max_attempts} tentativas: {url}")
       

def fetch_in_thread(url):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(get_site, url)
        return future.result()

def get_script():
    for url in companies:
        try:
            page = fetch_in_thread(url)
            #page = get_site(url, False)

            if not page:
                continue

            script = page.css(css_script)

            company_status = script.re_first(r"status:.'(.*)',")
            company_name = script.re_first(r"company:.'(.*)'")

            if not company_name or not company_status:
                logger.warning("campos nao extraidos do script", extra={
                    "url": url,
                    "company_name": company_name,
                    "company_status": company_status,
                    "event": "parse_incomplete"
                })
                continue

            downdetector.append({"empresa": company_name, "company_status": company_status})

        except Exception as e:
            logger.error("unexpected_error get_script", extra={
                "url": url,
                "error": str(e),
                "event": "unexpected_error"
            })
        finally:
            time.sleep(random.uniform(5, 15))

    upsert_status(downdetector)


def load_json(filepath):
    if not os.path.exists(filepath):
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except json.JSONDecodeError:
        logger.error("arquivo json corrompido ou invalido", extra={
            "filepath": filepath,
            "event": "load_error"
        })
        return []


def save_json(filepath, data):
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, filepath)


def upsert_status(new_entries: list):
    existing = load_json(JSON_FILE)
    index = {entry["empresa"]: entry for entry in existing}

    for entry in new_entries:
        name = entry["empresa"]
        status = entry["company_status"]

        if name not in index:
            index[name] = {"empresa": name, "company_status": status}
            logger.info("empresa adicionada", extra={
                "empresa": name,
                "status": status,
                "event": "insert"
            })
        elif index[name]["company_status"] != status:
            old_status = index[name]["company_status"]
            index[name]["company_status"] = status
            logger.info("status alterado", extra={
                "empresa": name,
                "status_anterior": old_status,
                "status_novo": status,
                "event": "status_change"
            })
    save_json(JSON_FILE, list(index.values()))
    logger.info("script finalizado", extra={
        "total_processadas": len(new_entries),
        "event": "done"
    })

if __name__ == "__main__":
    while True:
        start = time.time()

        downdetector.clear()
        get_script()

        duration = time.time() - start
        logger.info("execucao_finalizada", extra={
            "duracao_segundos": round(duration, 2)
        })

        time.sleep(1200)