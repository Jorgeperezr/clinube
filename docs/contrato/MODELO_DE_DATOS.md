# Modelo de datos

Generado con `bash scripts/exportar-contrato.sh` desde los modelos de Django; no editar a mano.
Todas las tablas con `tenant` pertenecen a una clínica y toda consulta se filtra por ella.

## accounts

### User — `accounts_user`

_Usuario_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `password` | CharField |  |  | máx. 128 |
| `last_login` | DateTimeField | sí |  |  |
| `is_superuser` | BooleanField |  | False | Indica que este usuario tiene todos los permisos sin asignárselos explícitamente. |
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey | sí |  | → common.Tenant (PROTECT); Nulo SOLO para el Super Administrador (opera sobre la plataforma, no dentro de una clínica). |
| `email` | CharField | sí |  | único; máx. 254 |
| `phone` | CharField | sí |  | único; máx. 20 |
| `full_name` | CharField |  |  | máx. 150 |
| `role` | CharField |  |  | máx. 20; opciones: `superadmin`, `admin`, `reception`, `doctor`, `auxiliary`, `patient` |
| `is_active` | BooleanField |  | True |  |
| `preferencias` | JSONField |  | dict() | Preferencias de la propia persona (p. ej. usar o no el odontograma 3D). Ver apps/accounts/preferencias.py. |
| `funciones` | JSONField |  | dict() | Módulos de gestión que puede usar (agenda, cobros, inventario…). Vacío = los que su rol tenía antes de existir las funciones. Ver apps/accounts/funciones.py. |
| `must_change_password` | BooleanField |  | False | Se marca cuando la contraseña la puso otra persona: el alta de una clínica o un restablecimiento. Mientras esté marcada, la cuenta solo puede hacer una cosa: elegir su propia contraseña. |
| `is_staff` | BooleanField |  | False |  |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `groups` | ManyToMany | | | → auth.Group |
| `user_permissions` | ManyToMany | | | → auth.Permission |

### DeviceToken — `accounts_devicetoken`

_Token de dispositivo (push)_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `user_id` | ForeignKey |  |  | → accounts.User (CASCADE) |
| `fcm_token` | CharField |  |  | único; máx. 255 |
| `platform` | CharField |  |  | máx. 10; opciones: `ios`, `android` |
| `is_active` | BooleanField |  | True |  |
| `created_at` | DateTimeField |  |  | se fija al crear |

### OTPCode — `accounts_otpcode`

_Código OTP_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `user_id` | ForeignKey |  |  | → accounts.User (CASCADE) |
| `code_hash` | CharField |  |  | máx. 128 |
| `purpose` | CharField |  |  | máx. 10; opciones: `login`, `recovery` |
| `expires_at` | DateTimeField |  |  |  |
| `used_at` | DateTimeField | sí |  |  |
| `created_at` | DateTimeField |  |  | se fija al crear |

- Índice: (user, purpose, expires_at)

### AuditLog — `accounts_auditlog`

_Registro de auditoría_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey | sí |  | → common.Tenant (PROTECT) |
| `user_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `action` | CharField |  |  | máx. 50 |
| `entity_type` | CharField |  |  | máx. 100 |
| `entity_id` | CharField |  |  | máx. 64 |
| `ip_address` | GenericIPAddressField | sí |  | máx. 39 |
| `metadata` | JSONField |  | dict() |  |
| `created_at` | DateTimeField |  |  | se fija al crear |

- Índice: (user, created_at)
- Índice: (entity_type, entity_id)
- Índice: (tenant, -created_at)

### PasswordResetToken — `accounts_passwordresettoken`

_Token de recuperación_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `user_id` | ForeignKey |  |  | → accounts.User (CASCADE) |
| `token_hash` | CharField |  |  | máx. 128 |
| `expires_at` | DateTimeField |  |  |  |
| `used_at` | DateTimeField | sí |  |  |
| `created_at` | DateTimeField |  |  | se fija al crear |

## agenda

### Doctor — `agenda_doctor`

_Doctor_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `user_id` | OneToOneField |  |  | → accounts.User (CASCADE); único |
| `calendar_color` | CharField |  | '#3b82f6' | máx. 7; Color hex para distinguirlo en la agenda. |
| `google_calendar_token` | JSONField | sí |  |  |
| `is_active` | BooleanField |  | True |  |
| `license_number` | CharField |  |  | máx. 50; Nº de registro profesional (aparece en las recetas). |
| `signature_image` | TextField |  |  | Firma manuscrita del doctor (imagen base64, dibujada en pantalla). Se estampa en las recetas. |
| `calendar_token` | UUIDField |  | uuid4() | único; Token secreto del feed iCalendar (suscripción desde Google Calendar). |
| `specialties` | ManyToMany | | | → specialties.Specialty |

### Appointment — `agenda_appointment`

_Cita_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (PROTECT) |
| `doctor_id` | ForeignKey |  |  | → agenda.Doctor (PROTECT) |
| `treatment_id` | ForeignKey | sí |  | → configuration.Treatment (SET_NULL) |
| `scheduled_start` | DateTimeField |  |  |  |
| `scheduled_end` | DateTimeField |  |  |  |
| `status` | CharField |  | 'pending' | máx. 15; opciones: `pending`, `confirmed`, `cancelled`, `rescheduled`, `completed`, `no_show` |
| `notes` | TextField |  |  |  |
| `checkin_at` | DateTimeField | sí |  |  |
| `attention_started_at` | DateTimeField | sí |  | Cuándo el doctor inició la atención (flujo: llegó → en atención → finalizada). |
| `checkout_at` | DateTimeField | sí |  |  |
| `reminder_sent_at` | DateTimeField | sí |  | Cuándo se envió el recordatorio WhatsApp (evita duplicados). |
| `google_calendar_event_id` | CharField |  |  | máx. 255 |
| `created_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |

- Índice: (tenant, doctor, scheduled_start)
- Índice: (tenant, scheduled_start)
- Índice: (status)
- Índice: (patient, scheduled_start)

