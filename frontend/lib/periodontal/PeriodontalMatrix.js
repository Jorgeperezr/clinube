"use client";

/**
 * Periodontograma (Sprint 52; revisado para dejar solo lo periodontal).
 * ────────────────────────────────────────────────────────────────────
 * La ficha periodontal como la usa un periodoncista: cada arcada con su
 * cara vestibular y su cara palatina o lingual, el diagrama de las
 * piezas con el margen gingival (rojo) y el fondo de la bolsa (azul), y
 * por cada cara:
 *
 *   Furca · Sangrado · Supuración · Placa · Margen gingival ·
 *   Profundidad de sondaje · Nivel de inserción (NIC, calculado)
 *
 * y por pieza: Presente · Implante · Movilidad · Pronóstico individual ·
 * Encía queratinizada.
 *
 * Fuera quedan los estados por superficie (caries, obturaciones…): son
 * del odontograma y se registran en sus otros modelos; aquí solo
 * estorbaban. El periodontograma no cambia nada de ellos.
 *
 * Cada exploración es una sesión con fecha: se puede crear otra para
 * comparar la evolución (hereda ausencias e implantes), elegir cuál se
 * ve, anotar observaciones, borrarla, y sacarla en PDF —con vista previa
 * y eligiendo qué lleva— o en imagen PNG.
 *
 * Las MEDICIONES las carga y guarda este componente contra
 * `periodontal-exams` / `periodontal-teeth`, con guardado diferido (450 ms
 * desde la última tecla) para que una serie de sondajes sea una petición.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, readList } from "../api";
import { useConfirm } from "../ConfirmDialog";
import { hoyISO } from "../fechas.mjs";
import { PERM_LOWER_L, PERM_LOWER_R, PERM_UPPER_L, PERM_UPPER_R } from "../odontogram/contract";
import VistaPreviaPDF from "../VistaPreviaPDF";
import {
  CELL_W, CampoPieza, FurcationMark, GradeSelect, ImplantCheck, PresenceSwitch, PronosticoSelect,
  SiteFlagRow, SiteNumberRow, SiteValueRow, ordenSitios,
} from "./cells";
import { DiagramaCara, LeyendaPeriodontal } from "./DiagramaPeriodontal";
import { descargarImagenPeriodontal } from "./ImagenPeriodontal";

const LABEL_W = 132;

/** Notación con punto (1.6), como en el FXML del proyecto. */
const dot = (code) => `${String(code)[0]}.${String(code).slice(1)}`;

/** «2026-10-19» → «19/10/2026». */
const fechaCorta = (iso) => (iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : "");

/* Arcadas con sus dos cuadrantes; la línea media los separa. */
const ARCHES = [
  { key: "sup", label: "Superior", interna: "Palatino", upper: true, right: PERM_UPPER_R, left: PERM_UPPER_L },
  { key: "inf", label: "Inferior", interna: "Lingual", upper: false, right: PERM_LOWER_R, left: PERM_LOWER_L },
];
const SEQUENCE = ARCHES.flatMap((a) => [...a.right, ...a.left]);

/* Furca: molares, y el primer premolar superior (bifurcado). */
const tieneFurca = (code, superior) => Number(String(code)[1]) >= 6 || (superior && String(code)[1] === "4");

/* Partes del PDF propio (las acepta la API en ?incluir=). */
const COMPONENTES_PDF = [
  { clave: "resumen", etiqueta: "Índices", ayuda: "Sondaje e inserción medios, sangrado, supuración y placa" },
  { clave: "diagrama", etiqueta: "Diagrama", ayuda: "Las piezas con el margen y el fondo de bolsa" },
  { clave: "piezas", etiqueta: "Datos por pieza", ayuda: "Movilidad, furcas, encía queratinizada y pronóstico" },
  { clave: "notas", etiqueta: "Observaciones" },
];

