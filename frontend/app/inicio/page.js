"use client";

/**
 * Portada pública de Clinube (clinube.com).
 *
 * Qué servicios hay (odontología ya, medicina y psicología por
 * solicitud), para quién (el profesional que trabaja solo o la clínica
 * con equipo), cómo entrar y dónde descargar las apps. Nginx la sirve en
 * la raíz del dominio; en app.clinube.com la raíz sigue llevando al panel.
 *
 * Tono editorial: titulares en Fraunces (public/fonts, OFL) sobre el
 * Inter del panel, y una muestra del producto hecha con HTML —no una
 * captura— para que se vea nítida en cualquier pantalla.
 */

import { useEffect } from "react";

import { IconoClinube, LogoClinube, MARCA } from "../../lib/marca";
import { CORREO_CONTACTO, TIENDA_ANDROID, TIENDA_IOS, useUrlApp } from "../../lib/sitio";
import { initColorMode } from "../../lib/theme";

const MODALIDADES = [
  {
    clave: "consultorio", titulo: "Trabajo por mi cuenta",
    texto: "Una sola cuenta para todo: agendas, atiendes, escribes la historia y firmas la receta.",
    puntos: ["Tu agenda y tus pacientes", "Tu firma y tu registro en cada documento", "Sumas a alguien cuando lo necesites"],
    accion: "Crear mi consultorio",
  },
  {
    clave: "clinica", titulo: "Tenemos un equipo",
    texto: "Recepción agenda y cobra, cada profesional ve a sus pacientes y la administración lleva las cuentas.",
    puntos: ["Funciones a medida de cada persona", "Caja, honorarios y rol de pagos", "Varios profesionales en una agenda"],
    accion: "Crear mi clínica",
  },
];

const SERVICIOS = [
  { clave: "odontologia", nombre: "Odontología", disponible: true,
    texto: "Odontograma, periodontograma, historia clínica, recetas y certificados." },
  { clave: "medicina", nombre: "Medicina", disponible: false,
    texto: "Historia clínica general, agenda y documentos para consultorios médicos." },
  { clave: "psicologia", nombre: "Psicología", disponible: false,
    texto: "Agenda de sesiones, notas clínicas privadas y seguimiento de cada paciente." },
];

const INCLUYE = [
  ["Agenda", "Citas, recordatorios y quién está ya en la sala de espera."],
  ["Historia clínica", "La ficha completa, con su odontograma y cada evolución."],
  ["Recetas y certificados", "Con tu firma y tu registro profesional, listos en PDF."],
  ["Cobros y finanzas", "Presupuestos, pagos, caja, honorarios y rol de pagos."],
  ["App para pacientes", "Sus citas, sus recetas y mensajes con su consulta."],
  ["Respaldo cifrado", "Una copia de la información de tus pacientes que solo tú puedes abrir."],
];

