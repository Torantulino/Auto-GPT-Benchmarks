import json
from typing import List, Optional

from pydantic import BaseModel


class Info(BaseModel):
    difficulty: str
    description: str
    side_effects: List[str]


class Ground(BaseModel):
    answer: str
    should_contain: Optional[List[str]] = None
    should_not_contain: Optional[List[str]] = None
    files: List[str]
    type: str


class ChallengeData(BaseModel):
    category: List[str]
    task: str
    dependencies: List[str]
    ground: Ground
    info: Info

    def serialize(self, path: str) -> None:
        with open(path, "w") as file:
            file.write(self.json())

    @staticmethod
    def deserialize(path: str) -> "ChallengeData":
        print("Deserializing", path)
        with open(path, "r") as file:
            data = json.load(file)
        return ChallengeData(**data)
