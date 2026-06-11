"""Container registry for deterministic LabFlow workflows."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from labflow_core.domain.containers import (
    Container,
    ContainerType,
    matrix_96_1ml_rubber_septum_type,
    matrix_96_1ml_screwtop_type,
)


class ContainerRegistry:
    """Resolve container properties from barcode/container IDs and type IDs."""

    def __init__(
        self,
        container_types: Mapping[str, ContainerType],
        containers: Mapping[str, Container] | None = None,
    ) -> None:
        self._container_types = dict(container_types)
        self._containers = dict(containers or {})

    @classmethod
    def with_defaults(cls) -> ContainerRegistry:
        container_types = {
            "matrix_96_1ml_screwtop": matrix_96_1ml_screwtop_type(),
            "matrix_96_1ml_septum": matrix_96_1ml_rubber_septum_type(),
        }
        return cls(container_types)

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> ContainerRegistry:
        type_config = config.get("container_registry", {})
        container_types: dict[str, ContainerType] = {}
        if isinstance(type_config, Mapping):
            for type_id, raw in type_config.items():
                if not isinstance(type_id, str) or not isinstance(raw, Mapping):
                    continue
                container_types[type_id] = ContainerType(
                    container_type_id=type_id,
                    name=str(raw["name"]),
                    format=str(raw["format"]),
                    rows=int(raw["rows"]),
                    columns=int(raw["columns"]),
                    nominal_capacity_ul=float(raw["nominal_capacity_ul"]),
                    max_working_volume_ul=float(raw["max_working_volume_ul"]),
                    closure_type=str(raw["closure_type"]),
                    vendor=str(raw.get("vendor", "Thermo Fisher")),
                )

        if not container_types:
            return cls.with_defaults()

        containers: dict[str, Container] = {}
        raw_containers = config.get("containers", {})
        if isinstance(raw_containers, Mapping):
            for container_id, raw in raw_containers.items():
                if not isinstance(container_id, str) or not isinstance(raw, Mapping):
                    continue
                barcode = str(raw.get("barcode", container_id))
                container_type_id = str(raw["container_type_id"])
                containers[container_id] = Container(
                    container_id=container_id,
                    barcode=barcode,
                    container_type_id=container_type_id,
                )
        return cls(container_types, containers)

    @property
    def container_types(self) -> dict[str, ContainerType]:
        return dict(self._container_types)

    @property
    def containers(self) -> dict[str, Container]:
        return dict(self._containers)

    def register_container(self, container: Container) -> None:
        self.resolve_type(container.container_type_id)
        self._containers[container.container_id] = container

    def resolve_type(self, container_type_id: str) -> ContainerType:
        try:
            return self._container_types[container_type_id]
        except KeyError as exc:
            msg = f"Unknown container type: {container_type_id}"
            raise KeyError(msg) from exc

    def resolve_container(self, container_id_or_barcode: str) -> Container:
        if container_id_or_barcode in self._containers:
            return self._containers[container_id_or_barcode]
        for container in self._containers.values():
            if container.barcode == container_id_or_barcode:
                return container
        msg = f"Unknown container: {container_id_or_barcode}"
        raise KeyError(msg)

    def resolve_container_type_for_container(self, container_id_or_barcode: str) -> ContainerType:
        container = self.resolve_container(container_id_or_barcode)
        return self.resolve_type(container.container_type_id)

    def ensure_container(
        self,
        container_id: str,
        container_type_id: str = "matrix_96_1ml_screwtop",
    ) -> Container:
        try:
            return self.resolve_container(container_id)
        except KeyError:
            container = Container(
                container_id=container_id,
                barcode=container_id,
                container_type_id=container_type_id,
            )
            self.register_container(container)
            return container
