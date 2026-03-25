#!/usr/bin/env python3
"""
Orquestrador do ETL — executa todas as fontes em sequência.

Antes de rodar pela primeira vez, aplique as migrações do banco:
    alembic upgrade head

Uso:
    python etl/run_all.py
    python etl/run_all.py icmbio funai inpe    # fontes específicas
"""
import sys

sys.path.insert(0, ".")

SOURCES = {
    "icmbio": ("etl.sources.icmbio", "ICMBio - Unidades de Conservação"),
    "funai": ("etl.sources.funai", "FUNAI - Terras Indígenas"),
    "inpe": ("etl.sources.inpe", "INPE - Queimadas"),
    "incra": ("etl.sources.incra", "INCRA - Assentamentos Rurais"),
    "palmares": ("etl.sources.palmares", "Palmares - Territórios Quilombolas"),
}


def run_source(key: str):
    module_path, label = SOURCES[key]
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print("=" * 60)
    module = __import__(module_path, fromlist=["run"])
    module.run()


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(SOURCES.keys())

    invalid = [t for t in targets if t not in SOURCES]
    if invalid:
        print(f"[run_all] Fontes inválidas: {invalid}")
        print(f"[run_all] Disponíveis: {list(SOURCES.keys())}")
        sys.exit(1)

    failed = []
    for key in targets:
        try:
            run_source(key)
            print(f"\n[OK] {key}")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"\n[ERRO] {key}: {exc}")
            failed.append(key)

    print(f"\n{'=' * 60}")
    if failed:
        print(f"[RESUMO] Falhou: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"[RESUMO] Todos os ETLs concluídos com sucesso.")


if __name__ == "__main__":
    main()
