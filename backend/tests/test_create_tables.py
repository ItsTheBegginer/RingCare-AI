import pytest
import boto3
from moto import mock_aws
from scripts.create_tables import create_events_table, create_settings_table, EVENTS_TABLE, SETTINGS_TABLE


@mock_aws
def test_create_tables_idempotent():
    ddb = boto3.resource("dynamodb", region_name="ap-south-1")

    # First call: creates tables
    t1 = create_events_table(ddb)
    t2 = create_settings_table(ddb)
    assert t1.table_name == EVENTS_TABLE
    assert t2.table_name == SETTINGS_TABLE

    # Second call: idempotent, does not fail
    t1_again = create_events_table(ddb)
    t2_again = create_settings_table(ddb)
    assert t1_again.table_name == EVENTS_TABLE
    assert t2_again.table_name == SETTINGS_TABLE
