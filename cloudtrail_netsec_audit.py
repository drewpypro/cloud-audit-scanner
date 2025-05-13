#!/usr/bin/env python3

import boto3
import csv
import json
import time
import re
from pathlib import Path
from botocore.exceptions import BotoCoreError, ClientError


REGIONS = ["us-east-1", "us-west-2"]
MAX_RESULTS = 50
EXCLUDED_USERS = ["AmazonEKS","25session"]
EVENT_LIST_FILE = "netsec_concerns.txt"
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
OUTPUT_FILE = f"aws_cloudtrail_netsec_audit_{timestamp}.csv"

event_names = Path(EVENT_LIST_FILE).read_text().splitlines()
event_names = [e.strip() for e in event_names if e.strip()]

def dynamic_sleep(start_time):
    elapsed = time.time() - start_time
    sleep_needed = max(0.5 - elapsed, 0)
    if sleep_needed > 0:
        time.sleep(sleep_needed)

def find_suspicious_cidrs(obj):
    suspicious = []

    def search_nested(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, (dict, list)):
                    search_nested(v)
                elif isinstance(v, str) and "cidr" in k.lower():
                    if re.match(r"\d+\.\d+\.\d+\.\d+/\d{1,2}", v):
                        prefix = int(v.split("/")[-1])
                        if 0 <= prefix <= 20:
                            suspicious.append(v)
        elif isinstance(d, list):
            for item in d:
                search_nested(item)

    search_nested(obj)
    return suspicious

def extract_security_flags(event_name, cloud_event):
    req = cloud_event.get("requestParameters") or {}
    resp = cloud_event.get("responseElements") or {}

    # CIDRs
    cidrs = find_suspicious_cidrs(req) + find_suspicious_cidrs(resp)

    # Public IP detection
    pub_ip = None
    try:
        instances = resp.get("instancesSet", {}).get("items", [])
        for inst in instances:
            # Check directly on instance level
            if "publicIp" in inst:
                pub_ip = inst["publicIp"]
            # Check in networkInterfaceSet
            ni_set = inst.get("networkInterfaceSet", {}).get("items", [])
            for ni in ni_set:
                assoc = ni.get("association", {})
                if "publicIp" in assoc:
                    pub_ip = assoc["publicIp"]
    except Exception:
        pass
    if not pub_ip and "associatePublicIpAddress" in json.dumps(req).lower():
        pub_ip = "true"

    return {
        "suspicious_cidrs": ", ".join(sorted(set(cidrs))) if cidrs else None,
        "public_ip": pub_ip
    }

with open(OUTPUT_FILE, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow([
        "Region", "Account", "Time", "User", "CallerIP", "ErrorCode", "Service", "EventName", "Resource",
        "SuspiciousCIDRs", "PublicIP"
    ])

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
                            username = event.get("Username", "").lower()
                            if any(excluded in username for excluded in EXCLUDED_USERS):
                                continue

                            flags = extract_security_flags(event_name, cloud_event)

                            row = [
                                region,
                                cloud_event.get("recipientAccountId", ""),
                                event.get("EventTime", ""),
                                event.get("Username", ""),
                                cloud_event.get("sourceIPAddress", ""),
                                cloud_event.get("errorCode", "None"),
                                event.get("EventSource", "").split(".")[0],
                                event.get("EventName", ""),
                                ",".join([r.get("ResourceName", "") for r in event.get("Resources", []) if r.get("ResourceName")]),
                                flags["suspicious_cidrs"],
                                flags["public_ip"]
                            ]
                            writer.writerow(row)
                        except json.JSONDecodeError:
                            print(f"    ⚠️ Invalid CloudTrailEvent JSON for {event_name}")
                    
                    next_token = response.get("NextToken")
                    dynamic_sleep(start_time)

                    if not next_token:
                        break
                except (BotoCoreError, ClientError) as e:
                    print(f"    ❌ Error in region {region} for {event_name}: {e}")
                    break

print(f"✅ Final audit complete. Results written to: {OUTPUT_FILE}")
