import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';

// ── EDIT THESE TWO LINES ──────────────────────────────────────────────
const API_URL = 'http://100.75.240.122:8787'; // laptop Tailscale IP (tailscale ip -4)
const API_KEY = 'c29b3ea420d5c252b90bc59d36690faa'; // API_KEY from .env
// ──────────────────────────────────────────────────────────────────────

async function api(path: string, method: 'GET' | 'POST' = 'GET') {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: { 'X-API-Key': API_KEY },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const GREEN = '#166534';
const GREEN_BG = '#dcfce7';
const RED = '#991b1b';
const RED_BG = '#fee2e2';
const GRAY = '#6b7280';
const BLUE = '#1e40af';

function Badge({ ok, label }: { ok: boolean | null; label: string }) {
  const fg = ok === null ? '#374151' : ok ? GREEN : RED;
  const bg = ok === null ? '#f3f4f6' : ok ? GREEN_BG : RED_BG;
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={{ color: fg, fontWeight: '700', fontSize: 12 }}>{label}</Text>
    </View>
  );
}

function Score({ label, value }: { label: string; value: string }) {
  const estimated = value?.endsWith('*');
  return (
    <View style={styles.score}>
      <Text style={styles.scoreLabel}>{label}</Text>
      <Text style={[styles.scoreValue, estimated && { color: '#2563eb' }]}>{value || '--'}</Text>
    </View>
  );
}