## app_paciente

### SolicitudCita — `app_paciente_solicitudcita`

_Solicitud de cita desde la app_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `fecha_preferida` | DateField |  |  |  |
| `franja` | CharField |  | 'cualquiera' | máx. 12; opciones: `manana`, `tarde`, `cualquiera` |
| `motivo` | CharField |  |  | máx. 300 |
| `estado` | CharField |  | 'pendiente' | máx. 12; opciones: `pendiente`, `agendada`, `rechazada` |
| `cita_id` | ForeignKey | sí |  | → agenda.Appointment (SET_NULL) |
| `respuesta` | CharField |  |  | máx. 300 |
| `atendida_por_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `atendida_en` | DateTimeField | sí |  |  |

- Orden por omisión: -created_at

### MensajeConsultorio — `app_paciente_mensajeconsultorio`

_Mensaje al consultorio_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `texto` | TextField |  |  |  |
| `respuesta` | TextField |  |  |  |
| `respondido_por_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `respondido_en` | DateTimeField | sí |  |  |

- Orden por omisión: -created_at

## billing

### Budget — `billing_budget`

_Presupuesto_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (PROTECT) |
| `status` | CharField |  | 'draft' | máx. 10; opciones: `draft`, `approved`, `rejected` |
| `total_amount` | DecimalField |  | 0 | 12,2 |
| `notes` | TextField |  |  |  |
| `created_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `created_at` | DateTimeField |  |  | se fija al crear |

### BudgetItem — `billing_budgetitem`

_Ítem de presupuesto_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `budget_id` | ForeignKey |  |  | → billing.Budget (CASCADE) |
| `treatment_id` | ForeignKey |  |  | → configuration.Treatment (PROTECT) |
| `tooth_fdi_code` | CharField |  |  | máx. 2 |
| `quantity` | PositiveIntegerField |  | 1 |  |
| `unit_price` | DecimalField |  |  | 10,2 |

### PaymentPlan — `billing_paymentplan`

_Plan de pago_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `budget_id` | OneToOneField |  |  | → billing.Budget (PROTECT); único |
| `patient_id` | ForeignKey |  |  | → patients.Patient (PROTECT) |
| `total_amount` | DecimalField |  |  | 12,2 |
| `installment_count` | PositiveIntegerField |  |  |  |
| `created_at` | DateTimeField |  |  | se fija al crear |

### Installment — `billing_installment`

_Cuota_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `payment_plan_id` | ForeignKey |  |  | → billing.PaymentPlan (CASCADE) |
| `patient_id` | ForeignKey |  |  | → patients.Patient (PROTECT) |
| `number` | PositiveIntegerField |  |  | Número de cuota (1, 2, 3...). |
| `due_date` | DateField |  |  |  |
| `amount` | DecimalField |  |  | 10,2 |
| `status` | CharField |  | 'pending' | máx. 10; opciones: `pending`, `paid`, `overdue` |

- Índice: (patient, status)
- Índice: (due_date, status)
- Orden por omisión: due_date

### Payment — `billing_payment`

_Pago_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `installment_id` | ForeignKey | sí |  | → billing.Installment (PROTECT) |
| `patient_id` | ForeignKey |  |  | → patients.Patient (PROTECT) |
| `amount` | DecimalField |  |  | 10,2 |
| `method` | CharField |  |  | máx. 10; opciones: `cash`, `transfer`, `card` |
| `date` | DateField |  |  |  |
| `registered_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `profesional_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `numero_comprobante` | PositiveIntegerField | sí |  |  |
| `created_at` | DateTimeField |  |  | se fija al crear |

- Índice: (patient, date)
- Índice: (tenant, date)

### DoctorFee — `billing_doctorfee`

_Honorario de doctor_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `doctor_id` | ForeignKey |  |  | → agenda.Doctor (CASCADE) |
| `treatment_id` | ForeignKey | sí |  | → configuration.Treatment (CASCADE); Nulo = regla general del doctor para todos los tratamientos. |
| `fee_type` | CharField |  |  | máx. 10; opciones: `percentage`, `fixed` |
| `value` | DecimalField |  |  | 10,2 |

## clinical

### ClinicalRecord — `clinical_clinicalrecord`

_Historia clínica_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | BigAutoField |  |  | clave primaria |
| `patient_id` | OneToOneField |  |  | → patients.Patient (CASCADE); único |
| `general_notes` | TextField |  |  |  |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |

### Evolution — `clinical_evolution`

_Evolución_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `doctor_id` | ForeignKey | sí |  | → agenda.Doctor (PROTECT); Nulo si registró un usuario clínico sin perfil de doctor (admin/auxiliar). |
| `appointment_id` | ForeignKey | sí |  | → agenda.Appointment (SET_NULL) |
| `type` | CharField |  | 'clinical_note' | máx. 20; opciones: `clinical_note`, `prescription`, `care_instruction` |
| `date` | DateField |  |  |  |
| `notes` | TextField |  |  |  |
| `visible_to_patient` | BooleanField |  | False | Si es True, el paciente lo ve en la app (RF-APP-03). |
| `follow_up_date` | DateField | sí |  | Fecha de seguimiento: genera una alerta cuando llega (Sprint 22). |
| `created_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL); Usuario que registró la evolución (doctor, admin o auxiliar). |
| `created_at` | DateTimeField |  |  | se fija al crear |

- Índice: (patient, date)
- Índice: (patient, type, visible_to_patient)

### Diagnosis — `clinical_diagnosis`

_Diagnóstico_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `doctor_id` | ForeignKey | sí |  | → agenda.Doctor (PROTECT) |
| `tooth_fdi_code` | CharField |  |  | máx. 2; Código FDI (ej. '26'); vacío si es diagnóstico general. |
| `code` | CharField |  |  | máx. 20; Código CIE-10. |
| `description` | TextField |  |  |  |
| `diagnosis_kind` | CharField |  | 'pre' | máx. 3; opciones: `pre`, `def`; PRE/DEF según formulario MSP 033. |
| `date` | DateField |  |  |  |
| `created_at` | DateTimeField |  |  | se fija al crear |

