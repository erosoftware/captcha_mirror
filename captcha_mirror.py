from flask import Flask, render_template, request, jsonify, url_for, Response, send_from_directory
from flask_socketio import SocketIO, emit
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import base64
import os
import time
import logging
import threading
import tempfile
import sys
import json
import uuid
import signal
from io import BytesIO
from PIL import Image
from datetime import datetime
from pathlib import Path

# Configuração de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('captcha_mirror')

# Configuração da aplicação Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'erosoftware_captcha_mirror'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25, 
                   engineio_logger=True, async_mode='threading')

# Configuração de caminhos
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DOWNLOAD_DIR = BASE_DIR / "downloads"

# Criar diretórios necessários
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Variáveis globais
driver = None
captcha_image = None
captcha_visible = False
in_captcha_page = False
last_screenshot = None
client_count = 0

# Registro de handlers de sinal para shutdown limpo
def signal_handler(sig, frame):
    logger.info("Sinal de encerramento recebido, fechando aplicação...")
    if driver:
        close_driver()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Configuração do Selenium WebDriver
def setup_selenium_driver():
    """Configura o driver do Selenium para Chrome."""
    global driver
    
    try:
        # Log de início
        logger.info("Configurando driver do Selenium")
        
        # Configuração do Chrome
        chrome_options = Options()
        
        # Configurações adicionais - NÃO use headless para permitir interação e visualização
        chrome_options.add_argument('--start-maximized')  # Inicia maximizado
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        
        # Desativa a mensagem "Chrome está sendo controlado por automação"
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Configura o diretório de downloads
        prefs = {
            'download.default_directory': str(DOWNLOAD_DIR),
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'safebrowsing.enabled': False
        }
        chrome_options.add_experimental_option('prefs', prefs)
        
        # Inicializa o serviço do ChromeDriver com o driver automaticamente baixado
        service = Service(ChromeDriverManager().install())
        
        # Inicializa o driver
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Define timeout padrão
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)  # Espera implícita para encontrar elementos
        
        logger.info("Driver do Selenium configurado com sucesso")
        socketio.emit('driver_status', {'active': True})
        return True
    except Exception as e:
        logger.error(f"Erro ao configurar driver do Selenium: {str(e)}")
        socketio.emit('driver_status', {'active': False, 'error': str(e)})
        return False

# Função para abrir o navegador no SICAR
def open_sicar_browser():
    """Abre o navegador no site do SICAR."""
    try:
        # Emite log para o cliente
        socketio.emit('server_log', {'message': 'Tentando abrir site do SICAR...', 'level': 'info'})
        
        # Define um timeout maior para carregar o site
        driver.set_page_load_timeout(60)
        
        try:
            driver.get("https://consultapublica.car.gov.br/publico/imoveis/index")
        except Exception as timeout_err:
            socketio.emit('server_log', {'message': f'Timeout ao carregar SICAR: {str(timeout_err)}', 'level': 'error'})
            logger.error(f"Timeout ao carregar site do SICAR: {str(timeout_err)}")
            
            # Mesmo com timeout, tenta continuar
            socketio.emit('server_log', {'message': 'Tentando continuar mesmo com timeout...', 'level': 'warning'})
            
        logger.info("Request para site do SICAR enviado")
        socketio.emit('server_log', {'message': 'Site do SICAR requisitado, aguardando carregamento...', 'level': 'info'})
        
        # Aguarda pelo menos um elemento da página carregar com timeout maior
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            socketio.emit('server_log', {'message': 'Elemento body encontrado na página', 'level': 'success'})
        except TimeoutException:
            socketio.emit('server_log', {'message': 'Timeout aguardando elemento body', 'level': 'error'})
            logger.error("Timeout aguardando elemento body")
            # Continua mesmo assim
        
        # Tenta detectar se a página carregou corretamente
        try:
            title = driver.title
            url = driver.current_url
            socketio.emit('server_log', {'message': f'Página carregada: {title} | URL: {url}', 'level': 'info'})
            
            # Verifica se está realmente na página do SICAR
            if "consultapublica.car.gov.br" in url or "CAR" in title:
                socketio.emit('server_log', {'message': 'Confirmado: estamos na página do SICAR', 'level': 'success'})
            else:
                socketio.emit('server_log', {'message': f'Alerta: URL ou título não parecem ser do SICAR', 'level': 'warning'})
        except Exception as title_err:
            socketio.emit('server_log', {'message': f'Erro ao verificar título/URL: {str(title_err)}', 'level': 'error'})
        
        # Tenta executar JavaScript para confirmar que a página está funcional
        try:
            js_works = driver.execute_script("return document.readyState")
            socketio.emit('server_log', {'message': f'Estado da página: {js_works}', 'level': 'info'})
        except Exception as js_err:
            socketio.emit('server_log', {'message': f'JavaScript não funcionou: {str(js_err)}', 'level': 'error'})
        
        logger.info("Página do SICAR carregada com sucesso")
        socketio.emit('server_log', {'message': 'Página do SICAR carregada com sucesso', 'level': 'success'})
        return True
    except Exception as e:
        logger.error(f"Erro ao abrir navegador no SICAR: {str(e)}")
        socketio.emit('server_log', {'message': f'Erro ao abrir site do SICAR: {str(e)}', 'level': 'error'})
        
        # Captura e envia um screenshot mesmo em caso de erro
        try:
            screenshot_path = str(STATIC_DIR / "error_screenshot.png")
            driver.save_screenshot(screenshot_path)
            socketio.emit('server_log', {'message': 'Screenshot de erro salvo', 'level': 'info'})
        except:
            pass
            
        return False

# Função para fechar o driver
def close_driver():
    """Fecha o driver do Selenium."""
    global driver
    
    if driver:
        try:
            driver.quit()
            driver = None
            logger.info("Driver do Selenium fechado com sucesso")
            socketio.emit('driver_status', {'active': False})
            return True
        except Exception as e:
            logger.error(f"Erro ao fechar driver: {str(e)}")
            return False
    else:
        logger.warning("Tentativa de fechar driver que já estava fechado")
        return True

