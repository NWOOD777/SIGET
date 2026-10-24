import re
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from siget.db import bloquear_operacion, siguiente_codigo
from siget.http import direccion_ip_cliente
from usuarios.models import Usuario
from usuarios.services import registrar_auditoria

from .models import (
    Activo,
    CategoriaActivo,
    EstadoActivo,
    Marca,
    ModeloActivo,
    Ubicacion,
)

LOCK_CATEGORIA = 70410
LOCK_MARCA = 70411
LOCK_MODELO = 70412
LOCK_UBICACION = 70413


def normalizar_espacios(valor: str) -> str:
    """Recorta espacios exteriores y colapsa espacios internos múltiples."""
    return " ".join(valor.strip().split())


def clave_normalizada(valor: str | None) -> str:
    """Clave canónica insensible a mayúsculas/minúsculas y espacios."""
    if not valor:
        return ""
    return normalizar_espacios(str(valor)).casefold()


def validar_texto_requerido(valor: Any, etiqueta: str, max_length: int) -> str:
    if not isinstance(valor, str):
        raise serializers.ValidationError(f"El campo {etiqueta} debe ser una cadena de texto válida.")
    limpio = normalizar_espacios(valor)
    if not limpio:
        raise serializers.ValidationError(
            f"El campo {etiqueta} es obligatorio y no puede contener solo espacios."
        )
    if len(limpio) > max_length:
        raise serializers.ValidationError(
            f"El campo {etiqueta} no puede superar los {max_length} caracteres."
        )
    return limpio


def validar_texto_opcional(valor: Any, etiqueta: str, max_length: int) -> str | None:
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise serializers.ValidationError(f"El campo {etiqueta} debe ser una cadena de texto válida.")
    if valor == "":
        return None
    limpio = normalizar_espacios(valor)
    if not limpio:
        raise serializers.ValidationError(
            f"El campo {etiqueta} no puede estar compuesto solo por espacios."
        )
    if len(limpio) > max_length:
        raise serializers.ValidationError(
            f"El campo {etiqueta} no puede superar los {max_length} caracteres."
        )
    return limpio


def auditar_evento_activos(
    request: Any,
    accion: str,
    entidad_afectada: str,
    id_registro_afectado: int | None,
    detalle_evento: str,
) -> None:
    """Registra auditoría reutilizando usuarios.services.registrar_auditoria."""
    usuario = getattr(request, "user", None)
    registrar_auditoria(
        usuario=usuario if isinstance(usuario, Usuario) else None,
        modulo="ACTIVOS",
        accion=accion,
        entidad_afectada=entidad_afectada,
        id_registro_afectado=id_registro_afectado,
        detalle_evento=detalle_evento,
        direccion_ip=direccion_ip_cliente(request) if request is not None else None,
    )


class _CatalogoBaseSerializer(serializers.ModelSerializer):
    CamposTexto: tuple[str, ...] = ()
    CamposEnterosRelacion: tuple[str, ...] = ()

    def _refrescar_instancia(self, instance: Any) -> None:
        """Revalida la existencia del registro al adquirir el bloqueo de escritura."""
        try:
            instance.refresh_from_db()
        except ObjectDoesNotExist as exc:
            raise NotFound("El registro del catálogo ya no existe.") from exc

    def to_internal_value(self, data: Any) -> Any:
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                {"detail": ["El cuerpo de la solicitud debe ser un objeto JSON válido."]}
            )
        errores: dict[str, list[str]] = {}
        for campo in self.CamposTexto:
            if campo in data and data[campo] is not None and not isinstance(data[campo], str):
                errores[campo] = ["Debe ingresar una cadena de texto válida."]
        for campo in self.CamposEnterosRelacion:
            if campo not in data or data[campo] is None:
                continue
            valor = data[campo]
            es_entero = type(valor) is int
            es_cadena_numerica = (
                isinstance(valor, str)
                and valor.strip().isascii()
                and valor.strip().isdecimal()
            )
            if not (es_entero or es_cadena_numerica):
                errores[campo] = ["Debe indicar un identificador entero válido."]
        if errores:
            raise serializers.ValidationError(errores)
        return super().to_internal_value(data)


