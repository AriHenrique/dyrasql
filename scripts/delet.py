import boto3
from boto3.dynamodb.conditions import Attr

TABLE_NAME = "dyrasql-history"
AWS_PROFILE = None  # Exemplo: "default" ou "dev", ou deixe None


def delete_all_items():
    if AWS_PROFILE:
        session = boto3.Session(profile_name=AWS_PROFILE)
    else:
        session = boto3.Session()

    dynamodb = session.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)

    print(f"🔍 Scanning table: {TABLE_NAME}")

    deleted = 0
    scan_kwargs = {}

    with table.batch_writer() as batch:
        while True:
            response = table.scan(**scan_kwargs)
            items = response.get("Items", [])

            for item in items:
                key = {}
                for key_name in table.key_schema:
                    attr = key_name["AttributeName"]
                    key[attr] = item[attr]

                batch.delete_item(Key=key)
                deleted += 1

            if "LastEvaluatedKey" in response:
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            else:
                break

    print(f"✅ Done! Deleted {deleted} items from {TABLE_NAME}")


if __name__ == "__main__":
    delete_all_items()
