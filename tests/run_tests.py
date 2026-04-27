#!/usr/bin/env python3
"""
Script de automação para executar testes de integração espaciais.
Execute: python run_tests.py [--verbose] [--coverage] [--errors-only]
"""

import subprocess
import sys
import os
import argparse
import asyncio
from pathlib import Path


TEST_DIR = Path("tests/integration/spatial")
TEST_FILES = {
    "intersection": "test_intersection_queries.py",
    "buffer": "test_buffer_queries.py",
    "proximity": "test_proximity_queries.py",
    "contains": "test_contains_function.py",
    "performance": "test_performance.py",
    "analytics": "test_analytics_queries.py",
    "validity": "test_geometry_validity.py",
    "errors": "test_error_scenarios.py",
}


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def run_command(cmd, description):
    """Executa comando e exibe resultado."""
    print(f"{Colors.BLUE}>>> {description}{Colors.RESET}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result


async def setup_database():
    """Configura o banco de dados de teste."""
    print(f"{Colors.YELLOW}=== Configurando banco de teste ==={Colors.RESET}")
    result = subprocess.run(
        [sys.executable, "tests/setup_test_db.py", "--full"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"{Colors.RED}Erro no setup: {result.stderr}{Colors.RESET}")
    else:
        print(f"{Colors.GREEN}{result.stdout}{Colors.RESET}")
    return result.returncode == 0


def run_pytest(args):
    """Executa pytest com argumentos."""
    cmd = [sys.executable, "-m", "pytest", "-v"]
    cmd.extend(args)
    result = subprocess.run(cmd, text=True)
    return result.returncode, result.stdout, result.stderr


async def main():
    parser = argparse.ArgumentParser(description="Executar testes de integração espaciais")
    parser.add_argument("--verbose", "-v", action="store_true", help="Saída detalhada")
    parser.add_argument("--coverage", "-c", action="store_true", help="Executar com coverage")
    parser.add_argument("--errors-only", "-e", action="store_true", help="Apenas testes de erro")
    parser.add_argument("--quick", "-q", action="store_true", help="Execução rápida")
    parser.add_argument("--setup", "-s", action="store_true", help="Setup do banco")
    parser.add_argument("--parallel", "-p", action="store_true", help="Execução paralela")
    parser.add_argument("--junit", "-j", action="store_true", help="Gerar relatório JUnit")
    parser.add_argument("--markers", "-m", action="store_true", help="Listar marcadores")
    args = parser.parse_args()

    print(f"\n{Colors.BLUE}="*50)
    print(" Script de Testes de Integração Espaciais ")
    print("="*50 + f"{Colors.RESET}\n")

    if args.setup:
        await setup_database()
        return 0

    if args.markers:
        run_command(f'{sys.executable} -m pytest --markers', "Listando marcadores")
        return 0

    pytest_args = []

    if args.verbose:
        pytest_args.append("-v")

    if args.coverage:
        pytest_args.extend(["--cov=.=", "--cov-report=term", "--cov-report=html"])

    if args.errors_only:
        pytest_args.append("tests/integration/spatial/test_error_scenarios.py")

    if args.junit:
        pytest_args.append(f"--junit-xml=test-results/junit.xml")
        os.makedirs("test-results", exist_ok=True)

    if args.parallel:
        pytest_args.extend(["-n", "auto"])

    if args.quick:
        pytest_args.append("-x")

    if not pytest_args:
        pytest_args.append("-v")

    pytest_args.append("tests/integration/spatial/")

    print(f"{Colors.YELLOW}Executando testes...{Colors.RESET}\n")

    returncode, stdout, stderr = run_pytest(pytest_args)

    print(stdout)

    if stderr:
        print(f"{Colors.RED}Erros:{Colors.RESET}\n{stderr}")

    if returncode == 0:
        print(f"\n{Colors.GREEN}✓ Todos os testes passaram!{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}✗ Alguns testes falharam{Colors.RESET}")

    return returncode


def check_dependencies():
    """Verifica dependências necessárias."""
    required = ["pytest", "sqlalchemy", "asyncpg", "geoalchemy2"]
    missing = []

    for pkg in required:
        result = subprocess.run(
            [sys.executable, "-c", f"import {pkg}"],
            capture_output=True
        )
        if result.returncode != 0:
            missing.append(pkg)

    if missing:
        print(f"{Colors.RED} Dependências faltando: {', '.join(missing)}{Colors.RESET}")
        print(f" Instale com: pip install {' '.join(missing)}")
        return False
    return True


if __name__ == "__main__":
    if not check_dependencies():
        sys.exit(1)

    exit_code = asyncio.run(main())
    sys.exit(exit_code)