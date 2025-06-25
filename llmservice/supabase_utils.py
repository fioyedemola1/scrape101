from supabase import create_client, Client

import os
from dotenv import load_dotenv
import logging

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
client = create_client(supabase_url, supabase_key)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reconcile_url_marker_supabase(
    supabase: Client,
    base_table: str,
    lookup_table: str,
    url_column: str = "url",
    marker_column: str = "is_in_lookup",
    id_column: str = "id"
):
    """
    For each row in base_table, set marker_column to True if url_column exists in lookup_table, else False.
    This function assumes the marker_column already exists in the base_table.
    Args:
        supabase: Supabase Python client
        base_table: str, name of the base table
        lookup_table: str, name of the lookup table
        url_column: str, name of the URL column (default: 'url')
        marker_column: str, name of the marker column (default: 'is_in_lookup')
        id_column: str, primary key column in base_table (default: 'id')
    Note:
        This function does not add the marker column if missing. Add it manually in the Supabase dashboard if needed.
    """
    logger.info(f"Starting reconciliation: {base_table} vs {lookup_table} on '{url_column}', marking '{marker_column}'")
    try:
        # 1. Get all URLs from lookup_table
        lookup_rows = supabase.table(lookup_table).select(url_column).execute().data
        lookup_url_set = set(row[url_column] for row in lookup_rows)
        logger.info(f"Fetched {len(lookup_url_set)} URLs from {lookup_table}")

        # 2. Get all rows from base_table
        # Fetch all rows in batches
        base_rows = []
        page_size = 1000
        count_response = supabase.table(base_table).select("*", count="exact").eq(marker_column, False).execute()
        total_records = count_response.count
        for offset in range(0, total_records, page_size):
            batch = supabase.table(base_table)\
                .select("*")\
                .range(offset, min(offset + page_size - 1, total_records - 1))\
                .execute().data
            base_rows.extend(batch)
            logger.info(f"Fetched {len(batch)} records (total so far: {len(base_rows)})")
        
        logger.info(f"Fetched {len(base_rows)} total rows from {base_table}")

        # 3. For each row, update marker_column
        updated_count = 0
        for row in base_rows:
            url = row.get(url_column)
            row_id = row.get(id_column)
            if row_id is None or url is None:
                continue
            marker_value = url in lookup_url_set
            supabase.table(base_table).update({marker_column: marker_value}).eq(id_column, row_id).execute()
            updated_count += 1
        logger.info(f"Updated {updated_count} rows in {base_table} with marker '{marker_column}'")
    except Exception as e:
        logger.error(f"Error during reconciliation: {e}")

def drop_duplicates_supabase(
    supabase: Client,
    table: str,
    subset: list,
    timestamp_column: str = "created_at",
    id_column: str = "id",
    batch_size: int = 1000
):
    """
    Remove duplicate rows from a table, keeping only the most recent one based on timestamp_column.
    Fetches all rows in batches to handle large tables.
    Args:
        supabase: Supabase Python client
        table: str, table name
        subset: list of columns to consider for duplicates (e.g., ['url'])
        timestamp_column: str, column to determine recency (default: 'created_at')
        id_column: str, primary key column (default: 'id')
        batch_size: int, number of rows to fetch per batch (default: 1000)
    Note:
        This function loads all rows into memory. For very large tables, consider batching or server-side deduplication.
    """
    logger.info(f"Starting duplicate removal for table '{table}' on columns {subset}, keeping most recent by '{timestamp_column}'")
    try:
        # 1. Fetch all rows in batches
        all_rows = []
        from_idx = 0
        while True:
            to_idx = from_idx + batch_size - 1
            batch = supabase.table(table).select("*").range(from_idx, to_idx).execute().data
            if not batch:
                break
            all_rows.extend(batch)
            logger.info(f"Fetched rows {from_idx} to {to_idx} ({len(batch)} rows)")
            if len(batch) < batch_size:
                break
            from_idx += batch_size

        if not all_rows:
            logger.info("No rows found. Nothing to deduplicate.")
            return

        logger.info(f"Fetched {len(all_rows)} rows from {table}")

        # 2. Sort and group by subset columns
        from collections import defaultdict

        grouped = defaultdict(list)
        for row in all_rows:
            key = tuple(row.get(col) for col in subset)
            grouped[key].append(row)

        # 3. For each group, keep the most recent, delete the rest
        ids_to_delete = []
        for group_rows in grouped.values():
            if len(group_rows) <= 1:
                continue
            # Sort by timestamp_column descending
            sorted_rows = sorted(
                group_rows,
                key=lambda r: r.get(timestamp_column, ""),
                reverse=True
            )
            # Keep the first (most recent), delete the rest
            ids_to_delete.extend(row[id_column] for row in sorted_rows[1:] if row.get(id_column) is not None)

        logger.info(f"Identified {len(ids_to_delete)} duplicate rows to delete in '{table}'")

        # 4. Delete duplicates
        deleted_count = 0
        for del_id in ids_to_delete:
            supabase.table(table).delete().eq(id_column, del_id).execute()
            deleted_count += 1
        logger.info(f"Deleted {deleted_count} duplicate rows from '{table}'")
    except Exception as e:
        logger.error(f"Error during duplicate removal: {e}")

def get_analysis_rows_not_in_sub_analysis(
    supabase: Client,
    analysis_table: str = "scraped_analysis",
    sub_analysis_table: str = "scraped_sub_analysis",
    url_column: str = "url"
) -> list:
    """
    Returns all rows from analysis_table whose url is not present in sub_analysis_table.
    Adds debug logging and normalizes URLs for accurate comparison.
    """
    batch_size = 1000
    offset = 0
    all_rows = []

    while True:
        response = supabase.rpc("get_urls_missing_in_sub_analysis").range(offset, offset + batch_size - 1).execute()
        data = response.data
        if not data:
            break
        all_rows.extend(data)
        offset += batch_size

    print(f"Fetched total: {len(all_rows)} rows")

    return all_rows

if __name__ == "__main__":
    reconcile_url_marker_supabase(client, "scraped_datav2", "scraped_analysis")