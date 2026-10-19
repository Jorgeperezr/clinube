"""
Quién atiende pacientes, además de quien tiene el rol de doctor.

Un profesional que trabaja solo es a la vez el administrador de su
consultorio y quien atiende: necesita su ficha `Doctor` para aparecer en
la agenda, firmar recetas y que la historia quede a su nombre, sin dejar
de administrar. Lo mismo vale para el dueño de una clínica que también
atiende. Lo que decide si alguien atiende es que tenga una ficha `Doctor`
activa, no el rol.

Dejar de atender no borra la ficha —de ella cuelgan citas e historia—,
solo la desactiva; volver a marcarlo la reactiva con su firma y su
registro intactos.
"""

from apps.agenda.models import Doctor


def atiende(user):
    if not user.tenant_id:
        return False
    return Doctor.objects.filter(tenant_id=user.tenant_id, user=user, is_active=True).exists()


def cambiar(user, valor):
    if valor:
        doctor, creada = Doctor.objects.get_or_create(tenant_id=user.tenant_id, user=user)
        if not creada and not doctor.is_active:
            doctor.is_active = True
            doctor.save(update_fields=["is_active"])
    else:
        Doctor.objects.filter(tenant_id=user.tenant_id, user=user).update(is_active=False)
