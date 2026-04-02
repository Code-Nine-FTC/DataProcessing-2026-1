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

    # Register all pipelines
    try:
        from sources.icmbio import create_pipeline as create_icmbio
        from sources.funai import create_pipeline as create_funai
        from sources.incra import create_pipeline as create_incra
        from sources.palmares import create_pipeline as create_palmares
        from sources.datageo_sp import create_pipeline as create_datageo_sp
        from sources.car import create_pipeline as create_car
        from sources.inpe import create_pipeline as create_inpe

        orchestrator.register_pipeline("icmbio", create_icmbio)
        orchestrator.register_pipeline("funai", create_funai)
        orchestrator.register_pipeline("incra", create_incra)
        orchestrator.register_pipeline("palmares", create_palmares)
        orchestrator.register_pipeline("datageo_sp", create_datageo_sp)
        orchestrator.register_pipeline("car", create_car)
        orchestrator.register_pipeline("inpe", create_inpe)

    except ImportError as e:
        logger.error(f"Failed to import pipeline: {str(e)}")
        sys.exit(1)

    # Handle CLI commands
    if args.list:
        print("\nAvailable pipelines:")
        for name in sorted(orchestrator.pipelines.keys()):
            print(f"  • {name}")
        return

    if args.order:
        order = [
            "icmbio",
            "funai",
            "incra",
            "palmares",
            "datageo_sp",
            "car",
            "inpe",
        ]
        print("\nDefault execution order:")
        for i, name in enumerate(order, 1):
            print(f"  {i}. {name}")
        print("\nNote: Spatial relationships computed after all data is loaded")
        return

    # Run pipelines
    if args.pipelines:
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
        # Run all in default order
        logger.info("Running all pipelines in default order")
        order = [
            "icmbio",
            "funai",
            "incra",
            "palmares",
            "datageo_sp",
            "car",
            "inpe",
        ]
        successful, failed = orchestrator.run_all(order)
        orchestrator.print_summary()

        # Run post-processing (spatial relationships)
        if successful > 0:
            logger.info("\n" + "="*70)
            logger.info("STARTING SPATIAL RELATIONSHIP POST-PROCESSING")
            logger.info("="*70)
            try:
                from sources.relacoes_espaciais_refactored import run_post_processing
                run_post_processing(orchestrator.engine)
                logger.info("✓ Post-processing completed successfully")
            except Exception as e:
                logger.error(f"Post-processing failed: {str(e)}")
                failed += 1

        sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