function useLoader<T>(path: string): [T | null, boolean, string, () => Promise<void>] {
  const [data, setData] = useState<T | null>(null);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState('');
  const load = useCallback(async () => {
    setBusy(true);
    setErr('');
    try {
      setData(await api(path));
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  }, [path]);
  useEffect(() => {
    load();
  }, [load]);
  return [data, busy, err, load];
}

function GradesScreen() {
  const [data, busy, err, load] = useLoader<any>('/api/grades/S4');
  return (
    <ScrollView
      style={styles.body}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={load} />}
    >
      {err ? <Text style={styles.error}>{err}</Text> : null}
      {data?.modules?.map((m: any) => (
        <View key={m.code} style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.kicker}>
              {m.code} · coef {m.coef} · seuil {m.seuil}
            </Text>
            <Badge
              ok={m.validated}
              label={
                m.moy === '--'
                  ? 'En attente'
                  : `${m.moy}${m.partial ? ' (partielle)' : ''} ${m.validated ? '✓' : '✗'}`
              }
            />
          </View>
          <Text style={styles.title}>{m.title}</Text>
          {m.elements.map((el: any) => (
            <View key={el.code} style={styles.elementBox}>
              <Text style={styles.elementTitle}>
                {el.code} — {el.title}
              </Text>
              <View style={styles.scoresRow}>
                <Score label="CC" value={el.cc} />
                <Score label="EX" value={el.ex} />
                <Score label="TP" value={el.tp} />
                <Score label="Moy" value={el.moy} />
                <Badge
                  ok={el.validated}
                  label={el.moy === '--' ? '…' : el.validated ? 'Validé' : 'Non validé'}
                />
              </View>
            </View>
          ))}
        </View>
      ))}
      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

function AbsencesScreen() {
  const [data, busy, err, load] = useLoader<any>('/api/absences');
  const sanctions = data?.sanctions || {};
  return (
    <ScrollView
      style={styles.body}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={load} />}
    >
      {err ? <Text style={styles.error}>{err}</Text> : null}
      {Object.keys(sanctions).length > 0 && (
        <View style={[styles.card, { borderLeftColor: RED, borderLeftWidth: 4 }]}>
          <Text style={styles.kicker}>SANCTIONS</Text>
          {Object.entries(sanctions).map(([k, v]) => (
            <Text key={k} style={styles.sanctionLine}>
              {k}: <Text style={{ fontWeight: '700' }}>{String(v)}</Text>
            </Text>
          ))}
        </View>
      )}
      {data?.absences?.map((a: any, i: number) => (
        <View key={i} style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.kicker}>
              {a.element} · {a.date}
            </Text>
            <Badge ok={a.justified} label={a.justified ? 'Justifiée' : 'Non justifiée'} />
          </View>
          <Text style={styles.title}>{a.title}</Text>
          <Text style={styles.sub}>{a.seance}</Text>
          {a.remarks ? <Text style={styles.sub}>{a.remarks}</Text> : null}
        </View>
      ))}
      {data && !data.absences?.length ? <Text style={styles.empty}>Aucune absence 🎉</Text> : null}
      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

// "V", "VAL", "VRAT" → validated; "NV", "AJ", "RAT" → not; anything else unknown
function decOk(dec: string): boolean | null {
  const d = (dec || '').trim().toUpperCase();
  if (!d || d === '--') return null;
  if (d.startsWith('V')) return true;
  return false;
}

function ResultsScreen() {
  const [sems, busySem, errSem, loadSem] = useLoader<any>('/api/semesters');
  const [mods, busyMod, errMod, loadMod] = useLoader<any>('/api/modules');
  const busy = busySem || busyMod;
  const reload = useCallback(async () => {
    await Promise.all([loadSem(), loadMod()]);
  }, [loadSem, loadMod]);
  return (
    <ScrollView
      style={styles.body}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={reload} />}
    >
      {errSem || errMod ? <Text style={styles.error}>{errSem || errMod}</Text> : null}

      <Text style={styles.sectionHeader}>🎓 Semestres</Text>
      {sems?.semesters?.map((s: any, i: number) => (
        <View key={i} style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.kicker}>
              {s.niveau} · {s.au}
            </Text>
            <Badge ok={decOk(s.dec)} label={s.dec || '--'} />
          </View>
          <Text style={styles.title}>{s.sem}</Text>
          <View style={styles.scoresRow}>
            <Score label="Moyenne" value={s.moy} />
            <Score label="Classement" value={s.rank} />
            {s.pj && s.pj !== '--' ? <Score label="PJ" value={s.pj} /> : null}
          </View>
        </View>
      ))}
      {sems && !sems.semesters?.length ? (
        <Text style={styles.empty}>Aucun résultat de semestre publié.</Text>
      ) : null}

      <Text style={styles.sectionHeader}>📋 Modules officiels</Text>
      {mods?.modules?.map((m: any, i: number) => (
        <View key={i} style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.kicker}>
              {m.code} · {m.au}
            </Text>
            <Badge ok={decOk(m.dec)} label={`${m.moy}  ${m.dec}`} />
          </View>
          <Text style={styles.title}>{m.title}</Text>
        </View>
      ))}
      {mods && !mods.modules?.length ? (
        <Text style={styles.empty}>Aucun résultat officiel publié.</Text>
      ) : null}
      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

