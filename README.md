# SICAR CAPTCHA Mirror

## Descrição
O SICAR CAPTCHA Mirror é uma interface facilitadora para download de shapefiles do Sistema de Cadastro Ambiental Rural (SICAR). A ferramenta atua como uma ponte entre o usuário e o site do SICAR, simplificando o processo de resolução de CAPTCHAs e download de arquivos.

## Funcionalidades
- Interface web amigável para interação com o site do SICAR
- Detecção automática de CAPTCHAs na página
- Exibição do CAPTCHA para resolução manual pelo usuário
- Gerenciamento simplificado de downloads
- Logs detalhados para depuração

## Como funciona
1. A aplicação abre uma sessão automatizada no site do SICAR
2. O usuário navega normalmente pelo site para encontrar a propriedade desejada
3. Quando um CAPTCHA é encontrado, a imagem é extraída e exibida na interface
4. O usuário (humano) digita os caracteres do CAPTCHA
5. A aplicação envia os caracteres para o site do SICAR
6. O download do shapefile é iniciado automaticamente

## Desafios e Limitações Conhecidas

### Detecção do CAPTCHA
Uma das principais limitações é a detecção confiável do CAPTCHA no site do SICAR. O sistema implementa múltiplas estratégias para identificar o CAPTCHA:

1. Busca direta por elementos `<img>` com "captcha" na URL
2. Busca por elementos de texto relacionados a CAPTCHA
3. Busca por campos de entrada com nome/ID "captcha"
4. Busca por textos contendo "código" ou "code"
5. Análise de iframes para possíveis CAPTCHAs

Mesmo com essas estratégias, alguns CAPTCHAs podem não ser detectados automaticamente devido a mudanças na estrutura do site ou carregamento dinâmico de elementos.

### Conformidade e Ética
Este software **NÃO viola** a proteção de CAPTCHA do site SICAR, pois:

- **Não realiza qualquer tipo de reconhecimento automatizado de caracteres**
- **Todos os CAPTCHAs são resolvidos manualmente por humanos**
- A ferramenta apenas facilita a visualização e inserção do CAPTCHA
- O usuário é responsável por identificar e digitar corretamente os caracteres

A ferramenta atua apenas como uma interface facilitadora, sem tentar burlar ou automatizar a resolução do CAPTCHA, respeitando assim o propósito do mecanismo de segurança.

## Requisitos
- Python 3.7+
- Flask
- Flask-SocketIO
- Selenium
- Chrome WebDriver

## Instalação
1. Clone este repositório
2. Instale as dependências: `pip install -r requirements.txt`
3. Execute o script: `python captcha_mirror.py`

## Uso
1. Acesse `http://localhost:5001` no navegador
2. Clique em "Iniciar Navegador"
3. Navegue até a propriedade desejada no SICAR
4. Quando encontrar um CAPTCHA, ele será exibido na interface (ou clique em "Forçar Baixar Shapefile")
5. Digite os caracteres do CAPTCHA e clique em "Enviar CAPTCHA"
6. O download do shapefile será iniciado automaticamente

## Suporte
Esta ferramenta foi desenvolvida para facilitar o acesso a dados públicos disponíveis no SICAR. 
Para problemas e sugestões, por favor abra uma issue no repositório.
