#!/usr/bin/env python3
"""
Idempotent script to provision DynamoDB tables and GSIs for RingCare AI.
Usage:
    python backend/scripts/create_tables.py
"""
import os
import sys
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

REGION = os.getenv("AWS_REGION", "ap-south-1")
ENDPOINT = os.getenv("DDB_ENDPOINT") or None
EVENTS_TABLE = os.getenv("DDB_EVENTS_TABLE", "RingCareEvents")
SETTINGS_TABLE = os.getenv("DDB_SETTINGS_TABLE", "RingCareSettings")


def get_dynamodb():
    kwargs = {"region_name": REGION}
    if ENDPOINT:
        kwargs["endpoint_url"] = ENDPOINT
    return boto3.resource("dynamodb", **kwargs)


def create_events_table(ddb):
    print(f"Checking table '{EVENTS_TABLE}'...")
    try:
        table = ddb.Table(EVENTS_TABLE)
        table.load()
        print(f"Table '{EVENTS_TABLE}' already exists (status: {table.table_status}).")
        return table
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise

    print(f"Creating table '{EVENTS_TABLE}' with GSIs...")
    table = ddb.create_table(
        TableName=EVENTS_TABLE,
        KeySchema=[
            {"AttributeName": "event_id", "KeyType": "HASH"},  # Partition Key
        ],
        AttributeDefinitions=[
            {"AttributeName": "event_id", "AttributeType": "S"},
            {"AttributeName": "home_id", "AttributeType": "S"},
            {"AttributeName": "event_ts", "AttributeType": "N"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "id", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by-home-time",
                "KeySchema": [
                    {"AttributeName": "home_id", "KeyType": "HASH"},
                    {"AttributeName": "event_ts", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "by-status-time",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "event_ts", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "by-public-id",
                "KeySchema": [
                    {"AttributeName": "id", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"Waiting for '{EVENTS_TABLE}' to become ACTIVE...")
    table.wait_until_exists()
    print(f"Table '{EVENTS_TABLE}' is ACTIVE.")
    return table


def create_settings_table(ddb):
    print(f"Checking table '{SETTINGS_TABLE}'...")
    try:
        table = ddb.Table(SETTINGS_TABLE)
        table.load()
        print(f"Table '{SETTINGS_TABLE}' already exists (status: {table.table_status}).")
        return table
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise

    print(f"Creating table '{SETTINGS_TABLE}'...")
    table = ddb.create_table(
        TableName=SETTINGS_TABLE,
        KeySchema=[
            {"AttributeName": "home_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "home_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"Waiting for '{SETTINGS_TABLE}' to become ACTIVE...")
    table.wait_until_exists()
    print(f"Table '{SETTINGS_TABLE}' is ACTIVE.")
    return table


def print_iam_policy():
    print("\n--- Least-Privilege IAM Policy for DynamoDB ---")
    print(f"""{{
  "Version": "2012-10-17",
  "Statement": [
    {{
      "Sid": "RingCareDynamoDBAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:BatchWriteItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:{REGION}:*:table/{EVENTS_TABLE}",
        "arn:aws:dynamodb:{REGION}:*:table/{EVENTS_TABLE}/index/*",
        "arn:aws:dynamodb:{REGION}:*:table/{SETTINGS_TABLE}"
      ]
    }}
  ]
}}""")


def main():
    ddb = get_dynamodb()
    create_events_table(ddb)
    create_settings_table(ddb)
    print_iam_policy()
    print("\nDynamoDB setup complete!")


if __name__ == "__main__":
    main()
