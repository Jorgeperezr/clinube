"use client";

/**
 * Descargas: las dos apps de Clinube en una página pública, como
 * whatsapp.com/download.
 *
 *   · la del PACIENTE (Flutter, movil/), en App Store y Google Play;
 *   · la del EQUIPO de la clínica, que es el panel instalado como app
 *     (lib/AppInstalable.js): se instala desde aquí mismo.
 *
 * Los enlaces de las tiendas se fijan al compilar con
 * NEXT_PUBLIC_URL_APP_STORE y NEXT_PUBLIC_URL_GOOGLE_PLAY. Mientras no
 * estén, la página dice «muy pronto» en vez de llevar a un enlace roto.
 *
 * Usa la marca de la plataforma (logotipo y paleta de lib/theme.js) y
 * respeta el modo claro/oscuro y «Sin color» de quien la abre.
 */

import { useEffect, useState } from "react";

import { instalar, useInstalacion } from "../../lib/AppInstalable";
import { IconoClinube, LEMA, LogoClinube, MARCA } from "../../lib/marca";
import { useUrlApp } from "../../lib/sitio";
import { initColorMode } from "../../lib/theme";

const APP_STORE = process.env.NEXT_PUBLIC_URL_APP_STORE || "";
const GOOGLE_PLAY = process.env.NEXT_PUBLIC_URL_GOOGLE_PLAY || "";

function useDispositivo() {
  const [d, setD] = useState("ordenador");
  useEffect(() => {
    const ua = navigator.userAgent;
    if (/iPad|iPhone|iPod/.test(ua) || (ua.includes("Macintosh") && navigator.maxTouchPoints > 1)) setD("ios");
    else if (/Android/i.test(ua)) setD("android");
  }, []);
  return d;
}

const NOMBRE_DISPOSITIVO = { ios: "un iPhone o iPad", android: "un teléfono Android", ordenador: "un ordenador" };

export default function DescargarPage() {
  useEffect(() => initColorMode(), []);
  const dispositivo = useDispositivo();
  const entrar = useUrlApp("/login/");

  return (
    <div className="dl">
      <header className="dl-cabecera">
        <a href="/" aria-label={MARCA}>
          <LogoClinube alto={30} tinta="#ffffff" acento="var(--mint)" />
        </a>
        <a className="dl-entrar" href={entrar}>Entrar al panel</a>
      </header>

      <section className="dl-portada">
        <IconoClinube alto={56} tinta="#ffffff" acento="var(--mint)" />
        <h1>Descarga {MARCA}</h1>
        <p>
          {LEMA}. Una app para los pacientes y otra para el equipo de la clínica, las dos
          gratuitas.
        </p>
        <span className="dl-chip">Estás en {NOMBRE_DISPOSITIVO[dispositivo]}</span>
      </section>

      <main className="dl-cuerpo">
        <div className="dl-tarjetas">
          <AppPaciente dispositivo={dispositivo} />
          <AppEquipo dispositivo={dispositivo} />
        </div>

        <section className="dl-seccion">
          <h2>Privacidad y seguridad</h2>
          <div className="dl-rejilla">
            <div>
              <h3>Los datos se quedan en la clínica</h3>
              <p>
                La app del equipo no guarda datos de pacientes en el dispositivo: solo lo
                necesario para abrir rápido. Si se pierde un teléfono, basta con cambiar la
                contraseña de esa persona.
              </p>
            </div>
            <div>
              <h3>Cada paciente ve lo suyo</h3>
              <p>
                El paciente entra con su número de teléfono y un código por WhatsApp, sin
                contraseñas que olvidar. Solo ve sus citas, su cuenta y lo que su profesional
                decidió mostrarle.
              </p>
            </div>
            <div>
              <h3>Conexiones cifradas</h3>
              <p>
                Todo viaja cifrado entre la app y el servidor, y cada clínica tiene sus datos
                separados de las demás. Los detalles están en el{" "}
                <a href="/privacidad/">aviso de privacidad</a>.
              </p>
            </div>
          </div>
        </section>

        <section className="dl-seccion">
          <h2>Preguntas frecuentes</h2>
          <Pregunta titulo="¿Cuánto cuestan las apps?">
            Nada. La app del paciente es gratuita en las tiendas, y la del equipo forma parte del
            servicio que tiene contratado la clínica.
          </Pregunta>
          <Pregunta titulo="Soy paciente: ¿cómo entro?">
            Con el número de teléfono que diste en tu clínica. Primero, en recepción activan tu
            acceso a la app en tu ficha; después pones ese número en la app, te llega un código por
            WhatsApp y listo. Si te dice que el número no tiene acceso, pide en recepción que lo
            activen o que revisen el teléfono de tu ficha.
          </Pregunta>
          <Pregunta titulo="Trabajo en una clínica: ¿por qué la app no está en las tiendas?">
            Porque es el mismo panel que usas en el ordenador, instalado como app: se actualiza
            solo, sin esperar a las tiendas, y funciona igual en Android, iPhone, iPad y en el
            ordenador. Entras con el correo y la contraseña que te dio la administración.
          </Pregunta>
          <Pregunta titulo="¿Qué pasa si cambio de teléfono?">
            Nada se pierde: los datos están en la clínica, no en el teléfono. Instala la app en
            el nuevo y vuelve a entrar.
          </Pregunta>
        </section>
      </main>

      <footer className="dl-pie">
        <LogoClinube alto={18} />
        <nav>
          <a href="/privacidad/">Aviso de privacidad</a>
          <a href="/condiciones/">Condiciones de uso</a>
          <a href={entrar}>Panel de la clínica</a>
        </nav>
      </footer>
    </div>
  );
}