# Função para capturar o CAPTCHA
def check_for_captcha():
    """Verifica se há um CAPTCHA na página e o captura."""
    global captcha_image, captcha_visible, in_captcha_page
    
    try:
        # Verifica se o driver está ativo antes de continuar
        if not is_driver_alive():
            return False
            
        logger.info("Verificando se há CAPTCHA na página...")
        socketio.emit('server_log', {'message': 'Verificando se há CAPTCHA na página...', 'level': 'info'})
        
        # Salva screenshot para debug
        debug_screenshot = str(STATIC_DIR / "debug_screenshot.png")
        driver.save_screenshot(debug_screenshot)
        
        # Método 0: Verifica se estamos na página de download que costuma ter CAPTCHA
        try:
            # Verifica por palavras-chave específicas na URL ou título
            current_url = driver.current_url
            page_title = driver.title
            
            download_keywords = ["download", "baixar", "shapefile", "captcha"]
            found_keyword = False
            
            for keyword in download_keywords:
                if keyword in current_url.lower() or keyword in page_title.lower():
                    found_keyword = True
                    socketio.emit('server_log', {'message': f'Detectada página de download: "{keyword}" na URL ou título', 'level': 'info'})
                    break
                    
            # Se estamos em uma página que provavelmente tem CAPTCHA, captura um screenshot da página inteira
            if found_keyword:
                socketio.emit('server_log', {'message': 'Possível página de CAPTCHA detectada, capturando screenshot...', 'level': 'info'})
                screenshot = driver.get_screenshot_as_base64()
                captcha_image = f"data:image/png;base64,{screenshot}"
                
                # Salva o screenshot para o usuário
                full_screenshot_path = str(STATIC_DIR / "full_page_captcha.png")
                driver.save_screenshot(full_screenshot_path)
                
                # Emite evento para o cliente
                socketio.emit('captcha_detected', {'image': captcha_image})
                socketio.emit('server_log', {'message': 'Screenshot da página de CAPTCHA enviado. Por favor, procure o CAPTCHA na imagem.', 'level': 'warning'})
                socketio.emit('log_message', {'message': 'Possível CAPTCHA detectado. Veja o screenshot completo da página.', 'level': 'warning'})
                
                captcha_visible = True
                in_captcha_page = True
                return True
        except Exception as url_err:
            socketio.emit('server_log', {'message': f'Erro ao verificar URL/título: {str(url_err)}', 'level': 'error'})
        
        # Verifica se está na página com CAPTCHA por diferentes métodos
        # Método 1: Busca a imagem do CAPTCHA diretamente
        captcha_elements = driver.find_elements(By.XPATH, "//img[contains(@src, 'captcha')]")
        
        if captcha_elements:
            captcha_element = captcha_elements[0]
            logger.info("CAPTCHA detectado na página (método 1)")
            socketio.emit('server_log', {'message': 'CAPTCHA detectado na página (imagem com "captcha" na URL)', 'level': 'success'})
            
            try:
                # Captura a imagem do CAPTCHA
                captcha_element_screenshot = captcha_element.screenshot_as_base64
                captcha_image = f"data:image/png;base64,{captcha_element_screenshot}"
                
                captcha_visible = True
                in_captcha_page = True
                
                # Salva a imagem no diretório estático
                captcha_local_path = str(STATIC_DIR / "captcha.png")
                captcha_element.screenshot(captcha_local_path)
                
                # Emite evento para o cliente
                socketio.emit('captcha_detected', {'image': captcha_image})
                
                logger.info("CAPTCHA capturado e enviado para o cliente")
                socketio.emit('server_log', {'message': 'CAPTCHA capturado e enviado para o cliente', 'level': 'success'})
                
                # Destaca o elemento CAPTCHA na página
                driver.execute_script("arguments[0].style.border = '5px solid red';", captcha_element)
                
                return True
            except Exception as img_err:
                socketio.emit('server_log', {'message': f'Erro ao capturar imagem do CAPTCHA: {str(img_err)}', 'level': 'error'})
        
        # Método 2: Busca por elementos de texto relacionados a CAPTCHA
        captcha_references = driver.find_elements(By.XPATH, 
            "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'captcha')]")
        
        if captcha_references:
            logger.info("Referência a CAPTCHA encontrada no texto da página (método 2)")
            socketio.emit('server_log', {'message': 'Referência a CAPTCHA encontrada no texto da página', 'level': 'info'})
            
            # Tenta localizar a imagem do CAPTCHA usando JavaScript
            try:
                captcha_src = driver.execute_script("""
                    // Procura por imagens que possam ser um CAPTCHA
                    const images = Array.from(document.querySelectorAll('img'));
                    
                    // Filtra imagens que possam ser CAPTCHA
                    const captchaImg = images.find(img => {
                        const src = img.src.toLowerCase();
                        // Verifica se a URL contém "captcha" ou tem extensão .jpg/.png
                        return src.includes('captcha') || /\.(jpg|png|gif)\b/.test(src);
                    });
                    
                    if (captchaImg) {
                        captchaImg.scrollIntoView({block: 'center'});
                        captchaImg.style.border = '5px solid red';
                        return captchaImg.src;
                    }
                    return null;
                """)
                
                if captcha_src:
                    socketio.emit('server_log', {'message': f'Imagem de CAPTCHA encontrada via JavaScript: {captcha_src}', 'level': 'success'})
                    
                    # Tenta capturar esse elemento
                    captcha_elem = driver.find_element(By.XPATH, f"//img[@src='{captcha_src}']")
                    
                    # Captura a imagem
                    captcha_element_screenshot = captcha_elem.screenshot_as_base64
                    captcha_image = f"data:image/png;base64,{captcha_element_screenshot}"
                    
                    captcha_visible = True
                    in_captcha_page = True
                    
                    # Salva a imagem
                    captcha_local_path = str(STATIC_DIR / "captcha.png")
                    captcha_elem.screenshot(captcha_local_path)
                    
                    # Emite evento para o cliente
                    socketio.emit('captcha_detected', {'image': captcha_image})
                    
                    logger.info("CAPTCHA capturado e enviado para o cliente")
                    socketio.emit('server_log', {'message': 'CAPTCHA capturado e enviado para o cliente', 'level': 'success'})
                    return True
            except Exception as js_err:
                socketio.emit('server_log', {'message': f'Erro ao tentar encontrar CAPTCHA via JavaScript: {str(js_err)}', 'level': 'error'})
            
            # Se não encontrou a imagem, mas encontrou referência, ainda considera que estamos na página de CAPTCHA
            in_captcha_page = True
            
            # Tenta capturar um screenshot da região onde provavelmente está o CAPTCHA
            try:
                # Destaca a área do CAPTCHA para o usuário ver
                driver.execute_script("""
                    const elements = document.querySelectorAll("*");
                    for (let i = 0; i < elements.length; i++) {
                        if (elements[i].innerText && elements[i].innerText.toLowerCase().includes('captcha')) {
                            elements[i].scrollIntoView({block: 'center'});
                            elements[i].style.border = '3px solid red';
                            
                            // Destaca elementos próximos que possam ser o CAPTCHA
                            const parent = elements[i].parentElement;
                            if (parent) {
                                const siblings = parent.children;
                                for (let j = 0; j < siblings.length; j++) {
                                    if (siblings[j].tagName === 'IMG') {
                                        siblings[j].style.border = '3px solid blue';
                                    }
                                }
                            }
                            break;
                        }
                    }
                """)
                
                # Espera um momento para a página rolar
                time.sleep(1)
                
                # Captura um screenshot da página
                screenshot = driver.get_screenshot_as_base64()
                captcha_image = f"data:image/png;base64,{screenshot}"
                
                captcha_local_path = str(STATIC_DIR / "captcha_area.png")
                driver.save_screenshot(captcha_local_path)
                
                # Emite evento para o cliente
                socketio.emit('captcha_detected', {'image': captcha_image})
                socketio.emit('server_log', {'message': 'Screenshot da página de CAPTCHA enviado. Por favor, procure o CAPTCHA na imagem.', 'level': 'warning'})
                socketio.emit('log_message', {'message': 'Possível CAPTCHA detectado. Veja o screenshot completo da página.', 'level': 'warning'})
                
                captcha_visible = True
                return True
            except Exception as e:
                socketio.emit('server_log', {'message': f'Erro ao tentar capturar área de CAPTCHA: {str(e)}', 'level': 'error'})
        
        # Método 3: Verifica por campos de entrada relacionados a CAPTCHA
        captcha_inputs = driver.find_elements(By.XPATH, 
            "//input[contains(@id, 'captcha') or contains(@name, 'captcha')]")
        
        if captcha_inputs:
            logger.info("Campo de entrada de CAPTCHA encontrado (método 3)")
            socketio.emit('server_log', {'message': 'Campo de entrada de CAPTCHA encontrado', 'level': 'info'})
            
            try:
                # Destaca o campo de entrada
                driver.execute_script("arguments[0].style.border = '3px solid red';", captcha_inputs[0])
                
                # Scoll para o campo
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_inputs[0])
                
                # Tenta encontrar e destacar a imagem do CAPTCHA próxima ao input
                driver.execute_script("""
                    const captchaInput = arguments[0];
                    const parent = captchaInput.closest('form') || captchaInput.parentElement;
                    
                    if (parent) {
                        // Procura por imagens no mesmo form/container
                        const images = parent.querySelectorAll('img');
                        for (let i = 0; i < images.length; i++) {
                            images[i].style.border = '3px solid blue';
                            images[i].scrollIntoView({block: 'center'});
                            return true;
                        }
                    }
                    return false;
                """, captcha_inputs[0])
                
                # Espera um momento para a página rolar
                time.sleep(1)
                
                # Captura screenshot
                screenshot = driver.get_screenshot_as_base64()
                captcha_image = f"data:image/png;base64,{screenshot}"
                
                captcha_local_path = str(STATIC_DIR / "captcha_area.png")
                driver.save_screenshot(captcha_local_path)
                
                # Emite evento para o cliente
                socketio.emit('captcha_detected', {'image': captcha_image})
                socketio.emit('log_message', {'message': 'Campo de CAPTCHA detectado. Por favor, verifique o screenshot e digite o código do CAPTCHA.', 'level': 'warning'})
                socketio.emit('server_log', {'message': 'Campo de CAPTCHA detectado - enviando screenshot da página completa', 'level': 'info'})
                
                captcha_visible = True
                in_captcha_page = True
                return True
            except Exception as highlight_err:
                socketio.emit('server_log', {'message': f'Erro ao destacar campo de CAPTCHA: {str(highlight_err)}', 'level': 'error'})
        
        # Método 4: Última tentativa - busca por imagens próximas a textos com "código"
        try:
            driver.execute_script("""
                // Busca por textos com "código" ou "code"
                const textNodes = [];
                const walker = document.createTreeWalker(
                    document.body, 
                    NodeFilter.SHOW_TEXT,
                    { acceptNode: function(node) { 
                        return (node.nodeValue.toLowerCase().includes('código') || 
                                node.nodeValue.toLowerCase().includes('code')) ? 
                                NodeFilter.FILTER_ACCEPT : 
                                NodeFilter.FILTER_REJECT; 
                    }},
                    false
                );
                
                while(walker.nextNode()) {
                    const node = walker.currentNode;
                    if (node.parentElement) {
                        node.parentElement.style.border = '2px dashed orange';
                        
                        // Busca por imagens próximas
                        const parent = node.parentElement.closest('div') || node.parentElement.parentElement;
                        if (parent) {
                            const images = parent.querySelectorAll('img');
                            for (let i = 0; i < images.length; i++) {
                                images[i].style.border = '4px solid green';
                                images[i].scrollIntoView({block: 'center'});
                            }
                        }
                    }
                }
            """)
            
            socketio.emit('server_log', {'message': 'Busca por textos contendo "código" ou "code" realizada', 'level': 'info'})
            
            # Espera um momento para a página rolar
            time.sleep(1)
            
            # Captura screenshot
            screenshot = driver.get_screenshot_as_base64()
            
            # Verifica se algo foi destacado antes de enviar
            has_highlights = driver.execute_script("""
                return document.querySelectorAll('[style*="border: 2px dashed orange"], [style*="border: 4px solid green"]').length > 0;
            """)
            
            if has_highlights:
                captcha_image = f"data:image/png;base64,{screenshot}"
                
                captcha_local_path = str(STATIC_DIR / "possible_captcha_area.png")
                driver.save_screenshot(captcha_local_path)
                
                # Emite evento para o cliente
                socketio.emit('captcha_detected', {'image': captcha_image})
                socketio.emit('log_message', {'message': 'Possíveis elementos relacionados a CAPTCHA encontrados. Verifique o screenshot e digite o código, se presente.', 'level': 'warning'})
                socketio.emit('server_log', {'message': 'Elementos com texto "código"/"code" encontrados - enviando screenshot', 'level': 'warning'})
                
                captcha_visible = True
                in_captcha_page = True
                return True
        except Exception as code_search_err:
            socketio.emit('server_log', {'message': f'Erro na busca por textos com "código": {str(code_search_err)}', 'level': 'error'})
        
        # Se chegou aqui, não encontrou CAPTCHA
        captcha_visible = False
        in_captcha_page = False
        socketio.emit('server_log', {'message': 'Nenhum CAPTCHA detectado na página', 'level': 'info'})
        return False
        
    except Exception as e:
        logger.error(f"Erro ao verificar CAPTCHA: {str(e)}")
        socketio.emit('server_log', {'message': f'Erro ao verificar CAPTCHA: {str(e)}', 'level': 'error'})
        return False

