import sys
import json
import pytest
from pathlib import Path
from typing import Any

from agbenchmark.ReportManager import ReportManager
from agbenchmark.start_benchmark import (
    CONFIG_PATH,
    INFO_TESTS_PATH,
    REGRESSION_TESTS_PATH,
)
from agbenchmark.utils import AGENT_NAME, calculate_success_percentage
from agbenchmark.challenges.data_types import DIFFICULTY_MAP, SuiteConfig
from agbenchmark.utils import replace_backslash

# tests that consistently pass are considered regression tests
regression_manager = ReportManager(REGRESSION_TESTS_PATH)

# user facing reporting information
info_manager = ReportManager(INFO_TESTS_PATH)

INTERNAL_LOGS_PATH = Path(__file__).resolve().parent

# internal db step in replacement track pass/fail rate
internal_info = ReportManager(str(INTERNAL_LOGS_PATH / "internal_info.json"))


def generate_suite_report(item, challenge_data):
    challenge_location: str = getattr(item.cls, "CHALLENGE_LOCATION", "")

    suite_config = SuiteConfig.deserialize(
        Path(challenge_location).resolve() / "suite.json"
    )
    item.test_name = suite_config.prefix

    # if suite_config.same_task:
    #     print("YEP SUITE TEST SAME TASK", suite_config)

    data_paths = suite_config.get_data_paths(challenge_location)
    scores = getattr(item, "scores", {})
    mock = "--mock" in sys.argv  # Check if --mock is in sys.argv

    tests = {}
    num_highest_difficulty: int = 0
    str_highest_difficulty: str = "No successful tests"
    for i, test_name in enumerate(challenge_data["ground"]):
        raw_difficulty = challenge_data["info"][test_name]["difficulty"]
        test_details = {
            "difficulty": raw_difficulty.value,
            "data_path": challenge_location,
        }

        test_info_details = {
            "data_path": replace_backslash(data_paths[i]),
            "is_regression": False,
            "answer": challenge_data["ground"][test_name]["answer"],
            "description": challenge_data["info"][test_name]["description"],
            "metrics": {
                "difficulty": raw_difficulty.value,
                "success": False,
            },
        }

        if scores["scores_obj"][test_name] == 1:
            # add dependency successful here

            test_info_details["metrics"]["success"] = True

            # replace the highest difficulty if needed
            if DIFFICULTY_MAP[raw_difficulty] > num_highest_difficulty:
                num_highest_difficulty = DIFFICULTY_MAP[raw_difficulty]
                str_highest_difficulty = raw_difficulty.value
        else:
            # add dependency fail here

            if not mock:  # don't remove if it's a mock test
                regression_manager.remove_test(test_name)

        prev_test_results: list[bool] = get_previous_test_results(
            test_name, test_info_details
        )

        update_regression_tests(
            prev_test_results, test_info_details, test_name, test_details
        )

        tests[test_name] = test_info_details

    info_details: Any = {
        "data_path": challenge_location,
        "task": challenge_data["task"],
        "category": suite_config.shared_category,
        "metrics": {
            "percentage": scores["percentage"],
            "highest_difficulty": str_highest_difficulty,
        },
        "tests": tests,
    }

    # user facing reporting
    item.info_details = info_details


def get_previous_test_results(test_name, info_details) -> list[bool]:
    agent_tests: dict[str, list[bool]] = {}
    mock = "--mock" in sys.argv  # Check if --mock is in sys.argv

    # if the structure is nested inside of the agent name
    if AGENT_NAME:
        agent_tests = internal_info.tests.get(AGENT_NAME, {})

    if agent_tests:
        prev_test_results = agent_tests.get(test_name, [])
    else:
        prev_test_results = internal_info.tests.get(test_name, [])

    if not mock:
        # only add if it's an actual test
        prev_test_results.append(info_details["metrics"]["success"])
        internal_info.add_test(test_name, prev_test_results, AGENT_NAME)

        # can calculate success rate regardless of mock
        info_details["metrics"]["success_%"] = calculate_success_percentage(
            prev_test_results
        )
    else:
        # can calculate success rate regardless of mock
        info_details["metrics"]["non_mock_success_%"] = calculate_success_percentage(
            prev_test_results
        )

    return prev_test_results


def update_regression_tests(
    prev_test_results: list[bool],
    info_details: dict,
    test_name: str,
    test_details: dict,
):
    if len(prev_test_results) >= 3 and prev_test_results[-3:] == [True, True, True]:
        # if the last 3 tests were successful, add to the regression tests
        info_details["is_regression"] = True
        regression_manager.add_test(test_name, test_details)


def generate_single_call_report(item, call, challenge_data):
    difficulty = challenge_data["info"]["difficulty"]

    # Extract the challenge_location from the class
    challenge_location: str = getattr(item.cls, "CHALLENGE_LOCATION", "")
    test_name = item.nodeid.split("::")[1]
    item.test_name = test_name

    test_details = {
        "difficulty": difficulty,
        "data_path": challenge_location,
    }

    info_details: Any = {
        "data_path": challenge_location,
        "is_regression": False,
        "category": challenge_data["category"],
        "task": challenge_data["task"],
        "answer": challenge_data["ground"]["answer"],
        "description": challenge_data["info"]["description"],
        "metrics": {
            "difficulty": difficulty,
            "success": False,
        },
    }

    mock = "--mock" in sys.argv  # Check if --mock is in sys.argv

    if call.excinfo is None:
        info_details["metrics"]["success"] = True
    else:
        if not mock:  # don't remove if it's a mock test
            regression_manager.remove_test(test_name)
        info_details["metrics"]["fail_reason"] = str(call.excinfo.value)

    prev_test_results: list[bool] = get_previous_test_results(test_name, info_details)

    update_regression_tests(prev_test_results, info_details, test_name, test_details)

    # user facing reporting
    item.info_details = info_details


def setup_dummy_dependencies(test_class_instance, test_class):
    """Sets up the dependencies if it's a suite. Creates tests that pass
    based on the main test run."""

    def create_test_func(test_name):
        # This function will return another function

        # Define a dummy test function that does nothing
        def setup_dependency_test(self, scores):
            scores = self.get_dummy_scores(test_name, scores)
            assert scores == 1

        return setup_dependency_test

    for test_name in test_class_instance.setup_dependencies:
        setup_dependency_test = create_test_func(test_name)
        # Add the dummy test function to the class that the current test is part of
        # TODO: remove on=[test_class.__name__] and fix the actual dependencies problem
        test_func = pytest.mark.depends(on=[test_class.__name__], name=test_name)(
            setup_dependency_test
        )
        # Parametrize to tell makereport to skip it
        test_func = pytest.mark.parametrize(
            "challenge_data",
            [None],
            indirect=True,
        )(test_func)
        test_func = pytest.mark.usefixtures("scores")(test_func)
        setattr(test_class, f"test_{test_name}", test_func)


def finalize_reports(item, challenge_data):
    run_time = dict(item.user_properties).get("run_time")

    info_details = getattr(item, "info_details", {})
    test_name = getattr(item, "test_name", "")

    if info_details and test_name:
        if run_time:
            info_details["metrics"]["run_time"] = f"{str(round(run_time, 3))} seconds"

            info_details["reached_cutoff"] = float(run_time) > challenge_data["cutoff"]

        info_manager.add_test(test_name, info_details)


def session_finish():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    internal_info.save()
    info_manager.end_info_report(config)
    regression_manager.save()
