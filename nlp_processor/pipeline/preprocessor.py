import re
import unicodedata
from abc import ABC, abstractmethod
from typing import Dict, List, Set, Tuple
import spacy
from spellchecker import SpellChecker

_LEXICO_DOMINIO: Set[str] = {
    "desmatamento", "desmatamentos", "desmatado", "desmatada", "desmatados",
    "desmatadas", "desmatar", "desmata", "desmatam", "desmatou", "desmataram",
    "supressao", "queimada", "queimadas", "queimar", "queimou", "queimaram",
    "incendio", "incendios", "foco", "focos", "fogo",
    "ranking", "bioma", "biomas",
    "sobreposicao", "sobreposicoes", "sobreposto", "sobrepostos", "sobreposta",
    "sobrepostas", "sobrepoe", "sobrepoem", "sobrepor",
    "intersecao", "interseccao", "intersecoes", "interseccoes",
    "intersecta", "intersectam", "cruzamento",
    "assentamento", "assentamentos", "quilombola", "quilombolas", "quilombo",
    "quilombos", "indigena", "indigenas", "conservacao", "municipio",
    "municipios", "homologada", "delimitada", "declarada",
}


# ==========================================
# INTERFACES BASE (Princípio SOLID - OCP)
# ==========================================

class TextTransformationStep(ABC):
    """Classe base abstrata para representar uma etapa modular no pipeline real."""
    @abstractmethod
    def transform(self, text: str) -> str:
        pass


# ==========================================
# ETAPAS CUSTOMIZADAS E PROTOCOLOS DE NEGÓCIO
# ==========================================

class CommaLabeler(TextTransformationStep):
    """
    Substitui temporariamente as vírgulas pelo rótulo 'chavevirg' para proteger
    números decimais (ex: 5,70) e evitar conflitos com ferramentas léxicas.
    """
    def __init__(self, reverse: bool = False) -> None:
        self._reverse = reverse
        self._token = "chavevirg"

    def transform(self, text: str) -> str:
        if not self._reverse:
            # Substituição inicial (Passo 1)
            return text.replace(",", self._token)
        # Reversão pós-normalização (Passo 6)
        return text.replace(self._token, ",")


class EmojiTransformer(TextTransformationStep):
    """Substitui emojis e emoticons comuns por rótulos de texto padronizados (Passo 3)."""
    def __init__(self) -> None:
        self._emoji_regex = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
        self._emoji_map = {
            # --- POSITIVOS E AGRADECIMENTOS ---
            "😀": "emojipositivo", "😃": "emojipositivo", "😄": "emojipositivo", 
            "😁": "emojipositivo", "😆": "emojipositivo", "🥰": "emojipositivo", 
            "😍": "emojipositivo", "😊": "emojipositivo", "😇": "emojipositivo",
            "🙂": "emojipositivo", "🙃": "emojipositivo", "😉": "emojipositivo",
            "😋": "facesavoringfood", "👍": "emojipositivo", "👏": "emojipositivo",
            "🙌": "emojipositivo", "🤝": "emojipositivo", "✅": "emojipositivo",
            "♥": "emojipositivo", "❤️": "emojipositivo", "🎉": "emojipositivo",
            " obrigada": " obrigado", # Pequeno ajuste extra útil de gênero
            
            # --- EMOTICONS CLÁSSICOS POSITIVOS ---
            ":)": "emojipositivo", ":-)": "emojipositivo", "(:": "emojipositivo",
            "-->": "emojipositivo", "=: )": "emojipositivo", "xd": "emojipositivo",
            
            # --- NEGATIVOS, PREOCUPAÇÃO E RECLAMAÇÃO ---
            "🙁": "emojinegativo", "☹️": "emojinegativo", "😮": "emojinegativo",
            "😲": "emojinegativo", "😳": "emojinegativo", "😰": "emojinegativo",
            "😥": "emojinegativo", "😢": "emojinegativo", "😭": "emojinegativo",
            "😱": "emojinegativo", "😖": "emojinegativo", "😣": "emojinegativo",
            "😞": "emojinegativo", "😓": "emojinegativo", "😩": "emojinegativo",
            "😫": "emojinegativo", "🥱": "emojinegativo", "😤": "emojinegativo",
            "😡": "emojinegativo", "😠": "emojinegativo", "🤬": "emojinegativo",
            "👎": "emojinegativo", "❌": "emojinegativo", "⚠️": "emojinegativo",
            "🚨": "emojinegativo",
            
            # --- EMOTICONS CLÁSSICOS NEGATIVOS ---
            ":(": "emojinegativo", ":-(": "emojinegativo", "):": "emojinegativo",
            ":/": "emojinegativo", ":-\\": "emojinegativo", ":|": "emojinegativo",
            
            # --- ELEMENTOS DO ESCOPO AMBIENTAL / GEO (Útil para o RAG/Imóveis) ---
            "🔥": "queimada incendio",  # Ajuda diretamente na intenção buscar_queimadas!
            "🌳": "arvore floresta",
            "🌱": "vegetacao planta",
            "🚜": "fazenda trator",
            "🗺️": "mapa dadosgeo",
            "📍": "localizacao coordenada",
            "🏢": "empresa governanca"
        }
    def transform(self, text: str) -> str:
# 1. Primeiro, substitui os emojis conhecidos que trazem valor para as intenções
        for emoji, tag in self._emoji_map.items():
            text = text.replace(emoji, tag)
            
        # 2. Emoticons de texto (ex: :) ou :() não entram no regex unicode, 
        # mas como já foram substituídos no passo acima, estão seguros.
        
        # 3. Varre o texto com a Regex e remove QUALQUER outro emoji que não foi mapeado
        text_cleaned = self._emoji_regex.sub("", text)
        
        # Remove espaços duplos remanescentes caso o emoji estivesse isolado entre espaços
        return re.sub(r"\s+", " ", text_cleaned).strip()


class UserAnonymizer(TextTransformationStep):
    """
    Anonimiza menções a usuários (@usuario) gerando rótulos sequenciais estáveis.
    Garante conformidade com privacidade e remove ruído do classificador (Passo 4).
    """
    def __init__(self) -> None:
        self._user_vault: Dict[str, str] = {}
        self._user_counter = 0

    def transform(self, text: str) -> str:
        mentions = re.findall(r"@\w+", text)
        for mention in mentions:
            if mention not in self._user_vault:
                self._user_counter += 1
                self._user_vault[mention] = f"@user{self._user_counter}"
            text = text.replace(mention, self._user_vault[mention])
        return text


class URLStripper(TextTransformationStep):
    """Remove URLs completas e protocolos web (Passo 5)."""
    def transform(self, text: str) -> str:
        url_pattern = r"https?://\s*\S+|www\.\s*\S+"
        return re.sub(url_pattern, "", text).strip()


class SpellingAndEnelvoCorrector(TextTransformationStep):
    """
    Simula e executa a normalização ortográfica de gírias, abreviações e erros (Passo 2).
    Protege termos críticos extraídos dos 400 exemplos de treino do sistema.
    """
    # Código CAR do SICAR (ex: SP-3500709-F80A461130164CF9A0B0FEAB5611FA40)
    # Deve ser detectado ANTES do corretor ortográfico para preservar os hifens
    _CAR_CODE_RE = re.compile(r"[A-Za-z]{2}-\d{5,7}-[A-Za-z0-9]{6,}")

    def __init__(self, protected_terms: Set[str]) -> None:
        self.spell = SpellChecker(language="pt")
        self.protected_terms = {term.lower() for term in protected_terms}
        # Garante que o corretor não altere os termos técnicos do sistema real
        self.spell.word_frequency.load_words(list(self.protected_terms))

        # Mapa de abreviações e internetês comuns (Padrão Enelvo)
        self._abbreviation_map = {
            "vc": "voce", "pq": "porque", "q": "que", "ta": "esta", "tbm": "tambem",
            "gostei mt": "gostei muito", "hj": "hoje", "qq": "qualquer"
        }

    def transform(self, text: str) -> str:
        # Normalização inicial de contrações textuais
        for abbrev, full_word in self._abbreviation_map.items():
            text = re.sub(r"\b" + abbrev + r"\b", full_word, text)

        words = text.split()
        corrected_words: List[str] = []

        for word in words:
            # Preserva código CAR do SICAR intacto (hifens são parte do formato oficial)
            car_match = self._CAR_CODE_RE.search(word)
            if car_match:
                corrected_words.append(car_match.group(0))
                continue

            # Limpa caracteres estruturais para validação ortográfica
            clean_word = re.sub(r"[^\w]", "", word).lower()
            # Se a palavra contiver "emoji", "chavevirg" ou for um termo técnico do sistema, o corretor IGNORA-A (não mexe, não apaga)
            if clean_word in self.protected_terms or "emoji" in clean_word or "chavevirg" in clean_word or len(clean_word) <= 3 or word != word.lower():
                corrected_words.append(word)
            else:
                correction = self.spell.correction(clean_word)
                corrected_words.append(correction if correction else word)

        return " ".join(corrected_words)