# Função para enviar o texto do CAPTCHA
def send_captcha_text(text):
    """Envia o texto do CAPTCHA para o campo apropriado no site."""
    try:
        # Procura pelo campo de input do CAPTCHA
        captcha_inputs = driver.find_elements(By.XPATH, "//input[contains(@id, 'captcha') or contains(@name, 'captcha')]")
        
        if captcha_inputs:
            # Preenche o campo com o texto
            captcha_input = captcha_inputs[0]
            captcha_input.clear()
            captcha_input.send_keys(text)
            logger.info(f"Texto do CAPTCHA '{text}' inserido no campo")
            
            # Busca o botão de envio
            submit_buttons = driver.find_elements(By.XPATH, "//button[@type='submit'] | //input[@type='submit'] | //button[contains(text(), 'Download')] | //button[contains(text(), 'Baixar')]")
            
            if submit_buttons:
                submit_buttons[0].click()
                logger.info("Botão de envio do CAPTCHA clicado")
                return True
            else:
                logger.warning("Botão de envio do CAPTCHA não encontrado")
                return False
        else:
            logger.warning("Campo de input do CAPTCHA não encontrado")
            return False
    except Exception as e:
        logger.error(f"Erro ao enviar texto do CAPTCHA: {str(e)}")
        return False

