# 🔧 Configuração Tesseract OCR

O erro **"tesseract is not installed or it's not in your PATH"** ocorre porque a biblioteca SICAR requer o Tesseract OCR para extrair dados de documentos. Este guia explica como configurar.

## 📋 Conteúdo

- [Windows](#windows)
- [Linux (Docker)](#linux--docker)
- [macOS](#macos)
- [Troubleshooting](#troubleshooting)

---

## Windows

### Opção 1: Instalador Automático (Recomendado)

1. **Download do Instalador**
   - Acesse: https://github.com/UB-Mannheim/tesseract/wiki
   - Clique no link do instalador `.exe` mais recente (ex: `tesseract-ocr-w64-setup-v5.x.x.exe`)

2. **Executar o Instalador**
   - Execute o `.exe` baixado
   - Escolha o local de instalação padrão: `C:\Program Files\Tesseract-OCR`

3. **Verificar Instalação**
   ```bash
   # Abra PowerShell e execute:
   tesseract --version
   ```
   
   Você deve ver a versão do Tesseract (ex: `tesseract 5.3.0`).

### Opção 2: Configurar Variável de Ambiente

Após instalar o Tesseract, defina a variável de ambiente `TESSERACT_PATH`:

**PowerShell:**
```powershell
[Environment]::SetEnvironmentVariable("TESSERACT_PATH", "C:\Program Files\Tesseract-OCR\tesseract.exe", "User")

# Reabra o terminal para a mudança surtir efeito
```

**Prompt de Comando:**
```cmd
setx TESSERACT_PATH "C:\Program Files\Tesseract-OCR\tesseract.exe"

REM Reabra o terminal
```

**Arquivo `.env` (Alternativa)**

Crie/edite o arquivo `.env` na raiz do projeto:
```env
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Opção 3: Instalação via Chocolatey

Se você tem Chocolatey instalado:

```powershell
choco install tesseract
```

---

## Linux / Docker

### ✅ Automático

O `Dockerfile` foi atualizado para instalar Tesseract automaticamente:

```dockerfile
RUN apt-get install -y tesseract-ocr
```

Basta reconstruir a imagem Docker:

```bash
docker-compose build
docker-compose up db
```

### Manual (se necessário)

```bash
# Debian/Ubuntu
apt-get install tesseract-ocr

# Red Hat/CentOS
yum install tesseract

# Alpine
apk add tesseract-ocr
```

---

## macOS

### Opção 1: Homebrew (Recomendado)

```bash
brew install tesseract
```

### Opção 2: MacPorts

```bash
sudo port install tesseract
```

### Verificar Instalação

```bash
tesseract --version
which tesseract
```

---

## Troubleshooting

### 1. Erro: "tesseract is not installed"

**Solução:**
- Verifique se o Tesseract está instalado:
  ```bash
  tesseract --version
  ```
  
- Se não aparecer, reinstale conforme o S.O.

### 2. Erro: pytesseract não consegue encontrar tesseract

**Solução:**

a) Definir variável de ambiente:
```bash
# Windows PowerShell
[Environment]::SetEnvironmentVariable("TESSERACT_PATH", "C:\Program Files\Tesseract-OCR\tesseract.exe", "User")

# Linux/macOS
export TESSERACT_PATH=/usr/bin/tesseract
```

b) Editar `.env`:
```env
TESSERACT_PATH=/caminho/para/tesseract
```

### 3. Erro com Idiomas Tesseract

Se precisar de dados de idiomas adicionais:

```bash
# Windows
# Baixe em: https://github.com/UB-Mannheim/tesseract/wiki
# Coloque arquivos .traineddata em: C:\Program Files\Tesseract-OCR\tessdata

# Linux
apt-get install tesseract-ocr-por  # Português
apt-get install tesseract-ocr-eng  # English
```

---

## 🧪 Verificar Funcionamento

### Teste Rápido

```python
import pytesseract
from PIL import Image

# Função de teste
try:
    img = Image.new('RGB', (100, 30), color='white')
    text = pytesseract.image_to_string(img)
    print("✅ Tesseract funcionando!")
except Exception as e:
    print(f"❌ Erro: {e}")
```

### Teste da Pipeline SICAR

```bash
cd data-ingestion
python main.py sicar
```

---

## 📚 Referências

- **Instalador Tesseract**: https://github.com/UB-Mannheim/tesseract/wiki
- **pytesseract Docs**: https://github.com/madmaze/pytesseract
- **Tesseract GitHub**: https://github.com/tesseract-ocr/tesseract

---

## ✅ Próximos Passos

Após configurar o Tesseract:

1. Reinstale dependências Python:
   ```bash
   pip install -r requirements.txt
   ```

2. Execute a pipeline SICAR:
   ```bash
   cd data-ingestion
   python main.py sicar
   ```

3. Se persistir o erro, verifique:
   - Variável de ambiente `TESSERACT_PATH` com `echo $TESSERACT_PATH`
   - Caminho da instalação do Tesseract
   - Permissões de leitura/execução no executável

