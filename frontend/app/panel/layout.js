"use client";

/**
 * Armazón del panel, al estilo de Música de macOS:
 *
 *   · barra lateral FLOTANTE y translúcida, con la búsqueda arriba, las
 *     secciones agrupadas bajo un título gris y el elemento activo en una
 *     píldora del color de acento;
 *   · el perfil abajo, con su menú: apariencia, color de acento, editar
 *     la barra lateral y cerrar sesión;
 *   · una barra flotante con la próxima cita (lib/ProximaCita.js), que
 *     hace de «reproductor».
 *
 * Lo personal (acento y secciones ocultas) se guarda en la cuenta
 * (/auth/me/preferencias/), así que se ve igual en el ordenador y en la
 * app del teléfono. Ocultar una sección no quita permisos: es orden.
 */

import { useEffect, useRef, useState } from "react";
import { api, currentUser, logout, RUTA_CONDICIONES, tieneFuncion } from "../../lib/api";
import { ACENTOS, recordarAcento } from "../../lib/acentos";
import { IconoClinube, LogoClinube, MARCA } from "../../lib/marca";
import {
  applyBrandingChrome, applyTheme, initColorMode, logoSrc, onBrandingUpdated, readBrandingCache,
  recordarTemaPersonal, saveBrandingCache,
} from "../../lib/theme";
import NavIcon from "../../lib/NavIcons";
import ProximaCita from "../../lib/ProximaCita";
import ThemeSwitch from "../../lib/ThemeSwitch";

// Navegación por rol (matriz de permisos del SRS), agrupada en secciones.
// `clave` es lo que se guarda al ocultarla; las que no la llevan no se
// pueden ocultar (Inicio y Mis preferencias: sin ellas no habría forma
// de volver a mostrar nada).
const NAV = [
  { href: "/panel/plataforma/", label: "Plataforma", iconName: "plataforma", roles: ["superadmin"] },
  { href: "/panel/", label: "Inicio", iconName: "inicio", roles: ["admin", "reception", "doctor", "auxiliary"] },
  { seccion: "Clínica", clave: "pacientes", href: "/panel/pacientes/", label: "Pacientes", iconName: "pacientes", roles: ["admin", "reception", "doctor", "auxiliary"] },
  { seccion: "Clínica", clave: "agenda", href: "/panel/agenda/", label: "Agenda", iconName: "agenda", roles: ["admin", "reception", "doctor"] },
  // Lo que piden los pacientes desde la app; con contador de pendientes.
  { seccion: "Clínica", clave: "bandeja", href: "/panel/bandeja/", label: "Bandeja de la app", iconName: "bandeja", roles: ["admin", "reception", "doctor", "auxiliary"], funcionalidad: "app_paciente", contador: "bandeja" },
  // Los módulos de gestión siguen la FUNCIÓN de cada profesional (ver
  // lib/api.js → tieneFuncion), no solo su rol.
  { seccion: "Gestión", clave: "pagos", href: "/panel/pagos/", label: "Pagos", iconName: "pagos", roles: ["admin", "reception", "doctor", "auxiliary"], funcion: "cobros" },
  { seccion: "Gestión", clave: "inventario", href: "/panel/inventario/", label: "Inventario", iconName: "inventario", roles: ["admin", "reception", "doctor", "auxiliary"], funcionalidad: "inventario", funcion: "inventario" },
  { seccion: "Gestión", clave: "reportes", href: "/panel/reportes/", label: "Reportes", iconName: "reportes", roles: ["admin", "reception", "doctor", "auxiliary"], funcionalidad: "reportes", funcion: "reportes" },
  // Sueldos y honorarios de todo el equipo: solo con la función «finanzas».
  { seccion: "Gestión", clave: "finanzas", href: "/panel/finanzas/", label: "Finanzas", iconName: "finanzas", roles: ["admin", "reception", "doctor", "auxiliary"], funcionalidad: "finanzas", funcion: "finanzas" },
  { seccion: "Gestión", clave: "configuracion", href: "/panel/configuracion/", label: "Configuración", iconName: "configuracion", roles: ["admin"] },
  { seccion: "Mi espacio", clave: "firma", href: "/panel/firma/", label: "Mi firma", iconName: "firma", roles: ["doctor"] },
  // La copia de los pacientes de cada profesional. La administración
  // tiene la de toda la clínica en Configuración → Copia de seguridad.
  { seccion: "Mi espacio", clave: "respaldo", href: "/panel/respaldo/", label: "Mi respaldo", iconName: "respaldo", roles: ["doctor", "auxiliary"], funcion: "respaldo" },
  // De cada persona para sí misma: por eso la ven todos los roles de clínica.
  { seccion: "Mi espacio", href: "/panel/preferencias/", label: "Mis preferencias", iconName: "preferencias", roles: ["admin", "reception", "doctor", "auxiliary"] },
];

