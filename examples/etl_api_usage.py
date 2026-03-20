#!/usr/bin/env python3
"""Example usage of the ETL Trigger API.

Demonstrates:
1. Triggering ETL pipelines manually
2. Receiving webhook triggers
3. Monitoring pipeline status
4. Viewing execution history
5. Listing available pipelines

Usage:
    PYTHONPATH=. python3 examples/etl_api_usage.py
"""

from __future__ import annotations

import json
import sys

import requests


def main() -> None:
    """Run ETL API usage examples."""
    base_url = "http://localhost:8000"
    api_key = "dev_api_key_12345"  # Development API key

    headers = {"X-API-Key": api_key}

    print("=" * 80)
    print("ETL Trigger API Examples")
    print("=" * 80)

    # Example 1: List available pipelines
    print("\n1. List Available Pipelines")
    print("-" * 80)
    resp = requests.get(f"{base_url}/api/etl/pipelines", headers=headers)
    if resp.status_code == 200:
        pipelines = resp.json()
        print(f"Found {len(pipelines)} pipelines:")
        for p in pipelines:
            print(f"  - {p['name']:15} | {p['entity_type']:20} | {p['schedule']}")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")

    # Example 2: Trigger papers pipeline (incremental mode)
    print("\n2. Trigger Papers Pipeline (Incremental Mode)")
    print("-" * 80)
    trigger_body = {
        "source": "manual",
        "pipeline_name": "papers",
        "mode": "incremental",
        "force_full": False,
    }
    resp = requests.post(
        f"{base_url}/api/etl/trigger",
        headers=headers,
        json=trigger_body,
    )
    if resp.status_code == 200:
        result = resp.json()
        run_id = result["run_id"]
        print(f"Pipeline triggered successfully!")
        print(f"  Run ID: {run_id}")
        print(f"  Status: {result['status']}")
        print(f"  Message: {result['message']}")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")
        sys.exit(1)

    # Example 3: Check pipeline status
    print("\n3. Check Pipeline Status")
    print("-" * 80)
    resp = requests.get(f"{base_url}/api/etl/status/{run_id}", headers=headers)
    if resp.status_code == 200:
        status = resp.json()
        print(f"Run Status for {run_id}:")
        print(f"  Pipeline: {status['pipeline_name']}")
        print(f"  Status: {status['status']}")
        print(f"  Processed: {status['records_processed']}")
        print(f"  Failed: {status['records_failed']}")
        print(f"  Skipped: {status['records_skipped']}")
        print(f"  Duration: {status['duration_seconds']:.3f}s")
        print(f"  Started: {status['started_at']}")
        print(f"  Completed: {status['completed_at']}")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")

    # Example 4: Trigger facilities pipeline (FULL mode)
    print("\n4. Trigger Facilities Pipeline (FULL Mode)")
    print("-" * 80)
    trigger_body = {
        "source": "schedule",
        "pipeline_name": "facilities",
        "mode": "full",
        "force_full": False,
    }
    resp = requests.post(
        f"{base_url}/api/etl/trigger",
        headers=headers,
        json=trigger_body,
    )
    if resp.status_code == 200:
        result = resp.json()
        print(f"Full rebuild triggered for facilities")
        print(f"  Run ID: {result['run_id']}")
        print(f"  Status: {result['status']}")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")

    # Example 5: Webhook trigger
    print("\n5. Webhook Trigger (Weather Data Changed)")
    print("-" * 80)
    webhook_payload = {
        "event": "data_changed",
        "entity_type": "WeatherCondition",
        "data": {
            "source": "KMA Marine Weather",
            "records_updated": 42,
        },
    }
    resp = requests.post(
        f"{base_url}/api/etl/webhook/weather",
        headers=headers,
        json=webhook_payload,
    )
    if resp.status_code == 200:
        result = resp.json()
        print(f"Webhook received and processed!")
        print(f"  Run ID: {result['run_id']}")
        print(f"  Pipeline: {result['pipeline_name']}")
        print(f"  Status: {result['status']}")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")

    # Example 6: View execution history
    print("\n6. View Execution History")
    print("-" * 80)
    resp = requests.get(f"{base_url}/api/etl/history?limit=10", headers=headers)
    if resp.status_code == 200:
        history = resp.json()
        print(f"Total runs: {history['total']}")
        print(f"Recent runs ({len(history['runs'])}):")
        for run in history["runs"]:
            print(f"  [{run['started_at']}] {run['pipeline_name']:15} - {run['status']:10} "
                  f"(processed: {run['records_processed']}, failed: {run['records_failed']})")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")

    print("\n" + "=" * 80)
    print("Examples completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to the API server.")
        print("Please start the server first:")
        print("  uvicorn kg.api.app:app --reload")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)
