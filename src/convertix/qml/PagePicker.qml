import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: picker
    property int count: tool.items.length ? tool.items[0].pages : 0
    property var selectedPages: []
    property alias ranges: ranges.text
    property string splitMode: ["extract", "each", "interval", "ranges"][mode.currentIndex]
    property alias interval: interval.value
    function toggle(page) {
        var a = selectedPages.slice()
        var i = a.indexOf(page)
        if (i >= 0) a.splice(i, 1); else a.push(page)
        a.sort(function(x,y) { return x-y })
        selectedPages = a
        ranges.text = a.join(",")
    }
    ComboBox { id: mode; objectName: "splitMode"; Layout.fillWidth: true; model: ["Extraer páginas seleccionadas", "Un PDF por página", "Dividir por intervalos", "Un PDF por grupo de rangos"] }
    RowLayout {
        visible: mode.currentIndex === 2
        Label { text: "Páginas por archivo" }
        SpinBox { id: interval; from: 1; to: Math.max(1, picker.count); value: 2; editable: true }
    }
    TextField { id: ranges; objectName: "pageRanges"; visible: mode.currentIndex === 0 || mode.currentIndex === 3; Layout.fillWidth: true; placeholderText: mode.currentIndex === 3 ? "1-5; 6-10; 11-20" : "1,3,5-8"; selectByMouse: true }
    Label { text: picker.selectedPages.length + " páginas marcadas de " + picker.count + ". Los rangos escritos prevalecen al ejecutar."; wrapMode: Text.WordWrap; Layout.fillWidth: true; font.pixelSize: 11 }
    Label { text: tool.splitPreview({pages: picker.ranges, split_mode: picker.splitMode, interval: picker.interval}); Layout.fillWidth: true; wrapMode: Text.WordWrap }
    GridView {
        id: grid
        objectName: "pageGrid"
        Layout.fillWidth: true; Layout.preferredHeight: 280; clip: true
        model: picker.count; cellWidth: 112; cellHeight: 150; cacheBuffer: 0
        ScrollBar.vertical: ScrollBar {}
        delegate: AbstractButton {
            id: pageTile
            required property int index
            objectName: "pageTile_" + index
            width: 104; height: 144
            onClicked: picker.toggle(index+1)
            Accessible.name: "Seleccionar página " + (index+1)
            background: Rectangle { radius: 8; color: pageTile.palette.base; border.width: 2; border.color: picker.selectedPages.indexOf(pageTile.index+1) >= 0 ? pageTile.palette.highlight : pageTile.palette.mid }
            contentItem: Column {
                Image { width: 96; height: 116; fillMode: Image.PreserveAspectFit; asynchronous: true; source: { tool.previewVersion; return tool.thumbnail(0, pageTile.index, 200) } }
                Label { width: 96; horizontalAlignment: Text.AlignHCenter; text: "Página " + (pageTile.index+1) }
            }
        }
    }
}
