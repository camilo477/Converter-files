# Convertix 2.1 — Verificación del 20 de octubre de 2026

La corrección posterior para Folder View, con diagnóstico, pruebas antes/después y actualización de
`~/.local`, está en [Integración con los archivos del escritorio](DESKTOP-INTEGRATION.md).
El informe siguiente conserva los resultados de la ampliación 2.1.

## Resultado

Se amplió la aplicación existente y se actualizó la instalación en `~/.local` a **2.1.0**.
Las conversiones de 2.0, OCR, preferencias, transparencia, notificaciones, teclado y ratón se conservaron.
No se instalaron paquetes nuevos del sistema ni bibliotecas Python para esta ampliación.

**El flujo completo desde el clic derecho de Dolphin sigue pendiente de comprobación física.**
No se considera aprobado por haber probado las ventanas de Convertix con eventos Qt.

## Línea base y pruebas

Antes de modificar código se leyeron README, el informe 2.0, motores, registro, QML, instalador, trabajador,
detección y publicación. En la inspección inicial Git no estaba disponible en el entorno de ejecución.
En la revisión de publicación el repositorio está disponible en `main`, con remoto `origin` en
`git@github.com:camilo477/Converter-files.git`. Se conservó una copia del código previo en `/tmp/convertix-v20-before-v21.tar.gz`.
El [informe 2.0](VERIFICATION-v2.md), [informe 1](VERIFICATION-v1.md) y sus evidencias permanecen disponibles.

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Línea base, antes de editar | **99 aprobadas**, sin omisiones | [JUnit inicial](v21-baseline.xml) |
| Regresión y nuevas herramientas | **201 aprobadas**, sin errores ni omisiones | [JUnit completo](v21-full-tests.xml) |
| Qt Quick en Wayland real | **32 aprobadas, 1 omitida** | [JUnit Wayland](v21-wayland.xml) |
| Qt Quick X11 bajo XWayland | **33 aprobadas**, sin omisiones | [JUnit XWayland](v21-xwayland.xml) |
| Corrección final de contraste y alfa | **3 aprobadas** | [JUnit de contraste](v21-final-palette.xml) |
| Seguridad final de archivos/carpetas | **18 aprobadas**, sin omisiones | [JUnit de seguridad final](v21-final-safety.xml) |
| Recorte final: 1:1, 16:9 y píxeles originales 8K | **3 aprobadas**, bajo Wayland | [JUnit de recorte final](v21-final-crop.xml) |
| Firma PDF criptográfica sintética | **1 aprobada** | [JUnit firma](v21-signed-pdf.xml) |
| Aplicación instalada: 11 flujos con ratón | **11 aprobados** | [JSON de resultados](v21-desktop-tools.json) |
| Dolphin temporal, menú contextual real | No se pudo abrir mediante automatización | [Resultado exacto](v21-dolphin-result.json) |

Se verificaron **205 casos distintos**: 201 en la regresión completa, uno adicional de profundidad de carpetas y tres de recorte final. [Resumen sin duplicar casos](v21-test-summary.json).

Las baterías gráficas y focalizadas repiten casos; no se suman como pruebas distintas a la regresión.
La omisión Wayland corresponde a la prueba de pérdida de foco: KWin no concede activar otra ventana sin un gesto físico.
XWayland es un backend X11 dentro de Wayland; no se afirma haber probado una sesión X11 nativa.

Se conservan los 99 casos anteriores. La revisión final de seguridad añade un caso de carpetas de más de 64 niveles: se rechaza la selección y se comprueba la limpieza de los temporales, sin borrar originales. Se verifica en la batería final de seguridad; no se suma esa batería entera como casos distintos. Las nuevas pruebas comprueban, con archivos sintéticos:

- Unión de dos/tres PDFs, orden invertido, tamaños/orientaciones, marcadores y anotaciones; originales iguales por SHA-256.
- Cuatro modos de división, rangos no consecutivos y orden de extracción, intervalos, rangos inválidos, archivos vacíos,
  corruptos y cifrados; las partes mantienen dimensiones y texto seleccionable y se publican como conjunto.
- Tres niveles de optimización PDF, texto/páginas preservados y comparación visual exacta en el modo sin pérdida.
  El ahorro se contrasta con tamaños reales; si no se reduce, se rechaza salvo elección explícita.