function Pregunta({ titulo, children }) {
  return (
    <details className="dl-pregunta">
      <summary>{titulo}</summary>
      <p>{children}</p>
    </details>
  );
}

function BotonTienda({ href, tienda, linea }) {
  if (!href) {
    return (
      <span className="dl-tienda dl-tienda--pronto" aria-disabled="true">
        <small>Muy pronto en</small>{tienda}
      </span>
    );
  }
  return (
    <a className="dl-tienda" href={href} target="_blank" rel="noopener">
      <small>{linea}</small>{tienda}
    </a>
  );
}

function AppPaciente({ dispositivo }) {
  const tiendas = [
    { clave: "ios", nodo: <BotonTienda key="ios" href={APP_STORE} tienda="App Store" linea="Descargar en el" /> },
    { clave: "android", nodo: <BotonTienda key="and" href={GOOGLE_PLAY} tienda="Google Play" linea="Disponible en" /> },
  ];
  // La tienda de su teléfono, primero.
  if (dispositivo === "android") tiendas.reverse();
  return (
    <article className={`dl-tarjeta${dispositivo !== "ordenador" ? " dl-tarjeta--destacada" : ""}`}>
      <span className="dl-etiqueta">Para pacientes</span>
      <h2>{MARCA}</h2>
      <p className="dl-lema">Tu clínica en el bolsillo.</p>
      <div className="dl-tiendas">{tiendas.map((t) => t.nodo)}</div>
      <ul className="dl-lista">
        <li>Tus próximas citas, con día, hora y profesional, y confirmar que irás.</li>
        <li>Pedir una cita o escribir a la clínica sin llamar.</li>
        <li>Lo que debes y cuándo vence cada cuota.</li>
        <li>Las indicaciones y recetas que tu profesional comparte contigo.</li>
        <li>Con el nombre, el logotipo y los colores de tu clínica.</li>
      </ul>
      <p className="dl-requisitos">iPhone con iOS 15 o posterior · Android 7.0 o posterior</p>
    </article>
  );
}

function AppEquipo({ dispositivo }) {
  const entrar = useUrlApp("/login/");
  const estado = useInstalacion();
  const [hecho, setHecho] = useState(false);

  let accion;
  if (estado === "instalada") {
    accion = <p className="dl-ok">Ya la estás usando como app en este dispositivo.</p>;
  } else if (estado === "aviso") {
    accion = (
      <button type="button" className="btn btn-primary dl-instalar"
              onClick={async () => setHecho(await instalar())}>
        Instalar en este dispositivo
      </button>
    );
  } else if (dispositivo === "ios") {
    accion = (
      <ol className="dl-pasos">
        <li>Abre esta página en <strong>Safari</strong>.</li>
        <li>Toca <strong>Compartir</strong> (el cuadrado con la flecha hacia arriba).</li>
        <li>Elige <strong>Añadir a pantalla de inicio</strong>.</li>
      </ol>
    );
  } else if (dispositivo === "android") {
    accion = (
      <ol className="dl-pasos">
        <li>Abre esta página en <strong>Chrome</strong>.</li>
        <li>Toca el menú <strong>⋮</strong> de arriba a la derecha.</li>
        <li>Elige <strong>Instalar app</strong> o <strong>Añadir a pantalla de inicio</strong>.</li>
      </ol>
    );
  } else {
    accion = (
      <p className="dl-pasos-texto">
        En <strong>Chrome</strong> o <strong>Edge</strong>, pulsa el icono de instalar que
        aparece a la derecha de la barra de direcciones. En Safari para Mac: Archivo →
        Añadir al Dock.
      </p>
    );
  }

  return (
    <article className="dl-tarjeta">
      <span className="dl-etiqueta">Para el equipo de la clínica</span>
      <h2>{MARCA} · Panel</h2>
      <p className="dl-lema">El panel completo, como una app.</p>
      <div className="dl-accion">
        {accion}
        {hecho && <p className="dl-ok">Listo: la encontrarás como «{MARCA}» en tu pantalla de inicio.</p>}
        <a className="dl-enlace" href={entrar}>O úsalo en el navegador →</a>
      </div>
      <ul className="dl-lista">
        <li>Agenda de la clínica y de cada profesional.</li>
        <li>Fichas de pacientes, odontograma e historia clínica.</li>
        <li>Presupuestos, cobros y reportes.</li>
        <li>Lo que piden los pacientes desde su app, en una bandeja.</li>
        <li>Se actualiza sola y no guarda datos de pacientes en el dispositivo.</li>
      </ul>
      <p className="dl-requisitos">Android, iPhone, iPad, Mac y Windows · Chrome, Edge o Safari actualizados</p>
    </article>
  );
}