# Função para clicar no botão de download
def click_on_download_button():
    """Tenta clicar no botão de download no site do SICAR."""
    try:
        logger.info("Tentando clicar no botão de download...")
        
        # Primeiro, faz zoom out para ver toda a página
        driver.execute_script("document.body.style.zoom='80%'")
        time.sleep(1)
        
        # Aguarda para garantir que a página está carregada
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Lista de seletores possíveis para o botão de download
        download_button_selectors = [
            (By.ID, "btnDownloadShapefileUC"),
            (By.XPATH, "//button[contains(text(), 'Baixar Shapefile')]"),
            (By.XPATH, "//button[contains(text(), 'Download') and contains(text(), 'Shapefile')]"),
            (By.XPATH, "//a[contains(text(), 'Baixar Shapefile')]"),
            (By.XPATH, "//a[contains(@href, 'shapefile') or contains(@href, 'download')]"),
            (By.XPATH, "//button[contains(@onclick, 'shapefile') or contains(@onclick, 'download')]"),
            (By.XPATH, "//button[@title='Baixar shapefile']"),
            (By.XPATH, "//a[@title='Baixar shapefile']"),
            (By.XPATH, "//button[contains(@class, 'download')]"),
            (By.XPATH, "//a[contains(@class, 'download')]")
        ]
        
        logger.info(f"Procurando botão de download com {len(download_button_selectors)} seletores diferentes")
        
        # Tenta cada seletor
        for selector_type, selector_value in download_button_selectors:
            try:
                elements = driver.find_elements(selector_type, selector_value)
                if elements:
                    logger.info(f"Botão de download encontrado: {selector_type}={selector_value} - {len(elements)} elementos")
                    for i, element in enumerate(elements):
                        try:
                            logger.info(f"Tentando clicar no elemento {i+1}/{len(elements)}")
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", element)
                            time.sleep(1)  # Dá tempo para a página responder
                            
                            # Verifica se o clique resultou em um CAPTCHA
                            if check_for_captcha():
                                logger.info("CAPTCHA detectado após clicar no botão de download")
                                return True
                        except Exception as element_err:
                            logger.warning(f"Erro ao clicar no elemento {i+1}: {str(element_err)}")
            except Exception as click_error:
                logger.warning(f"Erro ao usar seletor {selector_value}: {str(click_error)}")
                continue
        
        logger.warning("Nenhum botão de download encontrado com os seletores específicos")
        
        # Captura os botões visíveis na página para debug
        try:
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            all_links = driver.find_elements(By.TAG_NAME, "a")
            
            logger.info(f"Total de botões na página: {len(all_buttons)}")
            logger.info(f"Total de links na página: {len(all_links)}")
            
            visible_buttons = [b for b in all_buttons if b.is_displayed()]
            visible_links = [a for a in all_links if a.is_displayed()]
            
            logger.info(f"Botões visíveis: {len(visible_buttons)}")
            logger.info(f"Links visíveis: {len(visible_links)}")
            
            for i, button in enumerate(visible_buttons[:10]):  # Limita a 10
                try:
                    logger.info(f"Botão {i+1}: texto='{button.text}', class='{button.get_attribute('class')}', id='{button.get_attribute('id')}'")
                except:
                    pass
        except Exception as debug_err:
            logger.error(f"Erro ao capturar botões para debug: {str(debug_err)}")
        
        # Tenta uma abordagem mais agressiva - clicar em todos os botões e links da página
        logger.info("Tentando abordagem agressiva: clicar em elementos relacionados a download")
        
        # Clica em elementos com texto ou atributos relacionados a download/shapefile
        try:
            # Centraliza elementos relacionados a download no texto ou atributos
            download_keywords = ["baixar", "download", "shapefile", "shape", "arquivo"]
            for keyword in download_keywords:
                elements = driver.find_elements(By.XPATH, 
                    f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}') or "
                    f"contains(translate(@title, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}') or "
                    f"contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}') or "
                    f"contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}')]")
                
                logger.info(f"Encontrados {len(elements)} elementos contendo '{keyword}'")
                
                for element in elements:
                    try:
                        if element.is_displayed():
                            logger.info(f"Clicando em elemento contendo '{keyword}': {element.tag_name}")
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", element)
                            time.sleep(1)
                            
                            if check_for_captcha():
                                logger.info(f"CAPTCHA detectado após clicar em elemento com '{keyword}'")
                                return True
                    except:
                        continue
        except Exception as e:
            logger.error(f"Erro na abordagem agressiva: {str(e)}")
        
        # Tenta simular a tecla Enter
        try:
            logger.info("Tentando simular a tecla Enter")
            active_element = driver.switch_to.active_element
            active_element.send_keys("\n")
            time.sleep(1)
            
            if check_for_captcha():
                logger.info("CAPTCHA detectado após pressionar Enter")
                return True
        except Exception as e:
            logger.error(f"Erro ao simular tecla Enter: {str(e)}")
        
        # Tenta executar JavaScript para encontrar o botão de download
        try:
            logger.info("Tentando encontrar botão via JavaScript")
            found = driver.execute_script("""
                const buttons = document.querySelectorAll('button, a');
                for (let i = 0; i < buttons.length; i++) {
                    const text = buttons[i].innerText.toLowerCase();
                    const title = (buttons[i].title || '').toLowerCase();
                    const className = (buttons[i].className || '').toLowerCase();
                    const id = (buttons[i].id || '').toLowerCase();
                    
                    if (text.includes('baixar') || text.includes('download') || 
                        text.includes('shapefile') || title.includes('baixar') || 
                        title.includes('download') || title.includes('shapefile') ||
                        className.includes('download') || id.includes('download')) {
                        
                        // Tenta clicar no elemento
                        buttons[i].click();
                        return true;
                    }
                }
                return false;
            """)
            
            if found:
                logger.info("Botão encontrado e clicado via JavaScript")
                time.sleep(1)
                
                if check_for_captcha():
                    logger.info("CAPTCHA detectado após abordagem JavaScript")
                    return True
        except Exception as js_err:
            logger.error(f"Erro na abordagem JavaScript: {str(js_err)}")
        
        logger.warning("Falha em todas as tentativas de clicar no botão de download")
        return False
    except Exception as e:
        logger.error(f"Erro geral ao tentar clicar no botão de download: {str(e)}")
        return False

