import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.FormLayout {
    id: page

    property alias cfg_apiUrl: urlField.text
    property alias cfg_apiKey: keyField.text
    property alias cfg_refreshInterval: refreshSpin.value
    property alias cfg_notifyEnabled: notifyCheck.checked

    QQC2.TextField {
        id: urlField
        Kirigami.FormData.label: "API URL:"
        placeholderText: "http://localhost:8787"
        Layout.preferredWidth: Kirigami.Units.gridUnit * 16
    }

    QQC2.TextField {
        id: keyField
        Kirigami.FormData.label: "API key:"
        echoMode: TextInput.PasswordEchoOnEdit
        Layout.preferredWidth: Kirigami.Units.gridUnit * 16
    }

    QQC2.SpinBox {
        id: refreshSpin
        Kirigami.FormData.label: "Poll every:"
        from: 10
        to: 600
        stepSize: 5
        textFromValue: function(value) { return value + " s" }
        valueFromText: function(text) { return parseInt(text) }
    }

    Item { Kirigami.FormData.isSection: true }

    QQC2.CheckBox {
        id: notifyCheck
        Kirigami.FormData.label: "Notifications:"
        text: "Notify when a new change is detected"
    }
}