class CategoriaActivoSerializer(_CatalogoBaseSerializer):
    CamposTexto = ("nombre", "descripcion")

    class Meta:
        model = CategoriaActivo
        fields = [
            "id_categoria",
            "nombre",
            "descripcion",
        ]
        read_only_fields = ["id_categoria"]
        extra_kwargs = {
            "nombre": {
                "trim_whitespace": False,
                "allow_blank": True,
                "validators": [],
                "max_length": 500,
            },
            "descripcion": {
                "trim_whitespace": False,
                "allow_blank": True,
                "allow_null": True,
                "required": False,
                "max_length": 500,
            },
        }

    def validate_nombre(self, value: Any) -> str:
        return validar_texto_requerido(value, "nombre", 100)

    def validate_descripcion(self, value: Any) -> str | None:
        return validar_texto_opcional(value, "descripcion", 255)

    def _validar_unicidad(self, attrs: dict[str, Any]) -> None:
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", ""))
        clave = clave_normalizada(nombre)
        qs = CategoriaActivo.objects.all()
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if any(clave_normalizada(item.nombre) == clave for item in qs):
            raise serializers.ValidationError(
                {"nombre": ["Ya existe una categoría registrada con un nombre equivalente."]}
            )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        self._validar_unicidad(attrs)
        return attrs

    def create(self, validated_data: dict[str, Any]) -> CategoriaActivo:
        try:
            with transaction.atomic():
                bloquear_operacion(LOCK_CATEGORIA)
                self._validar_unicidad(validated_data)
                categoria = CategoriaActivo.objects.create(**validated_data)
                auditar_evento_activos(
                    self.context.get("request"),
                    accion="CATEGORIA_CREADA",
                    entidad_afectada="categoria_activo",
                    id_registro_afectado=categoria.pk,
                    detalle_evento=(
                        f"CATEGORIA_CREADA: nombre='{categoria.nombre}', "
                        f"descripcion='{categoria.descripcion or '—'}'."
                    ),
                )
                return categoria
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"nombre": ["Ya existe una categoría registrada con un nombre equivalente."]}
            ) from exc

    def update(self, instance: CategoriaActivo, validated_data: dict[str, Any]) -> CategoriaActivo:
        try:
            with transaction.atomic():
                bloquear_operacion(LOCK_CATEGORIA)
                self._refrescar_instancia(instance)
                prev_nombre = instance.nombre
                prev_desc = instance.descripcion
                self._validar_unicidad(validated_data)
                categoria = super().update(instance, validated_data)
                auditar_evento_activos(
                    self.context.get("request"),
                    accion="CATEGORIA_MODIFICADA",
                    entidad_afectada="categoria_activo",
                    id_registro_afectado=categoria.pk,
                    detalle_evento=(
                        f"CATEGORIA_MODIFICADA: ID {categoria.pk}. "
                        f"Antes: nombre='{prev_nombre}', descripcion='{prev_desc or '—'}'. "
                        f"Ahora: nombre='{categoria.nombre}', descripcion='{categoria.descripcion or '—'}'."
                    ),
                )
                return categoria
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"nombre": ["Ya existe una categoría registrada con un nombre equivalente."]}
            ) from exc