# Função para obter o screenshot atual
def take_screenshot():
    """Tira um screenshot da página atual e retorna como base64."""
    global last_screenshot
    
    try:
        if not driver:
            logger.error("Driver não inicializado para capturar screenshot")
            return None
        
        screenshot = driver.get_screenshot_as_base64
        last_screenshot = f"data:image/png;base64,{screenshot}"
        
        # Salva o screenshot no diretório estático
        screenshot_path = str(STATIC_DIR / "browser_screenshot.png")
        driver.save_screenshot(screenshot_path)
        
        # Verifica por CAPTCHA após screenshot
        check_for_captcha()
        
        return last_screenshot
    except Exception as e:
        logger.error(f"Erro ao capturar screenshot: {str(e)}")
        return None

# Função especial para detecção forçada de CAPTCHA
def captcha_force_detection():
    """Método especial para forçar a detecção de CAPTCHA quando os métodos normais falham."""
    global captcha_image, captcha_visible, in_captcha_page
    
    try:
        # Verifica se o driver está ativo
        if not is_driver_alive():
            return False
            
        socketio.emit('server_log', {'message': 'Iniciando detecção forçada de CAPTCHA...', 'level': 'info'})
        
        # Tira um screenshot da página inteira primeiro
        full_screenshot = driver.get_screenshot_as_base64()
        full_captcha_image = f"data:image/png;base64,{full_screenshot}"
        
        # Salva o screenshot completo
        full_screenshot_path = str(STATIC_DIR / "forced_full_page.png")
        driver.save_screenshot(full_screenshot_path)
        
        # Busca avançada por CAPTCHAs específicos do SICAR
        found_captcha = False
        
        # Método 1: Busca por DIVS relacionadas a CAPTCHA
        captcha_div = driver.find_elements(By.XPATH, 
            "//div[contains(@id, 'captcha') or contains(@class, 'captcha') or contains(@id, 'CAPTCHA') or contains(@class, 'CAPTCHA')]")
            
        if captcha_div:
            socketio.emit('server_log', {'message': f'Encontrado div de CAPTCHA: {len(captcha_div)} elementos', 'level': 'success'})
            
            # Destaca todos os elementos encontrados
            for div in captcha_div:
                driver.execute_script("arguments[0].style.border = '5px solid green';", div)
                
                # Tenta encontrar uma imagem dentro desta div
                try:
                    img = div.find_element(By.TAG_NAME, "img")
                    driver.execute_script("arguments[0].style.border = '5px solid red';", img)
                    socketio.emit('server_log', {'message': 'Imagem encontrada dentro da div de CAPTCHA!', 'level': 'success'})
                    
                    # Tenta capturar esta imagem
                    try:
                        img_screenshot = img.screenshot_as_base64
                        captcha_image = f"data:image/png;base64,{img_screenshot}"
                        
                        # Salva a imagem
                        img_local_path = str(STATIC_DIR / "forced_captcha.png")
                        img.screenshot(img_local_path)
                        
                        # Emite evento para o cliente
                        socketio.emit('captcha_detected', {'image': captcha_image})
                        socketio.emit('server_log', {'message': 'Imagem de CAPTCHA capturada com sucesso!', 'level': 'success'})
                        
                        captcha_visible = True
                        in_captcha_page = True
                        found_captcha = True
                    except Exception as img_err:
                        socketio.emit('server_log', {'message': f'Erro ao capturar imagem: {str(img_err)}', 'level': 'error'})
                except:
                    socketio.emit('server_log', {'message': 'Nenhuma imagem encontrada na div de CAPTCHA', 'level': 'warning'})
            
            # Se não achou imagem específica, envia o screenshot da div
            if not found_captcha and captcha_div:
                try:
                    div_screenshot = captcha_div[0].screenshot_as_base64
                    captcha_image = f"data:image/png;base64,{div_screenshot}"
                    
                    # Salva o screenshot
                    div_local_path = str(STATIC_DIR / "forced_captcha_div.png")
                    captcha_div[0].screenshot(div_local_path)
                    
                    # Emite evento para o cliente
                    socketio.emit('captcha_detected', {'image': captcha_image})
                    socketio.emit('server_log', {'message': 'Screenshot da div de CAPTCHA enviado', 'level': 'success'})
                    
                    captcha_visible = True
                    in_captcha_page = True
                    found_captcha = True
                except Exception as div_err:
                    socketio.emit('server_log', {'message': f'Erro ao capturar div: {str(div_err)}', 'level': 'error'})
        
        # Método 2: Busca por iframes que possam conter CAPTCHA
        if not found_captcha:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                socketio.emit('server_log', {'message': f'Encontrados {len(iframes)} iframes na página', 'level': 'info'})
                
                # Verifica cada iframe
                for i, iframe in enumerate(iframes):
                    socketio.emit('server_log', {'message': f'Verificando iframe {i+1}...', 'level': 'info'})
                    
                    # Destaca o iframe
                    driver.execute_script("arguments[0].style.border = '3px dashed orange';", iframe)
                    
                    try:
                        # Tenta mudar para o iframe
                        driver.switch_to.frame(iframe)
                        
                        # Captura screenshot do conteúdo do iframe
                        iframe_screenshot = driver.get_screenshot_as_base64()
                        iframe_image = f"data:image/png;base64,{iframe_screenshot}"
                        
                        # Salva o screenshot
                        iframe_local_path = str(STATIC_DIR / f"iframe_{i}_content.png")
                        driver.save_screenshot(iframe_local_path)
                        
                        # Busca por imagens no iframe
                        iframe_images = driver.find_elements(By.TAG_NAME, "img")
                        if iframe_images:
                            socketio.emit('server_log', {'message': f'Encontradas {len(iframe_images)} imagens no iframe {i+1}', 'level': 'success'})
                            
                            # Destaca as imagens
                            for img in iframe_images:
                                driver.execute_script("arguments[0].style.border = '2px solid purple';", img)
                            
                            # Emite o conteúdo do iframe como CAPTCHA
                            socketio.emit('captcha_detected', {'image': iframe_image})
                            socketio.emit('server_log', {'message': f'Conteúdo do iframe {i+1} enviado como possível CAPTCHA', 'level': 'success'})
                            
                            captcha_visible = True
                            in_captcha_page = True
                            found_captcha = True
                        
                        # Volta para o contexto principal
                        driver.switch_to.default_content()
                    except Exception as iframe_err:
                        socketio.emit('server_log', {'message': f'Erro ao verificar iframe {i+1}: {str(iframe_err)}', 'level': 'error'})
                        # Garante que voltamos para o contexto principal
                        driver.switch_to.default_content()
        
        # Método 3: Se não encontrou nada específico, envia o screenshot completo como último recurso
        if not found_captcha:
            socketio.emit('server_log', {'message': 'Nenhum elemento específico de CAPTCHA encontrado. Enviando screenshot completo.', 'level': 'warning'})
            socketio.emit('captcha_detected', {'image': full_captcha_image})
            socketio.emit('log_message', {'message': 'Possível CAPTCHA na página. Por favor, localize e digite o código do CAPTCHA visível na imagem.', 'level': 'warning'})
            
            captcha_visible = True
            in_captcha_page = True
            found_captcha = True
        
        return found_captcha
        
    except Exception as e:
        socketio.emit('server_log', {'message': f'Erro na detecção forçada de CAPTCHA: {str(e)}', 'level': 'error'})
        return False

