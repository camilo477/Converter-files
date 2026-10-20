import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: root
    objectName: "convertixWindow"
    title: "Convertix"
    visible: false
    color: "transparent"
    background: Item {}
    flags: Qt.Window | Qt.FramelessWindowHint
    property real uiScale: 1
    width: 640 * uiScale
    height: 664 * uiScale
    property bool dark: backend.preferences.theme === "dark" || (backend.preferences.theme === "system" && systemPalette.window.hslLightness < 0.5)
    property color surface: dark ? "#242830" : "#fafbfd"
    property color tile: dark ? "#303640" : "#ffffff"
    property color ink: dark ? "#eef2f8" : "#243043"
    property color muted: dark ? "#acb7c8" : "#626e80"
    property color edge: dark ? "#424a59" : "#dce3ed"
    property color accent: dark ? "#85baff" : "#286bc9"
    property int page: 0
    property int selected: 0
    property int perPage: 8
    property int pageCount: Math.max(1, Math.ceil(backend.targets.length / perPage))
    property var choices: backend.targets.slice(page * perPage, (page + 1) * perPage)
    property string hoverHint: ""
    property bool hadFocus: false
    property bool closeRequested: false
    property int motion: backend.preferences.animations ? 220 : 0
    property bool departing: false
    property real decorAlpha: 1 - backend.preferences.radial_transparency / 100
    function translucent(base, alpha) { return Qt.rgba(base.r, base.g, base.b, alpha) }
    palette.window: surface
    palette.windowText: ink
    palette.text: ink
    palette.base: tile
    palette.button: tile
    palette.buttonText: ink
    palette.highlight: accent
    palette.highlightedText: dark ? "#172235" : "#ffffff"
    SystemPalette { id: systemPalette; colorGroup: SystemPalette.Active }

    function requestClose() {
        closeRequested = true
        if (backend.mayClose()) { departing = true; exitTimer.start() }
        else closeTimer.start()
    }
    Timer { id: exitTimer; interval: Math.max(1, root.motion); onTriggered: root.close() }
    function selectCurrent() {
        if (backend.status === "ready" && choices.length > 0)
            backend.start(choices[selected].target)
    }
    onClosing: function(event) {
        event.accepted = backend.mayClose()
        if (!event.accepted) { closeRequested = true; closeTimer.start() }
    }
    Timer {
        id: closeTimer; interval: 150; repeat: true
        onTriggered: if (backend.mayClose()) { stop(); root.close() }
    }
    onActiveChanged: {
        if (active) {
            hadFocus = true
            if (!settings.opened && !details.opened) keyArea.forceActiveFocus()
        }
        else if (hadFocus && backend.status === "ready" && !settings.opened && !details.opened) blurTimer.restart()
    }
    Timer {
        id: blurTimer; interval: 180
        onTriggered: if (!root.active && backend.status === "ready" && !settings.opened && !details.opened) root.requestClose()
    }
    Connections {
        target: backend
        function onChanged() {
            if (backend.status === "ready") {
                root.page = 0; root.selected = 0; keyArea.forceActiveFocus()
            }
        }
    }

    Item {
        id: keyArea
        objectName: "keyArea"
        width: 640; height: 664
        scale: root.uiScale
        opacity: root.departing ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: root.motion } }
        transformOrigin: Item.TopLeft
        focus: true
        Keys.onPressed: function(event) {
            if (event.key === Qt.Key_Escape) {
                if (settings.opened) settings.close()
                else if (details.opened) details.close()
                else root.requestClose()
                event.accepted = true
            } else if (backend.status === "ready") {
                if ([Qt.Key_Right, Qt.Key_Down].indexOf(event.key) >= 0) {
                    root.selected = (root.selected + 1) % root.choices.length; event.accepted = true
                } else if ([Qt.Key_Left, Qt.Key_Up].indexOf(event.key) >= 0) {
                    root.selected = (root.selected + root.choices.length - 1) % root.choices.length; event.accepted = true
                } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    root.selectCurrent(); event.accepted = true
                } else if (event.key === Qt.Key_PageDown || event.key === Qt.Key_PageUp) {
                    root.page = (root.page + (event.key === Qt.Key_PageDown ? 1 : root.pageCount-1)) % root.pageCount
                    root.selected = 0; event.accepted = true
                }
            }
        }
        // Empty regions form a close zone. They do not promise click-through to other apps.
        MouseArea { anchors.fill: parent; onClicked: root.requestClose() }
        Rectangle {
            objectName: "statusBackdrop"
            visible: backend.status !== "ready"
            x: 32; y: 98; width: 576; height: 534; radius: 28
            color: root.translucent(root.surface, 0.97); border.color: root.edge
            MouseArea { anchors.fill: parent; onPressed: function(mouse) { mouse.accepted = true } }
        }
        Rectangle { x: 24; y: 22; width: 218; height: 57; radius: 18; color: root.translucent(root.surface, 0.94) }
        Row {
            x: 36; y: 29; spacing: 10
            Image { width: 23; height: 23; source: "image://theme/document-export"; sourceSize.width: 46; sourceSize.height: 46 }
            Text { text: "convertix"; color: root.ink; font.pixelSize: 18; font.weight: Font.DemiBold; font.letterSpacing: 0.5 }
        }
        Text { x: 36; y: 59; text: "TRANSFORMA TUS ARCHIVOS"; font.pixelSize: 9; font.letterSpacing: 1.8; color: root.muted }
        ToolButton {
            objectName: "settingsButton"; x: 520; y: 24; width: 38; height: 38
            text: "⚙"; font.pixelSize: 22; Accessible.name: "Preferencias"
            enabled: backend.status !== "processing" && backend.status !== "scanning"
            onClicked: settings.open()
            background: Rectangle { radius: 14; color: root.translucent(root.surface, 0.96); border.color: parent.hovered ? root.accent : root.edge }
            ToolTip.visible: hovered; ToolTip.text: "Preferencias"
        }
        ToolButton {
            x: 565; y: 24; width: 38; height: 38
            text: "×"; font.pixelSize: 25; Accessible.name: "Cerrar"
            onClicked: root.requestClose()
            background: Rectangle { radius: 14; color: root.translucent(root.surface, 0.96); border.color: parent.hovered ? root.accent : root.edge }
        }

        Item {
            id: radial
            objectName: "radial"
            anchors.fill: parent
            visible: backend.status === "ready"
            opacity: visible ? 1 : 0
            scale: visible ? 1 : 0.93
            Behavior on opacity { NumberAnimation { duration: root.motion } }
            Behavior on scale { NumberAnimation { duration: root.motion; easing.type: Easing.OutCubic } }
            Rectangle { objectName: "radialDecoration"; x: 124; y: 124; width: 392; height: 392; radius: 196; color: root.translucent(root.surface, root.decorAlpha); border.color: root.translucent(root.edge, root.decorAlpha) }
            Rectangle {
                objectName: "sourceCard"
                x: 238; y: 236; width: 164; height: 168; radius: 30
                color: root.translucent(root.surface, 0.45)
                border.color: root.translucent(root.edge, 0.5)
                MouseArea { anchors.fill: parent; onClicked: {} }
                Column {
                    anchors.centerIn: parent; width: 144; spacing: 9
                    Image { anchors.horizontalCenter: parent.horizontalCenter; width: 39; height: 39; sourceSize.width: 78; sourceSize.height: 78; source: "image://theme/" + backend.sourceIcon }
                    Text { width: parent.width; text: backend.sourceFormat; color: root.ink; font.pixelSize: 19; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter }
                    Text { width: parent.width; text: backend.sourceName; color: root.muted; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideMiddle; maximumLineCount: 2; wrapMode: Text.WrapAnywhere; textFormat: Text.PlainText }
                }
            }
            Repeater {
                model: root.choices
                delegate: AbstractButton {
                    id: option
                    required property var modelData
                    required property int index
                    property color formatAccent: modelData.accent
                    objectName: "target_" + modelData.target
                    property real angle: -Math.PI/2 + index * 2*Math.PI / root.choices.length
                    x: 320 + Math.cos(angle)*193 - width/2
                    y: 320 + Math.sin(angle)*193 - height/2
                    width: 102; height: 88
                    hoverEnabled: true
                    Accessible.name: "Convertir a " + modelData.label
                    Accessible.description: modelData.hint
                    activeFocusOnTab: true
                    scale: hovered || activeFocus ? 1.055 : 1
                    Behavior on scale { NumberAnimation { duration: root.motion/2 } }
                    onHoveredChanged: { if (hovered) { root.selected = index; root.hoverHint = modelData.hint } else root.hoverHint = "" }
                    onActiveFocusChanged: if (activeFocus) root.selected = index
                    onClicked: backend.start(modelData.target)
                    background: Rectangle {
                        objectName: "formatBackground"
                        radius: 20
                        color: Qt.tint(root.translucent(root.surface, 0.97), Qt.rgba(option.formatAccent.r, option.formatAccent.g, option.formatAccent.b, option.hovered ? 0.18 : 0.07))
                        border.width: root.selected === option.index ? 2 : 1
                        border.color: root.selected === option.index ? option.modelData.accent : root.edge
                        Behavior on color { ColorAnimation { duration: root.motion/2 } }
                        Rectangle { anchors.horizontalCenter: parent.horizontalCenter; y: parent.height-5; width: 19; height: 3; radius: 1.5; color: option.modelData.accent; visible: root.selected === option.index }
                    }
                    contentItem: Column {
                        spacing: 7; topPadding: 13
                        Image { anchors.horizontalCenter: parent.horizontalCenter; width: 28; height: 28; source: "image://theme/" + option.modelData.icon; sourceSize.width: 56; sourceSize.height: 56 }
                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: option.modelData.label; color: root.ink; font.pixelSize: 12; font.weight: Font.DemiBold; font.letterSpacing: 0.5 }
                    }
                }
            }
            Rectangle {
                x: 61; y: 566; width: 518; height: 54; radius: 16
                color: root.translucent(root.surface, 0.93)
            }
            Text {
                x: 61; y: 566; width: 518; height: 54
                text: root.hoverHint || (root.choices.length ? root.choices[root.selected].hint : "")
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                color: root.muted; font.pixelSize: 11; wrapMode: Text.WordWrap; elide: Text.ElideRight; maximumLineCount: 3
            }
            Rectangle { visible: root.pageCount === 1; x: 156; y: 624; width: 328; height: 24; radius: 12; color: root.translucent(root.surface, 0.94) }
            Text { visible: root.pageCount === 1; anchors.horizontalCenter: parent.horizontalCenter; y: 631; text: "↑ ↓ ELEGIR     ↵ CONVERTIR     ESC CERRAR"; color: root.muted; font.pixelSize: 9; font.letterSpacing: 0.6 }
            Rectangle { visible: root.pageCount > 1; x: 244; y: 616; width: 152; height: 42; radius: 18; color: root.translucent(root.surface, 0.94) }
            Row {
                visible: root.pageCount > 1; anchors.horizontalCenter: parent.horizontalCenter; y: 618; spacing: 8
                ToolButton { text: "‹"; onClicked: { root.page = (root.page+root.pageCount-1)%root.pageCount; root.selected=0 } }
                Label { anchors.verticalCenter: parent.verticalCenter; text: (root.page+1) + " / " + root.pageCount }
                ToolButton { text: "›"; onClicked: { root.page=(root.page+1)%root.pageCount; root.selected=0 } }
            }
        }

        Column {
            visible: backend.status === "scanning" || backend.status === "processing"
            x: 76; y: 195; width: 488; spacing: 24
            BusyIndicator { anchors.horizontalCenter: parent.horizontalCenter; width: 76; height: 76; running: parent.visible }
            Text { width: parent.width; text: backend.status === "scanning" ? "Un momento…" : "Convirtiendo…"; color: root.ink; font.pixelSize: 25; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter }
            Text { width: parent.width; text: backend.statusText; color: root.muted; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WrapAnywhere; textFormat: Text.PlainText }
            Text { width: parent.width; text: "El original se conserva intacto"; color: root.muted; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter }
            Button { anchors.horizontalCenter: parent.horizontalCenter; text: "Cancelar"; onClicked: backend.cancel() }
        }
        Column {
            visible: backend.status === "empty" || backend.status === "unavailable"
            x: 85; y: 206; width: 470; spacing: 22
            Image { anchors.horizontalCenter: parent.horizontalCenter; width: 58; height: 58; source: "image://theme/document-open" }
            Text { text: "Una nueva forma de convertir"; width: parent.width; color: root.ink; font.pixelSize: 23; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter }
            Text { text: backend.statusText; width: parent.width; color: root.muted; font.pixelSize: 13; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter }
            Button { text: "Seleccionar archivos…"; anchors.horizontalCenter: parent.horizontalCenter; onClicked: backend.chooseFiles() }
            Button { text: "Ver motores disponibles"; flat: true; anchors.horizontalCenter: parent.horizontalCenter; onClicked: { detailText.text = backend.dependencyInfo(); details.open() } }
        }
        ColumnLayout {
            visible: backend.status === "done" || backend.status === "error"
            x: 52; y: 113; width: 536; height: 486; spacing: 16
            Text { text: backend.status === "done" ? "✓" : "!"; color: backend.status === "done" ? "#57b993" : "#e56870"; font.pixelSize: 48; Layout.alignment: Qt.AlignHCenter }
            Text { text: backend.statusText; color: root.ink; font.pixelSize: 23; font.weight: Font.DemiBold; Layout.alignment: Qt.AlignHCenter }
            Text { text: "Los archivos originales permanecen intactos"; color: root.muted; font.pixelSize: 11; Layout.alignment: Qt.AlignHCenter }
            ListView {
                objectName: "resultList"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                spacing: 8; model: backend.results
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    required property var modelData
                    width: ListView.view.width; height: 89; radius: 13; color: root.tile; border.color: root.edge
                    Text { x: 13; y: 11; width: parent.width-26; text: (modelData.ok ? "✓  " : "!  ") + modelData.name; color: root.ink; font.pixelSize: 12; elide: Text.ElideMiddle; textFormat: Text.PlainText }
                    Text { x: 13; y: 32; width: parent.width-26; height: 20; text: modelData.detail; color: root.muted; font.pixelSize: 10; elide: Text.ElideRight; textFormat: Text.PlainText }
                    Row {
                        x: 5; y: 52; spacing: 7; visible: modelData.ok
                        Button { text: "Abrir"; flat: true; height: 30; onClicked: backend.openResult(modelData.location, false) }
                        Button { text: "Mostrar en Dolphin"; flat: true; height: 30; onClicked: backend.openResult(modelData.location, true) }
                    }
                }
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter; spacing: 12
                Button { text: "Detalles"; flat: true; onClicked: { detailText.text = backend.technicalDetails; details.open() } }
                Button { text: "Otros archivos…"; onClicked: backend.chooseFiles() }
                Button { text: "Cerrar"; onClicked: root.requestClose() }
            }
        }
    }

    Dialog {
        id: settings; title: "Preferencias"; modal: true
        anchors.centerIn: parent; width: Math.min(root.width-32, 480); height: Math.min(root.height-32, 590)
        standardButtons: Dialog.Save | Dialog.Cancel
        onOpened: {
            themeBox.currentIndex = ["system", "light", "dark"].indexOf(backend.preferences.theme)
            animations.checked = backend.preferences.animations
            notifications.checked = backend.preferences.notifications
            conflictBox.currentIndex = backend.preferences.conflicts === "fail" ? 1 : 0
            quality.value = backend.preferences.quality
            dpiBox.currentIndex = backend.preferences.pdf_dpi === 300 ? 2 : backend.preferences.pdf_dpi === 72 ? 0 : 1
            sheetBox.currentIndex = backend.preferences.sheet_pdf === "sheet" ? 1 : 0
            transparency.value = backend.preferences.radial_transparency
            ocrLanguages.text = backend.preferences.ocr_languages
        }
        onAccepted: backend.savePreferences({theme: ["system", "light", "dark"][themeBox.currentIndex], animations: animations.checked,
            notifications: notifications.checked, conflicts: conflictBox.currentIndex ? "fail" : "rename", quality: Math.round(quality.value),
            pdf_dpi: [72,150,300][dpiBox.currentIndex], sheet_pdf: sheetBox.currentIndex ? "sheet" : "print", timeout: backend.preferences.timeout,
            radial_transparency: Math.round(transparency.value), ocr_languages: ocrLanguages.text})
        contentItem: ScrollView {
            clip: true
            ColumnLayout {
                width: settings.availableWidth; spacing: 8
                Label { text: "Apariencia"; font.bold: true }
                ComboBox { id: themeBox; model: ["Seguir el sistema", "Claro", "Oscuro"]; Layout.fillWidth: true }
                CheckBox { id: animations; text: "Activar animaciones" }
                CheckBox { id: notifications; text: "Mostrar notificaciones" }
                Label { text: "Transparencia del fondo radial: " + Math.round(transparency.value) + " %"; font.bold: true }
                Slider { id: transparency; objectName: "transparencySlider"; from: 0; to: 100; stepSize: 1; Layout.fillWidth: true }
                Label { text: "Los botones e iconos conservan su contraste."; color: root.muted; font.pixelSize: 11 }
                Label { text: "Idiomas OCR (códigos separados por +)"; font.bold: true }
                TextField { id: ocrLanguages; placeholderText: "spa+eng"; Layout.fillWidth: true; selectByMouse: true }
                Label { text: "Si el destino ya existe"; font.bold: true }
                ComboBox { id: conflictBox; model: ["Crear un nombre disponible", "Detener e informar"]; Layout.fillWidth: true }
                Label { text: "Calidad JPG / WebP / PDF: " + Math.round(quality.value); font.bold: true }
                Slider { id: quality; from: 30; to: 100; stepSize: 1; Layout.fillWidth: true }
                Label { text: "Resolución PDF → imagen"; font.bold: true }
                ComboBox { id: dpiBox; model: ["72 ppp · pantalla", "150 ppp · equilibrada", "300 ppp · impresión"]; Layout.fillWidth: true }
                Label { text: "Hojas de cálculo → PDF"; font.bold: true }
                ComboBox { id: sheetBox; model: ["Respetar configuración de impresión", "Una página por hoja (incluye ocultas)"]; Layout.fillWidth: true }
                Label { text: "La segunda opción puede producir páginas muy grandes. CSV/TSV exportan todas las hojas, incluidas las ocultas, sin estilos ni fórmulas."; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 11; color: root.muted }
                Button { text: "Diagnóstico de motores"; flat: true; onClicked: { detailText.text = backend.dependencyInfo(); details.open() } }
            }
        }
    }
    Dialog {
        id: details; title: "Detalles de Convertix"; modal: true
        anchors.centerIn: parent; width: Math.min(root.width-32, 540); height: Math.min(root.height-32, 450)
        standardButtons: Dialog.Close
        ScrollView {
            anchors.fill: parent; clip: true
            TextArea { id: detailText; readOnly: true; wrapMode: TextEdit.WrapAnywhere; selectByMouse: true; textFormat: TextEdit.PlainText; font.family: "monospace"; font.pixelSize: 11 }
        }
    }
}