- JPG/PNG/WebP optimizados, recorte exacto con alfa y orientación EXIF, coordenadas inválidas, proporciones,
  dimensiones personalizadas y lotes. GIF/WebP animados y APNG con imagen de portada mantienen cuadros, tiempos y bucles.
- ZIP/7z, archivos de distintas carpetas con nombres repetidos, Unicode, espacios y carpetas vacías. ZIP se compara
  por SHA-256 al leer sus miembros y se valida CRC; 7z pasa su verificación de integridad.
- Cancelación durante copia, compresión y pendientes; rechazo de enlaces simbólicos/FIFOs, nombres peligrosos,
  opciones booleanas ambiguas, cambios desde la vista previa, permisos y publicación concurrente sin colisiones.
- Imágenes a PDF: una/varias, orden, distintas resoluciones, transparencia, A4, Carta, tamaño de imagen y personalizado.
- EXIF/GPS, campos textuales PNG, metadatos PDF y XMP, adjuntos seleccionados, autor/fechas de anotaciones y conservación visual.
  JPEG sin giro se limpia sin recomprimir, incluido JPEG progresivo.
- Las ventanas QML en ambos temas, categorías, selección con ratón, arrastre para reordenar, páginas y carga diferida,
  recorte visual que coincide con la región exportada, transparencia y cambio de tema durante la ejecución.

La prueba de firma genera un certificado autofirmado y una firma CMS desechables en el directorio temporal de pytest.
`pdfsig -nocert` verifica la integridad criptográfica antes de la operación; no valida una identidad de confianza.
La operación se bloquea sin aceptar el aviso y la copia reescrita deja de validar la firma original. El original no cambia.
No se utilizaron certificados ni documentos personales.

## Aplicación instalada e inspección visual

`tools_desktop_smoke.py` se ejecutó con el Python aislado instalado y `QT_QPA_PLATFORM=wayland`.
Se eligió la herramienta mediante clic en el botón radial y se pulsó el botón de ejecución QML:

1. Unir dos PDFs: seis páginas.
2. Dividir un PDF en dos partes mediante rangos.
3. Optimizar PDF sin pérdida: 2 709 355 → 1 194 416 bytes, ahorro **55,92 %** en esa muestra.
4. Optimizar PNG sin pérdida: 1 383 435 → 2 110 bytes, ahorro **99,85 %** en esa imagen sintética de colores planos.
5. Crear ZIP de carpeta y archivo.
6. Crear 7z de carpeta y archivo.
7. Recortar una región de 400 × 300 píxeles.
8. Redimensionar tres imágenes al 50 %.
9. Crear un PDF ordenado de tres imágenes.
10. Limpiar EXIF/GPS de JPG.
11. Limpiar PDF profundamente con eliminación explícita de adjuntos.

Los porcentajes anteriores son resultados de muestras, no promesas de reducción para otros archivos.
En los once flujos todos los registros fueron correctos, los originales mantuvieron SHA-256 y KDE aceptó las notificaciones.
En PDF/recorte se verificaron además páginas/dimensiones. Las pruebas automatizadas inspeccionan el contenido, no solo la existencia del resultado.

Se inspeccionaron capturas reales de [unión](v21-tool-merge.png), [división](v21-tool-split.png),
[recorte](v21-tool-crop.png), [redimensionado](v21-tool-resize.png), [imágenes a PDF](v21-tool-images-pdf.png),
[limpieza PDF](v21-tool-metadata-pdf.png), [radial oscuro](v21-radial-dark.png) y [radial claro](v21-radial-light.png).
Las capturas radiales conservan alfa: fuera de la decoración el fondo es transparente; no hay atenuación global de botones.
El fondo decorativo conserva el 85 % de transparencia predeterminado y las preferencias anteriores no se reescribieron.

La inspección encontró un fallo de contraste en el tema claro tras cambiar de tema: copiar el objeto de paleta no
actualizaba los roles de la ventana secundaria. Se corrigió vinculando los roles Qt y los colores Kirigami del árbol visual (el estilo `org.kde.desktop` usa estos últimos), con una prueba que comprueba
texto oscuro sobre claro y claro sobre oscuro. También se hicieron explícitos los glifos de preferencias/cierre.
La última captura se actualiza con `--preview-only`, sin sustituir el JSON de los once flujos funcionales.