### TreatmentPlan — `clinical_treatmentplan`

_Plan de tratamiento_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `created_by_id` | ForeignKey | sí |  | → agenda.Doctor (PROTECT) |
| `status` | CharField |  | 'draft' | máx. 10; opciones: `draft`, `active`, `completed` |
| `notes` | TextField |  |  |  |
| `created_at` | DateTimeField |  |  | se fija al crear |

### TreatmentPlanItem — `clinical_treatmentplanitem`

_Ítem de plan de tratamiento_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `treatment_plan_id` | ForeignKey |  |  | → clinical.TreatmentPlan (CASCADE) |
| `treatment_id` | ForeignKey |  |  | → configuration.Treatment (PROTECT) |
| `tooth_fdi_code` | CharField |  |  | máx. 2 |
| `order` | PositiveIntegerField |  | 1 |  |
| `status` | CharField |  | 'planned' | máx. 15; opciones: `planned`, `in_progress`, `done` |
| `estimated_price` | DecimalField |  | 0 | 10,2 |
| `price_is_manual` | BooleanField |  | False |  |

- Orden por omisión: order

### OdontogramState — `clinical_odontogramstate`

_Estado de odontograma_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `code` | CharField |  |  | máx. 30 |
| `label` | CharField |  |  | máx. 100 |
| `color` | CharField |  | '#000000' | máx. 7; Color hex para la UI. |
| `order` | PositiveIntegerField |  | 0 |  |
| `is_active` | BooleanField |  | True |  |

- Restricción `unique_odontogram_state_code_per_tenant`: (tenant, code)
- Orden por omisión: order, code

### ToothRecord — `clinical_toothrecord`

_Registro de pieza dental_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `tooth_fdi_code` | CharField |  |  | máx. 2; Código FDI: 11-48 (permanente), 51-85 (temporal). |
| `surface` | CharField |  | 'whole' | máx. 20; opciones: `whole`, `vestibular`, `palatal_lingual`, `mesial`, `distal`, `occlusal` |
| `state_id` | ForeignKey |  |  | → clinical.OdontogramState (PROTECT) |
| `doctor_id` | ForeignKey | sí |  | → agenda.Doctor (PROTECT) |
| `treatment_plan_item_id` | ForeignKey | sí |  | → clinical.TreatmentPlanItem (SET_NULL) |
| `date` | DateField |  |  |  |
| `notes` | TextField |  |  |  |
| `mobility` | PositiveSmallIntegerField | sí |  | Movilidad 1-4 (formulario MSP 033). |
| `recession` | PositiveSmallIntegerField | sí |  | Recesión 1-4 (formulario MSP 033). |
| `created_at` | DateTimeField |  |  | se fija al crear |

- Índice: (patient, tooth_fdi_code, surface)
- Índice: (patient, -created_at)

### RadiographPhoto — `clinical_radiographphoto`

_Radiografía / Fotografía_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `tooth_fdi_code` | CharField |  |  | máx. 2 |
| `file` | FileField |  |  | máx. 100 |
| `type` | CharField |  | 'radiograph' | máx. 15; opciones: `radiograph`, `photo` |
| `description` | CharField |  |  | máx. 255 |
| `date` | DateField |  |  |  |
| `uploaded_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `created_at` | DateTimeField |  |  | se fija al crear |

### InformedConsent — `clinical_informedconsent`

_Consentimiento informado_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (PROTECT) |
| `treatment_plan_id` | ForeignKey | sí |  | → clinical.TreatmentPlan (SET_NULL) |
| `title` | CharField |  | 'Consentimiento informado' | máx. 200 |
| `body_text` | TextField |  |  | Texto del consentimiento que el paciente acepta. |
| `status` | CharField |  | 'draft' | máx. 10; opciones: `draft`, `pending`, `signed`, `void` |
| `procedure` | TextField |  |  | Descripción del procedimiento. |
| `benefits` | TextField |  |  | Beneficios. |
| `risks` | TextField |  |  | Riesgos y posibles complicaciones. |
| `alternatives` | TextField |  |  | Alternativas terapéuticas. |
| `observations` | TextField |  |  | Observaciones (opcional). |
| `pdf_file` | FileField | sí |  | máx. 100 |
| `signature_image` | FileField | sí |  | máx. 100 |
| `signed_at` | DateTimeField | sí |  |  |
| `ip_address` | GenericIPAddressField | sí |  | máx. 39 |
| `device_info` | CharField |  |  | máx. 255 |
| `created_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `created_at` | DateTimeField |  |  | se fija al crear |

### TreatmentPlanTemplate — `clinical_treatmentplantemplate`

_Plantilla de plan de tratamiento_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `name` | CharField |  |  | máx. 150 |
| `description` | TextField |  |  |  |
| `is_active` | BooleanField |  | True |  |

- Único: (tenant, name)

### TreatmentPlanTemplateItem — `clinical_treatmentplantemplateitem`

_treatment plan template item_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `template_id` | ForeignKey |  |  | → clinical.TreatmentPlanTemplate (CASCADE) |
| `treatment_id` | ForeignKey |  |  | → configuration.Treatment (PROTECT) |
| `order` | PositiveIntegerField |  | 1 |  |
| `notes` | CharField |  |  | máx. 255 |

- Orden por omisión: order

### Cie10 — `clinical_cie10`

_Código CIE-10_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | BigAutoField |  |  | clave primaria |
| `code` | CharField |  |  | único; máx. 10 |
| `description` | CharField |  |  | máx. 255 |

- Orden por omisión: code

### Form033Record — `clinical_form033record`