# Função para verificar se o driver ainda está ativo
def is_driver_alive():
    """Verifica se o driver Selenium ainda está respondendo."""
    global driver
    
    if not driver:
        return False
        
    try:
        # Tenta uma operação simples para verificar se o driver está respondendo
        driver.current_url
        return True
    except Exception:
        # Se qualquer exceção ocorrer, considera que o driver não está mais ativo
        logger.warning("Driver não está mais respondendo, marcando como inativo")
        driver = None
        socketio.emit('browser_status', {'active': False})
        socketio.emit('server_log', {'message': 'Conexão com o navegador perdida. Por favor, reinicie o navegador.', 'level': 'error'})
        socketio.emit('log_message', {'message': 'Conexão com o navegador perdida. Por favor, clique em "Iniciar Navegador" novamente.', 'level': 'error'})
        return False

# Função para verificar o driver ou iniciar novo se necessário
def check_driver():
    """Verifica se o driver está iniciado e responde, caso contrário tenta reiniciar."""
    global driver
    
    try:
        if not driver:
            logger.info("Driver não está inicializado")
            socketio.emit('server_log', {'message': 'Navegador não está inicializado', 'level': 'info'})
            socketio.emit('browser_status', {'active': False})
            return False
            
        # Verifica se o driver ainda está respondendo
        if not is_driver_alive():
            logger.warning("Driver parou de responder, fechando e reiniciando")
            socketio.emit('server_log', {'message': 'Navegador parou de responder, tentando reiniciar...', 'level': 'warning'})
            close_driver()
            return False
            
        return True
    except Exception as e:
        logger.error(f"Erro ao verificar driver: {str(e)}")
        socketio.emit('server_log', {'message': f'Erro ao verificar navegador: {str(e)}', 'level': 'error'})
        return False