class MarcaSerializer(_CatalogoBaseSerializer):
    CamposTexto = ("nombre",)

    class Meta:
        model = Marca
        fields = [
            "id_marca",
            "nombre",
        ]
        read_only_fields = ["id_marca"]
        extra_kwargs = {
            "nombre": {
                "trim_whitespace": False,
                "allow_blank": True,
                "validators": [],
                "max_length": 500,
            },
        }

    def validate_nombre(self, value: Any) -> str:
        return validar_texto_requerido(value, "nombre", 100)

    def _validar_unicidad(self, attrs: dict[str, Any]) -> None:
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", ""))
        clave = clave_normalizada(nombre)
        qs = Marca.objects.all()
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if any(clave_normalizada(item.nombre) == clave for item in qs):
            raise serializers.ValidationError(
                {"nombre": ["Ya existe una marca registrada con un nombre equivalente."]}
            )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        self._validar_unicidad(attrs)
        return attrs

    def create(self, validated_data: dict[str, Any]) -> Marca:
        try:
            with transaction.atomic():
                bloquear_operacion(LOCK_MARCA)
                self._validar_unicidad(validated_data)
                marca = Marca.objects.create(**validated_data)
                auditar_evento_activos(
                    self.context.get("request"),
                    accion="MARCA_CREADA",
                    entidad_afectada="marca",
                    id_registro_afectado=marca.pk,
                    detalle_evento=f"MARCA_CREADA: nombre='{marca.nombre}'.",
                )
                return marca
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"nombre": ["Ya existe una marca registrada con un nombre equivalente."]}
            ) from exc

    def update(self, instance: Marca, validated_data: dict[str, Any]) -> Marca:
        try:
            with transaction.atomic():
                bloquear_operacion(LOCK_MARCA)
                self._refrescar_instancia(instance)
                prev_nombre = instance.nombre
                self._validar_unicidad(validated_data)
                marca = super().update(instance, validated_data)
                auditar_evento_activos(
                    self.context.get("request"),
                    accion="MARCA_MODIFICADA",
                    entidad_afectada="marca",
                    id_registro_afectado=marca.pk,
                    detalle_evento=(
                        f"MARCA_MODIFICADA: ID {marca.pk}. "
                        f"Antes: nombre='{prev_nombre}'. Ahora: nombre='{marca.nombre}'."
                    ),
                )
                return marca
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"nombre": ["Ya existe una marca registrada con un nombre equivalente."]}
            ) from exc