_Historia odontológica (Form 033)_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `motivo_consulta` | TextField |  |  |  |
| `embarazada` | BooleanField | sí |  |  |
| `enfermedad_actual` | TextField |  |  |  |
| `antecedentes_personales` | JSONField |  | dict() |  |
| `antecedentes_familiares` | JSONField |  | dict() |  |
| `temperatura` | DecimalField | sí |  | 4,1 |
| `pulso` | PositiveSmallIntegerField | sí |  |  |
| `frecuencia_respiratoria` | PositiveSmallIntegerField | sí |  |  |
| `presion_arterial` | CharField |  |  | máx. 15 |
| `examen_estomatognatico` | JSONField |  | dict() |  |
| `indicadores_salud_bucal` | JSONField |  | dict() |  |
| `doctor_id` | ForeignKey | sí |  | → agenda.Doctor (PROTECT) |
| `created_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `professional_snapshot` | JSONField |  | dict() |  |
| `date` | DateField |  |  |  |

- Orden por omisión: -date, -created_at

### ExamRequest — `clinical_examrequest`

_Pedido de examen_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `category` | CharField |  |  | máx. 20; opciones: `biometria`, `quimica_sanguinea`, `rayos_x`, `otros` |
| `detail` | CharField |  |  | máx. 255; Examen solicitado. |
| `justification` | TextField |  |  | Motivo o justificación clínica. |
| `observations` | TextField |  |  | Observaciones adicionales (opcional). |
| `priority` | CharField |  | 'normal' | máx. 10; opciones: `normal`, `urgent` |
| `status` | CharField |  | 'pending' | máx. 10; opciones: `pending`, `reported` |
| `report_notes` | TextField |  |  | M. Informe de exámenes. |
| `report_document_id` | ForeignKey | sí |  | → patients.PatientDocument (SET_NULL) |
| `requested_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `requested_at` | DateTimeField |  |  | se fija al crear |
| `reported_at` | DateTimeField | sí |  |  |

- Orden por omisión: -requested_at

### ConsentTemplate — `clinical_consenttemplate`

_Plantilla de consentimiento_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `procedure` | CharField |  |  | máx. 20; opciones: `extraccion`, `endodoncia`, `restauracion`, `profilaxis`, `cirugia`, `implante`, `protesis`, `ortodoncia`, `otro` |
| `title` | CharField |  |  | máx. 200 |
| `procedure_text` | TextField |  |  | Descripción del procedimiento. |
| `benefits` | TextField |  |  |  |
| `risks` | TextField |  |  |  |
| `alternatives` | TextField |  |  |  |
| `body_text` | TextField |  |  | Declaración de aceptación / cuerpo. |
| `created_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |

- Orden por omisión: procedure, title

### ConsentAuditLog — `clinical_consentauditlog`

_consent audit log_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `consent_id` | ForeignKey |  |  | → clinical.InformedConsent (CASCADE) |
| `action` | CharField |  |  | máx. 40 |
| `detail` | CharField |  |  | máx. 255 |
| `actor_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `at` | DateTimeField |  |  | se fija al crear |

- Orden por omisión: -at

### PeriodontalExam — `clinical_periodontalexam`

_Exploración periodontal_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `date` | DateField |  |  | Fecha de la exploración. |
| `notes` | TextField |  |  |  |
| `created_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |

- Orden por omisión: -date, -created_at

### PeriodontalTooth — `clinical_periodontaltooth`

_Pieza del periodontograma_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `exam_id` | ForeignKey |  |  | → clinical.PeriodontalExam (CASCADE) |
| `tooth_code` | CharField |  |  | máx. 2; Código FDI, p. ej. 16. |
| `is_present` | BooleanField |  | True | Pieza presente en boca. |
| `has_implant` | BooleanField |  | False |  |
| `mobility` | PositiveSmallIntegerField |  | 0 | Grado 0 a 3. |
| `furcation_buccal` | PositiveSmallIntegerField |  | 0 | Grado 0 a 3. |
| `furcation_lingual` | PositiveSmallIntegerField |  | 0 |  |
| `gum_width` | PositiveSmallIntegerField |  | 0 | Ancho de encía en mm. |
| `probing_depth` | JSONField |  | list() | 6 enteros (mm). |
| `gingival_margin` | JSONField |  | list() | 6 enteros (mm). |
| `bleeding` | JSONField |  | list() | 6 booleanos. |
| `plaque` | JSONField |  | list() | 6 booleanos. |
| `suppuration` | JSONField |  | list() | 6 booleanos. |
| `prognosis` | CharField |  | '' | máx. 10; opciones: `bueno`, `reservado`, `malo`, `imposible` |
| `notes` | CharField |  |  | máx. 255 |

- Restricción `unique_tooth_per_periodontal_exam`: (exam, tooth_code)
- Orden por omisión: tooth_code

## common

### Tenant — `common_tenant`

_Tenant (clínica)_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `name` | CharField |  |  | máx. 255 |
| `ruc` | CharField |  |  | máx. 20 |
| `address` | CharField |  |  | máx. 255 |
| `phone` | CharField |  |  | máx. 30 |
| `email` | CharField |  |  | máx. 254 |
| `is_active` | BooleanField |  | True |  |
| `funcionalidades` | JSONField |  | dict() | Qué módulos tiene esta clínica. El catálogo está en apps/common/funcionalidades.py. Apagar uno NO borra sus datos: deja de verse y de poder tocarse. |
| `modulos_clinica` | JSONField |  | dict() |  |
| `es_prueba` | BooleanField |  | False | Recibe las funciones nuevas antes que las demás. Lo que se prueba aquí no llega a otras clínicas hasta publicarlo desde Plataforma. |
| `modalidad` | CharField |  | 'clinica' | máx. 12; opciones: `clinica`, `consultorio` |
| `created_at` | DateTimeField |  |  | se fija al crear |

### PlatformConfiguration — `common_platformconfiguration`

_Configuración de plataforma_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `platform_name` | CharField |  | 'Clinube' | máx. 120 |
| `logo_url` | CharField |  |  | máx. 200 |
| `smtp_host` | CharField |  |  | máx. 255 |
| `smtp_port` | PositiveIntegerField |  | 587 |  |
| `smtp_user` | CharField |  |  | máx. 255 |
| `smtp_password` | CharField |  |  | máx. 255 |
| `timezone` | CharField |  | 'America/Guayaquil' | máx. 64 |
| `currency` | CharField |  | 'USD' | máx. 8 |
| `titular_nombre` | CharField |  |  | máx. 200 |
| `titular_ruc` | CharField |  |  | máx. 20 |
| `titular_correo` | CharField |  |  | máx. 254 |
| `proveedor_correo` | CharField |  |  | máx. 120; El servicio que envía los correos (p. ej. «Brevo»). Sale en el aviso de privacidad. |
| `canal_codigo_paciente` | CharField |  | 'correo' | máx. 10; opciones: `whatsapp`, `correo` |
| `google_client_id` | CharField |  |  | máx. 200; De Google Cloud → APIs y servicios → Credenciales. Termina en .apps.googleusercontent.com. |
| `funciones_publicadas` | JSONField |  | list() |  |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |

### AceptacionCondiciones — `common_aceptacioncondiciones`

_Aceptación de condiciones_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `version` | CharField |  |  | máx. 20 |
| `aceptada_por_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `nombre` | CharField |  |  | máx. 255 |
| `correo` | CharField |  |  | máx. 254 |
| `ip` | GenericIPAddressField | sí |  | máx. 39 |

