from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TableLoadStats:
    """Row loading counters and sample reject messages for one table."""
    table_name: str
    source_rows: int = 0
    loaded_rows: int = 0
    skipped_rows: int = 0
    mapped_rows: int = 0
    rejected_rows: int = 0
    reject_samples: List[str] = field(default_factory=list)

    def reject(self, message: str) -> None:
        """Track a rejected row and keep a small sample for the report."""
        self.rejected_rows += 1
        if len(self.reject_samples) < 5:
            self.reject_samples.append(message)


@dataclass
class PopulationResult:
    """Aggregate output from one full Phase 2 population run."""
    table_stats: Dict[str, TableLoadStats]
    db_row_counts: Dict[str, int]
    row_count_mismatches: Dict[str, str]
    fk_issues: List[str]

    @property
    def total_rejected_rows(self) -> int:
        """Total number of rejected rows across all loaded tables."""
        return sum(stats.rejected_rows for stats in self.table_stats.values())

    @property
    def is_clean(self) -> bool:
        """Whether the run had zero rejections and passed all integrity checks."""
        return (
            self.total_rejected_rows == 0
            and not self.row_count_mismatches
            and not self.fk_issues
        )