const ROLE_LABELS = {
  superadmin: "Super Administrador", admin: "Administrador",
  reception: "Recepción", doctor: "Doctor/a", auxiliary: "Auxiliar",
};

/** Guarda preferencias propias y las deja en el perfil en caché. */
async function guardarPreferencias(cambios) {
  const resp = await api("/auth/me/preferencias/", { method: "PATCH", body: JSON.stringify(cambios) });
  if (!resp.ok) throw new Error("No se pudo guardar.");
  const { preferencias } = await resp.json();
  const u = currentUser();
  if (u) localStorage.setItem("user", JSON.stringify({ ...u, preferencias }));
  window.dispatchEvent(new Event("perfil-actualizado"));
  return preferencias;
}

export default function PanelLayout({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [branding, setBranding] = useState(null);
  const [isMobile, setIsMobile] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editando, setEditando] = useState(false);
  const [ocultas, setOcultas] = useState([]);

  useEffect(() => {
    const u = currentUser();
    if (!u) { window.location.href = "/login/"; return; }
    if (u.condiciones_pendientes) { window.location.href = RUTA_CONDICIONES; return; }
    setUser(u);
    setReady(true);
    // Recordar la preferencia de menú colapsado
    try {
      if (localStorage.getItem("sidebarCollapsed") === "1") setCollapsed(true);
    } catch { /* SSR / sin storage */ }
    // El perfil guardado puede ser de antes: condiciones nuevas que
    // aceptar, o un acento o una barra cambiados desde otro dispositivo.
    api("/auth/me/")
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => {
        if (!me) return;
        localStorage.setItem("user", JSON.stringify(me));
        if (me.condiciones_pendientes) { window.location.href = RUTA_CONDICIONES; return; }
        setUser(me);
        recordarAcento(me.preferencias?.acento || "");
        // El tema propio solo vale si la clínica tiene la función (en
        // prueba, solo la clínica de pruebas): si no, el de la clínica.
        recordarTemaPersonal(me.funcionalidades?.temas_personales ? (me.preferencias?.tema || "") : "");
        applyTheme(null);
      })
      .catch(() => {});
    // Módulos o preferencias cambiados en esta sesión: el menú se
    // actualiza sin tener que volver a entrar.
    const alCambiarPerfil = () => setUser(currentUser());
    window.addEventListener("perfil-actualizado", alCambiarPerfil);
    // Apariencia (claro/oscuro/sistema) antes de pintar la marca, para
    // que los tonos se deriven ya con el modo correcto.
    const stopColorMode = initColorMode();

    // Identidad visual por clínica: pintado instantáneo desde caché,
    // refresco desde la API y actualización en vivo al guardar cambios.
    const cached = readBrandingCache();
    if (cached) {
      setBranding(cached);
      applyTheme(cached.theme);
      applyBrandingChrome(cached);
    }
    (async () => {
      // El Super Administrador no tiene clínica y por tanto no tiene
      // marca: pedirla solo devolvía un 403 en cada pantalla.
      if (u.role === "superadmin") return;
      try {
        const resp = await api("/config/branding/");
        if (resp.ok) {
          const b = await resp.json();
          setBranding(b);
          applyTheme(b.theme);
          applyBrandingChrome(b);
          saveBrandingCache(b);
        }
      } catch { /* sin identidad: tema del sistema */ }
    })();
    const unsubscribe = onBrandingUpdated((b) => {
      setBranding(b);
      applyTheme(b.theme);
      applyBrandingChrome(b);
    });
    return () => {
      unsubscribe(); stopColorMode();
      window.removeEventListener("perfil-actualizado", alCambiarPerfil);
    };
  }, []);

  useEffect(() => { setOcultas(user?.preferencias?.barra_oculta || []); }, [user]);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("sidebarCollapsed", next ? "1" : "0"); } catch {}
      return next;
    });
  }

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(max-width: 860px)");
    const apply = () => { setIsMobile(mq.matches); if (!mq.matches) setDrawerOpen(false); };
    apply();
    mq.addEventListener?.("change", apply);
    return () => mq.removeEventListener?.("change", apply);
  }, []);

  // Con el panel abierto se bloquea el desplazamiento del fondo
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.body.style.overflow = (isMobile && drawerOpen) ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [isMobile, drawerOpen]);

  /* Pendientes de la bandeja de la app, para el número del menú. Se
     pide al entrar, cada 2 minutos y cuando la propia bandeja avisa de
     que atendió algo. Si la clínica no tiene la app, la API responde 403
     y el número simplemente no aparece. */
  const [pendientesBandeja, setPendientesBandeja] = useState(0);
  useEffect(() => {
    if (!ready || !user || user.role === "superadmin" || (user.funcionalidades || {}).app_paciente === false) return;
    let vivo = true;
    const pedir = () => api("/bandeja-app/resumen/")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (vivo && d) setPendientesBandeja(d.solicitudes_pendientes + d.mensajes_sin_responder); })
      .catch(() => {});
    pedir();
    const cada = setInterval(pedir, 120000);
    window.addEventListener("bandeja-actualizada", pedir);
    return () => { vivo = false; clearInterval(cada); window.removeEventListener("bandeja-actualizada", pedir); };
  }, [ready, user]);

  if (!ready) return null;

  // Rol Y funcionalidad. Esconder el módulo es cortesía; lo que de
  // verdad lo cierra es `RequiereFuncionalidad` en la API, porque quien
  // conozca la URL entraría igual.
  //
  // `!== false` y no `=== true`: si el perfil viene de una sesión
  // anterior y todavía no trae `funcionalidades`, se enseña todo en vez
  // de dejar al usuario sin menú hasta que vuelva a entrar.
  const contratadas = user.funcionalidades || {};
  const permitidos = NAV.filter(
    (n) => n.roles.includes(user.role)
      && (!n.funcionalidad || contratadas[n.funcionalidad] !== false)
      && (!n.funcion || tieneFuncion(user, n.funcion)),
  );
  const path = typeof window !== "undefined" ? window.location.pathname : "";
  // Oculto por la persona, salvo que sea donde está ahora: no se le
  // esconde la página en la que está.
  const visibles = editando ? permitidos
    : permitidos.filter((n) => !n.clave || !ocultas.includes(n.clave) || path === n.href);
  const plegada = collapsed && !isMobile;
  const W = isMobile ? 272 : (plegada ? 76 : 248);
  const nombreClinica = branding?.short_name || branding?.display_name || branding?.nombre_clinica || "";

  async function terminarEdicion() {
    setEditando(false);
    try { await guardarPreferencias({ barra_oculta: ocultas }); } catch { /* se queda solo en esta pantalla */ }
  }

  // Agrupa respetando el orden de NAV.
  const grupos = [];
  for (const item of visibles) {
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && ultimo.seccion === (item.seccion || null)) ultimo.items.push(item);
    else grupos.push({ seccion: item.seccion || null, items: [item] });
  }

  const hayLogoPropio = Boolean(branding?.logo_url || branding?.icono_url);
  // En la clínica de pruebas se ven funciones que las demás aún no tienen.
  const etiquetaPrueba = user.clinica_de_pruebas && !plegada && (
    <span className="etiqueta-prueba lat-prueba"
          title="Clínica de pruebas: aquí se ven antes las funciones nuevas">Pruebas</span>
  );
  const marcaClinica = hayLogoPropio ? (
    <div className="lat-marca" style={{ justifyContent: plegada ? "center" : "flex-start" }}>
      <LogoDeLaClinica branding={branding} compacto={plegada}
                       alto={plegada ? 30 : 36} ancho={plegada ? 44 : 64} />
      {!plegada && <span className="lat-nombre">{nombreClinica || MARCA}{etiquetaPrueba}</span>}
    </div>
  ) : (
    // Sin logotipo propio la clínica lleva el de Clinube, y su nombre
    // debajo: quien trabaja ahí sigue viendo en qué clínica está.
    <div className="lat-marca" style={{ flexDirection: "column", alignItems: plegada ? "center" : "flex-start", gap: 4 }}>
      {plegada ? <IconoClinube alto={24} titulo={MARCA} /> : <LogoClinube alto={22} />}
      {!plegada && (nombreClinica || etiquetaPrueba) && (
        <span className="lat-nombre lat-nombre--suave">{nombreClinica}{etiquetaPrueba}</span>
      )}
    </div>
  );

  return (
    <div className="panel-armazon" style={{ flexDirection: isMobile ? "column" : "row" }}>
      {/* Barra superior: solo en pantallas estrechas */}
      {isMobile && (
        <header className="panel-superior">
          <button onClick={() => setDrawerOpen(true)} className="lat-boton-icono"
                  aria-label="Abrir menú" title="Menú">
            <MenuIcon />
          </button>
          {hayLogoPropio ? (
            <LogoDeLaClinica branding={branding} compacto alto={26} ancho={40} />
          ) : (
            <IconoClinube alto={22} />
          )}
          <span className="panel-superior-nombre">{nombreClinica || MARCA}</span>
        </header>
      )}

      {/* Fondo oscurecido al abrir el panel */}
      {isMobile && drawerOpen && (
        <div className="animate-fade lat-velo" onClick={() => setDrawerOpen(false)} aria-hidden="true" />
      )}

      <aside className={`lateral${isMobile ? " lateral--movil" : ""}${isMobile && drawerOpen ? " lateral--abierta" : ""}`}
             style={{ width: W, flexBasis: W }}>
        <div className="lat-cabecera">
          {marcaClinica}
          {isMobile ? (
            <button onClick={() => setDrawerOpen(false)} className="lat-boton-icono"
                    aria-label="Cerrar menú" title="Cerrar menú">
              <CloseIcon />
            </button>
          ) : !plegada && (
            <button onClick={toggleCollapsed} className="lat-boton-icono" aria-label="Contraer menú" title="Contraer menú">
              <PanelIcon open />
            </button>
          )}
        </div>
        {plegada && (
          <button onClick={toggleCollapsed} className="lat-boton-icono" style={{ alignSelf: "center", marginBottom: 8 }}
                  aria-label="Expandir menú" title="Expandir menú">
            <PanelIcon open={false} />
          </button>
        )}

        {permitidos.some((n) => n.clave === "pacientes") && <Buscador plegada={plegada} />}

        <nav className="lat-nav" aria-label="Secciones del panel">
          {grupos.map((g, i) => (
            <div key={g.seccion || `g${i}`} className="lat-grupo">
              {g.seccion && !plegada && <div className="lat-titulo">{g.seccion}</div>}
              {g.seccion && plegada && i > 0 && <div className="lat-separador" />}
              {g.items.map((item) => {
                const active = path === item.href;
                const oculta = item.clave && ocultas.includes(item.clave);
                return (
                  <div key={item.href} className="lat-fila">
                    <a href={item.href} title={plegada ? item.label : undefined}
                       className={`lat-item${oculta && editando ? " lat-item--oculta" : ""}`}
                       aria-current={active ? "page" : undefined}
                       onClick={() => isMobile && setDrawerOpen(false)}
                       style={{ justifyContent: plegada ? "center" : "flex-start" }}>
                      <span className="lat-icono" aria-hidden="true"><NavIcon name={item.iconName} /></span>
                      {!plegada && <span className="lat-etiqueta">{item.label}</span>}
                      {item.contador === "bandeja" && pendientesBandeja > 0 && !editando && (
                        <span className="lat-contador" aria-label={`${pendientesBandeja} pendientes`}>
                          {pendientesBandeja > 99 ? "99+" : pendientesBandeja}
                        </span>
                      )}
                    </a>
                    {editando && item.clave && (
                      <input type="checkbox" className="lat-casilla" checked={!oculta}
                             aria-label={`Mostrar ${item.label}`}
                             onChange={(e) => setOcultas((o) => e.target.checked
                               ? o.filter((c) => c !== item.clave) : [...o, item.clave])} />
                    )}
                  </div>
                );
              })}
            </div>
          ))}
          {editando && (
            <div className="lat-edicion">
              <p>Marca lo que quieres ver en tu barra lateral. Ocultar una sección no quita permisos.</p>
              <button type="button" className="btn btn-primary" onClick={terminarEdicion}>Listo</button>
            </div>
          )}
        </nav>

        <Perfil user={user} plegada={plegada} hayLogoPropio={hayLogoPropio}
                puedeEditar={user.role !== "superadmin"}
                alEditar={() => { setEditando(true); if (plegada) toggleCollapsed(); }} />
      </aside>

      <main className="panel-principal">
        <div className="panel-contenido">{children}</div>
        {["admin", "reception", "doctor"].includes(user.role) && <ProximaCita />}
      </main>
    </div>
  );
}