- Orden por omisión: -created_at

### SolicitudClinica — `common_solicitudclinica`

_Solicitud de clínica_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `tipo` | CharField |  |  | máx. 12; opciones: `odontologia`, `medicina`, `psicologia` |
| `estado` | CharField |  |  | máx. 12; opciones: `verificando`, `pendiente`, `creada`, `atendida`, `descartada` |
| `clinica` | CharField |  |  | máx. 150 |
| `ruc` | CharField |  |  | máx. 13 |
| `ciudad` | CharField |  |  | máx. 80 |
| `nombre` | CharField |  |  | máx. 150 |
| `correo` | CharField |  |  | máx. 254 |
| `telefono` | CharField |  |  | máx. 20 |
| `mensaje` | TextField |  |  |  |
| `modalidad` | CharField |  | 'clinica' | máx. 12; opciones: `clinica`, `consultorio` |
| `codigo_hash` | CharField |  |  | máx. 128 |
| `codigo_vence` | DateTimeField | sí |  |  |
| `intentos` | PositiveSmallIntegerField |  | 0 |  |
| `tenant_id` | ForeignKey | sí |  | → common.Tenant (SET_NULL) |
| `ip` | GenericIPAddressField | sí |  | máx. 39 |
| `nota` | CharField |  |  | máx. 300 |

- Orden por omisión: -created_at

## configuration

### Treatment — `configuration_treatment`

_Tratamiento_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `name` | CharField |  |  | máx. 150 |
| `specialty_id` | ForeignKey |  |  | → specialties.Specialty (PROTECT) |
| `base_price` | DecimalField |  | 0 | 10,2 |
| `consumes_inventory` | BooleanField |  | False |  |
| `is_active` | BooleanField |  | True |  |

- Índice: (tenant, specialty)

### Agreement — `configuration_agreement`

_Convenio_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `name` | CharField |  |  | máx. 150 |
| `discount_percentage` | DecimalField | sí |  | 5,2 |
| `is_active` | BooleanField |  | True |  |

### Tariff — `configuration_tariff`

_Tarifario_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `treatment_id` | ForeignKey |  |  | → configuration.Treatment (CASCADE) |
| `agreement_id` | ForeignKey | sí |  | → configuration.Agreement (CASCADE) |
| `price` | DecimalField |  |  | 10,2 |

- Restricción `unique_tariff_per_treatment_agreement`: (treatment, agreement)

### SystemParameter — `configuration_systemparameter`

_Parámetro del sistema_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `key` | CharField |  |  | máx. 100 |
| `value` | CharField |  |  | máx. 255 |
| `description` | TextField |  |  |  |

- Restricción `unique_parameter_key_per_tenant`: (tenant, key)

### TreatmentInventoryItem — `configuration_treatmentinventoryitem`

_Insumo de tratamiento_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `treatment_id` | ForeignKey |  |  | → configuration.Treatment (CASCADE) |
| `product_id` | ForeignKey |  |  | → inventory.Product (CASCADE) |
| `quantity_used` | DecimalField |  |  | 10,2 |

### ClinicBranding — `configuration_clinicbranding`

_clinic branding_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `logo` | FileField | sí |  | máx. 100 |
| `logo_oscuro` | FileField | sí |  | máx. 100 |
| `icono` | FileField | sí |  | máx. 100 |
| `paleta` | JSONField |  | list() |  |
| `temas` | JSONField |  | list() |  |
| `theme` | JSONField |  | _default_theme() |  |
| `display_name` | CharField |  |  | máx. 120; Nombre comercial de la clínica. |
| `short_name` | CharField |  |  | máx. 40; Nombre corto (opcional, para espacios reducidos). |
| `address` | CharField |  |  | máx. 200; Dirección de la clínica. |
| `phone` | CharField |  |  | máx. 40; Teléfono de contacto. |
| `email` | CharField |  |  | máx. 254; Correo electrónico institucional. |

- Restricción `uniq_branding_per_tenant`: (tenant)

### DocumentAppearance — `configuration_documentappearance`

_Apariencia de documentos_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `header` | JSONField |  | _default_doc_header() |  |
| `footer` | JSONField |  | _default_doc_footer() |  |
| `typography` | JSONField |  | _default_doc_typography() |  |
| `palette` | JSONField |  | _default_doc_palette() |  |
| `tables` | JSONField |  | _default_doc_tables() |  |
| `page` | JSONField |  | _default_doc_page() |  |
| `logo` | JSONField |  | _default_doc_logo() |  |
| `signature` | JSONField |  | _default_doc_signature() |  |
| `watermark` | JSONField |  | _default_doc_watermark() |  |

- Restricción `uniq_docappearance_per_tenant`: (tenant)

## finanzas

### ConfiguracionFinanzas — `finanzas_configuracionfinanzas`

