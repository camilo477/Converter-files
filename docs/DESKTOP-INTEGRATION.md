# Convertix 2.1: archivos del escritorio en Plasma 6

Verificación realizada el 20 de octubre de 2026. Se actualizó la instalación existente en `~/.local`.

## Diagnóstico comprobado

El sistema tiene Plasma Desktop/Workspace **6.7.5**, Dolphin **26.08.1**, KIO **6.31.0** y sesión Wayland.
Se consultaron los paquetes RPM, las rutas de QStandardPaths, los archivos de configuración de Plasma y Dolphin,
y los escritorios activos mediante D-Bus. Ambos escritorios usan `org.kde.plasma.folder`, con URL `desktop:/`.
La carpeta física configurada es `~/Escritorio`. No se cambió el diseño ni la configuración del escritorio.

El servicio instalado se encontró en `~/.local/share/kio/servicemenus/convertix.desktop`, propiedad del usuario
y con permisos **0755**. Ya tenía `Type=Service`, `Actions=convertix;`, los MIME de Convertix,
`X-KDE-Priority=TopLevel` y el lanzador absoluto con `-- %F`. No existe un `kservicemenurc` que desactive la acción.

La causa era **`X-KDE-Protocols=file`**. Folder View conserva el esquema `desktop:` en los elementos
seleccionados. KIO compara ese esquema con la lista del servicio y descartaba Convertix antes de crear la acción.
Se reprodujo con el FolderModel original instalado: PNG, PDF y selecciones múltiples no ofrecían la acción
con `desktop:`, mientras que las mismas selecciones con `file:` sí la ofrecían.

Se revisaron las fuentes oficiales correspondientes a las versiones instaladas:

