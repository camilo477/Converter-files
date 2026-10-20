# Convertix 2.0 — Verificación del 19–20 de octubre de 2026

## Resultado y alcance

Se amplió el proyecto existente y se actualizó la instalación de usuario en `~/.local` a **2.0.0**.
No se creó otra aplicación, no se modificaron originales ni preferencias existentes y no se hicieron commits ni push.
La carpeta `.git` está vacía y Git no la reconoce como repositorio; no se inventa un estado de ramas o cambios Git.
El [informe anterior](VERIFICATION-v1.md) y sus capturas se conservaron como referencia.

**La aceptación de extremo a extremo desde el clic derecho de Dolphin sigue pendiente de intervención manual.**
Las pruebas de la ventana radial instalada son independientes de esa aceptación y no se usan para darla por aprobada.

## Pruebas ejecutadas

| Batería | Resultado | Evidencia |
|---|---|---|
| Antes de modificar código: originales y matriz reportada de 110 pares | **58 aprobadas**, sin omisiones | [JUnit de línea base](v2-baseline.xml) |
| Versión final: regresión y pruebas nuevas | **99 aprobadas**, sin errores ni omisiones | [JUnit completo](v2-full-tests.xml) |
| Qt Quick en Wayland real | **12 aprobadas, 1 omitida** | [JUnit Wayland](v2-wayland.xml) |
| Qt Quick con backend X11 bajo XWayland | **13 aprobadas** | [JUnit XWayland](v2-xwayland.xml) |
| Ajuste final de contraste de la paginación: distribución, teclado, Escape y alfa | **8 aprobadas** | [JUnit visual final](v2-final-visual.xml) |
| Instalación real: seis flujos con selección mediante ratón y notificaciones KDE | **Aprobados** | [Resultado de escritorio](v2-desktop-smoke-result.json) |
| Dolphin aislado bajo XWayland | No se pudo abrir el menú contextual mediante automatización | [Resultado, sin éxito declarado](v2-dolphin-result.json) |

Las baterías gráficas repiten casos y no se suman a las 99 como casos distintos. La omisión Wayland se debe
a que KWin no concedió activar la segunda ventana para simular pérdida de foco. La misma prueba pasó en XWayland
y sin pantalla; falta comprobar el clic físico en otra aplicación bajo Wayland.

Se conservan los 58 casos originales. Sus expectativas se ajustaron únicamente donde cambia deliberadamente
el comportamiento: versión instalada 2.0.0 y GIF → WebP como una animación con todos sus cuadros, en lugar de
una carpeta de fotogramas. No se eliminaron pruebas para esconder errores.

También se recorren las rutas OCR completas hacia Markdown, HTML, ODT y RTF; se corrigió la clasificación de
GlyphLessFont para que su carácter monoespaciado no convierta todo el texto reconocido en bloques de código.
Las tablas con OCR previo se extraen sin necesitar otro reconocimiento.

Las 41 pruebas adicionales verifican texto editable, tablas, valores/códigos, imágenes separadas, encabezados,
código, enlaces relativos, dos columnas, saltos/secciones, OCR español/inglés juntos y por separado, páginas
rotadas, portada vacía, páginas mixtas y cabecera digital con cuerpo escaneado, OCR previo sin reprocesar,
PDF sin texto, cancelación, archivos originales, limpieza de temporales, preferencias preservadas, alfa real,
animaciones con tiempos/bucles/transparencia y formatos Office antiguos con contenido conservado tras reconversión.

En XLS se comprueba el rechazo de datos más allá de 65 536 filas/256 columnas. En PDF → XLSX se verifica una
hoja por tabla, dos tablas independientes, encabezados, números, identificadores `0012` y texto `=2+2` que permanece
como cadena y no se convierte en fórmula. Si no hay tablas no aparece XLSX; no se genera una hoja vacía de éxito.

## Flujos comprobados en la aplicación instalada

Se ejecutó `scripts/desktop_smoke.py` con el Python aislado de la instalación y `QT_QPA_PLATFORM=wayland`:

1. DOCX → PDF.
2. PDF digital con tabla → DOCX editable.
3. PDF escaneado → DOCX editable mediante OCR.
4. PDF escaneado → Markdown con encabezados y tabla.
5. PDF digital con tabla → XLSX con valores extraídos.
6. PDF mixto con portada vacía → PDF con texto seleccionable.

En los seis casos se eligió el destino mediante eventos de ratón sobre el control radial real, se validó el
archivo, el SHA-256 del original permaneció idéntico y `notify-send` obtuvo aceptación del servicio KDE.
El registro JSON contiene rutas, hashes y resultado de cada notificación. Los DOCX se abrieron con python-docx
y contienen párrafos con texto reconocido. Las pruebas de OCR comparan además los píxeles renderizados del PDF
buscable con el original: la capa textual añadida no cambió la apariencia de las muestras.

