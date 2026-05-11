from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import httpx

from bot.errors import (
    DopraxAuthError,
    DopraxNetworkError,
    DopraxNotFound,
    DopraxRateLimited,
    DopraxServerError,
    DopraxValidationError,
)
from bot.utils import safe_get


@dataclass(frozen=True, slots=True)
class DopraxConfig:
    base_url: str
    api_key: str
    dry_run: bool


class DopraxClient:
    """Async Doprax API wrapper with retries, dry-run fixtures, and error mapping."""

    def __init__(self, cfg: DopraxConfig, client: httpx.AsyncClient | None = None) -> None:
        self._cfg = cfg
        self._client = client
        self._owned_client = client is None

    async def open(self) -> None:
        if self._client is not None:
            return

        self._client = httpx.AsyncClient(
            base_url=self._cfg.base_url,
            follow_redirects=True,
            headers={
                "X-API-Key": self._cfg.api_key,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=10.0),
        )

    async def close(self) -> None:
        if self._owned_client and self._client is not None:
            await self._client.aclose()
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("DopraxClient has not been opened")
        return self._client

    async def _request(self, method: str, url: str, json_data: Any | None = None) -> Any:
        if self._cfg.dry_run:
            return self._mock(method, url, json_data)

        retries = 3
        backoff_seconds = 0.5
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                response = await self.client.request(method, url, json=json_data)
                return self._handle_response(response)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
            except DopraxRateLimited as exc:
                last_error = exc

            if attempt < retries:
                await asyncio.sleep(backoff_seconds * (2**attempt))

        raise DopraxNetworkError(
            message_key="something_wrong",
            details=str(last_error or "network_error"),
        )

    def _handle_response(self, response: httpx.Response) -> Any:
        status_code = response.status_code
        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {}

        if 200 <= status_code < 300:
            return data

        detail = str(data)[:1000] if isinstance(data, (dict, list)) else response.text[:1000]

        if status_code in (401, 403):
            raise DopraxAuthError(message_key="something_wrong", details=detail)
        if status_code == 404:
            raise DopraxNotFound(message_key="something_wrong", details=detail)
        if status_code == 429:
            raise DopraxRateLimited(message_key="something_wrong", details=detail)
        if 400 <= status_code < 500:
            raise DopraxValidationError(message_key="something_wrong", details=detail)
        raise DopraxServerError(message_key="something_wrong", details=detail)

    def _unwrap(self, data: Any) -> Any:
        """Return the payload stored in a standard Doprax API response envelope."""
        if isinstance(data, dict) and "data" in data and isinstance(data.get("success"), bool):
            return data.get("data")
        return data

    def _mock(self, method: str, url: str, json_data: Any | None) -> Any:
        """Return deterministic fixtures for tests and manual dry-run sessions."""
        if url.startswith("/api/v1/os/") and method == "GET":
            return [
                {"slug": "ubuntu_22_04"},
                {"slug": "ubuntu_24_04"},
                {"slug": "ubuntu_20_04"},
                {"slug": "centos_stream_9"},
            ]

        if url.startswith("/api/v1/vlocations/") and method == "GET":
            return [
                {
                    "locationCode": "loc-de-fra",
                    "locationName": "Germany, Frankfurt",
                    "machines": [
                        {"name": "DO1", "machineCode": "m-do-1"},
                        {"name": "DO2", "machineCode": "m-do-2"},
                        {"name": "H1", "machineCode": "m-h-1"},
                        {"name": "SW1", "machineCode": "m-sw-1"},
                    ],
                },
                {
                    "locationCode": "loc-nl-ams",
                    "locationName": "Netherlands, Amsterdam",
                    "machines": [
                        {"name": "DO1", "machineCode": "m-do-1"},
                        {"name": "V1", "machineCode": "m-v-1"},
                    ],
                },
            ]

        if "/status/" in url and method == "GET":
            vm_code = url.split("/api/v1/vms/", maxsplit=1)[1].split("/status/", maxsplit=1)[0]
            return {"vm_code": vm_code, "status": "RUNNING", "isActive": True}

        if url.startswith("/api/v1/vms/") and method == "GET":
            return [
                {
                    "name": "demo-1",
                    "vm_code": "vm_demo_1",
                    "status": "RUNNING",
                    "location": "Germany, Frankfurt",
                },
                {
                    "name": "demo-2",
                    "vm_code": "vm_demo_2",
                    "status": "STOPPED",
                    "location": "Netherlands, Amsterdam",
                },
            ]

        if url.startswith("/api/v1/vms/") and method == "POST":
            name = safe_get(json_data or {}, "name", default="vm")
            return {
                "name": name,
                "vm_code": "vm_created_dryrun",
                "status": "PROVISIONING",
            }

        return {}

    async def list_vms(self) -> list[dict[str, Any]]:
        raw = await self._request("GET", "/api/v1/vms/")
        data = self._unwrap(raw)
        return data if isinstance(data, list) else []

    async def create_vm(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = await self._request("POST", "/api/v1/vms/", json_data=payload)

        if isinstance(raw, dict) and isinstance(raw.get("vm"), dict):
            vm = raw.get("vm")
            if isinstance(vm, dict):
                return {str(key): value for key, value in vm.items()}

        data = self._unwrap(raw)
        return data if isinstance(data, dict) else {}

    async def get_vm_status(self, vm_code: str) -> dict[str, Any]:
        raw = await self._request("GET", f"/api/v1/vms/{vm_code}/status/")
        data = self._unwrap(raw)
        return data if isinstance(data, dict) else {}

    async def get_locations(self) -> list[dict[str, Any]]:
        raw = await self._request("GET", "/api/v1/vlocations/")
        data = self._unwrap(raw)

        if isinstance(data, dict):
            return _normalize_locations_response(data)

        return data if isinstance(data, list) else []

    async def get_os_list(self) -> list[dict[str, Any]]:
        raw = await self._request("GET", "/api/v1/os/")
        data = self._unwrap(raw)

        items: list[dict[str, Any]] = []
        if isinstance(data, dict):
            for provider, provider_items in data.items():
                if not isinstance(provider_items, list):
                    continue
                for item in provider_items:
                    if isinstance(item, dict):
                        items.append({**item, "provider_name": provider})
        elif isinstance(data, list):
            items = [item for item in data if isinstance(item, dict)]

        return _dedupe_os_items(items)

    async def resolve_location_and_machine_codes(
        self,
        plan: str,
        preferred_location: str,
    ) -> tuple[str | None, str | None, list[str]]:
        """Resolve Doprax location and machine codes from a plan and location hint."""
        locations = await self.get_locations()
        plan_norm = plan.strip().lower()
        preferred_tokens = [token for token in _tokens(preferred_location) if token]

        candidates: list[tuple[int, str, str, str]] = []
        for location in locations:
            location_code = safe_get(location, "locationCode")
            location_name = str(safe_get(location, "locationName", default=""))
            machines = safe_get(location, "machines", default=[])

            if not location_code or not isinstance(machines, list):
                continue

            for machine in machines:
                machine_name = str(safe_get(machine, "name", default="")).strip()
                machine_code = safe_get(machine, "machineCode")
                if not machine_code or machine_name.lower() != plan_norm:
                    continue

                score = _match_score(location_name, preferred_tokens)
                candidates.append((score, location_name, str(location_code), str(machine_code)))

        if not candidates:
            return None, None, _known_plan_suggestions(locations)

        candidates.sort(key=lambda candidate: candidate[0], reverse=True)
        best_score, best_location, best_location_code, best_machine_code = candidates[0]
        suggestions = [
            f"- {location} (locationCode={location_code}, machineCode={machine_code}, score={score})"
            for score, location, location_code, machine_code in candidates[:5]
        ]

        if best_score <= 0 and best_location:
            suggestions.insert(0, f"Best fallback location: {best_location}")

        return best_location_code, best_machine_code, suggestions


def _normalize_locations_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    locations_list = safe_get(data, "locationsList", default=[])
    mapping = safe_get(data, "locationMachineTypeMapping", default={})

    output: list[dict[str, Any]] = []
    if not isinstance(locations_list, list) or not isinstance(mapping, dict):
        return output

    for location in locations_list:
        if not isinstance(location, dict):
            continue

        location_code = safe_get(location, "locationCode")
        location_name = safe_get(location, "name", default="")
        if not location_code:
            continue

        machine_block = safe_get(mapping, str(location_code), default={})
        machine_list = safe_get(machine_block, "machineTypeList", default=[])
        machines: list[dict[str, str]] = []

        if isinstance(machine_list, list):
            for machine in machine_list:
                if isinstance(machine, dict):
                    machines.append(
                        {
                            "name": str(safe_get(machine, "name", default="")),
                            "machineCode": str(safe_get(machine, "machineCode", default="")),
                        }
                    )

        output.append(
            {
                "locationCode": str(location_code),
                "locationName": str(location_name),
                "machines": machines,
            }
        )

    return output


def _dedupe_os_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for item in items:
        slug = str(item.get("slug", "")).strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        deduped.append(item)

    deduped.sort(key=lambda item: str(item.get("slug", "")))
    return deduped


def _known_plan_suggestions(locations: list[dict[str, Any]]) -> list[str]:
    plan_names = sorted(
        {
            str(safe_get(machine, "name", default=""))
            for location in locations
            for machine in (safe_get(location, "machines", default=[]) or [])
            if safe_get(machine, "name")
        }
    )
    suffix = "…" if len(plan_names) > 20 else ""
    return [f"Known plans: {', '.join(plan_names[:20])}{suffix}"]


def _tokens(value: str) -> list[str]:
    return "".join(char if char.isalnum() else " " for char in value.casefold()).split()


def _match_score(location_name: str, preferred_tokens: Iterable[str]) -> int:
    location_tokens = set(_tokens(location_name))
    score = 0

    for token in preferred_tokens:
        if token in location_tokens:
            score += 10
        elif any(token in location_token for location_token in location_tokens):
            score += 3

    return score
