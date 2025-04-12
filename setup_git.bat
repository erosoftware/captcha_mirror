@echo off
echo Configurando repositório Git para o CAPTCHA Mirror...

REM Verificar se já existe um .git na pasta
IF EXIST ".git" (
    echo Repositório Git já inicializado nesta pasta.
) ELSE (
    echo Inicializando novo repositório Git...
    git init
)

REM Criar .gitignore para arquivos que não devem ser versionados
echo Criando arquivo .gitignore...
echo __pycache__/ > .gitignore
echo *.pyc >> .gitignore
echo *.pyo >> .gitignore
echo *.pyd >> .gitignore
echo .Python >> .gitignore
echo env/ >> .gitignore
echo venv/ >> .gitignore
echo ENV/ >> .gitignore
echo .env >> .gitignore
echo .venv >> .gitignore
echo chromedriver.exe >> .gitignore
echo geckodriver.exe >> .gitignore
echo *.log >> .gitignore
echo static/*.png >> .gitignore
echo static/*.jpg >> .gitignore

REM Adicionar todos os arquivos ao stage
echo Adicionando arquivos ao controle de versão...
git add .

REM Fazer o commit inicial
echo Fazendo commit inicial...
git commit -m "Versão inicial do CAPTCHA Mirror para SICAR"

REM Configurar origin (ajuste a URL para o seu repositório)
echo Para conectar ao GitHub, execute os seguintes comandos:
echo.
echo git remote add origin https://github.com/SEU_USUARIO/captcha_mirror.git
echo git branch -M main
echo git push -u origin main
echo.
echo Configuração do Git concluída!
echo Verifique se você tem um repositório criado no GitHub antes de fazer push.