Las capturas son [DOCX → PDF](v2-completed-docx-to-pdf.png), [PDF → DOCX](v2-completed-pdf-to-docx.png),
[escaneado → DOCX](v2-completed-ocr-to-docx.png), [escaneado → Markdown](v2-completed-ocr-to-markdown.png),
[PDF → XLSX](v2-completed-pdf-to-xlsx.png) y [PDF buscable](v2-completed-searchable-pdf.png).
Estos resultados usan archivos sintéticos; no prueban precisión OCR universal ni fidelidad perfecta con documentos arbitrarios.

## Rediseño visual

Se conservaron el componente radial, animaciones, teclado, ratón, Escape, cierre, cancelación y paginación.
Se quitó el panel rectangular de fondo del estado radial y se solicitó explícitamente un buffer alfa Qt Quick.
Los demás estados conservan una tarjeta de lectura y controles de resultados, sin alterar la transparencia de los botones radiales.

Inspección del resultado renderizado, en claro y oscuro:

- Regiones vacías fuera del círculo: alfa **0/255**.
- Fondo circular al 85 % de transparencia: alfa **38/255**, aproximadamente 15 % de opacidad.
- Botones: alfa **249/255**, aproximadamente 98 % de opacidad; iconos y texto no se atenúan globalmente.
- El ajuste 100 % elimina la decoración y 0 % la hace opaca; las pruebas comprueban sus píxeles por separado.
- Dos, tres, seis, ocho y doce opciones sin superposición. La paginación se trasladó al pie para no tapar la opción superior.

Se compararon visualmente [el menú anterior](radial-dark.png), [el nuevo oscuro](v2-radial-dark.png) y
[el nuevo claro](v2-radial-light.png). Las nuevas capturas son PNG con alfa real; su apariencia en un visor depende
del fondo que utilice ese visor. Las pruebas nativas Wayland y XWayland también verifican el canal alfa del buffer.
No se promete paso de clics hacia Dolphin: las áreas vacías son una zona de cierre dentro de la ventana.

## Motores y dependencias

Sistema observado: Fedora 44 KDE; Plasma 6.7.5; Dolphin 26.08.1; sesión Wayland; Python 3.14.8;
Qt/PySide6 y shiboken6 6.11.2; Pillow 12.3.0; LibreOffice 26.2.6.3 y Poppler disponibles.

Se añadieron al entorno virtual, sin pip global:

| Motor | Versión | Función |
|---|---|---|
| PyMuPDF | 1.27.2.3 | Texto/estilos, imágenes, tablas, rotación y composición PDF |
| python-docx | 1.2.0 | Generar DOCX con texto realmente editable |
| openpyxl | 3.1.5 | Generar y validar XLSX con tablas independientes |
| et-xmlfile | 2.0.0 | Dependencia de openpyxl |

El instalador copia también lxml y typing_extensions ya disponibles, junto con las dependencias anteriores,
a un venv sin `system-site-packages`. La ejecución usa `-I`; se comprobó que `sys.path` no contiene directorios
`site-packages` de `/usr`. Los motores importan desde la instalación de Convertix y constan en su manifiesto.
[Diagnóstico de la versión instalada](v2-installed-diagnostics.json).
La [comprobación final](v2-installed-final-check.json) confirma que los 28 archivos de código instalados coinciden
con el proyecto, los cinco archivos de integración conservan sus hashes y el intérprete usa aislamiento sin
paquetes Python globales en su ruta de importación.

Con autorización explícita se instalaron `tesseract-5.5.3-2.fc44` y `tesseract-langpack-spa-4.1.0-12.fc44`.
`tesseract-langpack-eng-4.1.0-12.fc44` ya estaba instalado. Se verificó la disponibilidad de `spa` y `eng`.
Fedora requirió autenticación gráfica Polkit; no se guardaron credenciales ni se usó sudo pip.

Se probó temporalmente otro Pillow dentro del venv para investigar el alfa animado y después se retiró:
la versión final utiliza el Pillow 12.3.0 original. La corrección usa fotogramas WebP independientes y valida
su alfa al decodificar; no reemplazó ni alteró el paquete Pillow del sistema.

