import os
import sys
import time
import requests

LOCAL_TEST = os.environ.get("LOCAL_TEST_MODE", "false").lower() in ("true", "1", "yes")
if not LOCAL_TEST:
    import oci

VERSION = "1.0"

# Check interval configuration (default: 30 minutes)
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL", 1800))

def get_metadata_value(path):
    """Retrieves a specific field from the OCI metadata service trying standard IPs."""
    ips = ["169.254.169.254", "192.0.0.192"]
    headers = {"Authorization": "Bearer Oracle"}
    for ip in ips:
        metadata_url = f"http://{ip}/opc/v2/instance/{path}"
        try:
            response = requests.get(metadata_url, headers=headers, timeout=3)
            if response.status_code == 200:
                return response.text.strip()
        except Exception:
            continue
    return None

def load_oci_config():
    """Prepares the OCI configuration based on environment variables."""
    user = os.environ.get("OCI_USER")
    tenancy = os.environ.get("OCI_TENANCY")
    fingerprint = os.environ.get("OCI_FINGERPRINT")
    region = os.environ.get("OCI_REGION")
    key_content = os.environ.get("OCI_KEY_CONTENT")

    # If region is not provided, try to fetch it from metadata
    if not region:
        print("[INFO] OCI_REGION not provided in environment. Attempting to retrieve from IMDS...")
        region = get_metadata_value("canonicalRegionName") or get_metadata_value("region")
        if region:
            print(f"[INFO] Auto-detected region from metadata: {region}")

    if user and tenancy and fingerprint and key_content and region:
        # Clean potential quotes and replace newlines robustly
        pem_key = key_content.strip('"').strip("'").replace("\\\\n", "\n").replace("\\n", "\n")
        return {
            "user": user,
            "tenancy": tenancy,
            "fingerprint": fingerprint,
            "region": region,
            "key_content": pem_key
        }
    
    # Alternative: load configuration from the mounted ~/.oci/config file
    default_config_path = "/root/.oci/config"
    if os.path.exists(default_config_path):
        try:
            profile = os.environ.get("OCI_PROFILE", "DEFAULT")
            return oci.config.from_file(default_config_path, profile)
        except Exception as e:
            print(f"[ERROR] Error loading config from {default_config_path}: {e}")
            
    print("[ERROR] OCI credentials not configured. Please supply environment variables or mount a config file.")
    sys.exit(1)

def send_telegram_message(message):
    """Sends a notification message to Telegram if credentials are configured."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[WARNING] Telegram not configured. Skipping message dispatch.")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("[INFO] Telegram notification sent successfully.")
        else:
            print(f"[ERROR] Failed to send Telegram message: {response.text}")
    except Exception as e:
        print(f"[ERROR] Exception occurred while sending Telegram message: {e}")

def run_monitor():
    print(f"[INIT] Starting lightweight auto-shutdown agent v{VERSION}...")
    config = load_oci_config()
    
    # Retrieve local instance OCID and compartment ID
    instance_id = get_metadata_value("id")
    if not instance_id:
        instance_id = os.environ.get("OCI_INSTANCE_ID")
        
    compartment_id = get_metadata_value("compartmentId")
        
    if not instance_id:
        print("[WARNING] Could not determine the OCID of this instance. The script will only warn but won't be able to stop the machine.")
    else:
        print(f"[INIT] Instance detected: {instance_id}")

    if compartment_id:
        print(f"[INIT] Compartment detected: {compartment_id}")

    budget_client = oci.budget.BudgetClient(config)
    compute_client = oci.core.ComputeClient(config)
    tenancy_id = config.get("tenancy")

    while True:
        try:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Executing budget review...")
            budgets = budget_client.list_budgets(compartment_id=tenancy_id).data
            
            over_budget = False
            current_spend = 0.0
            budget_name = ""
            budget_amount = 0.0
            
            for b in budgets:
                if b.lifecycle_state == "ACTIVE":
                    spend = b.actual_spend if b.actual_spend is not None else 0.0
                    print(f"  Budget '{b.display_name}': Spent = ${spend} USD / Limit = ${b.amount} USD")
                    if spend >= b.amount:
                        over_budget = True
                        current_spend = spend
                        budget_name = b.display_name
                        budget_amount = b.amount
                        break
            
            # Forced simulation flag for testing
            if os.environ.get("SIMULATE_OVER_BUDGET", "false").lower() in ("true", "1", "yes"):
                print("  [SIMULATION] Forcing budget overrun status...")
                over_budget = True
                if not budget_name:
                    budget_name = "Simulated_Budget"
                    budget_amount = 10.0
                    current_spend = 12.5
            
            if over_budget:
                print(f"  [ALERT] Budget exceeded (${current_spend} USD). Stopping this instance...")
                
                dry_run = os.environ.get("DRY_RUN", "false").lower() in ("true", "1", "yes")
                tag_dry = " (SIMULATION - DRY RUN)" if dry_run else ""
                
                comp_text = f"<b>Compartment OCID:</b> <code>{compartment_id}</code>\n" if compartment_id else ""
                msg = (
                    f"⚠️ <b>[OCI ALERT] Budget Exceeded{tag_dry}</b>\n\n"
                    f"The budget <b>{budget_name}</b> (${budget_amount} USD) has been met or exceeded.\n"
                    f"<b>Current spend:</b> ${current_spend} USD\n"
                    f"<b>Instance OCID:</b> <code>{instance_id or 'Not detected'}</code>\n"
                    f"{comp_text}\n"
                    f"🛑 Stopping the VPS immediately to prevent further charges..."
                )
                send_telegram_message(msg)

                if instance_id:
                    if dry_run:
                        print(f"  [DRY RUN] Simulated shutdown (real VPS will not be stopped) for instance {instance_id}.")
                    else:
                        print(f"  [STOPPING] Stopping instance {instance_id} via OCI API...")
                        compute_client.instance_action(instance_id=instance_id, action="STOP")
                else:
                    print("  [ERROR] Cannot stop the instance because its OCID is not known.")
            else:
                print("  [OK] Spend is within the budget limits.")
                
        except Exception as e:
            print(f"[ERROR] Error during review: {e}")
            
        print(f"Waiting {CHECK_INTERVAL_SECONDS} seconds for the next check...")
        time.sleep(CHECK_INTERVAL_SECONDS)

def run_local_simulation():
    """Simulate budget overrun locally without OCI credentials."""
    print(f"[INIT] Local test mode v{VERSION} - simulating budget overrun...")
    instance_id = os.environ.get("OCI_INSTANCE_ID", "unknown")
    dry_run = os.environ.get("DRY_RUN", "true").lower() in ("true", "1", "yes")
    tag_dry = " (SIMULATION - DRY RUN)" if dry_run else ""

    msg = (
        f"⚠️ <b>[OCI ALERT] Budget Exceeded{tag_dry}</b>\n\n"
        f"The budget <b>Simulated_Budget</b> ($10.00 USD) has been met or exceeded.\n"
        f"<b>Current spend:</b> $12.50 USD\n"
        f"<b>Instance OCID:</b> <code>{instance_id}</code>\n"
        f"<b>Version:</b> {VERSION}\n\n"
        f"🛑 Stopping the VPS immediately to prevent further charges..."
    )
    send_telegram_message(msg)
    print(f"  [DRY RUN] Simulated shutdown (real VPS will not be stopped) for instance {instance_id}.")

if __name__ == "__main__":
    if LOCAL_TEST:
        run_local_simulation()
    else:
        run_monitor()
