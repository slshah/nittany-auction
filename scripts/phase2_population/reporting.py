from .models import PopulationResult


def print_report(result: PopulationResult) -> None:
    """Print the per table load summary plus integrity validation results."""
    headers = (
        "table",
        "source",
        "loaded",
        "skipped",
        "mapped",
        "rejected",
        "db_count",
    )

    line = (
        f"{headers[0]:<18} {headers[1]:>8} {headers[2]:>8} {headers[3]:>8} "
        f"{headers[4]:>8} {headers[5]:>9} {headers[6]:>10}"
    )
    print("\nPhase 2 ETL Data-Quality Report")
    print(line)
    print("-" * len(line))

    for table_name, stats in result.table_stats.items():
        db_count = result.db_row_counts.get(table_name, 0)
        print(
            f"{table_name:<18} "
            f"{stats.source_rows:>8} "
            f"{stats.loaded_rows:>8} "
            f"{stats.skipped_rows:>8} "
            f"{stats.mapped_rows:>8} "
            f"{stats.rejected_rows:>9} "
            f"{db_count:>10}"
        )

    print("\nIntegrity checks")
    if result.row_count_mismatches:
        print("- Row count validation: FAIL")
        for table_name, message in result.row_count_mismatches.items():
            print(f"  - {table_name}: {message}")
    else:
        print("- Row count validation: PASS")

    if result.fk_issues:
        print("- Foreign key validation: FAIL")
        for issue in result.fk_issues[:10]:
            print(f"  - {issue}")
        if len(result.fk_issues) > 10:
            print(f"  - ... and {len(result.fk_issues) - 10} more")
    else:
        print("- Foreign key validation: PASS")

    if result.total_rejected_rows > 0:
        print(f"- Rejected rows: {result.total_rejected_rows}")
        for table_name, stats in result.table_stats.items():
            for sample in stats.reject_samples:
                print(f"  - [{table_name}] {sample}")
    else:
        print("- Rejected rows: 0")
