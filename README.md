# OCI Auto-Shutdown Agent

An ultra-lightweight Docker-packaged agent designed to run on individual Oracle Cloud Infrastructure (OCI) instances. It periodically monitors the tenancy budget and gracefully auto-stops the virtual instance at the OCI infrastructure level if spending limits are exceeded.

## Features

* **Ultra-lightweight**: Built on Python Alpine (minimal RAM and disk footprints).
* **Autonomous & Safe**: Automatically retrieves its own `Instance OCID` locally from the OCI Metadata Service (`192.0.0.192`), eliminating the need to manually configure the instance ID.
* **Clean Shutdown**: Utilizes the OCI SDK `STOP` instance action, which initiates a clean OS-level shutdown of the instance.
* **Telegram Alerts**: Sends rich notifications to a Telegram chat before executing the shutdown.
* **Safe Testing Mode**: Includes `DRY_RUN` and `SIMULATE_OVER_BUDGET` flags to verify the integration and Telegram alerts without actually shutting down the server.

## Deployment

1. Clone or copy this directory onto the OCI VPS instance you want to protect.
2. Configure the environment variables in a `.env` file or directly inside `docker-compose.yml` with your OCI API credentials:
   * `OCI_USER`: User OCID.
   * `OCI_TENANCY`: Tenancy OCID.
   * `OCI_FINGERPRINT`: OCI key fingerprint.
   * `OCI_REGION`: OCI Region (e.g., `sa-valparaiso-1`).
   * `OCI_KEY_CONTENT`: The contents of your API PEM private key in a single line (replacing actual newlines with `\n` characters).
   * `OCI_INSTANCE_ID`: (Optional) Manual fallback instance OCID if the metadata service is unreachable.
   * `TELEGRAM_BOT_TOKEN`: (Optional) Telegram Bot API token.
   * `TELEGRAM_CHAT_ID`: (Optional) Telegram chat ID where alerts should be sent.
   * `CHECK_INTERVAL`: Billing check interval in seconds (default is `1800` seconds / 30 minutes).
3. Spin up the container:
   ```bash
   docker compose up -d --build
   ```

## Testing & Simulation

To test that your OCI configuration and Telegram alerts are working properly without stopping your live server, configure these flags in your environment (e.g. `.env`):

```env
SIMULATE_OVER_BUDGET=true
DRY_RUN=true
```

Then recreate the container (`docker compose up -d`). The agent will immediately trigger a mock overrun alert, dispatch the Telegram notification, and print a simulated shutdown message to the logs:

```text
[SIMULATION] Forcing budget overrun status...
[ALERT] Budget exceeded ($12.5 USD). Stopping this instance...
[INFO] Telegram notification sent successfully.
[DRY RUN] Simulated shutdown (real VPS will not be stopped) for instance ...
```
Once verified, set both simulation flags to `false` and restart the container to return to normal active monitoring.