class ModeloActivoSerializer(_CatalogoBaseSerializer):
    CamposTexto = ("nombre",)
    CamposEnterosRelacion = ("id_marca", "id_categoria")

    marca = serializers.CharField(
        source="id_marca.nombre",
        read_only=True,
    )

    categoria = serializers.CharField(
        source="id_categoria.nombre",
        read_only=True,
    )

    class Meta:
        model = ModeloActivo
        fields = [
            "id_modelo",
            "nombre",
            "id_marca",
            "id_categoria",
            "marca",
            "categoria",
        ]
        read_only_fields = ["id_modelo", "marca", "categoria"]
        validators = []
        extra_kwargs = {
            "nombre": {
                "trim_whitespace": False,
                "allow_blank": True,
                "max_length": 500,
            },
        }

    def validate_nombre(self, value: Any) -> str:
        return validar_texto_requerido(value, "nombre", 100)

    def _validar_reglas_modelo(self, attrs: dict[str, Any]) -> None:
        marca_obj = attrs.get("id_marca", getattr(self.instance, "id_marca", None))
        categoria_obj = attrs.get("id_categoria", getattr(self.instance, "id_categoria", None))
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", ""))

        if marca_obj is None or not Marca.objects.filter(pk=marca_obj.pk).exists():
            raise serializers.ValidationError({"id_marca": ["La marca indicada no existe."]})
        if categoria_obj is None or not CategoriaActivo.objects.filter(pk=categoria_obj.pk).exists():
            raise serializers.ValidationError({"id_categoria": ["La categoría indicada no existe."]})

        if self.instance is not None:
            cambio_marca = marca_obj.pk != self.instance.id_marca.pk
            cambio_categoria = categoria_obj.pk != self.instance.id_categoria.pk
            if (cambio_marca or cambio_categoria) and Activo.objects.filter(id_modelo=self.instance).exists():
                errores: dict[str, list[str]] = {}
                if cambio_marca:
                    errores["id_marca"] = [
                        "No se puede cambiar la marca de un modelo que ya tiene activos asociados."
                    ]
                if cambio_categoria:
                    errores["id_categoria"] = [
                        "No se puede cambiar la categoría de un modelo utilizado por activos, "
                        "para proteger el significado histórico de inventario y solicitudes."
                    ]
                raise serializers.ValidationError(errores)

        clave = clave_normalizada(nombre)
        qs = ModeloActivo.objects.filter(id_marca=marca_obj, id_categoria=categoria_obj)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if any(clave_normalizada(item.nombre) == clave for item in qs):
            raise serializers.ValidationError(
                {
                    "nombre": [
                        "Ya existe un modelo con un nombre equivalente para la marca y categoría seleccionadas."
                    ]
                }
            )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        self._validar_reglas_modelo(attrs)
        return attrs

    def create(self, validated_data: dict[str, Any]) -> ModeloActivo:
        try:
            with transaction.atomic():
                bloquear_operacion(LOCK_CATEGORIA)
                bloquear_operacion(LOCK_MARCA)
                bloquear_operacion(LOCK_MODELO)
                self._validar_reglas_modelo(validated_data)
                modelo = ModeloActivo.objects.create(**validated_data)
                auditar_evento_activos(
                    self.context.get("request"),
                    accion="MODELO_CREADO",
                    entidad_afectada="modelo_activo",
                    id_registro_afectado=modelo.pk,
                    detalle_evento=(
                        f"MODELO_CREADO: nombre='{modelo.nombre}', "
                        f"marca='{modelo.id_marca.nombre}' (#{modelo.id_marca.pk}), "
                        f"categoria='{modelo.id_categoria.nombre}' (#{modelo.id_categoria.pk})."
                    ),
                )
                return modelo
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    "nombre": [
                        "Ya existe un modelo con un nombre equivalente para la marca y categoría seleccionadas."
                    ]
                }
            ) from exc

    def update(self, instance: ModeloActivo, validated_data: dict[str, Any]) -> ModeloActivo:
        try:
            with transaction.atomic():
                bloquear_operacion(LOCK_CATEGORIA)
                bloquear_operacion(LOCK_MARCA)
                bloquear_operacion(LOCK_MODELO)
                bloquear_operacion(70406)
                self._refrescar_instancia(instance)
                prev_nombre = instance.nombre
                prev_marca_nombre = instance.id_marca.nombre
                prev_marca_id = instance.id_marca.pk
                prev_cat_nombre = instance.id_categoria.nombre
                prev_cat_id = instance.id_categoria.pk
                self._validar_reglas_modelo(validated_data)
                modelo = super().update(instance, validated_data)
                auditar_evento_activos(
                    self.context.get("request"),
                    accion="MODELO_MODIFICADO",
                    entidad_afectada="modelo_activo",
                    id_registro_afectado=modelo.pk,
                    detalle_evento=(
                        f"MODELO_MODIFICADO: ID {modelo.pk}. "
                        f"Antes: nombre='{prev_nombre}', marca='{prev_marca_nombre}' (#{prev_marca_id}), "
                        f"categoria='{prev_cat_nombre}' (#{prev_cat_id}). "
                        f"Ahora: nombre='{modelo.nombre}', marca='{modelo.id_marca.nombre}' (#{modelo.id_marca.pk}), "
                        f"categoria='{modelo.id_categoria.nombre}' (#{modelo.id_categoria.pk})."
                    ),
                )
                return modelo
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    "nombre": [
                        "Ya existe un modelo con un nombre equivalente para la marca y categoría seleccionadas."
                    ]
                }
            ) from exc


