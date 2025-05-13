#!/usr/bin/env python3

import boto3
import csv
import json
import time
from pathlib import Path
from botocore.exceptions import BotoCoreError, ClientError

# Set as vars for providing inputs later
REGIONS = ["us-east-1", "us-west-2"]
MAX_RESULTS = 50
EVENT_LIST_FILE = "netsec_concerns.txt"
OUTPUT_FILE = "aws_cloudtrail_netsec_audit.csv"

# Load event names
event_names = Path(EVENT_LIST_FILE).read_text().splitlines()
event_names = [e.strip() for e in event_names if e.strip()]

# Calculate smart sleep based on AWS CloudTrail throttle: 2 req/sec
def dynamic_sleep(start_time):
    elapsed = time.time() - start_time
    sleep_needed = max(0.5 - elapsed, 0)
    if sleep_needed > 0:
        time.sleep(sleep_needed)

# Open CSV output
with open(OUTPUT_FILE, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Region", "Account", "Time", "User", "CallerIP", "Service", "EventName", "Resource"])

    for region in REGIONS:
        print(f"🔍 Scanning region: {region}")
        client = boto3.client("cloudtrail", region_name=region)

        for event_name in event_names:
            print(f"  ➤ Checking event: {event_name}")
            next_token = None
            while True:
                try:
                    start_time = time.time()
                    kwargs = {
                        "LookupAttributes": [{"AttributeKey": "EventName", "AttributeValue": event_name}],
                        "MaxResults": MAX_RESULTS
                    }
                    if next_token:
                        kwargs["NextToken"] = next_token

                    response = client.lookup_events(**kwargs)

                    for event in response.get("Events", []):
                        try:
                            cloud_event = json.loads(event["CloudTrailEvent"])
                            row = [
                                region,
                                cloud_event.get("recipientAccountId", ""),
                                event.get("EventTime", ""),
                                event.get("Username", ""),
                                cloud_event.get("sourceIPAddress", ""),
                                event.get("EventSource", "").split(".")[0],
                                event.get("EventName", ""),
                                ",".join([r.get("ResourceName", "") for r in event.get("Resources", []) if r.get("ResourceName")])
                            ]
                            writer.writerow(row)
                        except json.JSONDecodeError:
                            print(f"    ⚠️ Invalid CloudTrailEvent JSON for {event_name}")
                    
                    next_token = response.get("NextToken") # 50 is max for cloudtrail, you must go to next page
                    dynamic_sleep(start_time)

                    if not next_token:
                        break
                except (BotoCoreError, ClientError) as e:
                    print(f"    ❌ Error in region {region} for {event_name}: {e}")
                    break

print(f"✅ Scan complete. Results written to: {OUTPUT_FILE}")
