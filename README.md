# OCI Auto-Shutdown Agent

Agente ultraligero empaquetado en Docker diseñado para ejecutarse en instancias individuales de Oracle Cloud (OCI). 
Monitorea de forma periódica el presupuesto de la Tenancy en la que reside y, si detecta que se ha superado el tope asignado, se auto-apaga a nivel de infraestructura OCI.

## Características

* **Ultraligero**: Construido sobre Python Alpine (peso mínimo en RAM y almacenamiento).
* **Seguro y Autónomo**: Obtiene su propio `Instance OCID` localmente a través del servicio de metadatos de OCI (`192.0.0.192`), por lo que no es necesario configurarle manualmente el ID de la máquina donde corre.
* **Apagado Limpio**: Utiliza la acción `STOP` del SDK de OCI, lo que realiza un apagado del sistema operativo de manera ordenada en la instancia.

## Despliegue en la Instancia

1. Clona o copia esta carpeta en la máquina VPS de OCI que deseas auto-proteger.
2. Edita las variables de entorno en el archivo `docker-compose.yml` con tus credenciales de API de OCI correspondientes a la cuenta:
   * `OCI_USER`
   * `OCI_TENANCY`
   * `OCI_FINGERPRINT`
   * `OCI_REGION`
   * `OCI_KEY_CONTENT` (El texto de tu archivo `.pem` en una sola línea, usando `\n` para los saltos de línea).
   * `TELEGRAM_BOT_TOKEN` (Opcional: Token del bot de Telegram para alertas).
   * `TELEGRAM_CHAT_ID` (Opcional: ID de chat de Telegram donde enviar el reporte).
3. Levanta el contenedor:
   ```bash
   docker compose up -d --build
   ```

El agente se ejecutará en segundo plano, revisando el estado de facturación cada 30 minutos por defecto (puedes ajustar `CHECK_INTERVAL` en segundos).
Cuando se exceda el presupuesto, el agente enviará una notificación vía Telegram (si está configurada) justo antes de iniciar la detención del VPS.

