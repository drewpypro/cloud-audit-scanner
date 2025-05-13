# cloud-audit-scanner

# Goals
- create list of domain specific concerns in the form of eventName(AWS) or methodName (GCP). 
- scan CSP logging api's for this criteria in the past 24 hours or 7 days and return results as follows; 
    - account,date/time,userName,callerIP,service,action

# Manual working commands
- In AWS this works to find any changes in a given account i'm logged into and produces a csv output

```
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=ACreateNetworkInterface \
  --output json | jq -r '
  .Events[] | 
    .CloudTrailEvent |= fromjson |
    [
      .CloudTrailEvent.recipientAccountId,
      .EventTime,
      .Username,
      .CloudTrailEvent.sourceIPAddress,
      (.EventSource | split(".") | first),
      .EventName,
      (.Resources | map(.ResourceName) // [] | join(","))
    ] | @csv'

  "394823984723","2025-03-03T20:08:44-07:00","frankb","s3","CreateBucket","drewpys989588498","1.1.1.1"
  ```

- In GCP this works to find any changes in a given account i'm logged into and produces a csv output
  ```
    gcloud logging read "protoPayload.methodName=storage.buckets.create" \
    --format=json 2>/dev/null | jq -r '
    .[] | [
        .resource.labels.project_id,
        .timestamp,
        .protoPayload.authenticationInfo.principalEmail,
        .protoPayload.requestMetadata.callerIp,
        .protoPayload.methodName,
        (.protoPayload.resourceName | split("/") | last)
    ] | @csv'
    "project123zyx","2025-05-12T17:35:15.161442825Z","frankb@gmail.com","1.1.1.1","storage.buckets.create","drewpys989588498"

- Rebuild each query into URL for accessing directly
- AWS
    - https://console.aws.amazon.com/cloudtrail/home?region=<region>#/events?EventId=<eventID>
    - https://console.aws.amazon.com/cloudtrail/home?region=us-east-1#/events?EventId=fa089df7-af73-4653-ad95-c39cb6b4c8f4

        aws cloudtrail lookup-events   --lookup-attributes AttributeKey=EventName,AttributeValue=CreateBucket   --output json 
        {
            "Events": [
                {
                    "EventId": "fa089df7-af73-4653-ad95-c39cb6b4c8f4",
                    "EventName": "CreateBucket",
                    "ReadOnly": "false",
                    "AccessKeyId": "",
                    "EventTime": "2025-03-03T20:08:44-07:00",
                    "EventSource": "s3.amazonaws.com",
                    "Username": "drewpy",
                    "Resources": [
                        {
                            "ResourceType": "AWS::S3::Bucket",
                            "ResourceName": "goblin-iej4ij8r84h"
                        }
                    ],
                    "CloudTrailEvent": "{\"eventVersion\":\"1.11\",\"userIdentity\":{\"type\":\"Root\",\"principalId\":\"11111111111111111111111\",\"arn\":\"arn:aws:iam::11111111111111111111111:root\",\"accountId\":\"11111111111111111111111\",\"accessKeyId\":\"\"},\"eventTime\":\"2025-03-04T03:08:44Z\",\"eventSource\":\"s3.amazonaws.com\",\"eventName\":\"CreateBucket\",\"awsRegion\":\"us-east-1\",\"sourceIPAddress\":\"69.69.69.69\",\"userAgent\":\"[APN/1.0 HashiCorp/1.0 Terraform/1.11.0 (+https://www.terraform.io) terraform-provider-aws/5.82.2 (+https://registry.terraform.io/providers/hashicorp/aws) aws-sdk-go-v2/1.32.6 ua/2.1 os/linux lang/go#1.23.3 md/GOOS#linux md/GOARCH#amd64 api/s3#1.71.0]\",\"requestParameters\":{\"bucketName\":\"projectyuzsbucketse33423-k4vr\",\"Host\":\"projectyuzsbucketse33423-k4vr.s3.amazonaws.com\",\"x-amz-acl\":\"private\"},\"responseElements\":null,\"additionalEventData\":{\"SignatureVersion\":\"SigV4\",\"CipherSuite\":\"TLS_AES_128_GCM_SHA256\",\"bytesTransferredIn\":0,\"AuthenticationMethod\":\"AuthHeader\",\"x-amz-id-2\":\"ssr4jyfltbC6/243Zjdj4330u44hjf5442nd349830387+9/6vRpjXfPxu17i9tYIU=\",\"bytesTransferredOut\":0},\"requestID\":\"CKYFAQB569H1JQ2\",\"eventID\":\"fa089df7-af73-4653-ad95-c39cb6b4c8f4\",\"readOnly\":false,\"eventTyp
        e\":\"AwsApiCall\",\"managementEvent\":true,\"recipientAccountId\":\"11111111111111111111111\",\"eventCategory\":\"Management\",\"tlsDetails\":{\"tlsVersion\":\"TLSv1.3\",\"cipherSuite\":\"TLS_AES_128_GCM_SHA256\",\"clientProvidedHostHeader\":\"projectyuzsbucketse33423-k4vr.s3.amazonaws.com\"}}"
                }
            ]
        }
- GCP
    - rebuild a new url based on a query based on the reported line output; 
     - https://console.cloud.google.com/logs/query;query=<FILTER>?project=<PROJECT_ID>
     - https://console.cloud.google.com/logs/query;query=protoPayload.methodName%3D%22storage.buckets.create%22;cursorTimestamp=2025-05-12T17:35:15.161442825Z&project=project123zyx
     - https://console.cloud.google.com/logs/query;query=protoPayload.methodName%3D%22storage.buckets.create%22%20AND%20timestamp:%20%222025-05-12T17:35:15.161442825Z%22;cursorTimestamp=2025-05-12T17:35:15.161442825Z;duration=P1D?referrer=search&inv=1&invt=AbxPlg&project=project123zyx

