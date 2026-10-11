import json
import logging
from pathlib import Path
from typing import cast

logger = logging.getLogger(__name__)


class KeywordStorage:
    """
    Orquestrador da leitura e gravação do arquivo JSON de palavras-chave, com validação e normalização.

    Estrutura em memória: dict[str, set[str]] onde a chave é o chat_id do usuário.
    Todas as operações de escrita são persistidas imediatamente no disco.
    """

    def __init__(self, file_path: Path) -> None:
        self._path = file_path
        self._cache: dict[str, set[str]] = {}
        self._load()

    def _sync(self) -> None:
        """Persiste os dados ordenados no disco de forma atômica/formatada."""
        try:
            payload = {user_id: sorted(terms) for user_id, terms in self._cache.items()}
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except (OSError, UnicodeError) as e:
            logger.error("Falha ao persistir dados em %s: %s", self._path, e)

    def _reset_cache(self, error: str, *args: object) -> None:
        """Reseta o cache para vazio e persiste no disco, registrando um aviso."""
        logger.warning(error + "\nInicializando cache vazio.", *args)
        self._cache = {}
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
            self._cache = {}
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
        if not isinstance(data, dict):
            self._reset_cache(
                "Formato inválido em %s: esperada um dicionário JSON "
                "{user_id: [termo1, termo2, ...]}, mas encontrado %s.",
                self._path,
                type(data).__name__,
            )
            return
        parsed_cache: dict[str, set[str]] = {}
        raw_dict = cast(dict[object, object], data)
        for raw_user, raw_terms in raw_dict.items():
            user_id = str(raw_user).strip()
            if not user_id:
                continue
            if not isinstance(raw_terms, list):
                logger.warning(
                    "Termos do usuário %s ignorados: esperado uma lista.", user_id
                )
                parsed_cache[user_id] = set()
                continue
            items = cast(list[object], raw_terms)
            parsed_cache[user_id] = {
                term
                for item in items
                if isinstance(item, str) and (term := item.strip().lower())
            }
        self._cache = parsed_cache
        self._sync()

    def add(self, user_id: str, raw_text: str) -> tuple[set[str], set[str]]:
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
        user_set = self._cache.setdefault(user_id, set())
        inserted = new_tokens.difference(user_set)
        ignored = new_tokens.intersection(user_set)
        if inserted:
            user_set.update(inserted)
            self._sync()
        return inserted, ignored

    def remove(self, user_id: str, keyword: str) -> bool:
        """Remove termo. Retorna True se o termo existia e foi removido."""
        if user_id not in self._cache:
            return False
        term = keyword.strip().lower()
        if term not in self._cache[user_id]:
            return False
        self._cache[user_id].remove(term)
        self._sync()
        return True

    def get_user_terms(self, user_id: str) -> set[str]:
        """Retorna uma cópia dos termos de um usuário específico em O(1)."""
        return self._cache.get(user_id, set()).copy()

    def get_all_users(self) -> dict[str, set[str]]:
        """Retorna uma cópia profunda de todos os usuários e seus conjuntos de termos."""
        return {uid: terms.copy() for uid, terms in self._cache.items()}

    def get_all_terms_flattened(self) -> set[str]:
        """Retorna a união de todos os termos cadastrados de todos os usuários."""
        return set[str]().union(*self._cache.values())
