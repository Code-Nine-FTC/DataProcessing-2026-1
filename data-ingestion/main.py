#!/usr/bin/env python
"""
Entry Point - Script principal para executar pipelines ETL
"""
import sys
import logging
import argparse

# Setup paths
sys.path.insert(0, str(sys.path[0]))

from core.config import AppConfig
from core.exceptions import PipelineException
from etl.orchestrator import PipelineOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Todas as pipelines ETL em sources/ (exceto relacoes_espaciais, só pós-processamento).
# Ordem: federais (WFS) → estadual SP → CAR → focos INPE.
DEFAULT_PIPELINE_ORDER = [
    "icmbio",
    "funai",
    "incra",
    "palmares",
    "datageo_sp",
    "car",
    "inpe",
    "prodes_desmatamento",
]


def main():
    parser = argparse.ArgumentParser(
        description="ETL Pipeline Orchestrator - Data Processing System"
    )

    parser.add_argument(
        "pipelines",
        nargs="*",
        help="Specific pipelines to run. If empty, runs all in default order.",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available pipelines",
    )

    parser.add_argument(
        "--order",
        action="store_true",
        help="Show default execution order",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Load configuration
    config = AppConfig.from_env()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    # Create orchestrator
    orchestrator = PipelineOrchestrator(config)
    try:
        from sources.icmbio import create_pipeline as create_icmbio
        from sources.funai import create_pipeline as create_funai
        from sources.incra import create_pipeline as create_incra
        from sources.palmares import create_pipeline as create_palmares
        from sources.datageo_sp import create_pipeline as create_datageo_sp
        from sources.car import create_pipeline as create_car
        from sources.inpe import create_pipeline as create_inpe
        from sources.prodes_desmatamento import create_pipeline as create_prodes_desmatamento

        orchestrator.register_pipeline("icmbio", create_icmbio)
        orchestrator.register_pipeline("funai", create_funai)
        orchestrator.register_pipeline("incra", create_incra)
        orchestrator.register_pipeline("palmares", create_palmares)
        orchestrator.register_pipeline("datageo_sp", create_datageo_sp)
        orchestrator.register_pipeline("car", create_car)
        orchestrator.register_pipeline("inpe", create_inpe)
        orchestrator.register_pipeline("prodes_desmatamento", create_prodes_desmatamento)

    except ImportError as e:
        logger.error(f"Failed to import pipeline: {str(e)}")
        orchestrator.close()
        sys.exit(1)

    registered = set(orchestrator.pipelines.keys())
    missing_default = [n for n in DEFAULT_PIPELINE_ORDER if n not in registered]
    if missing_default:
        logger.error(
            "DEFAULT_PIPELINE_ORDER referencia pipelines não registradas: %s",
            missing_default,
        )
        orchestrator.close()
        sys.exit(1)
    extra_registered = sorted(registered - set(DEFAULT_PIPELINE_ORDER))
    if extra_registered:
        logger.warning(
            "Há pipelines registradas fora de DEFAULT_PIPELINE_ORDER: %s — "
            "não entram no `python main.py` sem argumentos; inclua-as na lista ou passe por CLI.",
            extra_registered,
        )

    try:
        # Handle CLI commands
        if args.list:
            print("\nAvailable pipelines:")
            for name in sorted(orchestrator.pipelines.keys()):
                print(f"  • {name}")
            return

        if args.order:
            print("\nDefault execution order (todas as fontes em sources/):")
            for i, name in enumerate(DEFAULT_PIPELINE_ORDER, 1):
                print(f"  {i}. {name}")
            print(
                "\nApós essas pipelines, roda o pós-processamento espacial (rel_imovel_*), "
                "se definiu DATABASE_URL e a execução teve sucesso."
            )
            return

        # Run pipelines
        if args.pipelines:
            unknown = [p for p in args.pipelines if p not in orchestrator.pipelines]
            if unknown:
                logger.error(f"Pipelines desconhecidas: {unknown}. Use --list para ver disponíveis.")
                sys.exit(1)
            logger.info(f"Running specific pipelines: {', '.join(args.pipelines)}")
            successful = 0
            failed = 0
            for pipeline in args.pipelines:
                try:
                    orchestrator.run_single(pipeline)
                    successful += 1
                except Exception as e:
                    logger.error(str(e))
                    failed += 1
            print(f"\nResult: {successful} successful, {failed} failed")
            sys.exit(0 if failed == 0 else 1)
        else:
            logger.info(
                "Running all pipelines in default order: %s",
                " → ".join(DEFAULT_PIPELINE_ORDER),
            )
            successful, failed = orchestrator.run_all(list(DEFAULT_PIPELINE_ORDER))
            orchestrator.print_summary()

            # Run post-processing (spatial relationships)
            if successful > 0:
                logger.info("\n" + "="*70)
                logger.info("STARTING SPATIAL RELATIONSHIP POST-PROCESSING")
                logger.info("="*70)
                try:
                    from sources.relacoes_espaciais import run_post_processing
                    run_post_processing(orchestrator.engine)
                    logger.info("✓ Post-processing completed successfully")
                except Exception as e:
                    logger.error(f"Post-processing failed: {str(e)}")
                    failed += 1

            sys.exit(0 if failed == 0 else 1)
    finally:
        orchestrator.close()


if __name__ == "__main__":
    main()
