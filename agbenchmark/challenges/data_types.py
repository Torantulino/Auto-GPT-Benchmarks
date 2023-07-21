import json
import glob
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict

from pydantic import BaseModel, validator


class DifficultyLevel(Enum):
    interface = "interface"
    basic = "basic"
    novice = "novice"
    intermediate = "intermediate"
    advanced = "advanced"
    expert = "expert"
    human = "human"


# map from enum to difficulty level (numeric)
DIFFICULTY_MAP = {
    DifficultyLevel.interface: 1,
    DifficultyLevel.basic: 2,
    DifficultyLevel.novice: 3,
    DifficultyLevel.intermediate: 4,
    DifficultyLevel.advanced: 5,
    DifficultyLevel.expert: 6,
    DifficultyLevel.human: 7,
}


class Info(BaseModel):
    difficulty: DifficultyLevel
    description: str
    side_effects: List[str]

    @validator("difficulty", pre=True)
    def difficulty_to_enum(cls: "Info", v: str | DifficultyLevel) -> DifficultyLevel:
        """Convert a string to an instance of DifficultyLevel."""
        if isinstance(v, DifficultyLevel):
            return v

        if isinstance(v, str):
            try:
                return DifficultyLevel(v.lower())
            except ValueError:
                pass

        raise ValueError(f"Cannot convert {v} to DifficultyLevel.")


class Ground(BaseModel):
    answer: str
    should_contain: Optional[List[str]] = None
    should_not_contain: Optional[List[str]] = None
    files: List[str]
    type: str


class ChallengeData(BaseModel):
    name: str
    category: List[str]
    task: str
    dependencies: List[str]
    cutoff: int
    ground: Ground | Dict[str, Ground]
    info: Info | Dict[str, Info]

    def serialize(self, path: str) -> None:
        with open(path, "w") as file:
            file.write(self.json())

    def get_data(self) -> dict:
        return self.dict()

    @staticmethod
    def get_json_from_path(json_path: Path | str) -> dict:
        path = Path(json_path).resolve()
        with open(path, "r") as file:
            data = json.load(file)
        return data

    @staticmethod
    def deserialize(path: str) -> "ChallengeData":
        # this script is in root/agbenchmark/challenges/define_task_types.py
        script_dir = Path(__file__).resolve().parent.parent.parent
        json_path = script_dir / Path(path)

        with open(json_path, "r") as file:
            data = json.load(file)

        return ChallengeData(**data)


class SuiteConfig(BaseModel):
    same_task: bool
    reverse_order: bool
    prefix: str
    task: str
    cutoff: int
    dependencies: List[str]
    shared_category: List[str]
    info: Optional[Dict[str, Info]] = None
    ground: Optional[Dict[str, Ground]] = None

    @staticmethod
    def suite_data_if_suite(json_path: Path) -> Optional["SuiteConfig"]:
        """Return the suite data if the path is in a suite."""
        if SuiteConfig.check_if_suite(json_path):
            return SuiteConfig.deserialize_from_test_data(json_path)
        else:
            return None

    @staticmethod
    def check_if_suite(json_path: Path) -> bool:
        """Check if the json file is in a suite."""

        # if its in a suite, suite.json is in the parent suite/suite.json & 1_challenge/data.json
        suite_path = json_path.parent.parent / "suite.json"

        # validation and loading data from suite.json
        return suite_path.exists()

    @staticmethod
    def deserialize_from_test_data(data_path: Path) -> "SuiteConfig":
        suite_path = data_path.parent.parent / "suite.json"

        """Deserialize from a children path when children and order of children does not matter."""
        print("Deserializing suite", data_path)

        return SuiteConfig.deserialize(suite_path)

    @staticmethod
    def deserialize(suite_path: Path) -> "SuiteConfig":
        with open(suite_path, "r") as file:
            data = json.load(file)
        return SuiteConfig(**data)

    @staticmethod
    def get_data_paths(suite_path: Path | str) -> List[str]:
        return glob.glob(f"{suite_path}/**/data.json", recursive=True)

    def challenge_from_datum(self, file_datum: list[dict]) -> "ChallengeData":
        same_task_data = {
            "name": self.prefix,
            "dependencies": self.dependencies,
            "category": self.shared_category,
            "task": self.task,
            "cutoff": self.cutoff,
        }

        if not self.info:
            same_task_data["info"] = {
                datum["name"]: datum["info"] for datum in file_datum
            }
        else:
            same_task_data["info"] = self.info

        if not self.ground:
            same_task_data["ground"] = {
                datum["name"]: datum["ground"] for datum in file_datum
            }
        else:
            same_task_data["ground"] = self.ground

        return ChallengeData(**same_task_data)