# Rotas da API
@app.route('/')
def index():
    """Rota principal da aplicação."""
    return render_template('captcha_mirror.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve arquivos estáticos."""
    return send_from_directory(str(STATIC_DIR), filename)

@app.route('/captcha_image')
def serve_captcha():
    """Serve a imagem do CAPTCHA."""
    captcha_path = STATIC_DIR / "captcha.png"
    if captcha_path.exists():
        return send_from_directory(str(STATIC_DIR), "captcha.png")
    else:
        return "", 404

@app.route('/start_browser', methods=['POST'])
def start_browser():
    """Inicia o navegador SICAR."""
    global driver
    
    try:
        if driver:
            logger.warning("Tentativa de iniciar driver que já está em execução")
            return jsonify({'success': True, 'message': 'Navegador já está em execução'})
        
        # Configura o driver
        if not setup_selenium_driver():
            return jsonify({'success': False, 'error': 'Erro ao configurar driver do Selenium'})
        
        # Abre o navegador no SICAR
        if not open_sicar_browser():
            close_driver()
            return jsonify({'success': False, 'error': 'Erro ao abrir site do SICAR'})
        
        take_screenshot()
        socketio.emit('browser_status', {'active': True})
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Erro ao iniciar navegador: {str(e)}")
        # Garante que o driver é fechado em caso de erro
        if driver:
            close_driver()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/stop', methods=['POST'])
def stop_browser():
    """Para o navegador SICAR."""
    global driver, captcha_image, captcha_visible, in_captcha_page
    
    if not driver:
        return jsonify({'success': False, 'message': 'Navegador não está em execução'})
    
    if close_driver():
        # Reseta variáveis globais
        captcha_image = None
        captcha_visible = False
        in_captcha_page = False
        socketio.emit('browser_status', {'active': False})
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Erro ao fechar navegador'})

@app.route('/send_captcha', methods=['POST'])
def send_captcha():
    """Recebe o texto do CAPTCHA e o envia para o site."""
    if not driver:
        return jsonify({'success': False, 'error': 'Navegador não está inicializado'})
    
    if not in_captcha_page:
        return jsonify({'success': False, 'error': 'Não estamos em uma página com CAPTCHA'})
    
    data = request.json
    captcha_text = data.get('text', '')
    
    if not captcha_text:
        return jsonify({'success': False, 'error': 'Texto do CAPTCHA não fornecido'})
    
    if send_captcha_text(captcha_text):
        take_screenshot()  # Atualiza o screenshot após enviar o CAPTCHA
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Erro ao enviar texto do CAPTCHA'})

@app.route('/check_captcha_status', methods=['GET'])
def check_captcha_status():
    """Verifica o status atual do CAPTCHA."""
    return jsonify({
        'captcha_visible': captcha_visible, 
        'captcha_url': '/captcha_image?t=' + str(time.time()) if captcha_visible else None
    })

@app.route('/get_screenshot', methods=['GET'])
def get_screenshot():
    """Obtém o screenshot atual."""
    if not driver:
        return jsonify({'url': None, 'error': 'Navegador não está inicializado'})
    
    screenshot_url = take_screenshot()
    if screenshot_url:
        return jsonify({'url': screenshot_url})
    else:
        return jsonify({'url': None, 'error': 'Erro ao capturar screenshot'})

@app.route('/force_download_button', methods=['POST'])
def force_download_button():
    """Força um clique no botão de download."""
    if not driver:
        return jsonify({'success': False, 'message': 'Navegador não está inicializado'})
    
    if click_on_download_button():
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Não foi possível encontrar ou clicar no botão de download'})

@app.route('/check_driver', methods=['GET'])
def check_driver():
    """Verifica se o driver do navegador está ativo."""
    try:
        if driver:
            return jsonify({'active': True})
        else:
            return jsonify({'active': False})
    except Exception as e:
        return jsonify({'active': False, 'error': str(e)})

@app.route('/get_browser_status', methods=['GET'])
def get_browser_status():
    """Obtém o status atual do navegador."""
    return jsonify({'driver_active': driver is not None})

@app.route('/browser_click', methods=['POST'])
def browser_click():
    """Processa cliques no navegador."""
    if not driver:
        return jsonify({'success': False, 'error': 'Navegador não está inicializado'})
    
    try:
        # Obtém as coordenadas relativas do clique do JSON
        data = request.json
        rel_x = float(data.get('x', 0))
        rel_y = float(data.get('y', 0))
        
        # Obtém o tamanho atual da janela
        window_size = driver.get_window_size()
        window_width = window_size['width']
        window_height = window_size['height']
        
        # Converte para coordenadas absolutas
        abs_x = int(rel_x * window_width)
        abs_y = int(rel_y * window_height)
        
        logger.info(f"Tentando clicar em ({abs_x}, {abs_y})")
        
        # Tenta mover e clicar usando JavaScript
        try:
            # Executa script para clicar na posição
            driver.execute_script(f"""
                function simulateClick(x, y) {{
                    const element = document.elementFromPoint(x, y);
                    if (element) {{
                        const event = new MouseEvent('click', {{
                            view: window,
                            bubbles: true,
                            cancelable: true,
                            clientX: x,
                            clientY: y
                        }});
                        element.dispatchEvent(event);
                        return true;
                    }}
                    return false;
                }}
                return simulateClick({abs_x}, {abs_y});
            """)
            logger.info(f"Clique via JavaScript realizado em ({abs_x}, {abs_y})")
        except Exception as js_err:
            logger.error(f"Erro ao clicar via JavaScript: {str(js_err)}")
            
            # Se JavaScript falhar, tenta ActionChains
            try:
                # Executa o clique através do ActionChains
                actions = ActionChains(driver)
                actions.move_by_offset(abs_x, abs_y)
                actions.click()
                actions.perform()
                
                # Reseta a posição do mouse
                actions.move_by_offset(-abs_x, -abs_y)
                actions.perform()
                
                logger.info(f"Clique via ActionChains realizado em ({abs_x}, {abs_y})")
            except Exception as action_err:
                logger.error(f"Erro ao clicar via ActionChains: {str(action_err)}")
                
                # Tenta um terceiro método - encontrar elementos na área do clique
                try:
                    elements = driver.find_elements(By.XPATH, "//*")
                    for element in elements:
                        try:
                            location = element.location
                            size = element.size
                            elem_x = location['x']
                            elem_y = location['y'] 
                            width = size['width']
                            height = size['height']
                            
                            # Verifica se o clique foi dentro deste elemento
                            if (elem_x <= abs_x <= elem_x + width and 
                                elem_y <= abs_y <= elem_y + height):
                                element.click()
                                logger.info(f"Clique realizado em elemento na posição ({abs_x}, {abs_y})")
                                break
                        except:
                            continue
                except Exception as elem_err:
                    logger.error(f"Erro ao buscar elementos para clique: {str(elem_err)}")
        
        # Aguarda um momento para a página responder
        time.sleep(1)
        
        # Captura um novo screenshot após o clique
        take_screenshot()
        
        # Verifica se o clique resultou em um CAPTCHA
        captcha_detected = check_for_captcha()
        
        return jsonify({'success': True, 'captcha_detected': captcha_detected})
    except Exception as e:
        logger.error(f"Erro ao processar clique: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/force_download', methods=['POST'])
def force_download():
    """Rota para forçar o download do shapefile, mesmo sem detectar CAPTCHA."""
    global in_captcha_page
    
    # Verifica se o driver está ativo antes de prosseguir
    if not is_driver_alive():
        return jsonify({'success': False, 'message': 'Navegador não está respondendo. Por favor, reinicie o navegador.'})
    
    socketio.emit('server_log', {'message': 'Tentando forçar download do shapefile...', 'level': 'info'})
    
    try:
        # Primeiro tenta encontrar o botão de download
        download_buttons = []
        
        # Método 1: Busca por botão com texto "baixar", "download" ou "shapefile"
        try:
            buttons = driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'baixar') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'shapefile')]")
            download_buttons.extend(buttons)
            socketio.emit('server_log', {'message': f'Encontrados {len(buttons)} botões com texto para download', 'level': 'info'})
        except Exception as e:
            socketio.emit('server_log', {'message': f'Erro ao buscar botões por texto: {str(e)}', 'level': 'error'})
        
        # Método 2: Busca por links com os mesmos textos
        try:
            links = driver.find_elements(By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'baixar') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'shapefile')]")
            download_buttons.extend(links)
            socketio.emit('server_log', {'message': f'Encontrados {len(links)} links com texto para download', 'level': 'info'})
        except Exception as e:
            socketio.emit('server_log', {'message': f'Erro ao buscar links por texto: {str(e)}', 'level': 'error'})
        
        # Método 3: Busca por elementos com ID ou classe que contenha "download"
        try:
            id_elements = driver.find_elements(By.CSS_SELECTOR, "[id*='download'], [id*='baixar'], [class*='download'], [class*='baixar']")
            download_buttons.extend(id_elements)
            socketio.emit('server_log', {'message': f'Encontrados {len(id_elements)} elementos com ID/classe de download', 'level': 'info'})
        except Exception as e:
            socketio.emit('server_log', {'message': f'Erro ao buscar elementos por ID/classe: {str(e)}', 'level': 'error'})
            
        # Se encontrou botões, tenta clicar no primeiro
        if download_buttons:
            try:
                # Primeiro tenta rolar até o botão para garantir que esteja visível
                socketio.emit('server_log', {'message': 'Rolando até o botão de download...', 'level': 'info'})
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", download_buttons[0])
                time.sleep(1)
                
                # Tenta destacar visualmente o botão
                driver.execute_script("arguments[0].style.border = '3px solid red';", download_buttons[0])
                
                # Captura um screenshot antes de clicar
                button_screenshot = str(STATIC_DIR / "download_button.png")
                driver.save_screenshot(button_screenshot)
                socketio.emit('server_log', {'message': 'Screenshot capturado com o botão destacado', 'level': 'info'})
                
                # Tenta clicar no botão usando diferentes métodos
                try:
                    # Método 1: Clique normal
                    download_buttons[0].click()
                    socketio.emit('server_log', {'message': 'Clique normal realizado no botão de download', 'level': 'info'})
                except Exception as click_err:
                    socketio.emit('server_log', {'message': f'Erro no clique normal: {str(click_err)}', 'level': 'warning'})
                    
                    try:
                        # Método 2: Clique via JavaScript
                        driver.execute_script("arguments[0].click();", download_buttons[0])
                        socketio.emit('server_log', {'message': 'Clique via JavaScript realizado no botão de download', 'level': 'info'})
                    except Exception as js_click_err:
                        socketio.emit('server_log', {'message': f'Erro no clique via JavaScript: {str(js_click_err)}', 'level': 'warning'})
                        
                        try:
                            # Método 3: Actions chains
                            ActionChains(driver).move_to_element(download_buttons[0]).click().perform()
                            socketio.emit('server_log', {'message': 'Clique via ActionChains realizado no botão de download', 'level': 'info'})
                        except Exception as action_click_err:
                            socketio.emit('server_log', {'message': f'Erro no clique via ActionChains: {str(action_click_err)}', 'level': 'error'})
                            return jsonify({'success': False, 'message': 'Não foi possível clicar no botão de download'})
                
                # Marca que estamos em uma página que pode ter CAPTCHA
                in_captcha_page = True
                
                # Espera um pouco para que o CAPTCHA apareça
                socketio.emit('server_log', {'message': 'Aguardando possível aparecimento de CAPTCHA...', 'level': 'info'})
                time.sleep(3)
                
                # Forçar uma verificação imediata de CAPTCHA
                captcha_found = check_for_captcha()
                
                if captcha_found:
                    socketio.emit('server_log', {'message': 'CAPTCHA detectado após clique no botão de download!', 'level': 'success'})
                    return jsonify({'success': True, 'captcha_detected': True})
                else:
                    # Se não achou CAPTCHA, tenta usar captcha_force_detection especial
                    socketio.emit('server_log', {'message': 'CAPTCHA não detectado pelos métodos normais. Tentando detecção forçada...', 'level': 'warning'})
                    time.sleep(1)
                    captcha_found = captcha_force_detection()
                    
                    if captcha_found:
                        socketio.emit('server_log', {'message': 'CAPTCHA detectado após detecção forçada!', 'level': 'success'})
                        return jsonify({'success': True, 'captcha_detected': True})
                    else:
                        socketio.emit('server_log', {'message': 'Nenhum CAPTCHA detectado mesmo após detecção forçada', 'level': 'warning'})
                        return jsonify({'success': True, 'captcha_detected': False})
            
            except Exception as button_err:
                socketio.emit('server_log', {'message': f'Erro ao interagir com botão de download: {str(button_err)}', 'level': 'error'})
                return jsonify({'success': False, 'message': str(button_err)})
        
        else:
            # Se não encontrou botões, tenta usar JavaScript para verificar a página
            socketio.emit('server_log', {'message': 'Nenhum botão de download encontrado. Tentando busca avançada...', 'level': 'warning'})
            
            # Captura um screenshot da página
            page_screenshot = str(STATIC_DIR / "page_screenshot.png")
            driver.save_screenshot(page_screenshot)
            
            # Tenta usar JavaScript para encontrar elementos interativos
            driver.execute_script("""
                // Destaca todos os botões e links na página
                const elements = document.querySelectorAll('button, a');
                for (let i = 0; i < elements.length; i++) {
                    elements[i].style.border = '2px dashed blue';
                }
            """)
            
            # Captura screenshot com elementos destacados
            elements_screenshot = str(STATIC_DIR / "elements_screenshot.png")
            driver.save_screenshot(elements_screenshot)
            socketio.emit('server_log', {'message': 'Screenshot com elementos interativos destacados foi gerado', 'level': 'info'})
            
            # Força detecção de CAPTCHA mesmo sem clicar
            captcha_found = captcha_force_detection()
            
            if captcha_found:
                socketio.emit('server_log', {'message': 'CAPTCHA detectado após busca na página!', 'level': 'success'})
                return jsonify({'success': True, 'captcha_detected': True})
            else:
                socketio.emit('server_log', {'message': 'Nenhum botão de download ou CAPTCHA encontrado', 'level': 'error'})
                return jsonify({'success': False, 'message': 'Nenhum botão de download encontrado'})
    
    except Exception as e:
        socketio.emit('server_log', {'message': f'Erro ao forçar download: {str(e)}', 'level': 'error'})
        return jsonify({'success': False, 'message': str(e)})

