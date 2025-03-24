FROM python:3.11

WORKDIR /app

# Copia a pasta app e outros ficheiros necessários
COPY ./app /app


# Copia o requirements.txt se existir
COPY requirements.txt ./

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Expõe a porta padrão do Flask (ajuste conforme necessário)
EXPOSE 5000

# Comando de entrada
CMD ["python", "app.py"]
