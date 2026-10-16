"use client";

/**
 * Portada pública de Clinube (clinube.com).
 *
 * Tres cosas y nada más: qué servicios hay (odontología ya, medicina y
 * psicología por solicitud), cómo entrar a la app y dónde descargar las
 * apps. Nginx la sirve en la raíz del dominio; en app.clinube.com la raíz
 * sigue llevando al panel.
 */

import { useEffect } from "react";

import { IconoClinube, LogoClinube, MARCA } from "../../lib/marca";
import { CORREO_CONTACTO, TIENDA_ANDROID, TIENDA_IOS, useUrlApp } from "../../lib/sitio";
import { initColorMode } from "../../lib/theme";

const SERVICIOS = [
  {
    clave: "odontologia", nombre: "Odontología", disponible: true,
    texto: "Odontograma, historia clínica, recetas, certificados y las finanzas de la clínica.",
    accion: "Crear mi clínica",
  },
  {
    clave: "medicina", nombre: "Medicina", disponible: false,
    texto: "Historia clínica general, agenda y documentos para consultorios médicos.",
    accion: "Solicitar acceso",
  },
  {
    clave: "psicologia", nombre: "Psicología", disponible: false,
    texto: "Agenda de sesiones, notas clínicas privadas y seguimiento de cada paciente.",
    accion: "Solicitar acceso",
  },
];

const INCLUYE = [
  ["Agenda", "Citas, recordatorios y la sala de espera del día."],
  ["Historia clínica", "Ficha completa del paciente y sus documentos en PDF."],
  ["Cobros y finanzas", "Pagos, caja, honorarios y rol de pagos."],
  ["App para pacientes", "Sus citas, sus documentos y mensajes con la clínica."],
];

export default function Portada() {
  useEffect(() => initColorMode(), []);
  const entrar = useUrlApp("/login/");

  return (
    <div className="web">
      <header className="web-barra">
        <a href="/" aria-label={MARCA} className="web-marca"><LogoClinube alto={24} /></a>
        <nav className="web-nav" aria-label="Secciones">
          <a href="#servicios">Servicios</a>
          <a href="#apps">Descargas</a>
        </nav>
        <a className="web-boton web-boton--chico" href={entrar}>Entrar</a>
      </header>

      <main>
        <section className="web-portada">
          <IconoClinube alto={52} />
          <h1>Tu consulta, organizada en la nube.</h1>
          <p>Agenda, historia clínica, cobros y una app para tus pacientes. En el ordenador, la tableta o el teléfono.</p>
          <div className="web-acciones">
            <a className="web-boton" href={entrar}>Entrar a Clinube</a>
            <a className="web-boton web-boton--claro" href="#apps">Descargar las apps</a>
          </div>
        </section>

        <section id="servicios" className="web-seccion">
          <h2>Servicios</h2>
          <div className="web-servicios">
            {SERVICIOS.map((s) => (
              <article key={s.clave} className={`web-servicio${s.disponible ? " web-servicio--activo" : ""}`}>
                <span className={`web-estado${s.disponible ? " web-estado--si" : ""}`}>
                  {s.disponible ? "Disponible" : "Próximamente"}
                </span>
                <h3>{s.nombre}</h3>
                <p>{s.texto}</p>
                <a className={`web-boton${s.disponible ? "" : " web-boton--claro"}`}
                   href={`/crear-clinica/?tipo=${s.clave}`}>{s.accion}</a>
              </article>
            ))}
          </div>
        </section>

        <section className="web-seccion">
          <h2>Lo que incluye</h2>
          <div className="web-incluye">
            {INCLUYE.map(([t, d]) => (
              <div key={t}><h3>{t}</h3><p>{d}</p></div>
            ))}
          </div>
        </section>

        <section id="apps" className="web-seccion">
          <h2>Apps</h2>
          <div className="web-apps">
            <article className="web-app">
              <h3>Para el equipo de la clínica</h3>
              <p>Funciona en el navegador de cualquier dispositivo y se puede instalar como app en el teléfono o el ordenador.</p>
              <div className="web-acciones web-acciones--izq">
                <a className="web-boton" href={entrar}>Abrir Clinube</a>
                <a className="web-enlace" href="/descargar/">Cómo instalarla →</a>
              </div>
            </article>
            <article className="web-app">
              <h3>Para los pacientes</h3>
              <p>La app de Clinube para pedir citas, ver sus documentos y escribir a su clínica.</p>
              <div className="web-tiendas">
                <Tienda href={TIENDA_IOS} linea="Descargar en el" tienda="App Store" />
                <Tienda href={TIENDA_ANDROID} linea="Disponible en" tienda="Google Play" />
              </div>
              <a className="web-enlace" href="/descargar/">Todas las descargas →</a>
            </article>
          </div>
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