Durante el desarrollo también se corrigieron un argumento DPI entero requerido por MuPDF, el borrado explícito de
fechas/autor en anotaciones, conservación de RGB bajo alfa en WebP sin pérdida, IFD de la muestra TIFF y el cálculo de
la posición de soltar una fila. No se relajaron las expectativas para esconder esos errores. Los informes provisionales
se identifican con `initial`; una primera ejecución XWayland falló una medición de alfa durante una transición de ventana,
y la repetición aislada aprobó los 32 casos conservando la misma prueba; la comprobación final aprobó 33, incluyendo cambio de tema.

## Arquitectura, límites y garantías

Los nuevos módulos están en `src/convertix/tools/`: catálogo explícito, controlador, inspección/miniaturas, PDF,
imágenes, composición PDF, metadatos, JPEG, archivos comprimidos, opciones, copias seguras, RPC y servicio.
La interfaz se divide en `ToolWindow.qml`, `OrderEditor.qml`, `PagePicker.qml`, `CropEditor.qml` y `ResizeEditor.qml`.
Se reutilizan trabajador aislado, límites de recursos/red, preferencias, notificaciones, `publish` y `renameat2(RENAME_NOREPLACE)`.
[Lista de archivos añadidos/modificados](v21-changed-files.json).

- La carpeta de destino se muestra antes de ejecutar: por defecto, carpeta del primer archivo de la selección inicial.
  Reordenar no la cambia. El usuario puede elegir otra; los lotes también utilizan la carpeta visible.
- Las entradas se copian desde descriptores sin seguir enlaces finales ni enlaces dentro de las carpetas, con comprobación de cambios durante la copia.
  Las imágenes editadas se comparan con su identidad/tamaño/fecha de la vista previa, también al abrir el descriptor.
- Las divisiones múltiples se publican mediante un único cambio de nombre de una carpeta completa. Un fallo intermedio
  impide publicar ese conjunto. Lotes de operaciones independientes conservan resultados ya completados y muestran los errores/pendientes.
- No hay sobrescritura ni modificación del original. Los permisos resultantes no amplían los de las entradas.
  Los temporales están en el mismo sistema de archivos; se limpian al fallar/cancelar y se termina el grupo de procesos.
- Los límites de edición son 512 MiB por archivo, 500 páginas/cuadros y 150 millones de píxeles. Archivos comprimidos:
  2 GiB sin comprimir, 10 000 entradas y 64 niveles, sin enlaces, dispositivos ni FIFOs. No se crea el archivo dentro de una carpeta incluida.
- Se mantienen tiempos y memoria acotados; las miniaturas se solicitan según las celdas visibles y se almacenan temporalmente.
  No se renderiza un PDF completo para mostrar su selector. El bloqueo de red no es un sandbox completo del sistema de archivos.
- PDF conserva páginas sin rasterizarlas. Se intentan conservar anotaciones, formularios y marcadores simples.
  Destinos avanzados y enlaces hacia páginas excluidas pueden perderse. Firmas previas no se conservan válidas.
- Recorte y creación de PDF no admiten animaciones/multipágina. Redimensionar mantiene cuadros; ampliar interpola.
- JPG con giro EXIF necesita recodificación; otros JPG limpian segmentos sin recomprimir. GIF tiene alfa binaria y paleta limitada.
  La vista previa usa una imagen reducida, mientras el recorte se expresa en píxeles de la imagen orientada original.
- La limpieza no elimina texto visible, comentarios, rostros, marcas de agua ni valores de formularios. Adjuntos no seleccionados,
  recursos incrustados y estructuras privadas pueden conservar datos. No se promete anonimización forense ni eliminación de toda información sensible.
  Profundo elimina JavaScript PDF y puede cambiar cálculos/interactividad de formularios; el contenido visible se conserva.
- No se probaron físicamente varios monitores, cambios reales de densidad, discos extraíbles, falta real de espacio ni una sesión X11 nativa.
  Se verificaron rutas Unicode, permisos y escalado de interfaz; no se anuncian las comprobaciones físicas como aprobadas.