_Configuración de finanzas_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `salario_basico` | DecimalField |  | Decimal('482.00') | 8,2; SBU vigente. 482 US$ en 2026. Sirve para el décimo cuarto. |
| `aporte_personal_iess` | DecimalField |  | Decimal('9.45') | 5,2 |
| `aporte_patronal_iess` | DecimalField |  | Decimal('11.15') | 5,2 |
| `aporte_iece_secap` | DecimalField |  | Decimal('1.00') | 5,2; 0,5 % + 0,5 % que paga el empleador junto al aporte patronal. |
| `fondos_reserva` | DecimalField |  | Decimal('8.33') | 5,2; Desde el segundo año de trabajo. |
| `retencion_honorarios` | DecimalField |  | Decimal('10.00') | 5,2; Impuesto a la Renta que se retiene al profesional que factura a la clínica. |
| `siguiente_comprobante` | PositiveIntegerField |  | 1 |  |
| `region` | CharField |  | 'sierra' | máx. 6; opciones: `sierra`, `costa` |
| `recargo_suplementarias` | DecimalField |  | Decimal('50.00') | 5,2; Hasta las 24:00 y en días laborables. 50 % según el Código del Trabajo. |
| `recargo_extraordinarias` | DecimalField |  | Decimal('100.00') | 5,2; Fines de semana, feriados y de 24:00 a 06:00. 100 %. |

- Restricción `finanzas_config_unica`: (tenant)

### CategoriaEgreso — `finanzas_categoriaegreso`

_Categoría de egreso_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `nombre` | CharField |  |  | máx. 80 |
| `clave` | CharField |  |  | máx. 30 |
| `activa` | BooleanField |  | True |  |
| `orden` | PositiveSmallIntegerField |  | 50 |  |

- Orden por omisión: orden, nombre

### Egreso — `finanzas_egreso`

_Egreso_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `fecha` | DateField |  |  | Del pago o, si está por pagar, de la factura. |
| `categoria_id` | ForeignKey |  |  | → finanzas.CategoriaEgreso (PROTECT) |
| `concepto` | CharField |  |  | máx. 200 |
| `monto` | DecimalField |  |  | 12,2 |
| `forma_pago` | CharField |  | 'efectivo' | máx. 15; opciones: `efectivo`, `transferencia`, `tarjeta`, `cheque` |
| `estado` | CharField |  | 'pagado' | máx. 10; opciones: `pagado`, `por_pagar` |
| `vence` | DateField | sí |  | Para las cuentas por pagar. |
| `proveedor` | CharField |  |  | máx. 150 |
| `proveedor_ruc` | CharField |  |  | máx. 13 |
| `numero_factura` | CharField |  |  | máx. 20; Como viene en la factura: 001-001-000000123. |
| `comprobante` | FileField | sí |  | máx. 100 |
| `profesional_id` | ForeignKey | sí |  | → accounts.User (PROTECT) |
| `descontar_al_profesional` | BooleanField |  | False | Se resta de lo que se le paga (p. ej. el laboratorio de sus casos). |
| `origen` | CharField |  |  | máx. 20; Quién lo creó si no fue a mano: «liquidacion», «rol», «inventario», «iess», «sri», «decimo_tercero» o «decimo_cuarto». |
| `periodo` | DateField | sí |  |  |
| `registrado_por_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `anulado` | BooleanField |  | False |  |
| `motivo_anulacion` | CharField |  |  | máx. 200 |

- Índice: (tenant, fecha)
- Orden por omisión: -fecha, -created_at

### CierreCaja — `finanzas_cierrecaja`

_Cierre de caja_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `fecha` | DateField |  |  |  |
| `saldo_inicial` | DecimalField |  | Decimal('0.00') | 12,2 |
| `cobros_efectivo` | DecimalField |  | Decimal('0.00') | 12,2 |
| `egresos_efectivo` | DecimalField |  | Decimal('0.00') | 12,2 |
| `esperado` | DecimalField |  | Decimal('0.00') | 12,2 |
| `contado` | DecimalField |  |  | 12,2 |
| `diferencia` | DecimalField |  | Decimal('0.00') | 12,2 |
| `retirado` | DecimalField |  | Decimal('0.00') | 12,2 |
| `observaciones` | CharField |  |  | máx. 300 |
| `cerrado_por_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |

- Restricción `un_cierre_por_dia`: (tenant, fecha)
- Orden por omisión: -fecha

### PerfilLaboral — `finanzas_perfillaboral`

_Perfil laboral_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `usuario_id` | OneToOneField |  |  | → accounts.User (CASCADE); único |
| `modalidad` | CharField |  | 'ninguna' | máx. 12; opciones: `honorarios`, `dependencia`, `ninguna` |
| `cedula` | CharField |  |  | máx. 13 |
| `cargo` | CharField |  |  | máx. 80 |
| `base_honorarios` | CharField |  | 'cobrado' | máx. 10; opciones: `cobrado`, `fijo` |
| `porcentaje` | DecimalField |  | Decimal('40.00') | 5,2 |
| `monto_fijo` | DecimalField |  | Decimal('0.00') | 10,2 |
| `emite_factura` | BooleanField |  | True | Si factura a la clínica, se le retiene el Impuesto a la Renta. |
| `sueldo` | DecimalField |  | Decimal('0.00') | 10,2 |
| `fecha_ingreso` | DateField | sí |  |  |
| `decimo_tercero_mensual` | BooleanField |  | False | Cobrarlo cada mes en vez de en diciembre. |
| `decimo_cuarto_mensual` | BooleanField |  | False | Cobrarlo cada mes en vez de una vez al año. |
| `fondos_reserva_mensual` | BooleanField |  | True | Cobrarlos cada mes en el rol en vez de que se acumulen en el IESS. |

### Liquidacion — `finanzas_liquidacion`