/**
 * El logotipo de la clínica que toca en cada sitio: el ícono donde no
 * cabe el logotipo (barra plegada, cabecera del teléfono) y, en modo
 * oscuro, el de fondo oscuro si lo tiene. El cambio de modo lo resuelve
 * el CSS (.logo-para-oscuro): se pintan los dos y se ve uno.
 */
function LogoDeLaClinica({ branding, compacto = false, alto, ancho }) {
  const version = branding.updated_at;
  const conIcono = Boolean(branding.icono_url) && (compacto || !branding.logo_url);
  const principal = conIcono ? branding.icono_url : branding.logo_url;
  const oscuro = conIcono ? null : branding.logo_oscuro_url;
  const estilo = { height: alto, maxWidth: ancho, objectFit: "contain" };
  return (
    <>
      <img src={logoSrc(principal, version)} alt="Logotipo de la clínica" style={estilo}
           className={oscuro ? "logo-para-claro--con-oscuro" : undefined} />
      {oscuro && (
        <img src={logoSrc(oscuro, version)} alt="" aria-hidden="true" style={estilo}
             className="logo-para-oscuro" />
      )}
    </>
  );
}

/** Buscar pacientes desde cualquier pantalla, como «Buscar» en Música. */
function Buscador({ plegada }) {
  const [texto, setTexto] = useState("");
  if (plegada) {
    return (
      <a href="/panel/pacientes/" className="lat-item" title="Buscar pacientes" style={{ justifyContent: "center" }}>
        <span className="lat-icono" aria-hidden="true"><LupaIcon /></span>
      </a>
    );
  }
  return (
    <form className="lat-buscar" role="search"
          onSubmit={(e) => {
            e.preventDefault();
            window.location.href = `/panel/pacientes/?buscar=${encodeURIComponent(texto.trim())}`;
          }}>
      <LupaIcon />
      <input type="search" placeholder="Buscar pacientes" aria-label="Buscar pacientes"
             value={texto} onChange={(e) => setTexto(e.target.value)} />
    </form>
  );
}

