"""Ingestion pipeline definition.

Chains the four ingestion nodes into a Kedro Pipeline:
    validate_columns → parse_and_clean → deduplicate → insert_to_postgres
"""

from kedro.pipeline import Pipeline, node

from .nodes import (
    deduplicate,
    insert_to_postgres,
    parse_and_clean,
    validate_columns,
)


def create_pipeline(**kwargs) -> Pipeline:
    """Create the ingestion pipeline.

    The pipeline reads raw CSV call logs, validates columns, parses and cleans
    the data, deduplicates against existing database records, and inserts
    surviving rows into PostgreSQL.

    The ``engine`` input must be provided via the Kedro catalog (e.g. as a
    MemoryDataset populated by a hook or session-scoped factory).
    """
    return Pipeline(
        [
            node(
                func=validate_columns,
                inputs="raw_call_logs",
                outputs="validated_call_logs",
                name="validate_columns",
            ),
            node(
                func=parse_and_clean,
                inputs="validated_call_logs",
                outputs="cleaned_call_logs",
                name="parse_and_clean",
            ),
            node(
                func=deduplicate,
                inputs=["cleaned_call_logs", "engine"],
                outputs="deduplicated_call_logs",
                name="deduplicate",
            ),
            node(
                func=insert_to_postgres,
                inputs=["deduplicated_call_logs", "engine"],
                outputs="ingestion_summary",
                name="insert_to_postgres",
            ),
        ]
    )
