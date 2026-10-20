# Verificación de Convertix — 19 de octubre de 2026

## Resultado

Aplicación de escritorio implementada e instalada para `camiska`, sin sudo, sin paquetes globales nuevos
y sin commits ni push. La aceptación completa todavía requiere accionar **Convertir…** desde el menú real
de Dolphin. Ese paso no se ha podido automatizar y no se presenta como aprobado.

| Comprobación | Resultado y evidencia |
|---|---|
| Motor, casos obligatorios, rutas y seguridad | **44 aprobadas**, 0 omitidas: [JUnit](test-results-engine.xml) |
| PDF con texto real → TXT | **1 aprobada**, 0 omitidas: [JUnit](test-results-pdf-text.xml) |
| Permisos privados de salida | **1 aprobada**: [JUnit](test-results-permissions.xml) |
| Qt Quick sin pantalla, lotes e instalador | **12 aprobadas**, 0 omitidas: [JUnit](test-results-ui-install.xml) |
| Qt Quick en Wayland real | **10 aprobadas, 1 omitida**: [JUnit](test-results-wayland.xml) |
| Aplicación instalada, selección PDF con ratón, DOCX → PDF y notificación KDE | **Aprobado**: [resultado JSON](desktop-smoke-result.json), [captura](wayland-completed.png) |
| Original del DOCX de escritorio | SHA-256 antes/después idéntico, registrado en el JSON anterior |
| Instalación aislada | Python `-I`, sin directorios `site-packages` de `/usr` en `sys.path`; paquetes importados del venv local |
| Entrada Dolphin | Instalada, ejecutable, `%F`, icono y prioridad `TopLevel`; sintaxis KDE inspeccionada |
| Dolphin real | Abierto con configuración temporal; selección del DOCX por AT-SPI correcta; AT-SPI no pudo abrir el contexto en Wayland |

Son **58 pruebas automatizadas aprobadas en las baterías principales**. Las 10 aprobadas de Wayland
repiten casos gráficos en otro backend y no se suman como casos nuevos. La omisión de Wayland corresponde
al cierre por pérdida de foco: KWin no concedió activar una segunda ventana sin un gesto físico.
La misma prueba pasó en el backend sin pantalla; falta el clic físico en otra aplicación.

## Conversiones comprobadas

Pasaron las nueve rutas obligatorias con archivos válidos, originales sin cambios y comprobaciones de contenido:

1. DOCX → PDF.
2. ODT → DOCX.
3. XLSX → PDF.
4. CSV → XLSX, incluida la comprobación de que `=2+2` permanezca como texto.
5. PPTX → PDF.
6. Markdown → DOCX.
7. PNG → JPG, con alfa compuesto sobre blanco.
8. JPG → PDF.
9. PDF → PNG.

La matriz adicional recorre todos los destinos anunciados para muestras DOCX, ODT, RTF, TXT, HTML,
Markdown, XLSX, ODS, CSV, TSV, PPTX, ODP, PNG, JPG, WebP, BMP, TIFF, GIF y PDF.
Otras tres pruebas crean documentos binarios DOC/XLS/PPT reales mediante LibreOffice, detectan su contenido
OLE y recorren todos sus destinos. Una prueba independiente comprueba PDF con dos páginas de texto → TXT.
En conjunto cubren los **110 pares origen/destino** registrados en este equipo, usando muestras sintéticas.
Esto acredita funcionamiento y estructura de salida, no fidelidad absoluta con cualquier documento complejo.

También se comprobaron nombres con espacios, tildes y japonés, extensión engañosa, colisiones concurrentes,
rechazo de sobrescritura, imágenes animadas, TIFF/PDF multipágina, conservación de todos los cuadros,
exportación de todas las hojas CSV/TSV, fuentes corruptas, PDF sin texto, enlaces simbólicos, permisos POSIX,
cancelación real con terminación de procesos, cancelación de pendientes de un lote, tiempo límite,
originales conservados, limpieza de temporales, límite de entrada, orientación EXIF y bloqueo de sockets de red.

El instalador se probó en un prefijo con espacios y tildes, desde otro directorio, con importación hostil desde
el directorio de trabajo, actualización, rechazo de archivos editados manualmente y desinstalación conservadora.