class AdvancedSpecialCharacterFilter(TextTransformationStep):
    """
    Remove pontuações gerais, mas PRESERVA cirurgicamente:
    Hashtags (#), datas (20/05) e números com vírgulas já restaurados (5,70) (Passo 7).
    """
    # Código CAR do SICAR: UF-CODIBGE-HASH (ex: SP-3500709-F80A461130164CF9A0B0FEAB5611FA40)
    # Usa search para tolerar pontuação colada no final (ex: "SP-3500709-...?")
    _CAR_CODE_RE = re.compile(r"[A-Za-z]{2}-\d{5,7}-[A-Za-z0-9]{6,}")

    def transform(self, text: str) -> str:
        words = text.split()
        cleaned_words = []
        for word in words:
            # Preserva código CAR do SICAR intacto (hifens são parte do formato oficial)
            car_match = self._CAR_CODE_RE.search(word)
            if car_match:
                cleaned_words.append(car_match.group(0))
                continue

            # Detecção de Padrões Reais (Datas, Hashtags, Decimais)
            is_date = bool(re.search(r"\d+/\d+", word))
            is_decimal = bool(re.search(r"\d+,\d+", word))
            is_hashtag = word.startswith("#")

            if is_hashtag or is_date or is_decimal:
                # Remove pontuações coladas no final (ex: "20/05?" -> "20/05")
                cleaned_word = re.sub(r"[.!?;:]+$", "", word)
                cleaned_words.append(cleaned_word)
            else:
                # Remoção de acentos com unicodedata para normalização uniforme (Opcional avançado)
                # Mantém letras, números e marcadores específicos como @
                word_normalized = "".join(
                    c for c in unicodedata.normalize("NFD", word)
                    if unicodedata.category(c) != "Mn"
                )
                cleaned_word = re.sub(r"[^a-zA-Z0-9@#,\s]", "", word_normalized)
                if cleaned_word:
                    cleaned_words.append(cleaned_word)

        return " ".join(cleaned_words)


# ==========================================
# UTILITÁRIO DE NORMALIZAÇÃO LEVE
# ==========================================

