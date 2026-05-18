import os
import yaml
from dataclasses import dataclass


@dataclass
class Config:
    keywords: list[str]
    adzuna_countries: list[str]
    jooble_locations: list[str]
    min_match_score: int
    max_alerts_per_run: int
    cv_path: str

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(
            keywords=data.get("keywords", []),
            adzuna_countries=data.get("adzuna_countries", []),
            jooble_locations=data.get("jooble_locations", []),
            min_match_score=int(data.get("min_match_score", 50)),
            max_alerts_per_run=int(data.get("max_alerts_per_run", 15)),
            cv_path=data.get("cv_path", "data/cv.pdf"),
        )