/** El perfil al pie y su menú: apariencia, acento, barra lateral, salir. */
function Perfil({ user, plegada, hayLogoPropio, puedeEditar, alEditar }) {
  const [abierto, setAbierto] = useState(false);
  const [acento, setAcento] = useState(user.preferencias?.acento || "");
  const caja = useRef(null);

  useEffect(() => { setAcento(user.preferencias?.acento || ""); }, [user]);
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e) => { if (caja.current && !caja.current.contains(e.target)) setAbierto(false); };
    const esc = (e) => { if (e.key === "Escape") setAbierto(false); };
    document.addEventListener("mousedown", fuera);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", fuera); document.removeEventListener("keydown", esc); };
  }, [abierto]);

  async function elegirAcento(clave) {
    setAcento(clave);
    recordarAcento(clave);
    applyTheme(null);
    try { await guardarPreferencias({ acento: clave }); } catch { /* queda en este navegador */ }
  }

  const nombre = user.full_name || user.email;
  return (
    <div className="lat-pie" ref={caja}>
      {abierto && (
        <div className="lat-menu" role="menu">
          <ThemeSwitch />
          {puedeEditar && (
            <>
              <div className="lat-menu-titulo">Color de acento</div>
              <div className="lat-acentos" role="radiogroup" aria-label="Color de acento">
                {ACENTOS.map((a) => (
                  <button key={a.clave || "clinica"} type="button" role="radio" aria-checked={acento === a.clave}
                          title={a.nombre} aria-label={a.nombre} onClick={() => elegirAcento(a.clave)}
                          className={`lat-acento${acento === a.clave ? " lat-acento--activo" : ""}`}
                          style={{ background: a.color || "conic-gradient(from 45deg, var(--petrol), var(--mint), var(--petrol))" }} />
                ))}
              </div>
            </>
          )}
          <div className="lat-menu-opciones">
            {puedeEditar && user.funcionalidades?.temas_personales && (
              <a className="lat-menu-opcion" href="/panel/preferencias/#tema">Elegir tema…</a>
            )}
            {puedeEditar && (
              <button type="button" className="lat-menu-opcion" onClick={() => { setAbierto(false); alEditar(); }}>
                Editar barra lateral…
              </button>
            )}
            <a className="lat-menu-opcion" href="/descargar/">Instalar las apps</a>
            <button type="button" className="lat-menu-opcion lat-menu-opcion--salir" onClick={logout}>Cerrar sesión</button>
          </div>
        </div>
      )}
      <button type="button" className="lat-perfil" aria-haspopup="menu" aria-expanded={abierto}
              onClick={() => setAbierto((v) => !v)} title={plegada ? nombre : "Tu perfil y apariencia"}
              style={{ justifyContent: plegada ? "center" : "flex-start" }}>
        {/* Iniciales: se reconoce de un vistazo quién tiene la sesión abierta. */}
        <span aria-hidden="true" className="lat-avatar">{iniciales(nombre)}</span>
        {!plegada && (
          <span style={{ minWidth: 0, textAlign: "left" }}>
            <span className="lat-perfil-nombre">{nombre}</span>
            <span className="lat-perfil-rol">{ROLE_LABELS[user.role] || user.role}</span>
          </span>
        )}
      </button>
      {/* Con logotipo propio, la marca de la clínica va arriba y la de la
          plataforma aquí, discreta. Sin él, Clinube ya está arriba. */}
      {!plegada && hayLogoPropio && (
        <div className="lat-plataforma">
          <LogoClinube alto={11} tinta="var(--lat-ink-soft)" acento="var(--lat-ink-soft)" />
        </div>
      )}
    </div>
  );
}

