import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: editor
    property int originalWidth: tool.items.length ? tool.items[0].width : 1
    property int originalHeight: tool.items.length ? tool.items[0].height : 1
    property real factor: percentMode.checked ? percent.value/100 : Math.min(Number(widthField.text)/originalWidth || Infinity, Number(heightField.text)/originalHeight || Infinity)
    property int finalWidth: percentMode.checked || keep.checked ? Math.round(originalWidth*factor) : Number(widthField.text)
    property int finalHeight: percentMode.checked || keep.checked ? Math.round(originalHeight*factor) : Number(heightField.text)
    property var options: ({percent: percentMode.checked ? percent.value : 0, width: Number(widthField.text), height: Number(heightField.text), keep_aspect: keep.checked, interpolation: ["lanczos","bicubic","nearest"][interpolation.currentIndex]})
    Label { text: "Original: " + originalWidth + " × " + originalHeight + " px · " + tool.items.length + " archivo(s)"; font.bold: true }
    ComboBox {
        objectName: "resizePreset"
        model: ["50 %", "25 %", "75 %", "200 % · interpolación", "1920 × 1080 como límite", "1280 × 720 como límite", "Personalizado"]
        onActivated: {
            if (currentIndex < 4) { percentMode.checked=true; percent.value=[50,25,75,200][currentIndex] }
            else if (currentIndex < 6) { percentMode.checked=false; keep.checked=true; widthField.text=currentIndex===4 ? "1920" : "1280"; heightField.text=currentIndex===4 ? "1080" : "720" }
        }
    }
    RowLayout {
        CheckBox { id: percentMode; text: "Porcentaje"; checked: true }
        SpinBox { id: percent; objectName: "resizePercent"; from: 1; to: 1000; value: 50; editable: true; enabled: percentMode.checked }
        Label { text: "%" }
    }
    RowLayout {
        Label { text: "Ancho" }
        TextField { id: widthField; objectName: "resizeWidth"; text: "1920"; enabled: !percentMode.checked; validator: IntValidator { bottom: 1; top: 30000 } Layout.fillWidth: true }
        Label { text: "Alto" }
        TextField { id: heightField; objectName: "resizeHeight"; text: "1080"; enabled: !percentMode.checked; validator: IntValidator { bottom: 1; top: 30000 } Layout.fillWidth: true }
    }
    CheckBox { id: keep; text: "Mantener proporciones (ancho/alto como límites)"; checked: true; enabled: !percentMode.checked }
    ComboBox { id: interpolation; model: ["LANCZOS · alta calidad", "Bicúbica", "Vecino más próximo"] }
    Label { text: "Resultado de la primera imagen: " + finalWidth + " × " + finalHeight + " px. Ampliar usa interpolación; no recupera detalle real."; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    Rectangle {
        Layout.preferredWidth: 280; Layout.preferredHeight: 170; color: "#e5e5e5"; clip: true
        Image {
            anchors.centerIn: parent
            width: Math.min(parent.width, parent.height*editor.finalWidth/Math.max(1,editor.finalHeight))
            height: width*Math.max(1,editor.finalHeight)/Math.max(1,editor.finalWidth)
            fillMode: Image.Stretch; asynchronous: true
            source: { tool.previewVersion; return tool.thumbnail(0,0,420) }
        }
    }
}
