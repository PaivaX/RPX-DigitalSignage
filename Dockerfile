FROM python:3.11

WORKDIR /app

# Copia o requirements.txt se existir (se não tiver, só pula isso)
COPY requirements.txt ./

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Exemplo de porta Django
EXPOSE 8000

# Comando de entrada
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
