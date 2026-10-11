import logging
import re

logger = logging.getLogger(__name__)


class MatchEngine:
    """
    Motor de casamento de padrões via Expressões Regulares (AOT - Ahead Of Time).
    Ignora a origem dos dados, trabalhando estritamente com primitivas em memória.
    """

    PRICE_REGEX = re.compile(
        r"(?i)(?:R\$)\s?"
        r"((?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{2})?)"
        r"(?![\d.,])"
    )

    def __init__(self) -> None:
        self._compiled_regex: re.Pattern[str] | None = None

    def _is_valid_regex(self, pattern: str) -> bool:
        """
        Garante que a entrada do usuário não possua sintaxe Regex quebrada
        que possa causar uma exceção de compilação.
        """
        try:
            re.compile(pattern)
            return True
        except re.error:
            return False

    def compile(self, keywords: set[str]) -> set[str]:
        """
        Recebe um conjunto de termos, valida-os e compila uma única árvore
        Regex global com boundaries (\b).

        Retorna:
            set[str]: Conjunto de termos malformados que falharam na compilação.
        """
        if not keywords:
            self._compiled_regex = None
            return set()
        valid_patterns: set[str] = set()
        invalid_patterns: set[str] = set()
        for keyword in keywords:
            normalized_pattern = re.sub(r"\s+", r"\\s+", keyword.strip().lower())
            if self._is_valid_regex(normalized_pattern):
                valid_patterns.add(normalized_pattern)
            else:
                invalid_patterns.add(keyword)
        num_valid = len(valid_patterns)
        if num_valid > 0:
            final_pattern = rf"\b({'|'.join(valid_patterns)})\b"
            self._compiled_regex = re.compile(final_pattern, re.IGNORECASE)
            logger.info(
                "Motor Regex compilado com %d padr%s ativo%s.",
                num_valid,
                "ões" if num_valid > 1 else "ão",
                "s" if num_valid > 1 else "",
            )
        else:
            self._compiled_regex = None
        return invalid_patterns

    def search(self, text: str) -> str | None:
        """
        Executa a busca do padrão no texto do Telegram em O(L)
        onde L é o tamanho do texto, não a quantidade de keywords.
        """
        if not self._compiled_regex or not text:
            return None
        match = self._compiled_regex.search(text)
        return match.group(0) if match else None

    def extract_price(self, text: str) -> float | None:
        """
        Extrai o preço do texto, se houver, e retorna como float.
        Suporta formatos como R$ 1234 ou 1.234,56 ou $1234,56.
        """
        match = self.PRICE_REGEX.search(text)
        if match is None:
            return None
        price_str = match.group(1).replace(".", "").replace(",", ".")
        try:
            return float(price_str)
        except ValueError:
            logger.warning("Falha ao converter preço extraído: %s", price_str)
            return None
