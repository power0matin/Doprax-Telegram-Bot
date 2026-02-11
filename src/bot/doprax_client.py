from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Tuple

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


@dataclass(frozen=True)
class DopraxConfig:
    base_url: str
    api_key: str
    dry_run: bool


class DopraxClient:
    """Async Doprax API wrapper with retries and error mapping."""

    def __init__(
        self, cfg: DopraxConfig, client: Optional[httpx.AsyncClient] = None
    ) -> None:
        self._cfg = cfg
        self._client = client
        self._owned_client = client is None

    async def open(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._cfg.base_url,
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
            raise RuntimeError("DopraxClient not opened")
        return self._client

    async def _request(
        self, method: str, url: str, json_data: Any | None = None
    ) -> Any:
        if self._cfg.dry_run:
            return self._mock(method, url, json_data)

        retries = 3
        backoff = 0.5
        last_exc: Exception | None = None

        for attempt in range(retries + 1):
            try:
                resp = await self.client.request(method, url, json=json_data)
                return self._handle_response(resp)
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exc = e
                if attempt >= retries:
                    break
                await asyncio.sleep(backoff * (2**attempt))
            except DopraxRateLimited as e:
                last_exc = e
                if attempt >= retries:
                    break
                await asyncio.sleep(backoff * (2**attempt))
        raise DopraxNetworkError(
            message_key="something_wrong", details=str(last_exc or "network_error")
        )

    def _handle_response(self, resp: httpx.Response) -> Any:
        status = resp.status_code
        try:
            data = resp.json() if resp.content else {}
        except Exception:
            data = {}

        if 200 <= status < 300:
            return data

        detail = (
            str(data)[:1000] if isinstance(data, (dict, list)) else resp.text[:1000]
        )

        if status in (401, 403):
            raise DopraxAuthError(message_key="something_wrong", details=detail)
        if status == 404:
            raise DopraxNotFound(message_key="something_wrong", details=detail)
        if status == 429:
            raise DopraxRateLimited(message_key="something_wrong", details=detail)
        if 400 <= status < 500:
            raise DopraxValidationError(message_key="something_wrong", details=detail)
        raise DopraxServerError(message_key="something_wrong", details=detail)

    def _mock(self, method: str, url: str, json_data: Any | None) -> Any:
        # Deterministic, stable responses for tests/manual dry-run
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
        if "/status/" in url and method == "GET":
            vm_code = url.split("/api/v1/vms/")[1].split("/status/")[0]
            return {"vm_code": vm_code, "status": "RUNNING", "isActive": True}
        return {}

    async def list_vms(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/v1/vms/")
        return data if isinstance(data, list) else []

    async def create_vm(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request("POST", "/api/v1/vms/", json_data=payload)
        return data if isinstance(data, dict) else {}

    async def get_vm_status(self, vm_code: str) -> dict[str, Any]:
        data = await self._request("GET", f"/api/v1/vms/{vm_code}/status/")
        return data if isinstance(data, dict) else {}

    async def get_locations(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/v1/vlocations/")
        return data if isinstance(data, list) else []

    async def get_os_list(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/v1/os/")
        return data if isinstance(data, list) else []

    async def resolve_location_and_machine_codes(
        self, plan: str, preferred_location: str
    ) -> Tuple[Optional[str], Optional[str], list[str]]:
        """
        Resolve (location_code, machine_type_code) based on plan and preferred location name.

        Logic:
        - Pull /vlocations/
        - Find machines where machine.name == plan (case-insensitive) and machineCode exists
        - Choose best location match against preferred_location by token overlap
        - Provide alternatives if exact match not found
        """
        locations = await self.get_locations()
        plan_norm = plan.strip().lower()
        pref = preferred_location.strip().lower()

        candidates: list[tuple[int, str, str, str]] = (
            []
        )  # (score, loc_name, loc_code, machine_code)
        all_suggestions: list[str] = []

        pref_tokens = [t for t in _tokens(pref) if t]

        for loc in locations:
            loc_code = safe_get(loc, "locationCode")
            loc_name = safe_get(loc, "locationName", default="")
            machines = safe_get(loc, "machines", default=[])
            if not isinstance(machines, list):
                continue

            for m in machines:
                m_name = str(safe_get(m, "name", default="")).strip()
                m_code = safe_get(m, "machineCode")
                if not m_code:
                    continue
                if m_name.strip().lower() != plan_norm:
                    continue

                loc_name_s = str(loc_name)
                score = _match_score(loc_name_s.lower(), pref_tokens)
                candidates.append((score, loc_name_s, str(loc_code), str(m_code)))

        if not candidates:
            # Provide suggestions: show available plan names from the dataset
            plan_names = sorted(
                {
                    str(safe_get(m, "name", default=""))
                    for loc in locations
                    for m in (safe_get(loc, "machines", default=[]) or [])
                    if safe_get(m, "name")
                }
            )
            all_suggestions.append(
                f"Known plans: {', '.join(plan_names[:20])}{'…' if len(plan_names) > 20 else ''}"
            )
            return None, None, all_suggestions

        # Sort by score desc; stable
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0]
        best_loc_name = best[1]

        # Suggestions list
        for score, loc_name, loc_code, m_code in candidates[:5]:
            all_suggestions.append(
                f"- {loc_name} (locationCode={loc_code}, machineCode={m_code}, score={score})"
            )

        # If preferred location doesn't match well, still return best but include context
        return (
            best[2],
            best[3],
            all_suggestions if best_loc_name.lower() != pref else all_suggestions,
        )


def _tokens(s: str) -> list[str]:
    return [t for t in "".join(ch if ch.isalnum() else " " for ch in s).split()]


def _match_score(location_name: str, pref_tokens: Iterable[str]) -> int:
    lt = set(_tokens(location_name))
    score = 0
    for t in pref_tokens:
        if t in lt:
            score += 10
        else:
            # partial match
            if any(t in x for x in lt):
                score += 3
    return score