def normalizar(texto: str) -> str:
    """Normalização rápida para dados internos: lowercase, remove acentos e pontuação."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s\-/]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


# ==========================================
# ORQUESTRADOR PRINCIPAL DO PIPELINE (Facade)
# ==========================================

class AdvancedGeoASGPreprocessor:
    """
    Orquestrador robusto que executa as transformações léxicas (Passos 1 a 7)
    e análises linguísticas avançadas do spaCy (Passos 8 e 9).
    """
    def __init__(self) -> None:
        # Carrega o modelo em português para POS Tagging e Parsing Sintático
        self.nlp = spacy.load("pt_core_news_sm", disable=["parser", "ner"])
        
        # Vocabulário protegido: siglas, acrônimos e termos técnicos do domínio ambiental/geoespacial de SP.
        # Impede que o corretor ortográfico altere ou remova estes termos.
        self.system_vocabulary: Set[str] = {
            # --- Cadastros e sistemas de registro ---
            "car", "sicar", "sigef", "cnir", "ccir", "nirf",

            # --- Programas e sistemas de monitoramento ---
            "prodes", "deter", "inpe", "bdqueimadas", "terraclass", "mapbiomas",

            # --- Satélites e sensores ---
            "aqua", "terra", "viirs", "modis", "goes", "noaa", "npp", "suomi",
            "landsat", "sentinel", "msg", "metop", "cbers",

            # --- Órgãos federais ---
            "ibama", "incra", "funai", "ibge", "ana", "mma", "icmbio", "abi",

            # --- Órgãos e secretarias estaduais de SP ---
            "cetesb", "daee", "itesp", "sima", "semil", "saa", "sabesp",
            "datageo", "cbrn", "igc", "igesp",

            # --- Programas ambientais ---
            "pra", "psf", "snuc", "cnuc", "fnc", "rppca",

            # --- Categorias de unidades de conservação (SNUC) ---
            "uc", "apa", "resex", "rebio", "flona", "rppn", "esec", "parna",
            "mona", "arie", "rds", "rva", "flota", "pe", "ee",

            # --- Categorias geopolíticas / administrativas ---
            "ra", "sp", "rmsp", "rmbs", "rmc", "rmvp", "ugrhi", "cbh",

            # --- Tipologias fundiárias ---
            "ti", "uc", "pa", "rl", "app", "car",

            # --- Biomas e vegetação ---
            "atlantica", "cerrado", "caatinga", "pampa", "pantanal", "amazonia", "bioma",
            "ciliar", "riparia",

            # --- Órgãos e entidades do 3º setor / legislação ---
            "fcp", "conama", "sma", "mpa", "incra", "itesp", "funbio",

            # --- Termos técnicos curtos protegidos ---
            "wfs", "wms", "gis", "sig", "pid", "shp", "kml", "geojson",
        }

        self.system_vocabulary.update(_LEXICO_DOMINIO)

        # Customização de Stopwords Críticas para Dados Ambientais / Geoespaciais de SP
        # Impedimos que "de", "do", "da" (essenciais para nomes de cidades e termos como "Área de Preservação") sumam.
        self.critical_geo_particles = {"de", "da", "do"}
        for word in self.critical_geo_particles:
            self.nlp.vocab[word].is_stop = False

        # Instanciação das etapas seguindo o Single Responsibility Principle (SRP)
        self._comma_injector = CommaLabeler(reverse=False)
        self._enelvo_corrector = SpellingAndEnelvoCorrector(protected_terms=self.system_vocabulary)
        self._emoji_parser = EmojiTransformer()
        self._anonymizer = UserAnonymizer()
        self._url_stripper = URLStripper()
        self._comma_restorer = CommaLabeler(reverse=True)
        self._character_cleaner = AdvancedSpecialCharacterFilter()

    def process(self, raw_text: str, remove_stopwords: bool = True) -> Dict[str, any]:
        """Processa o texto de ponta a ponta através de todas as camadas estruturais."""
        
        # --- CAMADA LÉXICA / ENGENHARIA DE REGRAS (Passos 1 ao 7) ---
        t1 = self._comma_injector.transform(raw_text)
        t2 = self._enelvo_corrector.transform(t1)
        t3 = self._emoji_parser.transform(t2)
        t4 = self._anonymizer.transform(t3)
        t5 = self._url_stripper.transform(t4)
        t6 = self._comma_restorer.transform(t5)
        normalized_text = self._character_cleaner.transform(t6)

        # --- CAMADA DE INTELIGÊNCIA LINGUÍSTICA (spaCy - Passos 8 e 9 + Avançado) ---
        doc = self.nlp(normalized_text)
        
        tokens: List[str] = []
        lemmas: List[str] = []
        part_of_speech: List[Tuple[str, str]] = []
        syntactic_dependencies: List[Dict[str, str]] = []

        for token in doc:
            if token.is_space:
                continue
                
            # Tokenização Avançada (Passo 9) - Mantém coesão de datas e decimais
            tokens.append(token.text)
            
            # Análise de Classes Gramaticais (POS Tagging)
            part_of_speech.append((token.text, token.pos_))
            
            # Parsing Sintático / Árvore de Dependências (Advanced Preprocessing)
            syntactic_dependencies.append({
                "token": token.text,
                "dependency_role": token.dep_,
                "head_word": token.head.text
            })

            # Remoção Condicional de Stopwords (Passo 8) + Lematização Integrada
            if remove_stopwords:
                if not token.is_stop:
                    lemmas.append(token.lemma_.lower())
            else:
                lemmas.append(token.lemma_.lower())

        return {
            "text_for_classifier": " ".join(lemmas),
            "text_for_entities_and_rag": normalized_text,
            "tokens": tokens,                                         
            "part_of_speech": part_of_speech,                         
            "syntactic_parsing": syntactic_dependencies,               
            "language_detected": "pt"                                 
        }