# Rota para o navigate_to_douradina foi removida pois o botão foi removido da interface

# Função para monitorar continuamente o CAPTCHA
def monitor_captcha():
    """Thread para monitorar continuamente o CAPTCHA."""
    global driver
    
    logger.info("Iniciando thread de monitoramento de CAPTCHA")
    
    while True:
        try:
            if is_driver_alive():
                check_for_captcha()
            time.sleep(2)  # Verifica a cada 2 segundos
        except Exception as e:
            logger.error(f"Erro na thread de monitoramento: {str(e)}")
            time.sleep(5)  # Espera um pouco mais se houver erro

# Eventos SocketIO
@socketio.on('connect')
def handle_connect():
    """Trata a conexão de um cliente via WebSocket."""
    global client_count
    
    client_count += 1
    logger.info(f"Cliente conectado: {request.sid} (Total: {client_count})")
    emit('status_update', {'driver_active': driver is not None})
    
    # Verifica se já existe CAPTCHA
    if captcha_visible and captcha_image:
        emit('captcha_detected', {'image': captcha_image})

@socketio.on('disconnect')
def handle_disconnect():
    """Trata a desconexão de um cliente via WebSocket."""
    global client_count
    
    client_count = max(0, client_count - 1)
    logger.info(f"Cliente desconectado: {request.sid} (Restantes: {client_count})")

@socketio.on('ping_server')
def handle_ping():
    """Responde a pings do cliente para manter a conexão viva."""
    emit('pong_response', {'timestamp': time.time()})

# Inicialização
if __name__ == '__main__':
    try:
        # Inicia a thread de monitoramento de CAPTCHA
        monitoring_thread = threading.Thread(target=monitor_captcha, daemon=True)
        monitoring_thread.start()
        
        # Inicia o servidor
        port = 5001
        logger.info(f"Iniciando servidor na porta {port}")
        socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        logger.info("Encerrando aplicação por interrupção do teclado")
        if driver:
            close_driver()
    except Exception as e:
        logger.error(f"Erro ao iniciar aplicação: {str(e)}")
