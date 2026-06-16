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

    readonly property string scriptPath: Qt.resolvedUrl("../scripts/schoolapp_status.py").toString().replace(/^file:\/\//, "")

    property bool ok: false
    property bool loaded: false
    property bool busy: false               // a backend request is in flight
    property string watcher: "unknown"     // active | inactive | paused | unknown
    property int nextCheckS: 0
    property int pollInterval: 0
    property string latestType: ""
    property string latestSummary: ""
    property var history: []
    property var gradeModules: []
    property string updated: "—"
    property string errorMsg: ""

    // Notification edge tracking: remember the newest ts we've already alerted on.
    property string lastNotifiedTs: ""

    // Keep in sync with TYPE_ICON in scripts/schoolapp_status.py.
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
        if (t === "grades") return "SchoolApp — grades"
        if (t === "absences") return "SchoolApp — absences"
        if (t === "modules") return "SchoolApp — modules"
        if (t === "semesters") return "SchoolApp — semesters"
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

    function truncate(str, n) {
        if (!str) return ""
        return str.length > n ? str.substring(0, n - 1) + "…" : str
    }

    function relativeFor(tsIso) {
        if (!tsIso) return ""
        var t = new Date(tsIso)
        if (isNaN(t.getTime())) return ""
        var mins = Math.floor((Date.now() - t.getTime()) / 60000)
        if (mins < 1) return "just now"
        if (mins < 60) return mins + "m ago"
        var h = Math.floor(mins / 60)
        if (h < 24) return h + "h ago"
        return Math.floor(h / 24) + "d ago"
    }

    // Compact panel summary text.
    readonly property string compactText: {
        if (!loaded) return "…"
        if (!ok) return "error"
        if (watcher === "inactive" || watcher === "unknown") return "stopped"
        if (watcher === "paused") return "paused"
        if (latestSummary.length === 0) return "No changes"
        var ic = typeIcon[latestType] || ""
        return (ic ? ic + " " : "") + truncate(latestSummary, 28)
    }

    Plasma5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: function(source, data) {
            disconnectSource(source)
            root.loaded = true
            root.busy = false
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
                root.updated = j.updated || "—"
                root.errorMsg = j.error || ""
                if (root.ok) root.maybeNotify(j)
            } catch (e) {
                root.ok = false
                root.errorMsg = "parse error"
            }
        }
        function poll() {
            root.busy = true
            connectSource("python3 '" + root.scriptPath + "' '"
                + Plasmoid.configuration.apiUrl + "' '" + Plasmoid.configuration.apiKey + "'")
        }
        function action(name) {
            root.busy = true
            connectSource("python3 '" + root.scriptPath + "' '"
                + Plasmoid.configuration.apiUrl + "' '" + Plasmoid.configuration.apiKey + "' '" + name + "'")
        }
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
        var s = "Watcher: " + watcher
        if (latestSummary.length > 0) s += "\nLatest: " + latestSummary
        return s + "\nNext check " + fmtCountdown(nextCheckS)
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

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.minimumHeight: Kirigami.Units.gridUnit * 18
        Layout.preferredWidth: Kirigami.Units.gridUnit * 20
        Layout.preferredHeight: Kirigami.Units.gridUnit * 22

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing

            // Header
            RowLayout {
                Layout.fillWidth: true
                Rectangle {
                    width: Kirigami.Units.iconSizes.small * 0.6; height: width; radius: width / 2
                    color: root.statusColor()
                }
                Kirigami.Heading { text: "SchoolApp Watcher"; level: 3; Layout.fillWidth: true }
                PlasmaComponents3.Label {
                    text: !root.loaded ? "…" : root.ok ? "live" : "offline"
                    opacity: 0.6
                    color: root.ok ? Kirigami.Theme.textColor : Kirigami.Theme.neutralTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }

            QQC2.TabBar {
                id: tabBar
                Layout.fillWidth: true
                QQC2.TabButton { text: "Status" }
                QQC2.TabButton { text: "Changes" }
                QQC2.TabButton { text: "Grades" }
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: tabBar.currentIndex

                // ---- STATUS TAB ----
                ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents3.Label { text: "Service"; opacity: 0.8; Layout.fillWidth: true }
                        PlasmaComponents3.Label { text: root.watcher; font.bold: true; color: root.statusColor() }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents3.Label { text: "Next check"; opacity: 0.8; Layout.fillWidth: true }
                        PlasmaComponents3.Label { text: root.fmtCountdown(root.nextCheckS); font.bold: true }
                    }
                    QQC2.ProgressBar {
                        Layout.fillWidth: true
                        from: 0; to: 1
                        value: root.pollInterval > 0
                            ? (1 - Math.min(1, root.nextCheckS / root.pollInterval)) : 0
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents3.Label { text: "Last change"; opacity: 0.8; Layout.fillWidth: true }
                        PlasmaComponents3.Label {
                            text: root.history.length > 0 ? root.relativeFor(root.history[0].ts) : "—"
                        }
                    }
                    Item { Layout.fillHeight: true }
                    PlasmaComponents3.Label {
                        visible: !root.ok
                        Layout.fillWidth: true; wrapMode: Text.WordWrap
                        color: Kirigami.Theme.neutralTextColor
                        text: "⚠ " + root.errorMsg
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        PlasmaComponents3.Button {
                            text: "Force check"; icon.name: "view-refresh"
                            enabled: !root.busy
                            onClicked: exec.action("check")
                        }
                        PlasmaComponents3.Button {
                            text: root.watcher === "paused" || root.watcher === "inactive" ? "Resume" : "Pause"
                            icon.name: root.watcher === "paused" || root.watcher === "inactive"
                                ? "media-playback-start" : "media-playback-pause"
                            enabled: !root.busy
                            onClicked: exec.action(
                                (root.watcher === "paused" || root.watcher === "inactive") ? "resume" : "pause")
                        }
                    }
                }

                // ---- CHANGES TAB ----
                QQC2.ScrollView {
                    clip: true
                    ListView {
                        model: root.history
                        spacing: Kirigami.Units.smallSpacing
                        delegate: RowLayout {
                            required property var modelData
                            width: ListView.view ? ListView.view.width : implicitWidth
                            PlasmaComponents3.Label {
                                text: root.typeIcon[modelData.type] || "•"
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                PlasmaComponents3.Label {
                                    text: modelData.summary
                                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                                    font.bold: modelData.new === true
                                }
                                PlasmaComponents3.Label {
                                    text: root.relativeFor(modelData.ts)
                                    opacity: 0.6; font.pointSize: Kirigami.Theme.smallFont.pointSize
                                }
                            }
                            PlasmaComponents3.Label {
                                visible: modelData.new === true
                                text: "NEW"
                                color: Kirigami.Theme.highlightColor
                                font.bold: true; font.pointSize: Kirigami.Theme.smallFont.pointSize
                            }
                        }
                    }
                }

                // ---- GRADES TAB ----
                QQC2.ScrollView {
                    clip: true
                    ColumnLayout {
                        width: parent.width
                        spacing: Kirigami.Units.smallSpacing
                        Repeater {
                            model: root.gradeModules
                            delegate: ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 1
                                PlasmaComponents3.Label {
                                    text: (modelData.code || "") + " — " + (modelData.title || "")
                                    font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight
                                }
                                Repeater {
                                    model: modelData.elements || []
                                    delegate: RowLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        PlasmaComponents3.Label {
                                            text: modelData.code; opacity: 0.8; Layout.fillWidth: true
                                        }
                                        PlasmaComponents3.Label {
                                            text: modelData.moy && modelData.moy !== "--" ? modelData.moy : "—"
                                            color: (modelData.moy && modelData.moy !== "--")
                                                ? Kirigami.Theme.positiveTextColor
                                                : Kirigami.Theme.disabledTextColor
                                            font.bold: true
                                        }
                                    }
                                }
                            }
                        }
                        PlasmaComponents3.Label {
                            visible: root.gradeModules.length === 0
                            text: "No snapshot yet"; opacity: 0.6
                        }
                    }
                }
            }

            // Footer
            Kirigami.Separator { Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true
                PlasmaComponents3.Label {
                    text: "Updated " + root.updated; opacity: 0.6
                    font.pointSize: Kirigami.Theme.smallFont.pointSize; Layout.fillWidth: true
                }
                PlasmaComponents3.Button {
                    text: "Refresh"; icon.name: "view-refresh"
                    enabled: !root.busy; onClicked: exec.poll()
                }
            }
        }
    }
}