/** «Valeria Núñez» → «VN»; sin nombre, la primera letra del correo. Solo letras y cifras: «Administración (demo)» → «AD». */
function iniciales(texto) {
  const partes = String(texto || "?").replace(/^(dra?\.|dr\.)\s*/i, "").split(/[\s@]+/)
    .map((p) => p.replace(/[^\p{L}\p{N}]/gu, "")).filter(Boolean);
  return ((partes[0]?.[0] || "?") + (partes[1]?.[0] || "")).toUpperCase();
}

/* Iconos de navegación del armazón: mismo trazo que NavIcons. */
const strokeIcon = {
  viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.9, strokeLinecap: "round", strokeLinejoin: "round",
};
function MenuIcon() {
  return <svg width="22" height="22" {...strokeIcon}><path d="M4 7h16M4 12h16M4 17h16" /></svg>;
}
function CloseIcon() {
  return <svg width="18" height="18" {...strokeIcon}><path d="M6 6l12 12M18 6L6 18" /></svg>;
}
function LupaIcon() {
  return <svg width="16" height="16" {...strokeIcon}><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4.5 4.5" /></svg>;
}
/* Panel lateral: un marco con su columna izquierda resaltada. Comunica
   "plegar/desplegar el menú" en lugar de una dirección, que se confundía
   con el botón de regresar. La barra interior se atenúa al contraer. */
function PanelIcon({ open }) {
  return (
    <svg width="17" height="17" {...strokeIcon}>
      <rect x="3" y="4.5" width="18" height="15" rx="2.2" />
      <path d="M9.5 4.5v15" />
      <path d="M13 9.5h4.5M13 14.5h4.5"
            style={{ opacity: open ? 1 : 0.35, transition: "opacity .2s var(--ease)" }} />
    </svg>
  );
}
