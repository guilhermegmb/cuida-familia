
FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copia o projeto
COPY . .

# Expõe a porta usada pelo Render
EXPOSE 10000

# Comando de inicialização
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
