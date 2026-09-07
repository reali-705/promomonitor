import json
import logging
from pathlib import Path
from typing import cast

logger = logging.getLogger(__name__)


class KeywordStorage:
    """
    Orquestrador da leitura e gravação do arquivo JSON de palavras-chave, com validação e normalização.

    O arquivo é carregado na inicialização e mantido em memória. Todas as operações de adição/remoção
    são persistidas imediatamente no disco.
    """

    def __init__(self, file_path: Path) -> None:
        self._path = file_path
        self._cache: set[str] = set()
        self._load()

    def _sync(self) -> None:
        """Persiste os dados ordenados no disco de forma atômica/formatada."""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(sorted(self._cache), f, ensure_ascii=False, indent=2)
        except (OSError, UnicodeError) as e:
            logger.error("Falha ao persistir dados em %s: %s", self._path, e)

    def _reset_cache(self, error: str, *args: object) -> None:
        """Reseta o cache para vazio e persiste no disco, registrando um aviso."""
        logger.warning(error + "\nInicializando cache vazio.", *args)
        self._cache = set()
        self._sync()

    def _load(self) -> None:
        """
        Carrega e valida o arquivo JSON.

        Cria um vazio caso não exista ou seja inválido.
        Normaliza os termos para minúsculas e remove duplicatas.
        """
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except FileNotFoundError:
            logger.info(
                "Arquivo de palavras-chave não encontrado em %s.",
                self._path,
            )
            self._sync()
            return
        except (OSError, UnicodeError) as exc:
            logger.error(
                "Erro ao ler o arquivo de palavras-chave em %s: %s.",
                self._path,
                exc,
            )
            self._cache = set()
            self._sync()
            return
        if not content:
            self._reset_cache(
                "Arquivo de palavras-chave em %s está vazio.",
                self._path,
            )
            return
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            self._reset_cache(
                "JSON inválido no arquivo de palavras-chave em %s: %s.",
                self._path,
                exc,
            )
            return
        if not isinstance(data, list):
            self._reset_cache(
                "Formato inválido em %s: esperada uma lista JSON.",
                self._path,
            )
            return
        items = cast(list[object], data)
        invalid_items = sum(not isinstance(item, str) for item in items)
        valid_terms = {
            term
            for item in items
            if isinstance(item, str) and (term := item.strip().lower())
        }
        if invalid_items:
            logger.warning(
                "%d item(ns) inválido(s) foram ignorados em %s; "
                "esperadas apenas strings.",
                invalid_items,
                self._path,
            )
        self._cache = valid_terms
        self._sync()

    def add(self, raw_text: str) -> tuple[set[str], set[str]]:
        """
        Processa string separada por vírgula usando operações matemáticas de conjuntos.
        Retorna tupla (inseridos, ignorados).
        """
        new_tokens = {
            cleaned
            for token in raw_text.split(",")
            if (cleaned := token.strip().lower())
        }
        if not new_tokens:
            return set(), set()
        inserted_set = new_tokens.difference(self._cache)
        ignored_set = new_tokens.intersection(self._cache)
        if inserted_set:
            self._cache.update(inserted_set)
            self._sync()
        return inserted_set, ignored_set

    def remove(self, keyword: str) -> bool:
        """Remove termo. Retorna True se o termo existia e foi removido."""
        term = keyword.strip().lower()
        if term not in self._cache:
            return False
        self._cache.remove(term)
        self._sync()
        return True

    def get_all(self) -> set[str]:
        """Retorna uma cópia do conjunto de palavras-chave."""
        return self._cache.copy()
