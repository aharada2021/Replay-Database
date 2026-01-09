#!/usr/bin/env python3
"""
DynamoDB dev -> prod migration script
"""
import boto3
import sys
import time

REGION = "ap-northeast-1"
dynamodb = boto3.resource("dynamodb", region_name=REGION)


def migrate_table(source_table_name: str, dest_table_name: str):
    """Migrate all items from source table to destination table."""
    source_table = dynamodb.Table(source_table_name)
    dest_table = dynamodb.Table(dest_table_name)

    print(f"Migrating {source_table_name} -> {dest_table_name}")

    # Scan all items from source
    items = []
    scan_kwargs = {}
    while True:
        response = source_table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        print(f"  Scanned {len(items)} items so far...")

    print(f"  Total items to migrate: {len(items)}")

    # Batch write to destination
    with dest_table.batch_writer() as batch:
        for i, item in enumerate(items):
            batch.put_item(Item=item)
            if (i + 1) % 100 == 0:
                print(f"  Written {i + 1}/{len(items)} items")

    print(f"  Migration complete: {len(items)} items")
    return len(items)


def main():
    migrations = [
        ("wows-replays-dev", "wows-replays-prod"),
        ("wows-ship-match-index-dev", "wows-ship-match-index-prod"),
        # Sessions table is not migrated (users will re-login)
    ]

    total = 0
    for source, dest in migrations:
        count = migrate_table(source, dest)
        total += count
        time.sleep(1)  # Brief pause between tables

    print(f"\nTotal migrated: {total} items")


if __name__ == "__main__":
    main()