export default function Portada() {
  useEffect(() => initColorMode(), []);
  const entrar = useUrlApp("/login/");

  return (
    <div className="web web-inicio">
      <header className="web-barra web-barra--inicio">
        <a href="/" aria-label={MARCA} className="web-marca">
          <LogoClinube alto={24} tinta="#fff" acento="var(--w-menta)" />
        </a>
        <nav className="web-nav" aria-label="Secciones">
          <a href="#para-quien">Para quién</a>
          <a href="#servicios">Especialidades</a>
          <a href="#apps">Descargas</a>
        </nav>
        <a className="web-boton web-boton--chico web-boton--menta" href={entrar}>Entrar</a>
      </header>

      <main>
        <section className="web-heroe">
          <div className="web-heroe-texto">
            <p className="web-antetitulo web-aparece" style={{ "--d": "0ms" }}>
              <span className="web-punto" aria-hidden="true" />Odontología · medicina y psicología, muy pronto
            </p>
            <h1 className="web-aparece" style={{ "--d": "80ms" }}>
              Tu consulta, <em>en orden</em> y contigo a donde vayas.
            </h1>
            <p className="web-heroe-bajada web-aparece" style={{ "--d": "160ms" }}>
              Agenda, historia clínica, recetas y cobros en un solo lugar. Para el profesional que atiende solo
              y para la clínica con equipo, en el ordenador, la tableta o el teléfono.
            </p>
            <div className="web-acciones web-acciones--izq web-aparece" style={{ "--d": "240ms" }}>
              <a className="web-boton web-boton--menta" href="/crear-clinica/?tipo=odontologia">Crear mi cuenta</a>
              <a className="web-boton web-boton--fantasma" href={entrar}>Ya tengo cuenta</a>
            </div>
          </div>
          <Muestra />
        </section>

        <section id="para-quien" className="web-seccion">
          <Encabezado numero="01" titulo="Hecho para cómo trabajas">
            Lo eliges al crear tu cuenta. Si empiezas solo y luego crece el equipo, no cambias de sistema.
          </Encabezado>
          <div className="web-modalidades">
            {MODALIDADES.map((m) => (
              <article key={m.clave} className={`web-modalidad web-modalidad--${m.clave}`}>
                <h3>{m.titulo}</h3>
                <p>{m.texto}</p>
                <ul>{m.puntos.map((p) => <li key={p}>{p}</li>)}</ul>
                <a className="web-boton" href={`/crear-clinica/?tipo=odontologia&modalidad=${m.clave}`}>{m.accion}</a>
              </article>
            ))}
          </div>
        </section>

        <section id="servicios" className="web-seccion">
          <Encabezado numero="02" titulo="Especialidades">
            Empezamos por la odontología. Las demás se abren en orden de solicitud.
          </Encabezado>
          <ol className="web-especialidades">
            {SERVICIOS.map((s) => (
              <li key={s.clave} className={s.disponible ? "web-especialidad--si" : ""}>
                <a href={`/crear-clinica/?tipo=${s.clave}`}>
                  <span className="web-especialidad-nombre">{s.nombre}</span>
                  <span className="web-especialidad-texto">{s.texto}</span>
                  <span className={`web-estado${s.disponible ? " web-estado--si" : ""}`}>
                    {s.disponible ? "Disponible" : "Solicitar acceso"}
                  </span>
                  <span className="web-flecha" aria-hidden="true">→</span>
                </a>
              </li>
            ))}
          </ol>
        </section>

        <section className="web-seccion">
          <Encabezado numero="03" titulo="Lo que incluye">
            Lo del día a día de una consulta, en la misma cuenta.
          </Encabezado>
          <div className="web-incluye">
            {INCLUYE.map(([t, d]) => (
              <div key={t}><h3>{t}</h3><p>{d}</p></div>
            ))}
          </div>
        </section>

        <section id="apps" className="web-seccion">
          <Encabezado numero="04" titulo="Apps">
            El panel funciona en el navegador y se instala como app. Tus pacientes tienen la suya.
          </Encabezado>
          <div className="web-apps">
            <article className="web-app">
              <h3>Para ti y tu equipo</h3>
              <p>En el navegador de cualquier dispositivo, o instalada en el teléfono y el ordenador.</p>
              <div className="web-acciones web-acciones--izq">
                <a className="web-boton" href={entrar}>Abrir Clinube</a>
                <a className="web-enlace" href="/descargar/">Cómo instalarla →</a>
              </div>
            </article>
            <article className="web-app">
              <h3>Para tus pacientes</h3>
              <p>Para pedir citas, ver sus recetas y documentos y escribir a su consulta.</p>
              <div className="web-tiendas">
                <Tienda href={TIENDA_IOS} linea="Descargar en el" tienda="App Store" />
                <Tienda href={TIENDA_ANDROID} linea="Disponible en" tienda="Google Play" />
              </div>
              <a className="web-enlace" href="/descargar/">Todas las descargas →</a>
            </article>
          </div>
        </section>

        <section className="web-cierre">
          <IconoClinube alto={44} tinta="#fff" acento="var(--w-menta)" />
          <h2>Empieza hoy, con tus pacientes de siempre.</h2>
          <p>Creas la cuenta con tu correo en un par de minutos.</p>
          <a className="web-boton web-boton--menta" href="/crear-clinica/?tipo=odontologia">Crear mi cuenta</a>
        </section>
      </main>

      <footer className="web-pie">
        <LogoClinube alto={18} />
        <nav aria-label="Enlaces">
          <a href="/privacidad/">Privacidad</a>
          <a href="/descargar/">Descargas</a>
          <a href={`mailto:${CORREO_CONTACTO}`}>Contacto</a>
        </nav>
        <span>© {new Date().getFullYear()} {MARCA}</span>
      </footer>
    </div>
  );
}

function Encabezado({ numero, titulo, children }) {
  return (
    <div className="web-encabezado">
      <span className="web-numero">{numero}</span>
      <h2>{titulo}</h2>
      <p>{children}</p>
    </div>
  );
}

/**
 * Muestra del producto: la agenda del día, una receta firmada y un aviso
 * de la app. Los datos son de ejemplo y no salen de ninguna clínica.
 */
function Muestra() {
  const citas = [
    ["08:30", "Control de ortodoncia", "Valeria R.", "En sala"],
    ["09:15", "Profilaxis", "Martín S.", ""],
    ["10:00", "Endodoncia · 2.ª sesión", "Camila T.", ""],
    ["11:30", "Valoración inicial", "Paciente nuevo", ""],
  ];
  return (
    <div className="web-muestra" aria-hidden="true">
      <div className="web-tarjeta web-tarjeta--agenda web-aparece" style={{ "--d": "200ms" }}>
        <div className="web-tarjeta-cabeza">
          <span>Hoy</span><span className="web-tarjeta-cifra">4 citas</span>
        </div>
        {citas.map(([h, motivo, quien, estado]) => (
          <div key={h} className="web-cita">
            <span className="web-cita-hora">{h}</span>
            <span className="web-cita-motivo">{motivo}<small>{quien}</small></span>
            {estado && <span className="web-cita-estado">{estado}</span>}
          </div>
        ))}
      </div>
      <div className="web-tarjeta web-tarjeta--receta web-aparece" style={{ "--d": "380ms" }}>
        <span className="web-tarjeta-etiqueta">Receta</span>
        <div className="web-receta-linea" style={{ width: "86%" }} />
        <div className="web-receta-linea" style={{ width: "64%" }} />
        <div className="web-receta-linea" style={{ width: "74%" }} />
        <svg className="web-firma" viewBox="0 0 160 48" fill="none">
          <path d="M6 34c10-18 18-26 22-22s-8 26-2 26 14-30 22-28-6 22 2 22 12-16 18-16 2 14 10 12 18-18 30-16 20 10 40 4"
                stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="web-sello">Firmada</span>
      </div>
      <div className="web-tarjeta web-tarjeta--aviso web-aparece" style={{ "--d": "520ms" }}>
        <span className="web-aviso-icono">✓</span>
        <span>Cita confirmada desde la app<small>Martín S. · 09:15</small></span>
      </div>
    </div>
  );
}

function Tienda({ href, linea, tienda }) {
  if (!href) {
    return (
      <span className="web-tienda web-tienda--pronto" aria-disabled="true">
        <small>Muy pronto en</small>{tienda}
      </span>
    );
  }
  return (
    <a className="web-tienda" href={href} target="_blank" rel="noopener">
      <small>{linea}</small>{tienda}
    </a>
  );
}
