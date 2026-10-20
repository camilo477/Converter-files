import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami

ApplicationWindow {
    id: window
    required property var host
    objectName: "toolWindow"
    title: "Convertix · " + tool.title
    visible: tool.status !== "closed"
    modality: Qt.WindowModal
    flags: Qt.Dialog
    width: Math.min(760, Screen.width-40)
    height: Math.min(850, Screen.height-80)
    minimumWidth: 400; minimumHeight: 400
    color: host.surface
    Kirigami.Theme.inherit: false
    Kirigami.Theme.backgroundColor: host.surface
    Kirigami.Theme.textColor: host.ink
    Kirigami.Theme.highlightColor: host.accent
    // Bind individual roles: copying the palette object misses later theme changes.
    palette.window: host.surface
    palette.windowText: host.ink
    palette.text: host.ink
    palette.base: host.tile
    palette.button: host.tile
    palette.buttonText: host.ink
    palette.highlight: host.accent
    palette.highlightedText: host.dark ? "#172235" : "#ffffff"
    palette.placeholderText: host.muted
    palette.mid: host.edge
    property bool configuring: tool.status === "configure"
    property bool ordered: ["pdf-merge", "images-pdf", "archive"].indexOf(tool.actionId) >= 0
    property bool hasPdf: tool.items.some(function(i) { return i.format === "pdf" })
    property bool signedPdf: tool.items.some(function(i) { return i.signed })
    onClosing: function(event) { event.accepted = false; tool.cancel() }
    Shortcut { sequence: "Escape"; onActivated: tool.cancel() }
    function execute() {
        var p = {output_name: outputName.text, allow_signed: allowSignature.checked}
        if (specific.item) {
            if (tool.actionId === "pdf-split") { p.pages = specific.item.ranges; p.split_mode = specific.item.splitMode; p.interval = specific.item.interval }
            if (tool.actionId === "crop") p.box = specific.item.box
            if (tool.actionId === "resize") Object.assign(p, specific.item.options)
        }
        if (tool.actionId === "optimize") {
            p.level = ["lossless","balanced","maximum"][compressionMode.currentIndex]
            p.quality = Math.round(quality.value)
            p.keep_larger = keepLarger.checked
        }
        if (tool.actionId === "images-pdf") {
            p.page_size = ["a4","letter","image","custom"][pageSize.currentIndex]
            p.orientation = ["auto","portrait","landscape"][orientation.currentIndex]
            p.fit = ["contain","cover","natural"][fit.currentIndex]
            p.margin_mm = Number(margins.text)
            p.page_width_mm = Number(pageWidth.text); p.page_height_mm = Number(pageHeight.text)
        }
        if (tool.actionId === "metadata") { p.metadata_mode = cleaningMode.currentIndex ? "deep" : "standard"; p.remove_attachments = removeAttachments.checked }
        if (tool.actionId === "archive") { p.archive_format = archiveFormat.currentText; p.compression = archiveLevel.value }
        tool.execute(p)
    }
    Connections {
        target: tool
        function onChanged() {
            if (tool.status === "loading") {
                outputName.text = tool.proposedName
                allowSignature.checked = false
                keepLarger.checked = false
                compressionMode.currentIndex = 0
            }
            if (tool.status === "configure" && tool.items.length && tool.items[0].format === "jpg" && compressionMode.currentIndex === 0) compressionMode.currentIndex=1
        }
    }
    header: ToolBar {
        Kirigami.Theme.inherit: false
        Kirigami.Theme.backgroundColor: host.surface
        Kirigami.Theme.textColor: host.ink
        Kirigami.Theme.highlightColor: host.accent
        RowLayout {
            anchors.fill: parent; anchors.margins: 10
            Label { text: tool.title; font.pixelSize: 21; font.bold: true; Layout.fillWidth: true }
            ToolButton { text: "×"; Accessible.name: "Cerrar herramienta"; onClicked: tool.cancel() }
        }
    }
    ScrollView {
        id: scroll
        Kirigami.Theme.inherit: false
        Kirigami.Theme.backgroundColor: host.surface
        Kirigami.Theme.textColor: host.ink
        Kirigami.Theme.highlightColor: host.accent
        anchors.fill: parent; anchors.margins: 18; clip: true
        contentWidth: availableWidth
        ColumnLayout {
            width: scroll.availableWidth; spacing: 13
            enabled: window.configuring
            Label { objectName: "toolFileHeading"; text: tool.items.length === 1 ? tool.items[0].name : tool.items.length + " archivos seleccionados"; font.bold: true; wrapMode: Text.WrapAnywhere; textFormat: Text.PlainText; Layout.fillWidth: true }
            Label { text: tool.statusText; visible: text.length > 0; color: host.accent; wrapMode: Text.WordWrap; textFormat: Text.PlainText; Layout.fillWidth: true }
            Loader {
                id: specific; Layout.fillWidth: true
                active: window.configuring
                source: window.ordered ? "OrderEditor.qml" : tool.actionId === "pdf-split" ? "PagePicker.qml" : tool.actionId === "crop" ? "CropEditor.qml" : tool.actionId === "resize" ? "ResizeEditor.qml" : ""
                onLoaded: if (window.ordered) item.folders = tool.actionId === "archive"
            }
            ColumnLayout {
                visible: tool.actionId === "optimize"; Layout.fillWidth: true
                Label { text: "Optimizar tamaño · conserva el formato"; font.bold: true }
                ComboBox { id: compressionMode; objectName: "optimizationMode"; model: ["Sin pérdida · estructura / recursos", "Equilibrado · imágenes con pérdida", "Máximo · menor resolución/calidad"]; Layout.fillWidth: true }
                Label { text: "JPG requiere recodificación con pérdida. PNG en modos Equilibrado/Máximo reduce colores. PDF conserva páginas y texto, sin rasterizarlo completo."; wrapMode: Text.WordWrap; Layout.fillWidth: true; opacity: 0.8 }
                Label { visible: !window.hasPdf; text: "Calidad JPG / WebP con pérdida: " + Math.round(quality.value) }
                Slider { id: quality; visible: !window.hasPdf; from: 10; to: 100; value: compressionMode.currentIndex === 2 ? 55 : 82; stepSize: 1; Layout.fillWidth: true }
                CheckBox { id: keepLarger; text: "Conservar expresamente el resultado aunque no reduzca tamaño"; Layout.fillWidth: true }
                Label { text: "Se muestran bytes originales, finales y ahorro real al terminar. No se promete un porcentaje."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            }
            ColumnLayout {
                visible: tool.actionId === "archive"; Layout.fillWidth: true
                Label { text: "Crear archivo comprimido · no cambia los formatos internos"; font.bold: true }
                ComboBox { id: archiveFormat; objectName: "archiveFormat"; model: tool.archiveFormats; onCurrentTextChanged: if (outputName.text === "archivos.zip" || outputName.text === "archivos.7z") outputName.text = "archivos."+currentText }
                RowLayout { Label { text: "Nivel (0–9)" } SpinBox { id: archiveLevel; from: 0; to: 9; value: 6 } }
                Label { text: "DOCX, JPG, MP4 y PDF pueden ocupar lo mismo o más dentro del ZIP/7z. No se implementa extracción."; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            }
            ColumnLayout {
                visible: tool.actionId === "images-pdf"; Layout.fillWidth: true
                ComboBox { id: pageSize; model: ["A4", "Carta", "Ajustar a cada imagen", "Personalizado"]; Layout.fillWidth: true }
                RowLayout {
                    visible: pageSize.currentIndex === 3
                    Label { text: "Ancho × alto (mm)" }
                    TextField { id: pageWidth; text: "210"; Layout.preferredWidth: 80; validator: DoubleValidator { bottom: 10; top: 5000 } }
                    TextField { id: pageHeight; text: "297"; Layout.preferredWidth: 80; validator: DoubleValidator { bottom: 10; top: 5000 } }
                }
                ComboBox { id: orientation; model: ["Orientación automática", "Vertical", "Horizontal"]; Layout.fillWidth: true }
                ComboBox { id: fit; model: ["Contener imagen completa", "Llenar página recortando", "Tamaño proporcional de impresión"]; Layout.fillWidth: true }
                RowLayout {
                    ComboBox { model: ["Márgenes pequeños", "Sin márgenes", "Personalizados"]; onActivated: margins.text = currentIndex === 1 ? "0" : "8" }
                    TextField { id: margins; text: "8"; Layout.preferredWidth: 70; validator: DoubleValidator { bottom: 0; top: 70 } }
                    Label { text: "mm" }
                }
                Label { text: "Vista previa de página (transparencia sobre blanco). Animaciones/multipágina no disponibles en esta herramienta."; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 11 }
                RowLayout {
                    SpinBox { id: previewIndex; from: 1; to: Math.max(1,tool.items.length); value: 1 }
                    Rectangle {
                        id: sheetPreview
                        property var entry: tool.items.length ? tool.items[Math.min(previewIndex.value-1,tool.items.length-1)] : ({width: 100, height: 100, dpi: [96,96]})
                        property real iw: entry.width || 100
                        property real ih: entry.height || 100
                        property real dpi: entry.dpi ? entry.dpi[0] : 96
                        property real naturalW: iw*25.4/dpi
                        property real naturalH: ih*25.4/dpi
                        property real baseW: pageSize.currentIndex === 1 ? 215.9 : pageSize.currentIndex === 2 ? naturalW+2*Number(margins.text) : pageSize.currentIndex === 3 ? Number(pageWidth.text) : 210
                        property real baseH: pageSize.currentIndex === 1 ? 279.4 : pageSize.currentIndex === 2 ? naturalH+2*Number(margins.text) : pageSize.currentIndex === 3 ? Number(pageHeight.text) : 297
                        property bool landscape: orientation.currentIndex === 0 ? iw > ih : orientation.currentIndex === 2
                        property bool swap: landscape !== (baseW > baseH)
                        property real pw: swap ? baseH : baseW
                        property real ph: swap ? baseW : baseH
                        Layout.preferredWidth: Math.min(190,220*pw/Math.max(1,ph))
                        Layout.preferredHeight: Math.min(220,190*ph/Math.max(1,pw))
                        color: "white"; border.color: "#aaa"; clip: true
                        Item {
                            anchors.fill: parent; anchors.margins: Number(margins.text)/Math.max(1,sheetPreview.pw)*sheetPreview.width
                            clip: true
                            Image {
                                anchors.centerIn: parent
                                width: fit.currentIndex === 2 ? Math.min(parent.width,sheetPreview.naturalW/sheetPreview.pw*sheetPreview.width) : parent.width
                                height: fit.currentIndex === 2 ? Math.min(parent.height,sheetPreview.naturalH/sheetPreview.ph*sheetPreview.height) : parent.height
                                fillMode: fit.currentIndex === 1 ? Image.PreserveAspectCrop : Image.PreserveAspectFit; asynchronous: true
                                source: { tool.previewVersion; return tool.thumbnail(previewIndex.value-1,0,420) }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                visible: tool.actionId === "metadata"; Layout.fillWidth: true
                Label { text: "Categorías detectadas"; font.bold: true }
                Repeater {
                    model: tool.items
                    Label { required property var modelData; text: modelData.name + ": " + (modelData.metadata.length ? modelData.metadata.join(", ") : "sin campos comunes detectados"); textFormat: Text.PlainText; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
                ComboBox { id: cleaningMode; objectName: "cleaningMode"; model: ["Estándar · datos personales comunes", "Profunda · metadatos prescindibles adicionales"]; Layout.fillWidth: true }
                CheckBox { id: removeAttachments; objectName: "removeAttachments"; visible: window.hasPdf; text: "Eliminar archivos adjuntos del PDF" }
                Label { text: window.hasPdf ? "Siempre: campos del documento y XMP. Profunda: XMP de objetos, historial PieceInfo, autor/fechas de anotaciones y JavaScript. Se conservan texto visible, comentarios, formularios, enlaces y OCR. Adjuntos solo si los seleccionas." : "Elimina EXIF/GPS, XMP, comentarios y texto auxiliar. Conserva orientación aplicada, transparencia, animación y perfil ICC. Profunda también omite la resolución de impresión. JPG se limpia sin recomprimir; si requiere aplicar orientación EXIF, se recodifica a calidad 100 y puede variar ligeramente."; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                Label { text: "No elimina texto visible, marcas de agua ni rostros. No garantiza anonimización forense. Revisa también el contenido."; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: host.accent }
            }
            Label { visible: window.hasPdf; text: "Las páginas conservan sus dimensiones. Se intentan mantener anotaciones, enlaces y formularios compatibles; marcadores/destinos complejos pueden cambiar."; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 11 }
            CheckBox { id: allowSignature; visible: window.signedPdf; text: "Entiendo que la copia reescrita puede invalidar firmas digitales"; Layout.fillWidth: true }
            Label { text: "Carpeta de destino"; font.bold: true }
            RowLayout {
                Label { text: tool.outputDirectory; Layout.fillWidth: true; elide: Text.ElideMiddle; textFormat: Text.PlainText }
                Button { text: "Elegir…"; onClicked: tool.chooseDestination() }
            }
            Label { text: "Por defecto: carpeta del primer archivo de la lista inicial. Cambiar el orden no cambia el destino. Los originales se conservan."; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 11 }
            TextField { id: outputName; objectName: "toolOutputName"; Layout.fillWidth: true; visible: window.ordered || tool.actionId === "pdf-split" || tool.items.length === 1; placeholderText: "Nombre automático según la operación"; selectByMouse: true }
        }
    }
    footer: ToolBar {
        Kirigami.Theme.inherit: false
        Kirigami.Theme.backgroundColor: host.surface
        Kirigami.Theme.textColor: host.ink
        Kirigami.Theme.highlightColor: host.accent
        RowLayout {
            anchors.fill: parent; anchors.margins: 8; spacing: 10
            BusyIndicator { running: !window.configuring; visible: running; Layout.preferredWidth: 30; Layout.preferredHeight: 30 }
            Label { visible: !window.configuring; text: tool.statusText; Layout.fillWidth: true; elide: Text.ElideMiddle }
            Item { Layout.fillWidth: true; visible: window.configuring }
            Button { text: window.configuring ? "Cancelar" : "Cancelar operación"; onClicked: tool.cancel() }
            Button { objectName: "executeTool"; text: tool.actionId === "pdf-merge" ? "Combinar" : "Crear copia"; enabled: window.configuring && tool.items.length > 0 && (!window.signedPdf || allowSignature.checked); highlighted: true; onClicked: window.execute() }
        }
    }
}
