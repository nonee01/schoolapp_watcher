import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.notification

PlasmoidItem {
    id: root

    readonly property string scriptPath: Qt.resolvedUrl("../scripts/schoolapp_status.py").toString().replace("file://", "")

    property bool ok: false
    property bool loaded: false
    property string watcher: "unknown"     // active | inactive | paused | unknown
    property int nextCheckS: 0
    property int pollInterval: 0
    property string latestType: ""
    property string latestSummary: ""
    property var history: []
    property var gradeModules: []
    property string updated: "-"
    property string errorMsg: ""

    // Notification edge tracking: remember the newest ts we've already alerted on.
    property string lastNotifiedTs: ""

    readonly property var typeIcon: ({
        "grades": "📊", "absences": "🚫", "modules": "📋", "semesters": "🎓"
    })

    Notification {
        id: changeNotification
        componentName: "plasma_workspace"
        eventId: "notification"
        iconName: "view-calendar-tasks"
        title: "SchoolApp Watcher"
        flags: Notification.Persistent
    }

    function titleForType(t) {
        if (t === "grades") return "SchoolApp - grades"
        if (t === "absences") return "SchoolApp - absences"
        if (t === "modules") return "SchoolApp - modules"
        if (t === "semesters") return "SchoolApp - semesters"
        return "SchoolApp Watcher"
    }

    function maybeNotify(j) {
        if (!Plasmoid.configuration.notifyEnabled) return
        if (!j.new_change || !j.new_summaries || j.new_summaries.length === 0) return
        var newestTs = j.history && j.history.length > 0 ? j.history[0].ts : ""
        if (newestTs === "" || newestTs === lastNotifiedTs) return  // already alerted
        var lines = j.new_summaries.slice(0, 3)
        var extra = j.new_summaries.length - lines.length
        var body = lines.join("\n")
        if (extra > 0) body += "\n+ " + extra + " more"
        changeNotification.title = titleForType(j.latest_change_type)
        changeNotification.text = body
        changeNotification.sendEvent()
        lastNotifiedTs = newestTs
    }

    function statusColor() {
        if (!ok) return Kirigami.Theme.neutralTextColor
        if (watcher === "active") return Kirigami.Theme.positiveTextColor
        if (watcher === "paused") return Kirigami.Theme.neutralTextColor
        return Kirigami.Theme.negativeTextColor
    }

    function fmtCountdown(s) {
        if (s <= 0) return "now"
        var m = Math.floor(s / 60)
        var sec = s % 60
        if (m <= 0) return sec + "s"
        return m + "m " + (sec < 10 ? "0" : "") + sec + "s"
    }

    function elide(str, n) {
        if (!str) return ""
        return str.length > n ? str.substring(0, n - 1) + "…" : str
    }

    // Compact panel summary text.
    readonly property string compactText: {
        if (!loaded) return "…"
        if (!ok) return "error"
        if (watcher === "inactive" || watcher === "unknown") return "stopped"
        if (watcher === "paused") return "paused"
        if (latestSummary.length === 0) return "No changes"
        var ic = typeIcon[latestType] || ""
        return (ic ? ic + " " : "") + elide(latestSummary, 28)
    }

    Plasma5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: function(source, data) {
            disconnectSource(source)
            root.loaded = true
            var out = (data["stdout"] || "").trim()
            if (out.length === 0) {
                root.ok = false
                root.errorMsg = (data["stderr"] || "no output").trim().substring(0, 60)
                return
            }
            try {
                var j = JSON.parse(out)
                root.ok = j.ok === true
                root.watcher = j.watcher || "unknown"
                root.nextCheckS = j.next_check_s || 0
                root.pollInterval = j.poll_interval || 0
                root.latestType = j.latest_change_type || ""
                root.latestSummary = j.latest_change_summary || ""
                root.history = j.history || []
                root.gradeModules = (j.grades && j.grades.modules) ? j.grades.modules : []
                root.updated = j.updated || "-"
                root.errorMsg = j.error || ""
                if (root.ok) root.maybeNotify(j)
            } catch (e) {
                root.ok = false
                root.errorMsg = "parse error"
            }
        }
        function poll() { connectSource("python3 '" + root.scriptPath + "' '"
            + Plasmoid.configuration.apiUrl + "' '" + Plasmoid.configuration.apiKey + "'") }
        function action(name) { connectSource("python3 '" + root.scriptPath + "' '"
            + Plasmoid.configuration.apiUrl + "' '" + Plasmoid.configuration.apiKey + "' " + name) }
    }

    // Poll timer (network).
    Timer {
        interval: Math.max(10, Plasmoid.configuration.refreshInterval) * 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: exec.poll()
    }

    // 1s local countdown ticker (no network).
    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: if (root.nextCheckS > 0) root.nextCheckS -= 1
    }

    Plasmoid.icon: "view-calendar-tasks"
    toolTipMainText: "SchoolApp Watcher"
    toolTipSubText: {
        if (!loaded) return "Loading…"
        if (!ok) return "⚠ " + errorMsg
        var s = "Watcher: " + watcher + "\n"
        if (latestSummary.length > 0) s += "Latest: " + latestSummary + "\n"
        return s + "Next check " + fmtCountdown(nextCheckS)
    }

    compactRepresentation: MouseArea {
        id: compact
        property bool horizontal: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
        Layout.minimumWidth: horizontal ? row.implicitWidth + Kirigami.Units.smallSpacing * 2 : 0
        Layout.minimumHeight: horizontal ? 0 : row.implicitHeight + Kirigami.Units.smallSpacing * 2
        acceptedButtons: Qt.LeftButton
        onClicked: root.expanded = !root.expanded

        RowLayout {
            id: row
            anchors.centerIn: parent
            spacing: Kirigami.Units.smallSpacing

            Rectangle {
                width: Kirigami.Units.iconSizes.small * 0.5
                height: width
                radius: width / 2
                color: root.statusColor()
                Layout.alignment: Qt.AlignVCenter
            }
            PlasmaComponents3.Label {
                text: root.compactText
                font.bold: true
                color: root.ok ? Kirigami.Theme.textColor : Kirigami.Theme.neutralTextColor
            }
        }
    }

    // Replaced with the full 3-tab popup in Task 7.
    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.minimumHeight: Kirigami.Units.gridUnit * 16
        PlasmaComponents3.Label { anchors.centerIn: parent; text: "popup placeholder" }
    }
}