class UbicacionSerializer(_CatalogoBaseSerializer):
    CamposTexto = ("nombre_area", "edificio", "piso")

    class Meta:
        model = Ubicacion
        fields = [
            "id_ubicacion",
            "nombre_area",
            "edificio",
            "piso",
        ]
        read_only_fields = ["id_ubicacion"]
        extra_kwargs = {
            "nombre_area": {
                "trim_whitespace": False,
                "allow_blank": True,
                "max_length": 500,
            },
            "edificio": {
                "trim_whitespace": False,
                "allow_blank": True,
                "allow_null": True,
                "required": False,
                "max_length": 500,
            },
            "piso": {
                "trim_whitespace": False,
                "allow_blank": True,
                "allow_null": True,
                "required": False,
                "max_length": 500,
            },
        }

    def validate_nombre_area(self, value: Any) -> str:
        return validar_texto_requerido(value, "nombre_area", 100)

    def validate_edificio(self, value: Any) -> str | None:
        return validar_texto_opcional(value, "edificio", 50)

    def validate_piso(self, value: Any) -> str | None:
        return validar_texto_opcional(value, "piso", 20)

    def _validar_unicidad(self, attrs: dict[str, Any]) -> None:
        nombre_area = attrs.get("nombre_area", getattr(self.instance, "nombre_area", ""))
        edificio = attrs.get("edificio", getattr(self.instance, "edificio", None)) if "edificio" in attrs or self.instance is not None else None
        piso = attrs.get("piso", getattr(self.instance, "piso", None)) if "piso" in attrs or self.instance is not None else None

        identidad = (
            clave_normalizada(nombre_area),
            clave_normalizada(edificio),
            clave_normalizada(piso),
        )
        qs = Ubicacion.objects.all()
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        for item in qs:
            item_id = (
                clave_normalizada(item.nombre_area),
                clave_normalizada(item.edificio),
                clave_normalizada(item.piso),
            )
            if item_id == identidad:
                raise serializers.ValidationError(
                    {
                        "nombre_area": [
                            "Ya existe una ubicación registrada con la misma combinación de área, edificio y piso."
                        ]
                    }
                )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        self._validar_unicidad(attrs)
        return attrs

    def create(self, validated_data: dict[str, Any]) -> Ubicacion:
        try:
            with transaction.atomic():
                bloquear_operacion(LOCK_UBICACION)
                self._validar_unicidad(validated_data)
                ubicacion = Ubicacion.objects.create(**validated_data)
                auditar_evento_activos(
                    self.context.get("request"),
                    accion="UBICACION_CREADA",
                    entidad_afectada="ubicacion",
                    id_registro_afectado=ubicacion.pk,
                    detalle_evento=(
                        f"UBICACION_CREADA: nombre_area='{ubicacion.nombre_area}', "
                        f"edificio='{ubicacion.edificio or '—'}', piso='{ubicacion.piso or '—'}'."
                    ),
                )
                return ubicacion
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    "nombre_area": [
                        "Ya existe una ubicación registrada con la misma combinación de área, edificio y piso."
                    ]
                }
            ) from exc

    def update(self, instance: Ubicacion, validated_data: dict[str, Any]) -> Ubicacion:
        try:
            with transaction.atomic():
                bloquear_operacion(LOCK_UBICACION)
                self._refrescar_instancia(instance)
                prev_area = instance.nombre_area
                prev_edificio = instance.edificio
                prev_piso = instance.piso
                self._validar_unicidad(validated_data)
                ubicacion = super().update(instance, validated_data)
                auditar_evento_activos(
                    self.context.get("request"),
                    accion="UBICACION_MODIFICADA",
                    entidad_afectada="ubicacion",
                    id_registro_afectado=ubicacion.pk,
                    detalle_evento=(
                        f"UBICACION_MODIFICADA: ID {ubicacion.pk}. "
                        f"Antes: nombre_area='{prev_area}', edificio='{prev_edificio or '—'}', piso='{prev_piso or '—'}'. "
                        f"Ahora: nombre_area='{ubicacion.nombre_area}', edificio='{ubicacion.edificio or '—'}', piso='{ubicacion.piso or '—'}'."
                    ),
                )
                return ubicacion
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    "nombre_area": [
                        "Ya existe una ubicación registrada con la misma combinación de área, edificio y piso."
                    ]
                }
            ) from exc


class EstadoActivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoActivo
        fields = [
            "id_estado_activo",
            "nombre",
            "descripcion",
        ]