_Liquidación de honorarios_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `numero` | PositiveIntegerField |  |  |  |
| `profesional_id` | ForeignKey |  |  | → accounts.User (PROTECT) |
| `desde` | DateField |  |  |  |
| `hasta` | DateField |  |  |  |
| `base` | DecimalField |  | Decimal('0.00') | 12,2; Lo cobrado a sus pacientes en el período. |
| `porcentaje` | DecimalField |  | Decimal('0.00') | 5,2 |
| `honorario` | DecimalField |  | Decimal('0.00') | 12,2 |
| `descuentos` | DecimalField |  | Decimal('0.00') | 12,2 |
| `ajustes` | DecimalField |  | Decimal('0.00') | 12,2; Bonos (+) o anticipos (−) puestos a mano. |
| `retencion_porcentaje` | DecimalField |  | Decimal('0.00') | 5,2 |
| `retencion` | DecimalField |  | Decimal('0.00') | 12,2 |
| `a_pagar` | DecimalField |  | Decimal('0.00') | 12,2 |
| `detalle` | JSONField |  | dict() |  |
| `nota` | CharField |  |  | máx. 300 |
| `estado` | CharField |  | 'borrador' | máx. 10; opciones: `borrador`, `pagada`, `anulada` |
| `egreso_id` | OneToOneField | sí |  | → finanzas.Egreso (SET_NULL); único |
| `creada_por_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |

- Orden por omisión: -hasta, -numero

### RolPagos — `finanzas_rolpagos`

_Rol de pagos_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `empleado_id` | ForeignKey |  |  | → accounts.User (PROTECT) |
| `mes` | DateField |  |  | El día 1 del mes del rol. |
| `dias_trabajados` | PositiveSmallIntegerField |  | 30 |  |
| `horas_extra` | DecimalField |  | Decimal('0.00') | 10,2; Otro valor por horas extra, en dólares. |
| `horas_suplementarias` | DecimalField |  | Decimal('0.00') | 6,2; Número de horas con recargo del 50 %. |
| `horas_extraordinarias` | DecimalField |  | Decimal('0.00') | 6,2; Número de horas con recargo del 100 %. |
| `otros_ingresos` | DecimalField |  | Decimal('0.00') | 10,2; Bonos o comisiones. |
| `anticipos` | DecimalField |  | Decimal('0.00') | 10,2 |
| `prestamos_iess` | DecimalField |  | Decimal('0.00') | 10,2 |
| `otros_descuentos` | DecimalField |  | Decimal('0.00') | 10,2 |
| `calculo` | JSONField |  | dict() |  |
| `neto` | DecimalField |  | Decimal('0.00') | 12,2 |
| `costo_empleador` | DecimalField |  | Decimal('0.00') | 12,2 |
| `estado` | CharField |  | 'borrador' | máx. 10; opciones: `borrador`, `pagado`, `anulado` |
| `egreso_id` | OneToOneField | sí |  | → finanzas.Egreso (SET_NULL); único |
| `creado_por_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |

- Restricción `un_rol_por_mes`: (tenant, empleado, mes) si (NOT (AND: ('estado', 'anulado')))
- Orden por omisión: -mes

## inventory

### Product — `inventory_product`

_Producto_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `name` | CharField |  |  | máx. 150 |
| `unit` | CharField |  | 'unidad' | máx. 30; ej. unidad, ml, caja |
| `min_stock` | DecimalField |  | 0 | 10,2; Umbral de alerta de stock mínimo (RF-INV-03). |
| `is_active` | BooleanField |  | True |  |

### Batch — `inventory_batch`

_Lote_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `product_id` | ForeignKey |  |  | → inventory.Product (CASCADE) |
| `batch_number` | CharField |  |  | máx. 100 |
| `quantity` | DecimalField |  | 0 | 10,2 |
| `expiration_date` | DateField | sí |  |  |
| `received_at` | DateField |  |  | se fija al crear |

- Índice: (expiration_date)
- Orden por omisión: expiration_date

### InventoryMovement — `inventory_inventorymovement`

_Movimiento de inventario_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `id` | UUIDField |  | uuid4() | clave primaria |
| `product_id` | ForeignKey |  |  | → inventory.Product (PROTECT) |
| `batch_id` | ForeignKey | sí |  | → inventory.Batch (SET_NULL) |
| `movement_type` | CharField |  |  | máx. 5; opciones: `in`, `out` |
| `quantity` | DecimalField |  |  | 10,2 |
| `reason` | CharField |  |  | máx. 15; opciones: `purchase`, `consumption`, `adjustment` |
| `related_treatment_plan_item_id` | ForeignKey | sí |  | → clinical.TreatmentPlanItem (SET_NULL) |
| `date` | DateTimeField |  |  | se fija al crear |

- Índice: (tenant, -date)
- Orden por omisión: -date

## logros

### Logro — `logros_logro`

_Logro_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `nombre` | CharField |  |  | máx. 80 |
| `descripcion` | CharField |  |  | máx. 200; Lo que el paciente lee en la app. |
| `icono` | CharField |  | 'estrella' | máx. 30; estrella · diente · racha · corazon · escudo · regalo |
| `beneficio` | CharField |  |  | máx. 200; Lo que gana. Informativo: no se aplica solo al presupuesto. |
| `regla` | CharField |  | 'manual' | máx. 25; opciones: `manual`, `asistencia_mensual`, `al_dia_pagos` |
| `meses_requeridos` | PositiveSmallIntegerField |  | 1 |  |
| `activo` | BooleanField |  | True |  |

- Restricción `logro_unico_por_clinica`: (tenant, nombre)
- Orden por omisión: nombre

### LogroDePaciente — `logros_logrodepaciente`

