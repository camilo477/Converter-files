import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: editor
    property bool folders: false
    property var tones: ApplicationWindow.window.palette
    Label { text: "Orden de salida · arrastra una fila o usa las flechas"; font.bold: true }
    ListView {
        id: list
        objectName: "orderedFiles"
        Layout.fillWidth: true; Layout.preferredHeight: 255; clip: true
        model: tool.items; spacing: 6
        ScrollBar.vertical: ScrollBar {}
        delegate: Item {
            id: row
            required property var modelData
            required property int index
            width: list.width; height: 76
            Rectangle {
                id: card
                objectName: "orderCard_" + row.index
                width: row.width; height: 72; radius: 10
                color: editor.tones.base; border.color: editor.tones.mid
                RowLayout {
                    anchors.fill: parent; anchors.margins: 7; spacing: 8
                    Label { text: "☰"; font.pixelSize: 20 }
                    Image { Layout.preferredWidth: 48; Layout.preferredHeight: 57; fillMode: Image.PreserveAspectFit; asynchronous: true; source: { tool.previewVersion; return tool.thumbnail(row.index, 0, 160) } }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Label { text: row.modelData.name; elide: Text.ElideMiddle; Layout.fillWidth: true; textFormat: Text.PlainText }
                        Label { text: (row.modelData.pages ? row.modelData.pages + " páginas · " : row.modelData.width ? row.modelData.width + " × " + row.modelData.height + " · " : "") + (row.modelData.size/1024).toFixed(1) + " KiB"; font.pixelSize: 11; opacity: 0.75 }
                    }
                    ToolButton { text: "↑"; enabled: row.index > 0; onClicked: tool.move(row.index, row.index-1); Accessible.name: "Mover arriba" }
                    ToolButton { text: "↓"; enabled: row.index < tool.items.length-1; onClicked: tool.move(row.index, row.index+1); Accessible.name: "Mover abajo" }
                    ToolButton { text: "×"; onClicked: tool.remove(row.index); Accessible.name: "Quitar archivo" }
                }
            }
            // A real drop is translated once into a move of the backing selection.
            MouseArea {
                id: dragArea
                objectName: "dragRow_" + row.index
                x: 0; y: 0; width: 34; height: row.height
                preventStealing: true
                drag.threshold: 0
                drag.target: card; drag.axis: Drag.YAxis
                onReleased: function(mouse) {
                    var point = mapToItem(list.contentItem, mouse.x, mouse.y)
                    var destination = Math.max(0, Math.min(tool.items.length-1, Math.floor(point.y/82)))
                    card.y = 0
                    if (destination !== row.index) tool.move(row.index, destination)
                }
                onCanceled: card.y = 0
            }
        }
    }
    RowLayout {
        Button { text: "Añadir archivos…"; onClicked: tool.add() }
        Button { visible: editor.folders; text: "Añadir carpeta…"; onClicked: tool.addFolder() }
        Label { text: tool.items.length + " seleccionados"; opacity: 0.75 }
    }
}
