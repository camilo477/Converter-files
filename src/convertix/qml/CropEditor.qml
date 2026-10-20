import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: editor
    objectName: "cropEditor"
    property int imageWidth: tool.items.length ? tool.items[0].width : 1
    property int imageHeight: tool.items.length ? tool.items[0].height : 1
    property real cropX: 0
    property real cropY: 0
    property real cropWidth: imageWidth
    property real cropHeight: imageHeight
    property real aspect: [0, 1, 4/3, 3/2, 16/9, imageWidth/imageHeight][aspectBox.currentIndex]
    property var box: [Math.round(cropX), Math.round(cropY), Math.round(cropX+cropWidth), Math.round(cropY+cropHeight)]
    function reset() {
        cropWidth = imageWidth; cropHeight = imageHeight
        if (aspect > 0) {
            cropWidth = Math.min(imageWidth, imageHeight*aspect)
            cropHeight = cropWidth/aspect
        }
        cropX = (imageWidth-cropWidth)/2; cropY = (imageHeight-cropHeight)/2
    }
    onImageWidthChanged: reset()
    onImageHeightChanged: reset()
    onAspectChanged: reset()
    RowLayout {
        ComboBox { id: aspectBox; objectName: "cropAspect"; model: ["Libre", "1:1", "4:3", "3:2", "16:9", "Original"] }
        Button { text: "Restablecer"; onClicked: editor.reset() }
        Button { text: "Ajustar"; onClicked: zoom.value = 1 }
        Label { text: "Zoom" }
        Slider { id: zoom; from: 1; to: 4; value: 1; Layout.fillWidth: true }
    }
    Flickable {
        id: viewport
        Layout.fillWidth: true; Layout.preferredHeight: 325
        contentWidth: canvas.width; contentHeight: canvas.height; clip: true
        ScrollBar.horizontal: ScrollBar {}
        ScrollBar.vertical: ScrollBar {}
        Item {
            id: canvas
            property real factor: Math.min(viewport.width/editor.imageWidth, viewport.height/editor.imageHeight)*zoom.value
            width: editor.imageWidth*factor; height: editor.imageHeight*factor
            Image { anchors.fill: parent; fillMode: Image.Stretch; asynchronous: true; source: { tool.previewVersion; return tool.thumbnail(0, 0, 1400) } }
            Rectangle {
                id: region
                objectName: "cropRegion"
                x: editor.cropX*canvas.factor; y: editor.cropY*canvas.factor
                width: editor.cropWidth*canvas.factor; height: editor.cropHeight*canvas.factor
                color: "#204f9fff"; border.color: "#63b3ff"; border.width: 2
                focus: true; activeFocusOnTab: true
                Keys.onPressed: function(event) {
                    var step = event.modifiers & Qt.ShiftModifier ? 10 : 1
                    if (event.key === Qt.Key_Left) editor.cropX = Math.max(0, editor.cropX-step)
                    else if (event.key === Qt.Key_Right) editor.cropX = Math.min(editor.imageWidth-editor.cropWidth, editor.cropX+step)
                    else if (event.key === Qt.Key_Up) editor.cropY = Math.max(0, editor.cropY-step)
                    else if (event.key === Qt.Key_Down) editor.cropY = Math.min(editor.imageHeight-editor.cropHeight, editor.cropY+step)
                    else return
                    event.accepted = true
                }
                MouseArea {
                    anchors.fill: parent; cursorShape: Qt.SizeAllCursor; preventStealing: true
                    property point start
                    property real originalX
                    property real originalY
                    onPressed: function(mouse) { start = mapToItem(canvas, mouse.x, mouse.y); originalX=editor.cropX; originalY=editor.cropY; region.forceActiveFocus() }
                    onPositionChanged: function(mouse) {
                        if (!pressed) return
                        var p = mapToItem(canvas, mouse.x, mouse.y)
                        editor.cropX = Math.max(0, Math.min(editor.imageWidth-editor.cropWidth, originalX+(p.x-start.x)/canvas.factor))
                        editor.cropY = Math.max(0, Math.min(editor.imageHeight-editor.cropHeight, originalY+(p.y-start.y)/canvas.factor))
                    }
                }
                Repeater {
                    model: 4
                    delegate: Rectangle {
                        id: handle
                        required property int index
                        property bool east: index === 1 || index === 3
                        property bool south: index >= 2
                        objectName: "cropHandle_" + index
                        x: east ? region.width-7 : -7; y: south ? region.height-7 : -7
                        width: 14; height: 14; radius: 3; color: "white"; border.color: "#286bc9"
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.SizeFDiagCursor; preventStealing: true
                            property real anchorX
                            property real anchorY
                            onPressed: { anchorX = handle.east ? editor.cropX : editor.cropX+editor.cropWidth; anchorY = handle.south ? editor.cropY : editor.cropY+editor.cropHeight }
                            onPositionChanged: function(mouse) {
                                if (!pressed) return
                                var p = mapToItem(canvas, mouse.x, mouse.y)
                                var maxW = handle.east ? editor.imageWidth-anchorX : anchorX
                                var maxH = handle.south ? editor.imageHeight-anchorY : anchorY
                                var w = Math.max(1, Math.min(maxW, Math.abs(p.x/canvas.factor-anchorX)))
                                var h = Math.max(1, Math.min(maxH, Math.abs(p.y/canvas.factor-anchorY)))
                                if (editor.aspect > 0) { w = Math.min(w, h*editor.aspect, maxH*editor.aspect); h = w/editor.aspect }
                                editor.cropWidth = w; editor.cropHeight = h
                                editor.cropX = handle.east ? anchorX : anchorX-w
                                editor.cropY = handle.south ? anchorY : anchorY-h
                            }
                        }
                    }
                }
            }
        }
    }
    Label { text: "Recorte: " + Math.round(editor.cropWidth) + " × " + Math.round(editor.cropHeight) + " px · origen " + Math.round(editor.cropX) + ", " + Math.round(editor.cropY) + ". Flechas: mover; Mayús: 10 px."; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Rectangle {
        Layout.preferredWidth: Math.min(180, 90*editor.cropWidth/Math.max(1,editor.cropHeight)); Layout.preferredHeight: Math.min(90, 180*editor.cropHeight/Math.max(1,editor.cropWidth)); clip: true; color: "#ddd"
        Image { x: -editor.cropX*parent.width/editor.cropWidth; y: -editor.cropY*parent.height/editor.cropHeight; width: editor.imageWidth*parent.width/editor.cropWidth; height: editor.imageHeight*parent.height/editor.cropHeight; source: { tool.previewVersion; return tool.thumbnail(0,0,1400) } }
    }
}
