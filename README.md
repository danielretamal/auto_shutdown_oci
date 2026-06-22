# OCI Auto-Shutdown Agent

An ultra-lightweight Docker-packaged agent that periodically monitors the Oracle Cloud Infrastructure (OCI) tenancy budget and gracefully shuts down the virtual instance at the OCI infrastructure level if spending limits are exceeded.

This agent is ideal for protecting against unexpected billing surprises (e.g., from resource leaks, compromised accounts, or testing environments left active) by automatically stopping the instance.

## How It Works

1. **Active Monitoring**: The agent runs continuously in a loop, waking up at configurable intervals (`CHECK_INTERVAL`, default: 30 minutes).
2. **Budget Verification**: Using the OCI SDK, it queries all active budgets defined under the tenancy root compartment.
3. **Overrun Detection**: If the actual spend of any active budget equals or exceeds its configured limit (or if simulated via environment flags), the shutdown sequence triggers.
4. **Telegram Notification**: Before initiating the shutdown, the agent sends a formatted HTML alert via Telegram (if configured).
5. **Clean Shutdown**: It calls the OCI SDK Core Compute API to trigger a clean OS-level `STOP` action for the VPS instance.

---

## Configuration & Environment Variables

You can configure the agent either by passing environment variables (e.g., in a `.env` file or directly inside `docker-compose.yml`) or by mounting your existing `~/.oci/config` file.

### Environment Variables

| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `CHECK_INTERVAL` | No | `1800` | Inspection interval in seconds (e.g., `1800` = 30 minutes). |
| `OCI_USER` | Yes* | - | User OCID for OCI API. |
| `OCI_TENANCY` | Yes* | - | Tenancy OCID. |
| `OCI_FINGERPRINT` | Yes* | - | Fingerprint of the OCI API private key. |
| `OCI_REGION` | No | - | Target region (e.g., `sa-valparaiso-1`). If not provided, it is automatically queried from the IMDS metadata service. |
| `OCI_KEY_CONTENT` | Yes* | - | Private key PEM content in a single line (newlines replaced with `\n` or `\\n`). |
| `OCI_PROFILE` | No | `DEFAULT` | Target profile to read if using the mounted file option. |
| `OCI_INSTANCE_ID` | No | - | OCID of the target instance. Auto-detected from metadata if not supplied. |
| `TELEGRAM_BOT_TOKEN`| No | - | Bot API token for dispatching Telegram messages. |
| `TELEGRAM_CHAT_ID` | No | - | Target Telegram user or group chat ID. |
| `LOCAL_TEST_MODE` | No | `false` | Skips importing OCI libraries and running checks; runs a local Telegram mock test and exits. |
| `SIMULATE_OVER_BUDGET`| No | `false` | Simulates budget overrun during normal OCI checks. |
| `DRY_RUN` | No | `false` | Logs actions and sends Telegram alerts, but skips calling the actual OCI `STOP` command. |

*\* Note: Required only if not using the mounted config volume.*

### Authentication Options

#### Option A: Using Environment Variables (Recommended for Docker Compose)
Store your OCI credentials in a `.env` file in the same directory:
```env
OCI_USER=ocid1.user.oc1..xxxxxx
OCI_TENANCY=ocid1.tenancy.oc1..xxxxxx
OCI_FINGERPRINT=xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx
OCI_REGION=sa-valparaiso-1
OCI_KEY_CONTENT="-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQ...\n-----END RSA PRIVATE KEY-----"
TELEGRAM_BOT_TOKEN=XXXXXXXX
TELEGRAM_CHAT_ID=XXXXXXXX
```

#### Option B: Mounting OCI Config Directory
If you already have a configured `~/.oci` folder on your server, you can uncomment the volume mount in `docker-compose.yml`:
```yaml
volumes:
  - ~/.oci:/root/.oci:ro
```
The script will look for `/root/.oci/config` and read the profile specified by `OCI_PROFILE` (defaults to `DEFAULT`).

---

## Instance and Region Auto-Detection

The agent attempts to dynamically query the OCI Instance Metadata Service (IMDS) using both link-local IPs:
- `169.254.169.254`
- `192.0.0.192`

From IMDS, the agent auto-detects:
* **Instance ID (`id`)**: To know exactly which virtual machine needs to be stopped.
* **Compartment ID (`compartmentId`)**.
* **Region (`canonicalRegionName` / `region`)**: Used to initialize OCI API clients.

> [!IMPORTANT]
> If your container cannot reach the link-local metadata IPs due to Docker network isolation, uncomment `network_mode: "host"` in `docker-compose.yml` or manually specify the `OCI_INSTANCE_ID` and `OCI_REGION` env variables.

---

## Deployment

1. Clone or copy the directory onto the VPS instance you want to monitor.
2. Create and configure your `.env` file.
3. Start the daemon with Docker Compose:
   ```bash
   docker compose up -d --build
   ```

To check current execution logs:
```bash
docker compose logs -f
```

---

## Testing & Verification

### Local Test Mode
You can quickly test your Telegram notifications on any local machine (even without OCI setup or libraries) using the `LOCAL_TEST_MODE` flag:
```env
LOCAL_TEST_MODE=true
TELEGRAM_BOT_TOKEN=XXXXXXXX
TELEGRAM_CHAT_ID=XXXXXXXX
```
Running the agent in this mode triggers an immediate mock overrun notification and exits safely.

### Budget Overrun Simulation
To test the full OCI flow (verifying OCI API connection and compartment budget query) without actually shutting down the server, use:
```env
SIMULATE_OVER_BUDGET=true
DRY_RUN=true
```
The agent will connect to OCI, fetch budgets, print them, and then simulate a budget breach. It will send a Telegram message stating `(SIMULATION - DRY RUN)` and log that a shutdown was simulated.
