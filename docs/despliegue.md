# Despliegue del panel en AWS

Cómo publicar el panel visual (`python -m panel`) en una instancia EC2 con Ubuntu 24.04, detrás de Caddy, con HTTPS y usuario y contraseña (decisión D18). Todo se hace desde la consola web de AWS y una terminal con `ssh`.

Qué queda en línea:

- **Caddy** es lo único que escucha en internet (puertos 80 y 443). Obtiene y renueva solo el certificado HTTPS y pide usuario y contraseña en todas las rutas salvo `/salud`.
- **El panel** corre como servicio `xenomorfo-q` con el usuario `xq`, escucha solo en `127.0.0.1:8000` y se reinicia solo si se cae o si la instancia arranca.
- **Una partida por visitante:** cada navegador recibe una cookie de sesión. Hay como máximo 30 sesiones vivas, y una sesión se descarta tras 30 minutos sin uso.
- **Cupos del chat:** como máximo 20 preguntas por sesión y 60 por hora en todo el servidor. Pasado un cupo, el chat responde con un aviso y el mapa, el modo observar y el modo Tú siguen funcionando. Los cupos se cambian con `XQ_PANEL_MAX_SESION` y `XQ_PANEL_MAX_HORA` (0 desactiva el cupo).
- **La clave del modelo** vive solo en `/etc/xenomorfo-q.env` del servidor (dueño root, permisos 600). Nunca llega al navegador ni a los registros.

Archivos en [deploy/](../deploy/):

| Archivo | Para qué |
|---|---|
| [instalar.sh](../deploy/instalar.sh) | Instala todo; se puede correr varias veces. |
| [actualizar.sh](../deploy/actualizar.sh) | Trae la última versión de `main` y reinicia el servicio. |
| [xenomorfo-q.service](../deploy/xenomorfo-q.service) | Servicio systemd del panel. |
| [Caddyfile.plantilla](../deploy/Caddyfile.plantilla) | Configuración de Caddy; el script la completa con el dominio, el usuario y el hash de la contraseña. |
| [xenomorfo-q.env.plantilla](../deploy/xenomorfo-q.env.plantilla) | Plantilla vacía de `/etc/xenomorfo-q.env`. |

## 1. Alarma de presupuesto

Antes de crear nada, una alarma avisa por correo si el gasto pasa de un monto.

1. En la consola de AWS, buscar **Billing and Cost Management** y abrir **Budgets**.
2. **Create budget**, **Use a template (simplified)**, plantilla **Monthly cost budget**.
3. Monto: por ejemplo 10 USD. Correo: el de quien administra la cuenta. **Create budget**.

En AWS Academy Learner Lab no se pueden crear presupuestos; el propio laboratorio muestra el crédito restante (ver la sección 11).

## 2. Lanzar la instancia

1. Abrir **EC2**, **Instances**, **Launch instances**.
2. **Name:** `xenomorfo-q`.
3. **Application and OS Images:** Ubuntu, **Ubuntu Server 24.04 LTS (HVM), SSD Volume Type**, arquitectura **64-bit (x86)**.
4. **Instance type:** `t3.micro` (2 vCPU, 1 GiB). Alcanza: el panel usa poca memoria y el modelo corre en OpenAI, no en la instancia.
5. **Key pair:** **Create new key pair**, tipo ED25519, formato `.pem`. El archivo se descarga una sola vez: guardarlo fuera del repositorio.
6. **Network settings:** dejar la VPC por defecto y **Create security group** (paso 3).
7. **Configure storage:** 8 GiB gp3 (el valor por defecto) alcanza.
8. **Launch instance**.

## 3. Grupo de seguridad

En **Network settings** del paso anterior (o después, en **Security Groups**, **Edit inbound rules**):

| Tipo | Puerto | Origen | Motivo |
|---|---|---|---|
| SSH | 22 | **My IP** | Solo tu conexión puede entrar por `ssh`. |
| HTTP | 80 | Anywhere (0.0.0.0/0) | Caddy lo usa para obtener el certificado y redirigir a HTTPS. |
| HTTPS | 443 | Anywhere (0.0.0.0/0) | El panel. |

No se abre el puerto 8000: el panel solo escucha dentro de la instancia. Si cambias de red (otra casa, la universidad), actualiza la regla de SSH con **My IP** otra vez.

## 4. IP elástica

Sin IP elástica, la IP pública cambia cada vez que la instancia se detiene, y con ella el dominio.

1. **EC2**, **Network & Security**, **Elastic IPs**, **Allocate Elastic IP address**, **Allocate**.
2. Seleccionarla, **Actions**, **Associate Elastic IP address**, elegir la instancia `xenomorfo-q`, **Associate**.
3. Anotar la IP, por ejemplo `3.91.20.15`.

AWS cobra cada IPv4 pública por hora, también la elástica mientras la instancia está detenida. Al terminar el proyecto hay que liberarla (sección 10).

## 5. Entrar por ssh

Desde la carpeta donde quedó el archivo `.pem`:

```bash
chmod 400 xenomorfo-q.pem
ssh -i xenomorfo-q.pem ubuntu@3.91.20.15
```

## 6. Instalar

En la instancia:

```bash
curl -fsSLO https://raw.githubusercontent.com/jalvarez01/Xenomorfo-Q/main/deploy/instalar.sh
sudo bash instalar.sh
```

El script:

1. Instala `python3-venv`, `git` y Caddy (desde el repositorio oficial de Caddy).
2. Crea el usuario `xq`, clona `main` en `/opt/xenomorfo-q` y crea el entorno virtual con `requirements.txt`.
3. Crea `/etc/xenomorfo-q.env` vacío, con permisos 600, solo si no existe.
4. Instala y arranca el servicio `xenomorfo-q`.
5. Pregunta tres datos:
   - **Dominio:** sugiere `<ip-con-guiones>.sslip.io`, por ejemplo `3-91-20-15.sslip.io`; basta con Enter.
   - **Usuario:** por defecto `equipo`.
   - **Contraseña:** mínimo 10 caracteres, no se muestra al escribirla. De la contraseña solo se guarda el hash bcrypt de `caddy hash-password`.
6. Escribe el Caddyfile, recarga Caddy, comprueba `/salud` e imprime los pasos siguientes.

[sslip.io](https://sslip.io) es un DNS público que resuelve `3-91-20-15.sslip.io` a `3.91.20.15`, así que no hace falta comprar un dominio para tener HTTPS.

## 7. Completar las variables

```bash
sudo nano /etc/xenomorfo-q.env
```

Completar estas dos líneas, guardar (Ctrl+O, Enter) y salir (Ctrl+X):

```
XQ_PROVEEDOR=openai
OPENAI_API_KEY=<la clave>
```

Después:

```bash
sudo systemctl restart xenomorfo-q
```

- Conviene usar una clave de OpenAI solo para este servidor, en un proyecto con límite de gasto mensual bajo: así se puede revocar sin afectar las demás.
- No copies ni muestres el contenido de ese archivo (ni con `cat` en una captura).
- Sin clave, el panel funciona igual y el chat explica qué falta.

## 8. Probar

```bash
curl https://3-91-20-15.sslip.io/salud
```

Debe responder `{"ok": true}`. Después, en el navegador:

1. Abrir `https://3-91-20-15.sslip.io/` y entrar con el usuario y la contraseña.
2. Revisar que el mapa carga y que **Paso** avanza la partida.
3. Hacer una pregunta de ejemplo, por ejemplo C1.
4. Abrir el panel en otro navegador o en una ventana privada: debe tener su propia partida.

Si algo falla:

```bash
sudo systemctl status xenomorfo-q
sudo journalctl -u xenomorfo-q -n 50
sudo journalctl -u caddy -n 50
```

El registro del panel no guarda las peticiones ni el chat. Si Caddy no obtiene el certificado, revisar que los puertos 80 y 443 estén abiertos y que el dominio tenga la IP elástica actual.

## 9. Actualizar

Cuando haya una versión nueva en `main`:

```bash
sudo bash /opt/xenomorfo-q/deploy/actualizar.sh
```

Trae `main`, reinstala las dependencias, reinicia el servicio y comprueba `/salud`. No toca `/etc/xenomorfo-q.env` ni el acceso.

Para cambiar el dominio, el usuario o la contraseña, volver a correr `sudo bash /opt/xenomorfo-q/deploy/instalar.sh` y responder `s` cuando lo pregunte.

## 10. Detener la instancia para ahorrar crédito

- **Detener:** **EC2**, **Instances**, seleccionar `xenomorfo-q`, **Instance state**, **Stop instance**.
  - Detenida no cobra cómputo, pero sí el disco y la IP elástica.
  - Al volver a arrancarla (**Start instance**), el panel y Caddy arrancan solos, con el mismo dominio gracias a la IP elástica.
- **Al terminar el proyecto:**
  1. **Terminate instance**.
  2. En **Elastic IPs**, **Release Elastic IP addresses**.
  3. Revocar la clave de OpenAI que usaba el servidor.

## 11. AWS Academy Learner Lab

Si la cuenta es de un Learner Lab de AWS Academy y no una cuenta propia, cambian algunas cosas; las reglas exactas están en el README del laboratorio.

- **El crédito es fijo y limitado**, y no se pueden crear presupuestos (sección 1).
- **Al terminar la sesión del laboratorio** (unas 4 horas), las instancias se detienen, y vuelven a arrancar al iniciar el laboratorio otra vez.
  - El panel no queda en línea de forma permanente. Para la sustentación hay que iniciar el laboratorio antes y probar `/salud`.
  - Con la IP elástica, el dominio no cambia entre sesiones.
- **Restricciones de la cuenta:** solo algunas regiones (normalmente `us-east-1` y `us-west-2`) y algunos tipos de instancia; `t3.micro` suele estar permitido.
  - Se puede usar el par de llaves del laboratorio (`vockey`, archivo `labsuser.pem`) en vez de crear uno.