- [FolderModel de Plasma 6.7.5](https://github.com/KDE/plasma-desktop/blob/v6.7.5/containments/desktop/plugins/folder/foldermodel.cpp):
  `openContextMenu()` pasa los archivos seleccionados a `KFileItemActions::addActionsTo()`.
- [KFileItemActions de KIO 6.31.0](https://github.com/KDE/kio/blob/v6.31.0/src/widgets/kfileitemactions.cpp):
  `shouldDisplayServiceMenu()` filtra `X-KDE-Protocols`; `serviceMenuFilePaths()` busca los servicios en disco.
- [Documentación de Service Menus](https://develop.kde.org/docs/apps/dolphin/service-menus/): ubicación,
  permiso ejecutable, MIME, prioridad y lista de protocolos separados por comas.

## Cambio e instalación

En `scripts/install.py`, el servicio generado ahora contiene:

```ini
X-KDE-Priority=TopLevel
X-KDE-Protocols=file,desktop

[Desktop Action convertix]
Name=Convertir…
Icon=convertix
Exec="/home/camiska/.local/bin/convertix" -- %F
```

Se ejecutó `.venv/bin/python scripts/install.py` para actualizar el servicio y su manifiesto de integridad.
No se editó el archivo instalado al margen del instalador. La versión sigue siendo **2.1.0**.
`file` conserva Dolphin; `desktop` añade Folder View. `%F` sigue enviando todos los archivos a una única
instancia, con argumentos separados y `--`. Se mantienen los MIME existentes, incluidas las carpetas locales.

Las pruebas pasaron antes de refrescar la caché: KIO relee estos servicios desde disco.
Después se ejecutó **`kbuildsycoca6`**, con resultado correcto, para actualizar la caché del usuario.
La caché y `TopLevel` no eran la causa del fallo. No hizo falta otra integración para Folder View.

La comparación con la instalación previa comprobó que los **48 archivos de la aplicación** son idénticos,
que las preferencias no cambiaron y que los **5 archivos gestionados** coinciden con su manifiesto.
El único cambio de contenido del Service Menu instalado es la lista de protocolos. No se tocaron fuentes
de Plasma, paquetes del sistema, motores, QML, conversiones ni herramientas. No hubo reinicios, commits ni push.

## Pruebas ejecutadas

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Reproducción previa: cuatro selecciones y fondo vacío, con `desktop:` y `file:` | 10 escenarios conforme al fallo descrito | [Antes](desktop-folderview-before.json) |
| Servicio actualizado: los mismos escenarios | 10 escenarios correctos; una acción de primer nivel por selección y ninguna en el fondo | [Después](desktop-folderview-after.json) |
| Activación KIO real desde esas acciones | 8 aperturas de la aplicación instalada; rutas locales exactas, espacios, Unicode, uno/varios archivos | [Después](desktop-folderview-after.json) |
| Menú radial instalado, mediante AT-SPI | Convertir y Modificar visibles en las 8 aperturas; cambiar a Modificar muestra Crear ZIP / 7z; cierre mediante su botón | [Después](desktop-folderview-after.json) |
| Instalación, actualización, conflicto y desinstalación bajo prefijo temporal con espacios/Unicode | 1 prueba aprobada | [JUnit](desktop-install-tests.xml) |
| Preferencias, navegación de categorías y redimensionado real | 3 pruebas aprobadas | [JUnit](desktop-regression-tests.xml) |
| Integridad de fuentes, preferencias, manifiesto y servicio instalado | Correcta | [Auditoría](desktop-installation-check.json) |

Se usaron exclusivamente PNG/PDF sintéticos creados directamente en el escritorio con nombres únicos.
Se comprobó que sus contenidos no cambiaron y se eliminaron al terminar. No se abrieron archivos personales.

El programa de prueba carga el **componente C++ instalado de Folder View** mediante su módulo QML;
su QMenu se construye con backend offscreen y se activa la acción KIO original. La aplicación Convertix
que abre es un proceso independiente de la instalación real, comprobado mediante argumentos y AT-SPI.
También se prueba `file:` usando ese componente compartido; esto no equivale a manejar la ventana de Dolphin.

Para repetirlo desde una sesión KDE con las dependencias de desarrollo del proyecto y AT-SPI disponibles:

```bash
.venv/bin/python scripts/folderview_smoke.py --launch --report /tmp/convertix-folderview.json
```

La prueba crea y retira archivos sintéticos en la carpeta del escritorio. `--before-fix` permite reproducir
el comportamiento anterior únicamente antes de instalar la corrección; no modifica el servicio por sí solo.

## Aceptación manual pendiente

No se automatizó un clic físico en el `plasmashell` que ya está en ejecución: su árbol de accesibilidad no
expone los elementos del escritorio en esta sesión. No se habilitaron mecanismos globales de entrada,
ni se reinició Plasma para forzar accesibilidad. La prueba con su componente instalado no sustituye ese paso.

1. Cierra cualquier menú contextual ya abierto. Sobre un PNG o PDF situado directamente en el escritorio,
   haz clic derecho **en el archivo** y comprueba **Convertir…** en primer nivel.
2. Ábrelo y verifica el menú radial con **Convertir** y **Modificar**. Ejecuta una conversión y una herramienta
   sobre copias de prueba; comprueba que los resultados se guardan junto al original.
3. Selecciona dos archivos con Ctrl y repite. Comprueba que una sola ventana recibe ambos.
4. Repite en la otra pantalla y, en Dolphin, sobre los mismos archivos. El clic completo en la ventana real
   de Dolphin conserva su comprobación manual pendiente del informe anterior.
5. Sobre el fondo vacío del escritorio no se espera la acción de Convertix.

No hace falta reiniciar la sesión ni Plasma. Si la acción faltara, comprueba `file,desktop`, permisos 0755,
la ruta que muestra `qtpaths6 --locate-dirs GenericDataLocation kio/servicemenus` y que Convertix esté habilitado
en Dolphin → Configurar Dolphin → Menú contextual. `kbuildsycoca6` puede refrescar la caché sin reiniciar Plasma.