class ActivoSerializer(serializers.ModelSerializer):
    modelo = serializers.CharField(
        source="id_modelo.nombre",
        read_only=True,
    )

    marca = serializers.CharField(
        source="id_modelo.id_marca.nombre",
        read_only=True,
    )

    categoria = serializers.CharField(
        source="id_modelo.id_categoria.nombre",
        read_only=True,
    )

    ubicacion = serializers.CharField(
        source="id_ubicacion.nombre_area",
        read_only=True,
    )

    estado = serializers.CharField(
        source="id_estado_activo.nombre",
        read_only=True,
    )

    class Meta:
        model = Activo
        fields = [
            "id_activo",
            "codigo_inventario",
            "numero_serie",
            "id_modelo",
            "id_ubicacion",
            "id_estado_activo",
            "valor_adquisicion",
            "fecha_compra",
            "fecha_garantia",
            "fecha_registro",
            "modelo",
            "marca",
            "categoria",
            "ubicacion",
            "estado",
        ]

        read_only_fields = [
            "id_activo",
            "fecha_registro",
            "codigo_inventario",
        ]

        extra_kwargs = {
            "numero_serie": {"trim_whitespace": False},
            "id_estado_activo": {
                "required": False,
            },
        }

    def validate_numero_serie(self, value):
        if re.fullmatch(r"[A-Za-z0-9]+(?:[-_./][A-Za-z0-9]+)*", value) is None:
            raise serializers.ValidationError(
                "Ingrese letras A-Z o números, sin espacios. Puede usar - _ . / entre grupos, "
                "sin repetir separadores ni dejarlos al inicio o al final."
            )
        return value

    def validate_valor_adquisicion(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "El valor de adquisición no puede ser negativo."
            )

        return value

    def validate(self, attrs):
        compra = attrs.get("fecha_compra", getattr(self.instance, "fecha_compra", None))
        garantia = attrs.get("fecha_garantia", getattr(self.instance, "fecha_garantia", None))
        if compra and garantia and garantia < compra:
            raise serializers.ValidationError({"fecha_garantia": ["La garantía no puede finalizar antes de la compra."]})
        if self.instance is not None:
            from asignaciones.models import Asignacion
            estado = attrs.get("id_estado_activo")
            modelo = attrs.get("id_modelo")
            if estado is not None or modelo is not None:
                abierta = Asignacion.objects.filter(id_activo=self.instance, fecha_finalizacion__isnull=True).exists()
                if abierta and estado is not None and estado.pk != self.instance.id_estado_activo.pk:
                    raise serializers.ValidationError({"id_estado_activo": ["Registre la devolución antes de cambiar el estado de un activo asignado."]})
                if abierta and modelo is not None and modelo.pk != self.instance.id_modelo.pk:
                    raise serializers.ValidationError({"id_modelo": ["No se puede cambiar el modelo mientras existe una asignación activa."]})
                if not abierta and estado is not None and estado.nombre == "Asignado":
                    raise serializers.ValidationError({"id_estado_activo": ["El estado Asignado se establece al registrar una entrega."]})
        return attrs

    def _auditar(self, activo, accion):
        request = self.context.get("request")
        usuario = getattr(request, "user", None)
        registrar_auditoria(
            usuario=usuario if isinstance(usuario, Usuario) else None,
            modulo="ACTIVOS", accion=accion, entidad_afectada="activo",
            id_registro_afectado=activo.pk,
            detalle_evento=f"{accion}: {activo.codigo_inventario}.",
            direccion_ip=direccion_ip_cliente(request) if request is not None else None,
        )

    def create(self, validated_data):
        with transaction.atomic():
            bloquear_operacion(70406)
            validated_data["codigo_inventario"] = siguiente_codigo("activo", "ACT")
            try:
                estado = EstadoActivo.objects.get(nombre="Disponible")
            except EstadoActivo.DoesNotExist:
                raise serializers.ValidationError({"id_estado_activo": ["Estado Disponible no configurado."]})
            validated_data["id_estado_activo"] = estado
            activo = Activo.objects.create(**validated_data)
            self._auditar(activo, "ACTIVO_CREADO")
            return activo

    def update(self, instance, validated_data):
        with transaction.atomic():
            bloquear_operacion(70403, instance.pk)
            instance.refresh_from_db()
            self.validate(validated_data)
            activo = super().update(instance, validated_data)
            self._auditar(activo, "ACTIVO_MODIFICADO")
            return activo
