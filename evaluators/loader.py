"""
Dynamically load custom evaluators from user-provided Python modules.
"""
import sys
import importlib.util
from pathlib import Path
from typing import Dict, Type

from evaluators.base import BaseEvaluator


def load_custom_evaluators(custom_eval_dir: str) -> Dict[str, Type[BaseEvaluator]]:
    """
    Load custom evaluators from a directory.

    Expects .py files where each file contains a class extending BaseEvaluator.
    The evaluator name is derived from the filename (e.g., sentiment_eval.py → sentiment_eval).

    Args:
        custom_eval_dir: Path to directory containing custom evaluator files

    Returns:
        Dict mapping evaluator names to evaluator classes
    """
    custom_evaluators = {}
    eval_dir = Path(custom_eval_dir)

    if not eval_dir.exists():
        print(f"Warning: Custom evaluator directory not found: {custom_eval_dir}")
        return custom_evaluators

    # Find all .py files in the directory
    for py_file in eval_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            # Skip __init__.py and private modules
            continue

        try:
            # Dynamically import the module
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            if spec is None or spec.loader is None:
                print(f"Warning: Could not load spec for {py_file}")
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[py_file.stem] = module
            spec.loader.exec_module(module)

            # Find BaseEvaluator subclasses in the module
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue

                attr = getattr(module, attr_name)

                # Check if it's a class and subclass of BaseEvaluator (but not BaseEvaluator itself)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseEvaluator)
                    and attr is not BaseEvaluator
                ):
                    evaluator_name = py_file.stem
                    custom_evaluators[evaluator_name] = attr
                    print(f"✓ Loaded custom evaluator: {evaluator_name}")

        except Exception as e:
            print(f"Error loading custom evaluator from {py_file}: {e}")

    return custom_evaluators


def get_custom_evaluator(
    evaluator_name: str, custom_evaluators: Dict[str, Type[BaseEvaluator]]
) -> BaseEvaluator | None:
    """
    Get an instantiated custom evaluator by name.

    Args:
        evaluator_name: Name of the evaluator (without .py extension)
        custom_evaluators: Dict of available custom evaluators

    Returns:
        Instantiated evaluator or None if not found
    """
    if evaluator_name not in custom_evaluators:
        return None

    evaluator_class = custom_evaluators[evaluator_name]
    return evaluator_class()
