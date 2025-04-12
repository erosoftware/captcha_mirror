# Navegue até o diretório específico do captcha_mirror
cd C:\Users\Administrator\CascadeProjects\erosoftware\eroview\captcha

# Crie um arquivo .gitignore específico para o projeto captcha_mirror
$gitignoreContent = @"
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
ENV/
.env
.venv
chromedriver.exe
geckodriver.exe
*.log
static/*.png
static/*.jpg
"@

Set-Content -Path .gitignore -Value $gitignoreContent

# Inicialize o repositório Git (se ainda não foi feito)
& "C:\Program Files\Git\bin\git.exe" init

# Adicione todos os arquivos ao staging
& "C:\Program Files\Git\bin\git.exe" add .

# Faça o commit
& "C:\Program Files\Git\bin\git.exe" commit -m "Versão inicial do CAPTCHA Mirror para SICAR"

# Adicione o repositório remoto (se não estiver adicionado)
# Substitua 'erosoftware' pelo seu nome de usuário do GitHub se necessário
& "C:\Program Files\Git\bin\git.exe" remote add origin https://github.com/erosoftware/captcha_mirror.git

# Se já estiver adicionado e precisar atualizar, use:
# & "C:\Program Files\Git\bin\git.exe" remote set-url origin https://github.com/erosoftware/captcha_mirror.git

# Push para o repositório remoto
# Substitua 'SEU_TOKEN_AQUI' pelo seu token GitHub
& "C:\Program Files\Git\bin\git.exe" push -u origin master

# Mensagem informativa
Write-Host "Repositório para o CAPTCHA Mirror configurado com sucesso!" -ForegroundColor Green
Write-Host "OBSERVAÇÃO: Certifique-se de criar o repositório 'captcha_mirror' no GitHub antes de executar o push." -ForegroundColor Yellow
Write-Host "URL do repositório: https://github.com/erosoftware/captcha_mirror" -ForegroundColor Cyan
