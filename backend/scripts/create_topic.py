#!/usr/bin/env python3
"""
Provisioning script for Amazon SNS alert topic for RingCare AI.
Idempotent: creates the topic if not present and returns the ARN.
Optionally subscribes an email address for caregiver alerts.

Usage:
    python backend/scripts/create_topic.py [--email user@example.com] [--topic-name ringcare-alerts]
"""
import argparse
import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Create or fetch RingCare AI Amazon SNS alert topic.")
    parser.add_argument("--topic-name", default=os.getenv("SNS_TOPIC_NAME", "ringcare-alerts"), help="SNS topic name")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"), help="AWS region")
    parser.add_argument("--email", default=None, help="Optional email address to subscribe")

    args = parser.parse_args()

    print(f"Connecting to Amazon SNS in region '{args.region}'...")
    try:
        sns = boto3.client("sns", region_name=args.region)
        resp = sns.create_topic(
            Name=args.topic_name,
            Attributes={
                "DisplayName": "RingCare AI Alerts",
            },
        )
        topic_arn = resp.get("TopicArn")
        print(f"\n[OK] SNS Topic ready:")
        print(f"     Topic Name: {args.topic_name}")
        print(f"     Topic ARN:  {topic_arn}")
    except ClientError as e:
        print(f"\n[ERROR] AWS SNS error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error connecting to AWS SNS: {e}", file=sys.stderr)
        sys.exit(1)

    if args.email:
        print(f"\nSubscribing email '{args.email}' to {topic_arn}...")
        try:
            sub_resp = sns.subscribe(
                TopicArn=topic_arn,
                Protocol="email",
                Endpoint=args.email,
                ReturnSubscriptionArn=True,
            )
            sub_arn = sub_resp.get("SubscriptionArn")
            print(f"[OK] Email subscription created:")
            print(f"     Subscription ARN: {sub_arn}")
            print(f"     NOTE: AWS has sent a confirmation email to {args.email}.")
            print(f"     The caregiver MUST click the confirmation link in the email to activate alerts.")
        except ClientError as e:
            print(f"[ERROR] Failed to subscribe email: {e}", file=sys.stderr)

    print("\n--------------------------------------------------------------")
    print("Action required: Add this to your backend/.env file:")
    print(f"SNS_TOPIC_ARN={topic_arn}")
    print("--------------------------------------------------------------\n")


if __name__ == "__main__":
    main()