function HistoryScreen() {
  const [data, busy, err, load] = useLoader<any>('/api/history?limit=200');
  const icons: Record<string, string> = {
    grades: '📚',
    absences: '🚨',
    modules: '📋',
    semesters: '🎓',
  };
  return (
    <ScrollView
      style={styles.body}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={load} />}
    >
      {err ? <Text style={styles.error}>{err}</Text> : null}
      {data?.history?.map((h: any, i: number) => (
        <View key={i} style={styles.card}>
          <Text style={styles.kicker}>
            {h.ts?.replace('T', ' ')} · {h.semester}
          </Text>
          <Text style={styles.historyLine}>
            {icons[h.type] || '•'} {h.summary}
          </Text>
        </View>
      ))}
      {data && !data.history?.length ? (
        <Text style={styles.empty}>Aucun changement enregistré pour le moment.</Text>
      ) : null}
      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

function fmtCountdown(s: number): string {
  if (s >= 3600) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  if (s >= 60) return `${Math.floor(s / 60)}m ${s % 60}s`;
  return `${s}s`;
}

function StatusScreen() {
  const [data, busy, err, load] = useLoader<any>('/api/status');
  const [msg, setMsg] = useState('');
  const [acting, setActing] = useState(false);
  const [now, setNow] = useState(Date.now());
  const fetchedAtRef = useRef(0);
  const lastAutoRef = useRef(0);

  useEffect(() => {
    if (data) fetchedAtRef.current = Date.now();
  }, [data]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const running = data?.watcher === 'active';

  // seconds until the next watcher check, ticking locally between fetches
  let remaining: number | null = null;
  if (running && data?.next_check && data?.server_time) {
    const base = (Date.parse(data.next_check) - Date.parse(data.server_time)) / 1000;
    remaining = Math.round(base - (now - fetchedAtRef.current) / 1000);
  }

  // when the countdown expires, refresh status (at most every 20s)
  useEffect(() => {
    if (remaining !== null && remaining <= 0 && !busy && now - lastAutoRef.current > 20000) {
      lastAutoRef.current = now;
      load();
    }
  }, [now]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (path: string, label: string) => {
    setActing(true);
    setMsg(`${label}…`);
    try {
      const r = await api(path, 'POST');
      setMsg(
        r.changed !== undefined
          ? r.changed
            ? '✅ Changement détecté — notification envoyée !'
            : 'Aucun changement.'
          : `Watcher: ${r.watcher}`
      );
      await load();
    } catch (e: any) {
      setMsg(`Erreur: ${e?.message || e}`);
    } finally {
      setActing(false);
    }
  };

  return (
    <ScrollView
      style={styles.body}
      refreshControl={<RefreshControl refreshing={busy} onRefresh={load} />}
    >
      {err ? <Text style={styles.error}>{err}</Text> : null}
      <View style={styles.card}>
        <View style={styles.rowBetween}>
          <Text style={styles.title}>Watcher</Text>
          <Badge ok={running} label={running ? 'Actif' : data?.watcher || '?'} />
        </View>
        <Text style={styles.sub}>Dernier check : {data?.last_check?.replace('T', ' ') || '—'}</Text>
        {data?.poll_interval ? (
          <Text style={styles.sub}>
            Intervalle : {data.poll_interval >= 120 ? `${Math.round(data.poll_interval / 60)} min` : `${data.poll_interval}s`}
          </Text>
        ) : null}
      </View>

      {running && remaining !== null && (
        <View style={[styles.card, styles.countdownCard]}>
          <Text style={styles.countdownLabel}>PROCHAIN CHECK</Text>
          {remaining > 0 ? (
            <Text style={styles.countdownValue}>{fmtCountdown(remaining)}</Text>
          ) : (
            <Text style={[styles.countdownValue, { color: '#92400e' }]}>imminent…</Text>
          )}
        </View>
      )}

      <Pressable
        style={[styles.actionBtn, { backgroundColor: BLUE }]}
        disabled={acting}
        onPress={() => act('/api/check?semester=S4', 'Vérification')}
      >
        {acting ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.actionText}>🔄 Vérifier maintenant</Text>
        )}
      </Pressable>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <Pressable
          style={[styles.actionBtn, { flex: 1, backgroundColor: '#b91c1c' }]}
          disabled={acting}
          onPress={() => act('/api/watcher/pause', 'Pause')}
        >
          <Text style={styles.actionText}>⏸ Pause</Text>
        </Pressable>
        <Pressable
          style={[styles.actionBtn, { flex: 1, backgroundColor: GREEN }]}
          disabled={acting}
          onPress={() => act('/api/watcher/resume', 'Reprise')}
        >
          <Text style={styles.actionText}>▶️ Reprendre</Text>
        </Pressable>
      </View>
      {msg ? <Text style={styles.msg}>{msg}</Text> : null}
    </ScrollView>
  );
}

const TABS = [
  { key: 'grades', label: 'Notes', icon: '📚' },
  { key: 'absences', label: 'Absences', icon: '🚨' },
  { key: 'results', label: 'Résultats', icon: '🎓' },
  { key: 'history', label: 'Historique', icon: '🕘' },
  { key: 'status', label: 'Statut', icon: '⚙️' },
] as const;

export default function App() {
  const [tab, setTab] = useState<(typeof TABS)[number]['key']>('grades');
  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="light-content" backgroundColor={BLUE} />
      <View style={styles.header}>
        <Text style={styles.headerSub}>SchoolApp · ENSAM UMI · S4</Text>
        <Text style={styles.headerTitle}>
          {TABS.find((t) => t.key === tab)?.icon} {TABS.find((t) => t.key === tab)?.label}
        </Text>
      </View>
      <View style={{ flex: 1 }}>
        {tab === 'grades' && <GradesScreen />}
        {tab === 'absences' && <AbsencesScreen />}
        {tab === 'results' && <ResultsScreen />}
        {tab === 'history' && <HistoryScreen />}
        {tab === 'status' && <StatusScreen />}
      </View>
      <View style={styles.tabbar}>
        {TABS.map((t) => (
          <Pressable key={t.key} style={styles.tab} onPress={() => setTab(t.key)}>
            <Text style={{ fontSize: 18 }}>{t.icon}</Text>
            <Text style={[styles.tabLabel, tab === t.key && { color: BLUE, fontWeight: '700' }]}>
              {t.label}
            </Text>
          </Pressable>
        ))}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#f3f4f6' },
  header: { backgroundColor: BLUE, paddingHorizontal: 20, paddingTop: 40, paddingBottom: 14 },
  headerSub: { color: '#bfdbfe', fontSize: 12 },
  headerTitle: { color: '#fff', fontSize: 20, fontWeight: '700', marginTop: 2 },
  body: { flex: 1, padding: 12 },
  sectionHeader: {
    fontSize: 13,
    fontWeight: '700',
    color: GRAY,
    marginBottom: 8,
    marginTop: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 2,
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
  },
  kicker: { color: GRAY, fontSize: 12 },
  title: { fontSize: 16, fontWeight: '700', color: '#111827', marginTop: 2 },
  sub: { color: '#374151', fontSize: 13, marginTop: 4 },
  elementBox: {
    borderTopWidth: 1,
    borderTopColor: '#f3f4f6',
    marginTop: 10,
    paddingTop: 8,
  },
  elementTitle: { fontSize: 13, fontWeight: '600', color: '#374151' },
  scoresRow: { flexDirection: 'row', alignItems: 'center', marginTop: 6, gap: 4, flexWrap: 'wrap' },
  score: { alignItems: 'center', minWidth: 52 },
  scoreLabel: { fontSize: 10, color: GRAY },
  scoreValue: { fontSize: 15, fontWeight: '700', color: '#111827' },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 14 },
  sanctionLine: { fontSize: 13, color: '#374151', marginTop: 4 },
  historyLine: { fontSize: 14, color: '#111827', marginTop: 4 },
  error: { color: RED, marginBottom: 8 },
  empty: { textAlign: 'center', color: GRAY, marginVertical: 20 },
  countdownCard: { alignItems: 'center', paddingVertical: 18 },
  countdownLabel: { fontSize: 11, color: GRAY, letterSpacing: 1, fontWeight: '600' },
  countdownValue: { fontSize: 34, fontWeight: '800', color: BLUE, marginTop: 4 },
  actionBtn: {
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
    marginBottom: 10,
  },
  actionText: { color: '#fff', fontWeight: '700' },
  msg: { textAlign: 'center', color: '#374151', marginTop: 8 },
  tabbar: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderTopColor: '#e5e7eb',
    paddingBottom: 6,
  },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 8 },
  tabLabel: { fontSize: 11, color: GRAY, marginTop: 2 },
});
