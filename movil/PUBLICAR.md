# Publicar la app del paciente sin avisos de seguridad

Qué hace falta para que la app se instale **sin errores ni avisos** en
iPhone y Android, y por qué a veces el teléfono la trata como una
amenaza aunque no lo sea.

## Por qué un iPhone dice «Desarrollador no fiable»

No es por el código. iOS solo confía en una app si llega por un canal
firmado por Apple:

| Cómo se instala | Qué ve el paciente |
| --- | --- |
| **App Store** | Nada: se instala y abre. |
| **TestFlight** (pruebas, hasta 10 000 personas) | Nada, desde la app TestFlight. |
| Desde Xcode con un Apple ID gratuito | «Desarrollador no fiable»; hay que confiar a mano en Ajustes → General → VPN y gestión de dispositivos, y **caduca a los 7 días**. |

Lo tercero sirve para probar en el iPhone propio, nunca para pacientes.
Para todo lo demás hace falta el **Apple Developer Program** (99 USD al
año), a nombre de la empresa si se quiere que la ficha diga «Clinube» y
no un nombre de persona (para eso Apple pide un número D-U-N-S, gratuito).

## Lo que ya está resuelto en el proyecto

- **Solo https.** iOS (App Transport Security) y Android
  (`usesCleartextTraffic="false"`) bloquean el tráfico sin cifrar, y la
  app no lo desactiva: es lo primero que una revisión marca como
  peligroso. En depuración se permite `http` solo para la API local.
- **Certificados.** La app nunca acepta un certificado no válido; dice
  «no se pudo establecer una conexión segura».
- **Permisos mínimos.** Solo internet. Ni cámara, ni ubicación, ni
  contactos: cada permiso de más es una pregunta de la revisión y un
  motivo de desconfianza para el paciente.
- **Manifiesto de privacidad** (`ios/Runner/PrivacyInfo.xcprivacy`): la
  app envía el teléfono (para entrar) y lo que el paciente escribe a su
  clínica. Sin rastreo ni publicidad.
- **Cifrado declarado** (`ITSAppUsesNonExemptEncryption = NO` en
  `Info.plist`): solo https, exento de exportación. Sin esto, App Store
  Connect retiene cada versión hasta contestar el cuestionario.
- **Sesión en el Keychain / Keystore**, que no viaja en las copias de
  seguridad: un teléfono restaurado no hereda la sesión de otro paciente,
  ni se queda sin poder arrancar por una clave que no puede descifrar.
- **Pantalla de arranque** que sigue el modo claro u oscuro del teléfono:
  sin el fogonazo blanco al abrirla de noche.

## iOS: de la primera prueba a la App Store

En el Mac, con Xcode completo y la cuenta de desarrollador:

1. Abrir el proyecto en Xcode:

   ```sh
   open movil/ios/Runner.xcworkspace
   ```

2. En **Runner → Signing & Capabilities**, elegir el equipo (*Team*). El
   identificador es `com.clinube.paciente`: no se puede cambiar una vez
   publicada.
3. En [App Store Connect](https://appstoreconnect.apple.com), crear la
   app con ese identificador. En **Privacidad de la app**, declarar lo
   mismo que el manifiesto: *Número de teléfono* y *Otro contenido del
   usuario*, ambos vinculados al usuario, para funcionalidad, sin rastreo.
4. Compilar y subir:

   ```sh
   bash scripts/movil.sh --compilar ios https://tu-dominio.ec
   ```

   y subir `build/ios/ipa/*.ipa` con la app **Transporter** o desde
   Xcode → Organizer.
5. Probar con **TestFlight** antes de enviar a revisión.

## Android: firma y Google Play

Google Play rechaza una app firmada con la clave de depuración, y Play
Protect avisa al instalarla a mano. La firma se crea una vez:

```sh
keytool -genkey -v -keystore ~/clinube-subida.jks -keyalg RSA -keysize 2048 -validity 10000 -alias subida
```

Y se escribe `movil/android/key.properties` (git lo ignora, igual que el
`.jks`):

```properties
storeFile=/Users/TU_USUARIO/clinube-subida.jks
storePassword=la-contraseña-del-almacén
keyAlias=subida
keyPassword=la-contraseña-de-la-clave
```

**Guarda el `.jks` y sus contraseñas fuera del Mac** (en el gestor de
contraseñas): sin ellos no se puede publicar una actualización. Con
*Play App Signing* activado (lo propone Play Console), Google guarda la
clave definitiva y esta es solo la de subida, que se puede reponer.

```sh
bash scripts/movil.sh --compilar android https://tu-dominio.ec
```

Se sube `build/app/outputs/bundle/release/app-release.aab` a Play
Console. El `.apk` del mismo directorio es para instalar a mano en un
teléfono de prueba.

## La cuenta para los revisores de Apple y Google

Los revisores tienen que poder entrar, y el código llega por WhatsApp a
un teléfono que no tienen. Sin una cuenta de prueba que funcione, la app
se rechaza («no pudimos iniciar sesión»).

1. En una **clínica de demostración**, crear un paciente de prueba con
   datos inventados y un teléfono que no sea de nadie, p. ej.
   `+593900000001`. Darle una cita y algún pago para que la app no se
   vea vacía, y en su ficha pulsar **Activar acceso** (App del paciente).
2. En el `.env` del servidor:

   ```properties
   APP_REVISION_TELEFONO=+593900000001
   APP_REVISION_CODIGO=246810
   ```

   Con ese teléfono, el código es siempre ese y no se envía WhatsApp.
   Solo vale para esa cuenta, y solo si ya existe.
3. Dar el teléfono y el código en **App Review Information** (App Store
   Connect) y en **Acceso a la app** (Play Console).
4. Cuando la app esté aprobada, se pueden vaciar las dos variables; hará
   falta volver a ponerlas para cada versión nueva que pase revisión.

## Antes de enviar a revisión

- [ ] La API responde por `https` con un certificado válido.
- [ ] El aviso de privacidad está publicado: `https://tu-dominio.ec/privacidad/`
      (se pone como *URL de la política de privacidad* en las dos tiendas).
- [ ] La cuenta de revisión entra y tiene datos.
- [ ] `bash scripts/movil.sh --compilar …` termina en verde.
- [ ] Probado en un iPhone real con TestFlight y en un Android real.
