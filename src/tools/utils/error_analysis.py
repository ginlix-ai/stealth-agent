"""
Error Analysis Tool Module
Provides detailed error analysis and debugging tips for Python code execution errors
"""

import re
from typing import List


def build_error_info(exception: Exception, code: str) -> str:
    """
    Build error information, selecting appropriate analysis method based on exception type

    Args:
        exception: Exception object
        code: Original code

    Returns:
        Formatted error message string
    """

    error_type = type(exception).__name__
    error_message = str(exception)
    import traceback
    traceback_lines = traceback.format_exc().strip().split('\n')
    return build_detailed_error_for_agent(error_type, error_message, traceback_lines, code)


def build_detailed_error_for_agent(error_type: str, error_message: str, traceback_lines: List[str], original_code: str) -> str:
    """
    Build detailed error information for Agent with sufficient context for debugging and fixing code
    """
    error_parts = []

    # 1. Error type and main information
    error_parts.append(f"Error Type: {error_type}")
    error_parts.append(f"Error Message: {error_message}")

    # 2. Extract error line number and context code
    error_line_num = None
    for line in traceback_lines:
        if 'File "<string>"' in line and 'line ' in line:
            line_match = re.search(r'line (\d+)', line)
            if line_match:
                error_line_num = int(line_match.group(1))
                break

    # 3. Display error code and its context
    if error_line_num and original_code:
        code_lines = original_code.strip().split('\n')
        error_parts.append(f"\nError Location: Line {error_line_num}")

        # Display code context around error line (3 lines before and after)
        start_line = max(0, error_line_num - 4)  # 3 lines before
        end_line = min(len(code_lines), error_line_num + 3)  # 3 lines after

        error_parts.append("Code Context:")
        for i in range(start_line, end_line):
            line_content = code_lines[i].rstrip()
            line_marker = ">>> " if (i + 1) == error_line_num else "    "
            error_parts.append(f"{line_marker}{i+1:3d}: {line_content}")

    # 4. Add debugging hints for specific error types
    debugging_hints = get_debugging_hints(error_type, error_message, original_code)
    if debugging_hints:
        error_parts.append(f"\nDebugging Tips: {debugging_hints}")

    # 5. Complete traceback (simplified display, but retain key information)
    relevant_traceback = []
    for line in traceback_lines:
        # Filter out some irrelevant internal traceback lines, but retain key information
        if any(keyword in line for keyword in [
            'File "<string>"', error_type + ':', 'line ', '^'
        ]) or line.strip().startswith(('File ', 'Traceback')):
            relevant_traceback.append(line)

    if relevant_traceback:
        error_parts.append("\nTraceback Information:")
        error_parts.extend(relevant_traceback)

    return '\n'.join(error_parts)


def get_debugging_hints(error_type: str, error_message: str, code: str) -> str:
    """
    Provide debugging hints based on error type and code content
    """
    hints = []

    if error_type == 'KeyError':
        if 'DataFrame' in code or '.df' in code or 'pd.' in code:
            hints.append("Check if DataFrame column names are correct, use df.columns to view all column names")
        if '[' in code and ']' in code:
            hints.append("Confirm that keys/column names exist in dictionary or DataFrame")

    elif error_type == 'NameError':
        if 'import' not in code and any(module in error_message for module in ['pd', 'np', 'plt', 'ts']):
            hints.append("May be missing import statements, such as: import pandas as pd, import numpy as np, etc.")

    elif error_type == 'ModuleNotFoundError':
        module_name = error_message.replace("No module named ", "").strip("'\"")
        hints.append(f"Missing module {module_name}, needs to be installed or import path checked")

    elif error_type in ['SyntaxError', 'IndentationError']:
        hints.append("Check code syntax, pay special attention to bracket matching, indentation, quote closure, etc.")

    elif error_type == 'AttributeError':
        if 'DataFrame' in error_message:
            hints.append("Check if DataFrame method name is correct, or if object is empty")

    elif error_type == 'TypeError':
        if 'not subscriptable' in error_message:
            hints.append("Attempted to use [] operation on object that doesn't support indexing")
        elif 'not callable' in error_message:
            hints.append("Attempted to call an object that is not a function")

    return '; '.join(hints) if hints else ""