export default function Periodontograma({ selectedTooth, onSurfaceClick, patientId }) {
  const [exams, setExams] = useState([]);
  const [examId, setExamId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [activeSite, setActiveSite] = useState(null);
  const [vistaPdf, setVistaPdf] = useState(false);
  const [notas, setNotas] = useState("");
  const [confirm, ConfirmUI] = useConfirm();
  const colRefs = useRef({});
  const pending = useRef({});   // { toothId: {campo: valor} } por guardar
  const timer = useRef(null);

  const exam = exams.find((e) => e.id === examId) || exams[0] || null;

  /* ── Carga de las exploraciones ── */
  const load = useCallback(async (elegir) => {
    if (!patientId) { setLoading(false); return; }
    setError("");
    try {
      const resp = await api(`/patients/${patientId}/periodontal-exams/`);
      if (!resp.ok) throw new Error(`No se pudo cargar el periodontograma (error ${resp.status}).`);
      setExams(await readList(resp));
      if (elegir !== undefined) setExamId(elegir);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setNotas(exam?.notes || ""); }, [exam?.id, exam?.notes]);

  async function nuevaExploracion() {
    setError("");
    try {
      const resp = await api(`/patients/${patientId}/periodontal-exams/`, {
        method: "POST", body: JSON.stringify({ date: hoyISO() }),
      });
      if (!resp.ok) throw new Error(`No se pudo crear la exploración (error ${resp.status}).`);
      const nueva = await resp.json();
      await load(nueva.id);
    } catch (err) { setError(err.message); }
  }

  async function borrarExploracion() {
    if (!exam) return;
    const ok = await confirm({
      title: "Borrar exploración",
      message: `Se borrará la exploración del ${fechaCorta(exam.date)} con todas sus mediciones. No se puede deshacer.`,
      confirmLabel: "Borrar", danger: true,
    });
    if (!ok) return;
    const resp = await api(`/periodontal-exams/${exam.id}/`, { method: "DELETE" });
    if (!resp.ok) { setError("No se pudo borrar la exploración."); return; }
    await load(null);
  }

  async function guardarExploracion(cambios) {
    if (!exam) return;
    const resp = await api(`/periodontal-exams/${exam.id}/`, { method: "PATCH", body: JSON.stringify(cambios) });
    if (!resp.ok) { setError("No se pudieron guardar las observaciones."); return; }
    const datos = await resp.json();
    setExams((prev) => prev.map((e) => (e.id === datos.id ? datos : e)));
  }

  /* ── Guardado diferido ──
     Se acumulan los cambios por pieza y se envían 450 ms después de la
     última edición: escribir seis sondajes produce una petición, no seis. */
  const flush = useCallback(async () => {
    const lote = pending.current;
    pending.current = {};
    const ids = Object.keys(lote);
    if (ids.length === 0) return;
    setSaving(true);
    try {
      await Promise.all(ids.map((id) =>
        api(`/periodontal-teeth/${id}/`, { method: "PATCH", body: JSON.stringify(lote[id]) })));
      await load();      // trae los índices recalculados
    } catch {
      setError("No se pudieron guardar algunos cambios.");
    } finally {
      setSaving(false);
    }
  }, [load]);

  const queue = useCallback((toothId, cambios) => {
    pending.current[toothId] = { ...(pending.current[toothId] || {}), ...cambios };
    // Actualización optimista: la ficha responde al instante
    setExams((prev) => prev.map((e) => ({
      ...e, teeth: e.teeth.map((t) => (t.id === toothId ? { ...t, ...cambios } : t)),
    })));
    clearTimeout(timer.current);
    timer.current = setTimeout(flush, 450);
  }, [flush]);

  useEffect(() => () => clearTimeout(timer.current), []);

  /* ── Piezas por código FDI, con el NIC recalculado al momento ── */
  const byCode = useMemo(() => {
    const map = {};
    (exam?.teeth || []).forEach((t) => {
      const gm = t.gingival_margin || [];
      map[t.tooth_code] = {
        ...t, attachment_level: (t.probing_depth || []).map((p, i) => (p || 0) + (gm[i] || 0)),
      };
    });
    return map;
  }, [exam]);

  /* ── Teclado: ← → recorren las piezas ── */
  useEffect(() => {
    function onKey(e) {
      const t = e.target;
      if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      const i = SEQUENCE.indexOf(selectedTooth);
      const acciones = {
        ArrowRight: () => onSurfaceClick(SEQUENCE[Math.min(SEQUENCE.length - 1, (i < 0 ? -1 : i) + 1)], "whole"),
        ArrowLeft: () => onSurfaceClick(SEQUENCE[Math.max(0, (i < 0 ? 1 : i) - 1)], "whole"),
      };
      const fn = acciones[e.key];
      if (fn) { e.preventDefault(); fn(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedTooth, onSurfaceClick]);

  useEffect(() => {
    const el = selectedTooth && colRefs.current[selectedTooth];
    el?.scrollIntoView?.({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [selectedTooth, zoom]);

  /* ── Constructores de fila ── */
  const rowLabel = (texto, calculada) => (
    <div style={{ width: LABEL_W, flexShrink: 0, position: "sticky", left: 0, zIndex: 3,
                  background: "var(--card)", display: "flex", alignItems: "center", gap: 6,
                  fontSize: 11, color: calculada ? "var(--ink-faint)" : "var(--ink-soft)", padding: "1px 8px",
                  borderRight: "1px solid var(--line)", fontStyle: calculada ? "italic" : "normal" }}>
      {texto}
    </div>
  );

  const midline = (
    <div aria-hidden="true" style={{ width: 9, alignSelf: "stretch", flexShrink: 0,
                                     borderLeft: "1px dashed var(--line-strong)" }} />
  );

  const cells = (codes, render) => codes.map((code) => (
    <div key={code} style={{ width: CELL_W + 8, flexShrink: 0, padding: "1px 0",
                             background: selectedTooth === code ? "var(--petrol-soft)" : "transparent" }}>
      {render(code, byCode[code])}
    </div>
  ));

  /* ── Filas ──
     Por pieza y por cara. Las de sitio muestran los tres valores en el
     orden anatómico de la pantalla (mesial hacia la línea media), igual
     que el diagrama. */
  function filas(arch) {
    const flag = (t, campo, idx) => {
      const arr = [...(t[campo] || [false, false, false, false, false, false])];
      arr[idx] = !arr[idx];
      queue(t.id, { [campo]: arr });
    };
    const num = (t, campo, idx, valor) => {
      const arr = [...(t[campo] || [0, 0, 0, 0, 0, 0])];
      arr[idx] = Math.max(-10, Math.min(20, Number(valor) || 0));
      queue(t.id, { [campo]: arr });
    };
    const foco = (code) => (i) => { setActiveSite(i); onSurfaceClick(code, "whole"); };

    const cara = (base, nombre, furca) => ({
      furca: { key: `fu-${base}`, label: `Furca ${nombre}`, render: (code, t) => t && t.is_present
        && !t.has_implant && tieneFurca(code, arch.upper) && (
        <FurcationMark grade={t[furca]} label={`Furca ${nombre} de ${code}`}
                       onCycle={() => queue(t.id, { [furca]: (t[furca] + 1) % 4 })} />) },
      sangrado: { key: `bop-${base}`, label: "Sangrado", render: (code, t) => t && (
        <SiteFlagRow values={t.bleeding} base={base} color="var(--red)" disabled={!t.is_present}
                     orden={ordenSitios(code)} label={`Sangrado ${nombre} de ${code}`}
                     onToggle={(i) => flag(t, "bleeding", i)} />) },
      supuracion: { key: `sup-${base}`, label: "Supuración", render: (code, t) => t && (
        <SiteFlagRow values={t.suppuration} base={base} color="var(--amber)" disabled={!t.is_present}
                     orden={ordenSitios(code)} label={`Supuración ${nombre} de ${code}`}
                     onToggle={(i) => flag(t, "suppuration", i)} />) },
      placa: { key: `pl-${base}`, label: "Placa", render: (code, t) => t && (
        <SiteFlagRow values={t.plaque} base={base} color="#7c4dcc" disabled={!t.is_present}
                     orden={ordenSitios(code)} label={`Placa ${nombre} de ${code}`}
                     onToggle={(i) => flag(t, "plaque", i)} />) },
      margen: { key: `gm-${base}`, label: "Margen gingival", render: (code, t) => t && (
        <SiteNumberRow values={t.gingival_margin} base={base} disabled={!t.is_present}
                       orden={ordenSitios(code)} alerta={3} negativos
                       label={`Margen gingival ${nombre} de ${code}`}
                       activeSite={selectedTooth === code ? activeSite : null}
                       onFocusSite={foco(code)}
                       onChange={(i, v) => num(t, "gingival_margin", i, v)} />) },
      sondaje: { key: `pd-${base}`, label: "Prof. de sondaje", render: (code, t) => t && (
        <SiteNumberRow values={t.probing_depth} base={base} disabled={!t.is_present}
                       orden={ordenSitios(code)}
                       label={`Sondaje ${nombre} de ${code}`}
                       activeSite={selectedTooth === code ? activeSite : null}
                       onFocusSite={foco(code)}
                       onChange={(i, v) => num(t, "probing_depth", i, v)} />) },
      nic: { key: `nic-${base}`, label: "Nivel de inserción", calculada: true, render: (code, t) => t && t.is_present && (
        <SiteValueRow values={t.attachment_level} base={base} orden={ordenSitios(code)} />) },
    });

    return {
      pieza: [
        { key: "present", label: "Presente", render: (code, t) => t && (
          <PresenceSwitch on={t.is_present} label={`Pieza ${code} presente`}
                          onToggle={() => queue(t.id, { is_present: !t.is_present })} />) },
        { key: "implant", label: "Implante", render: (code, t) => t && (
          <ImplantCheck on={t.has_implant} disabled={!t.is_present} label={`Implante en ${code}`}
                        onToggle={() => queue(t.id, { has_implant: !t.has_implant })} />) },
        { key: "mobility", label: "Movilidad", render: (code, t) => t && (
          <GradeSelect value={t.mobility} disabled={!t.is_present} label={`Movilidad de ${code}`}
                       onChange={(v) => queue(t.id, { mobility: v })} />) },
        { key: "prognosis", label: "Pronóstico", render: (code, t) => t && (
          <PronosticoSelect value={t.prognosis} disabled={!t.is_present} label={`Pronóstico de ${code}`}
                            onChange={(v) => queue(t.id, { prognosis: v })} />) },
      ],
      encia: { key: "gw", label: "Encía queratinizada", render: (code, t) => t && t.is_present && (
        <CampoPieza value={t.gum_width} label={`Encía queratinizada de ${code} (mm)`}
                    onChange={(v) => queue(t.id, { gum_width: v })} />) },
      vestibular: cara(0, "vestibular", "furcation_buccal"),
      interna: cara(3, arch.interna.toLowerCase(), "furcation_lingual"),
    };
  }

  const stats = exam?.statistics;

  function imagen() {
    const autor = exam.created_by_name && exam.created_by_name !== "—" ? ` · ${exam.created_by_name}` : "";
    descargarImagenPeriodontal({
      byCode,
      titulo: "Periodontograma",
      subtitulo: `${exam.patient_name ? `${exam.patient_name} · ` : ""}Exploración del ${fechaCorta(exam.date)}${autor}`,
      estadisticas: stats ? `Sondaje medio ${stats.mean_probing_depth} mm · NIC medio ${stats.mean_attachment_level} mm`
        + ` · Sangrado ${stats.bleeding_percent} % · Supuración ${stats.suppuration_percent ?? 0} %`
        + ` · Placa ${stats.plaque_percent} % · Sitios de más de 4 mm: ${stats.deep_sites ?? 0}` : "",
      nombre: `periodontograma_${exam.date}.png`,
    }).catch((e) => setError(e.message));
  }

  return (
    <div>
      {ConfirmUI}
      {vistaPdf && exam && (
        <VistaPreviaPDF titulo="Periodontograma" ruta={`/periodontal-exams/${exam.id}/pdf/`}
                        nombre={`periodontograma_${exam.date}.pdf`} clave="periodontograma"
                        componentes={COMPONENTES_PDF} onCerrar={() => setVistaPdf(false)} />
      )}

      {/* ── Barra de control ── */}
      <div className="perio-barra">
        {exams.length > 0 && (
          <label className="perio-exploracion">
            <span>Exploración</span>
            <select value={exam?.id || ""} onChange={(e) => setExamId(e.target.value)}>
              {exams.map((e, i) => (
                <option key={e.id} value={e.id}>{fechaCorta(e.date)}{i === 0 ? " · la más reciente" : ""}</option>
              ))}
            </select>
          </label>
        )}
        <button type="button" className="btn btn-ghost" onClick={nuevaExploracion}
                title="Una sesión nueva con la fecha de hoy; trae las ausencias y los implantes de la anterior">
          + Nueva exploración
        </button>
        {exam && (
          <>
            <button type="button" className="btn btn-ghost" onClick={() => setVistaPdf(true)}
                    title="Vista previa del PDF, eligiendo qué lleva">PDF</button>
            <button type="button" className="btn btn-ghost" onClick={imagen}
                    title="Descargar el periodontograma como imagen PNG">Imagen</button>
            <button type="button" className="btn btn-ghost perio-borrar" onClick={borrarExploracion}>Borrar</button>
          </>
        )}
        <div className="perio-derecha">
          <div style={{ display: "flex", gap: 3 }} aria-label="Ir al cuadrante">
            {[["1", PERM_UPPER_R], ["2", PERM_UPPER_L], ["3", PERM_LOWER_L], ["4", PERM_LOWER_R]].map(([n, codes]) => (
              <button key={n} type="button" className="btn btn-ghost" title={`Cuadrante ${n}`}
                      onClick={() => onSurfaceClick(codes[0], "whole")}
                      style={{ fontSize: 12, padding: "3px 10px" }}>{n}</button>
            ))}
          </div>
          {saving && <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>Guardando…</span>}
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--ink-soft)" }}>
            Zoom
            <input type="range" min="1" max="2.2" step="0.1" value={zoom}
                   onChange={(e) => setZoom(Number(e.target.value))}
                   aria-label="Nivel de zoom" style={{ width: 84 }} />
            <span className="tabular" style={{ minWidth: 30 }}>{zoom.toFixed(1)}×</span>
          </label>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      {loading && <div className="empty">Cargando periodontograma…</div>}

      {!loading && !exam && (
        <div className="card" style={{ marginBottom: 14, textAlign: "center" }}>
          <p style={{ fontSize: 13.5, color: "var(--ink-soft)", marginBottom: 10 }}>
            Este paciente no tiene periodontograma. Crea la primera exploración para registrar sondaje,
            margen gingival, sangrado, supuración, placa, movilidad, furcas y pronóstico.
          </p>
          <button className="btn btn-primary" onClick={nuevaExploracion}>Crear periodontograma</button>
        </div>
      )}

      {exam && (
        <div style={{ border: "1px solid var(--line)", borderRadius: "var(--radius)",
                      background: "var(--card)", overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <div style={{ transform: `scale(${zoom})`, transformOrigin: "top left",
                          transition: "transform var(--dur) var(--ease)", width: `${100 * zoom}%` }}>
              {ARCHES.map((arch) => {
                const g = filas(arch);

                const numeros = (
                  <div key="num" style={{ display: "flex", alignItems: "center", background: "var(--petrol-soft)",
                                          borderTop: "1px solid var(--line)" }}>
                    {rowLabel(arch.label)}
                    {[arch.right, arch.left].map((codes, ci) => (
                      <div key={ci} style={{ display: "flex" }}>
                        {ci === 1 && midline}
                        {codes.map((code) => (
                          <div key={code} ref={(el) => { colRefs.current[code] = el; }}
                               style={{ width: CELL_W + 8, flexShrink: 0, textAlign: "center" }}>
                            <button type="button" onClick={() => onSurfaceClick(code, "whole")}
                                    className="tabular" aria-label={`Pieza ${code}`} title={`Pieza ${dot(code)}`}
                                    style={{ width: "100%", border: "none", cursor: "pointer", borderRadius: 3,
                                             padding: "3px 0", fontSize: 12.5, fontWeight: 700, lineHeight: 1.1,
                                             background: selectedTooth === code ? "var(--petrol)" : "transparent",
                                             color: selectedTooth === code ? "var(--on-brand)" : "var(--ink)" }}>
                              {code}
                            </button>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                );

                const fila = (r) => (
                  <div key={r.key} style={{ display: "flex", alignItems: "center",
                                            borderTop: "1px solid var(--line)", minHeight: 22 }}>
                    {rowLabel(r.label, r.calculada)}
                    {cells(arch.right, r.render)}
                    {midline}
                    {cells(arch.left, r.render)}
                  </div>
                );

                const diagrama = (cara, nombre) => (
                  <div key={`dg-${cara}`} style={{ display: "flex", alignItems: "stretch", borderTop: "1px solid var(--line)" }}>
                    <div style={{ width: LABEL_W, flexShrink: 0, position: "sticky", left: 0, zIndex: 3,
                                  background: "var(--card)", display: "flex", alignItems: "center",
                                  padding: "0 8px", borderRight: "1px solid var(--line)",
                                  fontSize: 11.5, fontWeight: 700, letterSpacing: ".04em",
                                  textTransform: "uppercase", color: "var(--petrol)" }}>
                      {nombre}
                    </div>
                    {[arch.right, arch.left].map((codes, ci) => (
                      <div key={ci} style={{ display: "flex" }}>
                        {ci === 1 && midline}
                        <DiagramaCara codes={codes} cara={cara} byCode={byCode}
                                      selectedTooth={selectedTooth} onSurfaceClick={onSurfaceClick}
                                      etiqueta={`Diagrama ${nombre.toLowerCase()} ${arch.label.toLowerCase()}`} />
                      </div>
                    ))}
                  </div>
                );

                /* Cada cara, de fuera hacia el diagrama: furca, sangrado,
                   supuración, placa, margen, sondaje y NIC, así los
                   números quedan pegados a las líneas que dibujan. */
                const hacia = (c) => [c.furca, c.sangrado, c.supuracion, c.placa, c.margen, c.sondaje, c.nic].map(fila);
                const desde = (c) => [c.nic, c.sondaje, c.margen, c.placa, c.supuracion, c.sangrado, c.furca].map(fila);
                const pieza = g.pieza.map(fila);
                const bloque = arch.upper
                  ? [...pieza, fila(g.encia), ...hacia(g.vestibular), diagrama("v", "Vestibular"), numeros,
                     diagrama("l", arch.interna), ...desde(g.interna)]
                  : [...hacia(g.interna), diagrama("l", arch.interna), numeros, diagrama("v", "Vestibular"),
                     ...desde(g.vestibular), fila(g.encia), ...[...pieza].reverse()];

                return (
                  <div key={arch.key} style={{ borderBottom: "3px solid var(--line-strong)" }}>{bloque}</div>
                );
              })}
            </div>
          </div>

          <div style={{ padding: "8px 12px", borderTop: "1px solid var(--line)" }}>
            <LeyendaPeriodontal />
          </div>

          {stats && (
            <div className="perio-indices">
              {[["Sondaje medio", `${stats.mean_probing_depth} mm`],
                ["Nivel de inserción medio", `${stats.mean_attachment_level} mm`],
                ["Sangrado al sondaje", `${stats.bleeding_percent} %`],
                ["Supuración", `${stats.suppuration_percent ?? 0} %`],
                ["Placa", `${stats.plaque_percent} %`],
                ["Sitios de más de 4 mm", stats.deep_sites ?? 0],
                ["Piezas presentes", stats.teeth ?? "—"]].map(([k, v]) => (
                <span key={k}><span>{k}:</span> <strong className="tabular">{v}</strong></span>
              ))}
            </div>
          )}

          <div style={{ padding: "10px 12px", borderTop: "1px solid var(--line)" }}>
            <label htmlFor="perio-notas" style={{ display: "block", fontSize: 12, fontWeight: 600,
                                                   color: "var(--ink-soft)", marginBottom: 4 }}>
              Observaciones de la exploración
            </label>
            <textarea id="perio-notas" rows={2} value={notas} onChange={(e) => setNotas(e.target.value)}
                      onBlur={() => notas !== (exam.notes || "") && guardarExploracion({ notes: notas })}
                      placeholder="Diagnóstico periodontal, plan, próximo control…"
                      style={{ width: "100%", fontSize: 13 }} />
          </div>

          <p style={{ fontSize: 11.5, color: "var(--ink-faint)", padding: "0 12px 10px", margin: 0 }}>
            Pronóstico: B bueno · R reservado · M malo · I imposible · Flechas ← → recorren las piezas ·
            el nivel de inserción se calcula solo (sondaje + margen) · en rojo, sondajes de más de 4 mm y
            márgenes de más de 3 mm
          </p>
        </div>
      )}
    </div>
  );
}