## Dependencias e instalación

Se reutilizan PyMuPDF 1.27.2.3, Pillow 12.3.0, Python 3.14.8, PySide6/Qt 6.11.2 y la biblioteca estándar.
Se reutiliza también Kirigami 6.31.0 (`kf6-kirigami`), ya instalado por KDE. 7z 26.04 ya estaba instalado. No se instaló Gemini CLI: no estaba disponible, y no se envió código ni documentos a otro servicio.
LibreOffice, Poppler y Tesseract mantienen las conversiones 2.0. No se alteró el Python global.
[Comprobación de fuentes, integración, dependencias y aislamiento de la instalación](v21-installed-final-check.json).

Se revisaron los registros locales: dos eventos `job_failed` eran anteriores a esta ampliación y uno corresponde a una cancelación del primer capturador de vistas previas por transición de foco. Se corrigió el capturador; el JSON de los once flujos funcionales permanece separado. No se borraron registros. [Revisión del registro](v21-log-review.json).

El instalador/desinstalador se prueban dentro de la regresión: actualización, importación desde directorio hostil,
rutas Unicode, rechazo de integración modificada, conservación de archivos ajenos y desinstalación conservadora.
La acción de Dolphin sigue siendo ejecutable, usa `%F`, lanzador absoluto y prioridad de primer nivel.
Se añadió `application/octet-stream` e `inode/directory` para archivos generales/carpetas, según la
[documentación oficial KDE](https://develop.kde.org/docs/apps/dolphin/service-menus/).

Referencias técnicas: [MuPDF: páginas, guardado y metadatos](https://pymupdf.readthedocs.io/en/latest/document.html),
[Pillow: formatos y animaciones](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html),
[Qt Quick: arrastre y orden](https://doc.qt.io/qt-6/qtquick-draganddrop-example.html),
[OpenSSL CMS para la muestra firmada](https://docs.openssl.org/3.5/man1/openssl-cms/).

## Dolphin: aceptación manual pendiente

Se abrió una instancia XWayland de Dolphin con configuración temporal y archivos sintéticos, se localizaron y
seleccionaron mediante AT-SPI y se intentó abrir el menú contextual. No se obtuvo una acción visible «Convertir…».
No se afirma que Dolphin la haya reconocido visualmente. Se cerró únicamente la instancia de prueba y no se modificó
configuración global de Dolphin/KWin ni se activó un mecanismo de entrada exclusivo de X11 en producción.

Pasos para completar la aceptación física:

1. Abre `examples/v21` en Dolphin. Selecciona `Documento 1.pdf` y `Documento 2.pdf` y abre el clic derecho → **Convertir…**.
2. En **Modificar → Unir PDFs**, reordena, comprueba el destino mostrado, combina y abre el PDF de seis páginas.
3. Selecciona `Documento 1.pdf` → **Dividir PDF**. Introduce `1-2;3-4` en modo grupos; comprueba la carpeta con dos PDFs.
4. Prueba **Optimizar** y comprueba bytes/ahorro. Con un archivo que ya esté optimizado debe informar si no se reduce.
5. Selecciona las tres imágenes → **Redimensionar**, 50 %, y luego **Crear PDF**; verifica dimensiones y orden.
6. Abre **Recortar** con una imagen, mueve esquinas y comprueba el resultado. Repite después de cambiar de tema.
7. Selecciona `Foto con EXIF.jpg` → **Metadatos** y comprueba la copia. Repite con PDF y adjuntos seleccionados.
8. Selecciona `Carpeta para ZIP` y crea ZIP/7z. Comprueba su contenido con el gestor de archivos comprimidos.
9. Verifica una conversión anterior DOCX → PDF y PDF → DOCX, originales, notificación, teclado, Escape y cancelación.

Si no aparece la acción, consulta Dolphin → Configurar → Menú contextual y
`qtpaths6 --locate-dirs GenericDataLocation kio/servicemenus`. No ejecutes Dolphin como administrador.
Para usar las funciones mientras tanto, abre **Convertix** desde el lanzador o ejecuta
`~/.local/bin/convertix '/ruta/archivo'`; selecciona **Modificar**. [Guía y ejemplos CLI](../README.md).