La interfaz se probó con 0, 2, 3, 6, 8 y 12 opciones; posiciones sin superposición, paginación circular,
ratón, flechas, Enter, Escape, temas claro/oscuro, escala reducida, lotes reales y doble activación.
HiDPI se verifica parcialmente mediante la escala Qt; no se probó con cambios físicos entre monitores de distinta densidad.

## Entorno observado

- Fedora Linux 44, edición KDE; Plasma 6.7.5; Dolphin 26.08.1.
- Sesión Wayland; Qt/PySide6 y shiboken6 6.11.2; Python 3.14.8.
- LibreOffice Writer/Calc/Impress 26.2.6.3; Pillow 12.3.0; olefile 0.47.
- `pdfinfo`, `pdftoppm`, `pdftotext`, `notify-send` y `libseccomp.so.2` disponibles.
- Pandoc, PyMuPDF y Gemini CLI no disponibles. No se necesitaron ni se instalaron.
- pytest 9.1.1 disponible. QtTest procede de PySide6; pytest-qt no es requisito.

El aislamiento de comandos de Codex impedía acceder al bus/sesión gráfica y arrancar LibreOffice.
Los motores y las pruebas Wayland se ejecutaron con el acceso autorizado fuera de ese aislamiento,
manteniendo los documentos de prueba locales. El trabajador de Convertix conserva su propio bloqueo de red.

## Instalación y arquitectura entregadas

El lanzador está en `~/.local/bin/convertix`; la acción, en
`~/.local/share/kio/servicemenus/convertix.desktop`. La instalación contiene un venv sin
`system-site-packages`, con copias locales de PySide6, shiboken6, Pillow y olefile.
La versión de cada paquete figura en `~/.local/share/convertix/manifest.json`.
LibreOffice, Qt nativo, Poppler y libseccomp se reutilizan del sistema.

La separación definitiva es interfaz Qt Quick/controlador Qt, detección por contenido,
registro central de rutas, servicio de archivos/procesos, trabajador aislado, adaptadores por motor,
validación, preferencias XDG y notificaciones. El [README](../README.md) documenta los módulos,
actualización, uso, diagnóstico y desinstalación.

## Prueba manual de aceptación pendiente

1. En Dolphin abre la carpeta `examples` de este proyecto.
2. Haz clic derecho en `Documento de prueba.docx` y comprueba que **Convertir…** aparece en el primer nivel.
3. Acciona **Convertir…** y elige PDF en el círculo. Ya hay PDF de las pruebas de escritorio;
   el nuevo debe usar el siguiente nombre disponible, como `Documento de prueba (convertido 3).pdf`.
4. Comprueba que puedes abrirlo, que el DOCX sigue intacto y que llega una notificación de KDE.
5. Abre de nuevo el círculo y haz clic en otra aplicación: debe cerrarse sin iniciar una conversión.
6. Repite con varios archivos seleccionados y un destino común.

No se probaron físicamente sesiones X11, varios monitores, escalas distintas por monitor, discos FAT/NTFS
o desconexión de unidades durante escritura. La publicación falla de forma explícita si el montaje no
admite `renameat2(RENAME_NOREPLACE)`. No se afirma cobertura de archivos de cientos de MiB: se probaron
una imagen de 4000×4000 y el rechazo de una entrada dispersa superior a 512 MiB.

## Límites y siguientes mejoras

No hay OCR ni PDF → DOCX; PDF escaneado no ofrece TXT salvo que ya tenga texto.
Los vínculos a recursos fuera del documento no se incorporan. La fidelidad depende de filtros y fuentes;
CSV no conserva estilos/fórmulas y las animaciones se exportan como cuadros numerados o páginas con aviso.
El aislamiento de red y recursos no es un sandbox completo del sistema de archivos.

Las siguientes mejoras útiles son completar la aceptación manual de Dolphin, ensayar documentos reales
representativos sin subirlos a ningún servicio, probar monitores/montajes físicos y añadir OCR o un sandbox
de archivos como módulos optativos. No hay fallos críticos confirmados pendientes en las rutas probadas;
las restricciones de validación anteriores siguen abiertas.