`pdf2docx` se evaluó y no se seleccionó porque [Artifex informa que ya no lo mantiene activamente](https://pypi.org/project/pdf2docx/).
La reconstrucción usa [extracción y tablas de MuPDF](https://pymupdf.readthedocs.io/en/latest/recipes-text.html) con
[python-docx](https://python-docx.readthedocs.io/en/latest/user/quickstart.html). Para OCR se eligió
[Tesseract local](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html) con una capa textual selectiva;
no se necesita introducir OCRmyPDF, procesos extra de Ghostscript o rasterizar todas las páginas digitales.
Para Markdown/HTML se comparte el modelo estructurado extraído de MuPDF, sin modelos de IA ni descargas durante el uso.

## Arquitectura y archivos modificados

Se mantienen `service.py`, los adaptadores existentes y la publicación atómica sin sobrescritura.
`probe.py` reutiliza el trabajador para que el análisis pesado también sea cancelable, esté limitado y no ocurra
en el hilo gráfico. `capabilities.py` consulta módulos e idiomas, `pdf_analysis.py` clasifica páginas y detecta tablas,
`pdf_layout.py` construye el modelo editable y `pdf_export.py` lo serializa. Los nuevos adaptadores son
`adapters/pdf_documents.py` y `adapters/ocr.py`. LibreOffice se reutiliza solo para intermediarios definidos y validados.

La interfaz sigue en `qml/Main.qml` y `gui.py`; se añadieron transparencia e idiomas a las preferencias existentes.
La lista completa de archivos añadidos/modificados está en [v2-changed-files.json](v2-changed-files.json).
El instalador actualizado se probó con actualización, rutas Unicode/espacios, rechazo de archivos alterados,
aislamiento de imports desde un directorio hostil y desinstalación conservadora. No escribe preferencias al actualizar.

## Dolphin: estado exacto y comprobación manual

El servicio existente sigue instalado en `~/.local/share/kio/servicemenus/convertix.desktop`, es ejecutable,
usa un lanzador estable, `%F` y `X-KDE-Priority=TopLevel`. El instalador verificó sus campos y hashes.
No se afirma que Dolphin haya reconocido visualmente la acción: no se pudo abrir su menú por automatización.

Se abrió Dolphin con configuración temporal, se encontraron y seleccionaron los documentos sintéticos por AT-SPI
y se intentó abrir el contexto. KWin no anuncia el protocolo nativo de entrada para pruebas; también se intentó
XWayland, sin obtener elementos de menú visibles. No se cambió configuración de KWin ni de accesibilidad global.
No se declaró aprobado ese flujo ni se sustituyó por lanzar la aplicación desde una terminal.

Comprobación física pendiente:

1. Abre Dolphin en `examples` y haz clic derecho en `Documento de prueba.docx`.
2. Comprueba **Convertir…** en el primer nivel; selecciónalo y elige PDF en el círculo.
3. Abre el archivo generado con un nombre disponible, comprueba el original y la notificación KDE.
4. Abre `examples/v2`, selecciona `PDF digital con tabla.pdf` y repite **Convertir… → DOCX**.
5. Abre el DOCX y edita una frase o una celda para confirmar editabilidad.
6. Repite con `PDF escaneado.pdf` → DOCX y `PDF mixto con portada vacía.pdf` → **PDF + OCR**.
7. En este último, comprueba la selección de texto en las páginas escaneadas y la apariencia original.
8. Abre otra vez el círculo y haz clic en otra aplicación: debe cerrarse sin convertir. Comprueba también un lote.

Si no aparece el servicio, revisa Dolphin → Configurar Dolphin → Menú contextual, el permiso ejecutable y
`qtpaths6 --locate-dirs GenericDataLocation kio/servicemenus`. No ejecutes Dolphin como administrador.

## Límites conocidos

- Word/ODT/RTF/Markdown/HTML reconstruyen estructura y formato; no garantizan el diseño exacto del PDF.
  Los encabezados se estiman por fuentes; dos columnas claras se soportan, composiciones más complejas pueden perder orden.
- El OCR es selectivo y heurístico. Fotografías o escaneos extraños pueden clasificarse mal; un resultado sin texto útil
  o de confianza muy baja se rechaza. No mide una precisión universal ni realiza deskew/orientación general sin metadatos.
- No se separan automáticamente ilustraciones dentro del raster completo de un escaneo. Los recursos digitales separados sí se conservan.
- Tablas sin líneas, celdas fusionadas y tablas complejas/rotadas pueden no detectarse o perder estructura. No se ofrece extracción arbitraria a Excel.
- GIF pierde colores/alfa parcial y redondea tiempos; destinos estáticos mantienen todos los cuadros como archivos numerados con advertencia.
- DOC/XLS/PPT pueden perder funciones modernas; XLS rechaza entradas que exceden su capacidad.
- El bloqueo de red y los límites de recursos no constituyen un sandbox completo del sistema de archivos.
- No se probaron físicamente varios monitores, cambios de densidad entre monitores, discos extraíbles ni una sesión X11 nativa.
  XWayland se identifica expresamente como XWayland. KWin decide la posición de la ventana Wayland; no se afirma colocación exacta junto al cursor.
- Se conservan los límites de 512 MiB de entrada, 500 páginas/cuadros, 150 millones de píxeles y tiempos configurables descritos en el README.

No quedan regresiones críticas confirmadas en las rutas probadas. La aceptación manual de Dolphin y las
limitaciones indicadas permanecen abiertas; no se presentan como funcionalidades o pruebas ya completadas.
