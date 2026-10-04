# La aplicación de Celery se carga con Django. Sin esto, las tareas que se
# encolan desde una petición (el aviso al doctor de que su paciente llegó)
# usaban una aplicación de Celery por defecto, sin la configuración de
# settings: intentaban hablar con un broker inexistente y el aviso no
# salía nunca. El worker y beat sí la cargaban (`celery -A config`).
from .celery import app as celery_app

__all__ = ("celery_app",)
