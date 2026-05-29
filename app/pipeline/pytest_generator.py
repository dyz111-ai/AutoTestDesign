"""Generate pytest files from test cases and source code context."""

from app.core.llm_utils import chat_completion_text


def generate_pytest(
    testcases: list,
    source_files: dict[str, str],
    app_name: str = "",
) -> str:
    """
    Generate a pytest file from the given test cases and source file contents.

    Parameters
    ----------
    testcases : list
        List of test case dicts with fields: tc_id, req_id, coverage_id,
        test_method, priority, preconditions, test_data, steps, expected_result.
    source_files : dict[str, str]
        Mapping of filename -> file content for the source files under test.
    app_name : str
        Optional application/module name for context.

    Returns
    -------
    str
        The generated pytest code.
    """

    source_context = ""
    for fname, fcontent in source_files.items():
        source_context += f"\n=== {fname} ===\n{fcontent}\n"

    prompt = f"""
    You are a Senior QA Automation Engineer. Your task is to generate a complete,
    runnable pytest file based on the provided test cases and source code.

    Application under test: {app_name or "the target module"}

    --- SOURCE CODE ---
    {source_context}

    --- TEST CASES ---
    {testcases}

    --- GENERATION RULES ---

    1. Study the source code to understand:
       - Available functions/classes and their signatures
       - Module import paths
       - Expected input/output types

    2. Generate a pytest file that imports from the source modules under test.

    3. For each test case, create a pytest function following these conventions:
       - Function name: test_<tc_id_normalized>_<snake_case_description>
         * NORMALIZE the tc_id: lowercase it, replace hyphens with underscores
           Examples: TC-01 → tc01, TC-32 → tc32, TC-A1 → tc_a1
         * This ensures the TC ID is visible in pytest output lines like:
           FAILED tests/...::test_tc32_cart_unchanged_invalid_quantity
       - Include a docstring referencing the full original tc_id and intent
       - Set up test data exactly as specified in test_data
       - Call the function under test with the test data
       - Assert the expected_result against the actual output
       - Use plain assert statements (no unittest.TestCase)

    4. Code style (follow this exact pattern):
       ```python
       from __future__ import annotations

       from time import perf_counter

       from module.path import function_under_test


       def test_descriptive_name() -> None:
           result = function_under_test(...)

           assert result["key"] == "expected_value"
       ```

    5. IMPORTANT rules:
       - Use `from __future__ import annotations` at the top
       - Group imports: stdlib first, then third-party, then local modules
       - Every test function has `-> None` return type annotation
       - Keep tests focused: one test function per logical scenario
       - Use descriptive test function names that explain the scenario
       - Assertions should be simple and clear
       - If the source uses a class, import and instantiate it appropriately
       - Handle edge cases shown in test data (empty, invalid, boundary values)
       - For performance tests, use `time.perf_counter()`

    Return ONLY the raw Python code inside a single markdown code block.  No
    other text before or after the code block.
    """

    return chat_completion_text(prompt)
