from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    id: str
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    posted_date: Optional[str] = None
    salary: Optional[str] = None
    remote: bool = False
    tags: list[str] = field(default_factory=list)

    def short_desc(self, n: int = 1500) -> str:
        text = self.description or ""
        return text[:n]
