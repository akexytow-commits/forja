-- 007: Rama 4b — Academia de Seguridad (18-...md, MOD-090) + Laboratorio Linux (19-...md, MOD-091).

-- DB-009 currículo: Ruta → Módulo → Lección (estructura; el contenido lo genera el tutor al abrir la lección).
CREATE TABLE IF NOT EXISTS learning_paths (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre      TEXT NOT NULL,
  enfoque     TEXT NOT NULL CHECK (enfoque IN ('ofensivo','defensivo','ambos')),
  tipo        TEXT NOT NULL CHECK (tipo IN ('skill','rol')),
  descripcion TEXT,
  orden       INTEGER NOT NULL DEFAULT 0,
  enrolado_at TEXT
);
CREATE TABLE IF NOT EXISTS learning_modules (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  path_id    INTEGER NOT NULL REFERENCES learning_paths(id) ON DELETE CASCADE,
  nombre     TEXT NOT NULL,
  dificultad TEXT NOT NULL CHECK (dificultad IN ('fundamental','facil','medio','dificil')),
  orden      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS learning_sections (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  module_id          INTEGER NOT NULL REFERENCES learning_modules(id) ON DELETE CASCADE,
  titulo             TEXT NOT NULL,
  tipo               TEXT NOT NULL CHECK (tipo IN ('teoria','interactiva','evaluacion')),
  contenido_guia     TEXT,
  pregunta           TEXT,
  respuesta_esperada TEXT,   -- alternativas separadas por '|'; NULL = la valora el tutor
  orden              INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_mod_path ON learning_modules(path_id, orden);
CREATE INDEX IF NOT EXISTS idx_sec_mod ON learning_sections(module_id, orden);

-- DB-010 progreso (una fila por sección enrolada).
CREATE TABLE IF NOT EXISTS learning_progress (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  section_id    INTEGER NOT NULL UNIQUE REFERENCES learning_sections(id) ON DELETE CASCADE,
  estado        TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','en_curso','completada')),
  xp            INTEGER NOT NULL DEFAULT 0,
  pistas_usadas INTEGER NOT NULL DEFAULT 0,
  acertada      INTEGER NOT NULL DEFAULT 0,
  leccion_md    TEXT,      -- lo que generó el tutor (para no regenerarlo cada vez)
  notas         TEXT,
  completed_at  TEXT
);

-- DB-011 catálogo de herramientas/habilidades.
CREATE TABLE IF NOT EXISTS tool_catalog (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre     TEXT NOT NULL,
  categoria  TEXT,
  para_que   TEXT NOT NULL,
  enfoque    TEXT NOT NULL CHECK (enfoque IN ('ofensivo','defensivo','ambos')),
  seccion_id INTEGER REFERENCES learning_sections(id) ON DELETE SET NULL
);

-- Gate de laboratorio (BTN-087, FR-038): la declaración vigente es la última con activo = 1.
CREATE TABLE IF NOT EXISTS academia_lab (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  entorno      TEXT NOT NULL CHECK (entorno IN ('htb','thm','local','ctf','otro')),
  descripcion  TEXT NOT NULL,
  declarado_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  activo       INTEGER NOT NULL DEFAULT 1
);

-- Conversación tutor/copiloto por lección (FR-075/076).
CREATE TABLE IF NOT EXISTS academia_mensajes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  section_id INTEGER REFERENCES learning_sections(id) ON DELETE CASCADE,
  rol        TEXT NOT NULL CHECK (rol IN ('user','assistant')),
  contenido  TEXT NOT NULL,
  ts         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_acamsg ON academia_mensajes(section_id, id);

-- Auditoría: tipos nuevos para la declaración de laboratorio y las acciones del Laboratorio Linux (L-A4, ST-040).
CREATE TABLE audit_log_v7 (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime')),
  tipo    TEXT NOT NULL CHECK (tipo IN ('cambio_alcance','escalado_nube','accion_seguridad_confirmada',
                                        'descarga_modelo','export','engagement','guardarrail',
                                        'academia_laboratorio','academia_enfoque','lab_accion')),
  detalle TEXT
);
INSERT INTO audit_log_v7 (id, ts, tipo, detalle) SELECT id, ts, tipo, detalle FROM audit_log;
DROP TABLE audit_log;
ALTER TABLE audit_log_v7 RENAME TO audit_log;

INSERT OR IGNORE INTO settings (key, value) VALUES
  ('seguridad.enfoque',           'ofensivo'),
  ('seguridad.actividad',         'trabajo'),
  ('academia.xp_por_dificultad',  '{"fundamental":10,"facil":20,"medio":40,"dificil":80}'),
  ('academia.seccion',            ''),
  ('lab.backend',                 ''),           -- '' = el recomendado tras la detección
  ('lab.distro',                  'kali-linux'),
  ('lab.working_dir',             ''),           -- '' = %USERPROFILE%\FORJA-lab
  ('lab.attackbox_url',           'https://tryhackme.com/');

-- ---------------------------------------------------------------- semilla §A7 (orientativa, editable)
INSERT INTO learning_paths (id, nombre, enfoque, tipo, descripcion, orden) VALUES
 (1, 'Elige dirección: ofensivo o defensivo', 'ambos', 'skill', 'Qué hace un red team y un blue team, qué se practica en cada lado y cómo es un laboratorio legal.', 0),
 (2, 'Fundamentos ofensivos', 'ofensivo', 'skill', 'Redes, Linux y web: lo que todo lo demás da por sabido.', 1),
 (3, 'Pentester Jr', 'ofensivo', 'rol', 'Metodología de una prueba de intrusión en laboratorio: reconocimiento, enumeración, explotación controlada e informe.', 2),
 (4, 'Red Teamer', 'ofensivo', 'rol', 'Active Directory, movimiento lateral y escalada de privilegios en laboratorios dedicados.', 3),
 (5, 'Bug Bounty Hunter', 'ofensivo', 'rol', 'Web a fondo (OWASP Top 10), alcance, ética y redacción de informes. Enlaza con el modo Trabajo.', 4),
 (6, 'Fundamentos defensivos', 'defensivo', 'skill', 'Redes, logs y sistemas desde el lado de quien defiende.', 1),
 (7, 'Analista SOC Nivel 1', 'defensivo', 'rol', 'SIEM, triaje de alertas, análisis de tráfico y de phishing recibido.', 2),
 (8, 'Respuesta a incidentes y forense', 'defensivo', 'rol', 'Ciclo de respuesta, adquisición de evidencias, línea temporal y análisis de memoria/disco.', 3);

INSERT INTO learning_modules (id, path_id, nombre, dificultad, orden) VALUES
 (1, 1, 'Red team vs blue team', 'fundamental', 1),
 (2, 2, 'Redes y protocolos', 'fundamental', 1),
 (3, 2, 'Linux para seguridad', 'fundamental', 2),
 (4, 2, 'Cómo funciona la web', 'facil', 3),
 (5, 3, 'Reconocimiento y enumeración', 'facil', 1),
 (6, 3, 'Explotación controlada en laboratorio', 'medio', 2),
 (7, 3, 'Escalada de privilegios en Linux', 'medio', 3),
 (8, 4, 'Active Directory básico', 'medio', 1),
 (9, 4, 'Movimiento lateral en laboratorio', 'dificil', 2),
 (10, 5, 'OWASP Top 10', 'facil', 1),
 (11, 5, 'Proxy web y pruebas manuales', 'medio', 2),
 (12, 5, 'Alcance, ética e informes', 'facil', 3),
 (13, 6, 'Redes para defensores', 'fundamental', 1),
 (14, 6, 'Logs y registros del sistema', 'fundamental', 2),
 (15, 7, 'SIEM y triaje de alertas', 'facil', 1),
 (16, 7, 'Análisis de tráfico', 'medio', 2),
 (17, 8, 'Ciclo de respuesta a incidentes', 'facil', 1),
 (18, 8, 'Forense de disco y memoria', 'dificil', 2);

INSERT INTO learning_sections (id, module_id, titulo, tipo, contenido_guia, pregunta, respuesta_esperada, orden) VALUES
 (1, 1, 'Qué hace cada equipo', 'teoria', 'Diferencia red team / blue team / purple team; roles laborales típicos; por qué se practica solo en laboratorios.', '¿Cómo se llama el equipo que detecta y responde a ataques?', 'blue team|blue|equipo azul|azul', 1),
 (2, 1, 'Tu laboratorio legal', 'teoria', 'Opciones legales: salas de HTB/THM, apps vulnerables propias (Juice Shop, DVWA, Metasploitable), CTF. Qué NO es legal.', '¿Puedes practicar contra la web de tu instituto sin permiso? (sí/no)', 'no', 2),
 (3, 2, 'Modelo TCP/IP y puertos', 'teoria', 'Capas, TCP vs UDP, handshake de tres vías, puertos conocidos (22, 80, 443, 53, 445).', '¿Qué puerto TCP usa SSH por defecto?', '22', 1),
 (4, 2, 'DNS y HTTP de cerca', 'interactiva', 'En tu laboratorio, resuelve un nombre con dig/nslookup y haz una petición con curl -v; observa cabeceras.', '¿Qué tipo de registro DNS traduce un nombre a una IPv4?', 'a|registro a', 2),
 (5, 2, 'Evaluación: redes', 'evaluacion', 'Combina capas, puertos y DNS.', '¿Cuántos pasos tiene el handshake de TCP?', '3|tres', 3),
 (6, 3, 'Moverse por la terminal', 'interactiva', 'ls, cd, cat, grep, find, permisos (rwx), usuarios y sudo. Ejercicio en el Linux del laboratorio.', '¿Qué comando muestra el directorio actual?', 'pwd', 1),
 (7, 3, 'Permisos y SUID', 'interactiva', 'chmod/chown, notación octal, qué es el bit SUID y por qué importa en escalada.', '¿Qué permisos octales significan rwxr-xr-x?', '755', 2),
 (8, 4, 'Peticiones, respuestas y cookies', 'teoria', 'Métodos HTTP, códigos de estado, cookies y sesiones, same-origin.', '¿Qué código HTTP significa «no encontrado»?', '404', 1),
 (9, 4, 'Herramientas del navegador', 'interactiva', 'DevTools: pestaña red, almacenamiento, consola; contra una app de laboratorio (Juice Shop).', NULL, NULL, 2),
 (10, 5, 'Reconocimiento pasivo y activo', 'teoria', 'Diferencia pasivo/activo, por qué el alcance importa, qué se documenta.', '¿Mirar registros DNS públicos es reconocimiento pasivo o activo?', 'pasivo', 1),
 (11, 5, 'Escaneo de puertos en laboratorio', 'interactiva', 'Escanea la máquina de tu sala (HTB/THM o Metasploitable local) e interpreta los servicios. Solo IPs del laboratorio.', '¿Qué opción de nmap detecta versiones de servicios?', '-sv|-sV', 2),
 (12, 5, 'Enumeración web', 'interactiva', 'Descubrimiento de contenido y tecnologías en la app del laboratorio; leer robots.txt y cabeceras.', '¿Qué fichero suele listar rutas que los buscadores no deben indexar?', 'robots.txt|robots', 3),
 (13, 6, 'De una versión a una vulnerabilidad', 'teoria', 'Buscar avisos públicos (CVE) para la versión hallada, leer el aviso, entender el impacto antes de tocar nada.', '¿Qué significan las siglas CVE?', 'common vulnerabilities and exposures', 1),
 (14, 6, 'Explotación guiada en tu sala', 'interactiva', 'Con la máquina de la sala: valida la hipótesis paso a paso; la flag está en el laboratorio.', 'Introduce la flag que encontraste en la sala.', NULL, 2),
 (15, 7, 'Enumerar para escalar', 'interactiva', 'sudo -l, binarios SUID, tareas cron, ficheros con credenciales; metodología, no recetas.', '¿Qué comando lista lo que tu usuario puede ejecutar con sudo?', 'sudo -l', 1),
 (16, 7, 'Evaluación: escalada', 'evaluacion', 'Escala en la máquina de la sala y trae la flag de root.', 'Introduce la flag de root de la sala.', NULL, 2),
 (17, 8, 'Dominios, usuarios y Kerberos', 'teoria', 'Controlador de dominio, LDAP, Kerberos y NTLM a nivel conceptual.', '¿Qué protocolo de autenticación usa AD por defecto?', 'kerberos', 1),
 (18, 8, 'Enumerar AD en un laboratorio', 'interactiva', 'En un laboratorio de AD dedicado: usuarios, grupos y relaciones.', NULL, NULL, 2),
 (19, 9, 'Credenciales y confianza', 'teoria', 'Qué es el movimiento lateral, pass-the-hash a nivel conceptual y cómo se detecta.', NULL, NULL, 1),
 (20, 10, 'Inyecciones', 'interactiva', 'SQLi y XSS en Juice Shop/DVWA: por qué ocurren y cómo se arreglan (consultas parametrizadas, escape).', '¿Cuál es la defensa principal contra la inyección SQL?', 'consultas parametrizadas|parametrizadas|prepared statements|sentencias preparadas', 1),
 (21, 10, 'Control de acceso roto', 'interactiva', 'IDOR y falta de autorización en la app del laboratorio.', '¿Qué siglas describen acceder a objetos de otro usuario cambiando un identificador?', 'idor', 2),
 (22, 11, 'Interceptar con un proxy', 'interactiva', 'Configurar el proxy web con el navegador del laboratorio; repetir y modificar peticiones.', NULL, NULL, 1),
 (23, 12, 'Leer un programa de bug bounty', 'teoria', 'Alcance, exclusiones, safe harbor, qué no probar (DoS, ingeniería social).', '¿Está normalmente permitido el DoS en un programa de bug bounty? (sí/no)', 'no', 1),
 (24, 12, 'Escribir un buen informe', 'teoria', 'Resumen, impacto, pasos, evidencia, mitigación (plantilla del modo Trabajo).', NULL, NULL, 2),
 (25, 13, 'Qué se ve en la red', 'teoria', 'Flujos, NetFlow, puertos anómalos, beaconing.', '¿Qué herramienta gráfica clásica abre capturas .pcap?', 'wireshark', 1),
 (26, 14, 'Logs de Linux y Windows', 'interactiva', 'auth.log, journalctl, visor de eventos; ID 4625 (inicio de sesión fallido).', '¿Qué ID de evento de Windows indica un inicio de sesión fallido?', '4625', 1),
 (27, 15, 'Cómo trabaja un SIEM', 'teoria', 'Ingesta, normalización, reglas de correlación, falsos positivos.', NULL, NULL, 1),
 (28, 15, 'Triaje de una alerta', 'interactiva', 'Dado un evento de ejemplo, decide si es verdadero positivo y qué escalar.', NULL, NULL, 2),
 (29, 16, 'Analizar una captura', 'interactiva', 'Con una captura de laboratorio: filtros, seguir flujo TCP, extraer IOC.', '¿Qué filtro de Wireshark muestra solo tráfico HTTP?', 'http', 1),
 (30, 17, 'Fases NIST', 'teoria', 'Preparación, detección y análisis, contención/erradicación/recuperación, lecciones aprendidas.', '¿Cuál es la última fase del ciclo de respuesta del NIST?', 'lecciones aprendidas|post-incidente|actividad post-incidente', 1),
 (31, 18, 'Línea temporal y evidencias', 'teoria', 'Orden de volatilidad, cadena de custodia, hashes.', '¿Qué es más volátil, la RAM o el disco?', 'ram|la ram', 1),
 (32, 18, 'Memoria en laboratorio', 'interactiva', 'Con un volcado de memoria de laboratorio: procesos, conexiones, artefactos.', NULL, NULL, 2);

INSERT INTO tool_catalog (nombre, categoria, para_que, enfoque, seccion_id) VALUES
 ('Terminal Linux (bash)', 'Sistemas', 'Base de todo: moverse, leer ficheros, filtrar salidas y automatizar.', 'ambos', 6),
 ('dig / nslookup', 'Redes', 'Consultar DNS: qué IP tiene un nombre, qué registros existen.', 'ambos', 4),
 ('curl', 'Web', 'Hacer peticiones HTTP a mano y ver cabeceras y respuestas.', 'ambos', 4),
 ('nmap', 'Reconocimiento', 'Descubrir hosts, puertos y versiones de servicios dentro del laboratorio.', 'ofensivo', 11),
 ('Descubrimiento de contenido (gobuster/ffuf)', 'Web', 'Encontrar rutas y ficheros no enlazados en la app del laboratorio.', 'ofensivo', 12),
 ('DevTools del navegador', 'Web', 'Ver peticiones, cookies y almacenamiento de una web.', 'ambos', 9),
 ('Proxy web (Burp Suite / OWASP ZAP)', 'Web', 'Interceptar, repetir y modificar peticiones entre el navegador y la app.', 'ofensivo', 22),
 ('Búsqueda de avisos (CVE/NVD, searchsploit)', 'Investigación', 'Relacionar la versión de un servicio con vulnerabilidades públicas conocidas.', 'ofensivo', 13),
 ('Metasploit (en laboratorio)', 'Explotación', 'Marco de pruebas para validar vulnerabilidades conocidas en máquinas de práctica.', 'ofensivo', 14),
 ('linPEAS / enumeración local', 'Escalada', 'Revisar de forma sistemática configuraciones que permiten escalar privilegios.', 'ofensivo', 15),
 ('BloodHound', 'Active Directory', 'Visualizar relaciones de AD para entender rutas de privilegio en un laboratorio.', 'ambos', 18),
 ('Wireshark / tcpdump', 'Tráfico', 'Capturar y analizar tráfico de red: protocolos, flujos e indicadores.', 'defensivo', 29),
 ('Visor de eventos / journalctl', 'Logs', 'Leer los registros del sistema operativo para detectar actividad.', 'defensivo', 26),
 ('SIEM (Splunk / Elastic / Wazuh)', 'Detección', 'Centralizar logs, correlacionar eventos y generar alertas.', 'defensivo', 27),
 ('Sigma / YARA', 'Detección', 'Escribir reglas de detección para logs (Sigma) y para ficheros (YARA).', 'defensivo', 28),
 ('Volatility', 'Forense', 'Analizar volcados de memoria: procesos, conexiones y artefactos.', 'defensivo', 32),
 ('Autopsy / Sleuth Kit', 'Forense', 'Examinar imágenes de disco y construir una línea temporal.', 'defensivo', 31);
