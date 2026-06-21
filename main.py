import os
import sys
import time
import requests
import oci

# Configuración del intervalo (por defecto 30 minutos)
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL", 1800))

def get_instance_ocid():
    """Obtiene el OCID de la propia instancia desde el servicio de metadatos de OCI."""
    metadata_url = "http://192.0.0.192/opc/v2/instance/id"
    headers = {"Authorization": "Bearer Oracle"}
    try:
        response = requests.get(metadata_url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        print(f"[ERROR] No se pudo obtener el OCID de la instancia desde los metadatos: {e}")
    return None

def load_oci_config():
    """Prepara la configuración de OCI basada en variables de entorno."""
    user = os.environ.get("OCI_USER")
    tenancy = os.environ.get("OCI_TENANCY")
    fingerprint = os.environ.get("OCI_FINGERPRINT")
    region = os.environ.get("OCI_REGION")
    key_content = os.environ.get("OCI_KEY_CONTENT")

    if user and tenancy and fingerprint and key_content and region:
        # Limpiar posibles comillas y reemplazar saltos de línea de forma robusta
        pem_key = key_content.strip('"').strip("'").replace("\\\\n", "\n").replace("\\n", "\n")
        return {
            "user": user,
            "tenancy": tenancy,
            "fingerprint": fingerprint,
            "region": region,
            "key_content": pem_key
        }
    
    # Alternativa: cargar de archivo ~/.oci/config montado en /root/.oci/config
    default_config_path = "/root/.oci/config"
    if os.path.exists(default_config_path):
        try:
            profile = os.environ.get("OCI_PROFILE", "DEFAULT")
            return oci.config.from_file(default_config_path, profile)
        except Exception as e:
            print(f"[ERROR] Error al cargar configuración desde {default_config_path}: {e}")
            
    print("[ERROR] Credenciales OCI no configuradas. Por favor provea las variables de entorno o monte el archivo de configuración.")
    sys.exit(1)

def send_telegram_message(message):
    """Envía un mensaje de notificación a Telegram si los parámetros están configurados."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[WARNING] Telegram no configurado. Se omite el envío del mensaje.")
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
            print("[INFO] Notificación de Telegram enviada con éxito.")
        else:
            print(f"[ERROR] Error al enviar mensaje a Telegram: {response.text}")
    except Exception as e:
        print(f"[ERROR] Excepción al enviar mensaje a Telegram: {e}")

def run_monitor():
    print("[INIT] Iniciando agente auto-shutdown ultraligero...")
    config = load_oci_config()
    
    # Obtener OCID de la máquina actual
    instance_id = get_instance_ocid()
    if not instance_id:
        # Si no se puede obtener por metadatos (ej: pruebas locales), buscar variable
        instance_id = os.environ.get("OCI_INSTANCE_ID")
        
    if not instance_id:
        print("[WARNING] No se pudo determinar el OCID de esta instancia. El script solo advertirá pero no podrá apagar la máquina.")
    else:
        print(f"[INIT] Instancia detectada: {instance_id}")

    budget_client = oci.budget.BudgetClient(config)
    compute_client = oci.core.ComputeClient(config)
    tenancy_id = config.get("tenancy")

    while True:
        try:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Ejecutando revisión de presupuesto...")
            budgets = budget_client.list_budgets(compartment_id=tenancy_id).data
            
            over_budget = False
            current_spend = 0.0
            budget_name = ""
            budget_amount = 0.0
            
            for b in budgets:
                if b.lifecycle_state == "ACTIVE":
                    spend = b.actual_spend if b.actual_spend is not None else 0.0
                    print(f"  Presupuesto '{b.display_name}': Consumido = ${spend} USD / Límite = ${b.amount} USD")
                    if spend >= b.amount:
                        over_budget = True
                        current_spend = spend
                        budget_name = b.display_name
                        budget_amount = b.amount
                        break
            
            # Simulación forzada por entorno para pruebas
            if os.environ.get("SIMULATE_OVER_BUDGET", "false").lower() in ("true", "1", "yes"):
                print("  [SIMULACIÓN] Forzando estado de presupuesto superado...")
                over_budget = True
                if not budget_name:
                    budget_name = "Presupuesto_Simulado"
                    budget_amount = 10.0
                    current_spend = 12.5
            
            if over_budget:
                print(f"  [ALERTA] Presupuesto superado (${current_spend} USD). Deteniendo esta instancia...")
                
                # Enviar mensaje a Telegram antes de apagar
                dry_run = os.environ.get("DRY_RUN", "false").lower() in ("true", "1", "yes")
                tag_dry = " (SIMULACIÓN - DRY RUN)" if dry_run else ""
                msg = (
                    f"⚠️ <b>[ALERTA OCI] Presupuesto Superado{tag_dry}</b>\n\n"
                    f"El presupuesto <b>{budget_name}</b> (${budget_amount} USD) ha sido alcanzado o superado.\n"
                    f"<b>Consumo actual:</b> ${current_spend} USD\n"
                    f"<b>Instancia OCID:</b> <code>{instance_id or 'No detectada'}</code>\n\n"
                    f"🛑 Deteniendo el VPS ahora mismo para evitar cargos adicionales..."
                )
                send_telegram_message(msg)

                if instance_id:
                    if dry_run:
                        print(f"  [DRY RUN] Detención simulada (no se apagará el VPS real) para la instancia {instance_id}.")
                    else:
                        print(f"  [APAGANDO] Deteniendo instancia {instance_id} vía API OCI...")
                        compute_client.instance_action(instance_id=instance_id, action="STOP")
                else:
                    print("  [ERROR] No se puede apagar la instancia porque no se conoce su OCID.")
            else:
                print("  [OK] El consumo está dentro del límite de presupuesto.")
                
        except Exception as e:
            print(f"[ERROR] Error durante la revisión: {e}")
            
        print(f"Esperando {CHECK_INTERVAL_SECONDS} segundos para el próximo chequeo...")
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    run_monitor()

