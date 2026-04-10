import sys
import os
import uuid

# 🔥 PRIMEIRO ajusta o path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

sys.path.append(os.path.join(BASE_DIR, 'data-ingestion'))
sys.path.append(BASE_DIR)

# 🔥 AGORA sim importa
from sources.sicar import SICARExtractor, SICARTransformer, SICARLoader
from infrastructure.repositories import MunicipioRepository
from sqlalchemy import create_engine

# =========================

DATABASE_URL = 'postgresql+psycopg2://codenine:sabotagem@localhost:5432/codeninedb'
engine = create_engine(DATABASE_URL)

SICAR_FILE = './data/sicar/SP'

municipio_repo = MunicipioRepository(engine)

extractor = SICARExtractor(SICAR_FILE, state_code='SP')
extracted = extractor.extract()

transformer = SICARTransformer(municipio_repo)
records = [transformer.transform_feature(f) for f in extracted.rows]

dataset_id = str(uuid.uuid4())

loader = SICARLoader(engine)
loader.load(records, dataset_id)

print("✅ Dados SICAR carregados!")