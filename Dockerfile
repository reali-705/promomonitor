FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Cria um usuário não-root bloqueado para login
RUN useradd -m -U -s /bin/false appuser

WORKDIR /app

# Copia as definições de dependências e os metadados exigidos pelo hatchling
COPY pyproject.toml uv.lock README.md ./

# Instala EXCLUSIVAMENTE as dependências de terceiros (cache agressivo de camadas)
RUN uv sync --frozen --no-dev --no-install-project

# Copia o código-fonte
COPY promomonitor/ ./promomonitor/

# Instala o pacote raiz promomonitor no ambiente virtual
RUN uv sync --frozen --no-dev

# Transfere a propriedade de todo o diretório /app para o usuário seguro
RUN chown -R appuser:appuser /app

# Rebaixa os privilégios do container a partir desta linha
USER appuser

# O CMD invoca o binário gerado na .venv através do executor do uv
CMD ["uv", "run", "--no-dev", "promomonitor"]