_Logro de paciente_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `logro_id` | ForeignKey |  |  | → logros.Logro (PROTECT) |
| `otorgado_en` | DateTimeField |  |  | se fija al crear |
| `otorgado_por_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `periodo` | DateField | sí |  | Primer día del mes que se premia. Nulo si es manual. |
| `nota` | CharField |  |  | máx. 200 |

- Restricción `un_logro_por_paciente_y_periodo`: (patient, logro, periodo) si (AND: ('periodo__isnull', False))
- Orden por omisión: -otorgado_en

## patients

### Patient — `patients_patient`

_Paciente_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `is_active` | BooleanField |  | True |  |
| `deleted_at` | DateTimeField | sí |  |  |
| `user_id` | OneToOneField | sí |  | → accounts.User (SET_NULL); único; Solo se llena si el paciente usa la app/portal. |
| `first_name` | CharField |  |  | máx. 100 |
| `last_name` | CharField |  |  | máx. 100 |
| `national_id` | CharField |  |  | máx. 20; Cédula o pasaporte |
| `birth_date` | DateField | sí |  |  |
| `sex` | CharField |  |  | máx. 1; opciones: `H`, `M`; Literal A del formulario MSP 033. |
| `phone` | CharField |  |  | máx. 20 |
| `email` | CharField |  |  | máx. 254 |
| `address` | CharField |  |  | máx. 255 |
| `photo` | FileField | sí |  | máx. 100 |
| `agreement_id` | ForeignKey | sí |  | → configuration.Agreement (SET_NULL); Convenio o aseguradora que cubre al paciente (RF-CFG-04). Vacío = paciente particular. |

- Restricción `unique_national_id_per_tenant`: (tenant, national_id) si (AND: ('is_active', True))
- Índice: (tenant, national_id)
- Índice: (tenant, last_name, first_name)
- Índice: (tenant, created_at)

### MedicalBackground — `patients_medicalbackground`

_Antecedente médico_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | BigAutoField |  |  | clave primaria |
| `patient_id` | OneToOneField |  |  | → patients.Patient (CASCADE); único |
| `allergies` | TextField |  |  |  |
| `medications` | TextField |  |  |  |
| `conditions` | TextField |  |  |  |
| `is_pregnant` | BooleanField | sí |  |  |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `updated_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |

### PatientDocument — `patients_patientdocument`

_Documento de paciente_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | BigAutoField |  |  | clave primaria |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `doc_type` | CharField |  |  | máx. 20; opciones: `identification`, `medical_order`, `referral`, `radiograph`, `photo`, `exam`, `report`, `other` |
| `file` | FileField |  |  | máx. 100 |
| `description` | CharField |  |  | máx. 255 |
| `uploaded_by_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |
| `uploaded_at` | DateTimeField |  |  | se fija al crear |
| `is_active` | BooleanField |  | True |  |

### AvisoPrivacidadEntregado — `patients_avisoprivacidadentregado`

_Aviso de privacidad entregado_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `version` | CharField |  |  | máx. 20 |
| `medio` | CharField |  | 'en_persona' | máx. 20; opciones: `en_persona`, `enlace` |
| `registrado_por_id` | ForeignKey | sí |  | → accounts.User (SET_NULL) |

- Orden por omisión: -created_at

## specialties

### Specialty — `specialties_specialty`

_Especialidad_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `name` | CharField |  |  | máx. 100 |
| `description` | TextField |  |  |  |
| `is_active` | BooleanField |  | True |  |

- Restricción `unique_specialty_name_per_tenant`: (tenant, name)

### SpecialtyForm — `specialties_specialtyform`

_Formulario de especialidad_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `specialty_id` | ForeignKey |  |  | → specialties.Specialty (PROTECT) |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `doctor_id` | ForeignKey |  |  | → agenda.Doctor (PROTECT) |
| `date` | DateField |  |  |  |
| `form_data` | JSONField |  | dict() | Campos específicos de la especialidad (estructura flexible). |
| `created_at` | DateTimeField |  |  | se fija al crear |

- Índice: (patient, specialty)

## whatsapp

### WhatsAppTemplate — `whatsapp_whatsapptemplate`

_Plantilla de WhatsApp_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `name` | CharField |  |  | máx. 100 |
| `meta_template_name` | CharField |  |  | máx. 100 |
| `category` | CharField |  |  | máx. 20; opciones: `authentication`, `utility`, `marketing` |
| `language` | CharField |  | 'es' | máx. 10 |
| `variables` | JSONField |  | dict() |  |
| `is_active` | BooleanField |  | True |  |

### WhatsAppMessageLog — `whatsapp_whatsappmessagelog`

_Registro de mensaje WhatsApp_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_phone` | CharField |  |  | máx. 20 |
| `template_id` | ForeignKey | sí |  | → whatsapp.WhatsAppTemplate (SET_NULL) |
| `status` | CharField |  | 'queued' | máx. 20; opciones: `queued`, `sent`, `delivered`, `read`, `failed` |
| `provider_message_id` | CharField |  |  | máx. 100 |
| `raw_payload` | JSONField |  | dict() |  |

### WhatsAppOptIn — `whatsapp_whatsappoptin`

_Opt-in de WhatsApp_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `patient_id` | ForeignKey |  |  | → patients.Patient (CASCADE) |
| `opted_in_at` | DateTimeField |  |  | se fija al crear |
| `channel` | CharField |  | 'registro_recepcion' | máx. 50; Canal por el que el paciente dio su consentimiento. |
| `revoked_at` | DateTimeField | sí |  |  |

### ConfiguracionWhatsApp — `whatsapp_configuracionwhatsapp`

_Configuración de WhatsApp_

| Campo | Tipo | Nulo | Por omisión | Detalle |
|---|---|---|---|---|
| `id` | UUIDField |  | uuid4() | clave primaria |
| `tenant_id` | ForeignKey |  |  | → common.Tenant (PROTECT) |
| `created_at` | DateTimeField |  |  | se fija al crear |
| `updated_at` | DateTimeField |  |  | se actualiza al guardar |
| `phone_number_id` | CharField |  |  | máx. 60 |
| `numero_visible` | CharField |  |  | máx. 30; Con código de país, p. ej. +593999111222. |
| `access_token_cifrado` | TextField |  | '' |  |
| `plantilla_recordatorio` | CharField |  | 'recordatorio_cita' | máx. 80; Nombre de la plantilla aprobada en Meta. |
| `activo` | BooleanField |  | False | Mientras esté apagado no sale ningún mensaje automático. |
| `comprobado_en` | DateTimeField | sí |  |  |

- Restricción `una_configuracion_whatsapp_por_clinica`: (tenant)

