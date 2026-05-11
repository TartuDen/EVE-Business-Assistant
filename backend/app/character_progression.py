from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from .config import settings
from .database import (
    consume_oauth_state,
    create_saved_plan,
    delete_character_token,
    delete_saved_plan,
    get_character_token,
    list_character_tokens,
    list_saved_plans,
    save_character_token,
    save_oauth_state,
)


SCOPES = [
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-wallet.read_character_wallet.v1",
    "esi-assets.read_assets.v1",
    "esi-clones.read_implants.v1",
]

TRAINING_HOURS_BY_LEVEL = {
    1: 0.4,
    2: 2.0,
    3: 9.0,
    4: 45.0,
    5: 230.0,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))
    except (IndexError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Could not read EVE SSO token payload.") from exc


def _character_id_from_claims(claims: dict[str, Any]) -> int:
    subject = claims.get("sub", "")
    if isinstance(subject, str) and subject.startswith("CHARACTER:EVE:"):
        return int(subject.rsplit(":", 1)[1])
    if "character_id" in claims:
        return int(claims["character_id"])
    raise HTTPException(status_code=400, detail="EVE SSO token did not include a character id.")


def _auth_headers() -> dict[str, str]:
    raw = f"{settings.eve_client_id}:{settings.eve_client_secret}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": settings.esi_user_agent,
    }


def sso_configured() -> bool:
    return bool(settings.eve_client_id and settings.eve_client_secret)


def create_login_url() -> dict[str, Any]:
    if not sso_configured():
        return {
            "configured": False,
            "authorization_url": None,
            "message": "Set EVE_CLIENT_ID, EVE_CLIENT_SECRET, and EVE_CALLBACK_URL to enable EVE SSO.",
            "callback_url": settings.eve_callback_url,
            "scopes": SCOPES,
        }
    state = secrets.token_urlsafe(32)
    save_oauth_state(state)
    query = urlencode(
        {
            "response_type": "code",
            "redirect_uri": settings.eve_callback_url,
            "client_id": settings.eve_client_id,
            "scope": " ".join(SCOPES),
            "state": state,
        }
    )
    return {
        "configured": True,
        "authorization_url": f"{settings.eve_sso_authorize_url}?{query}",
        "callback_url": settings.eve_callback_url,
        "scopes": SCOPES,
    }


async def exchange_code_for_token(code: str, state: str) -> int:
    if not consume_oauth_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired SSO state.")
    if not sso_configured():
        raise HTTPException(status_code=400, detail="EVE SSO is not configured.")

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(
            settings.eve_sso_token_url,
            headers=_auth_headers(),
            data={"grant_type": "authorization_code", "code": code},
        )
        response.raise_for_status()
        token_data = response.json()

    claims = _decode_jwt_payload(token_data["access_token"])
    character_id = _character_id_from_claims(claims)
    character_name = claims.get("name") or claims.get("owner") or f"Character {character_id}"
    expires_at = (_utc_now() + timedelta(seconds=int(token_data.get("expires_in", 1199)))).isoformat()
    scopes = claims.get("scp") or token_data.get("scope", "").split()
    if isinstance(scopes, str):
        scopes = scopes.split()

    save_character_token(
        character_id=character_id,
        character_name=character_name,
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_at=expires_at,
        scopes=list(scopes),
        token_type=token_data.get("token_type", "Bearer"),
    )
    return character_id


async def _refresh_token_if_needed(token_row) -> str:
    expires_at = datetime.fromisoformat(token_row["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at > _utc_now() + timedelta(minutes=2):
        return token_row["access_token"]
    if not sso_configured():
        return token_row["access_token"]

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(
            settings.eve_sso_token_url,
            headers=_auth_headers(),
            data={"grant_type": "refresh_token", "refresh_token": token_row["refresh_token"]},
        )
        response.raise_for_status()
        token_data = response.json()

    claims = _decode_jwt_payload(token_data["access_token"])
    scopes = claims.get("scp") or token_row["scopes"].split()
    if isinstance(scopes, str):
        scopes = scopes.split()
    expires_at = (_utc_now() + timedelta(seconds=int(token_data.get("expires_in", 1199)))).isoformat()
    save_character_token(
        character_id=int(token_row["character_id"]),
        character_name=token_row["character_name"],
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", token_row["refresh_token"]),
        expires_at=expires_at,
        scopes=list(scopes),
        token_type=token_data.get("token_type", "Bearer"),
    )
    return token_data["access_token"]


async def _esi_get(path: str, access_token: str) -> Any:
    async with httpx.AsyncClient(
        base_url=settings.esi_base_url,
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": settings.esi_user_agent},
        timeout=settings.request_timeout_seconds,
    ) as client:
        response = await client.get(path)
        response.raise_for_status()
        return response.json()


async def authenticated_character_data(character_id: int | None = None) -> dict[str, Any]:
    token_row = get_character_token(character_id)
    if token_row is None:
        raise HTTPException(status_code=401, detail="Connect an EVE character first.")
    cid = int(token_row["character_id"])
    access_token = await _refresh_token_if_needed(token_row)

    character, skills, queue, wallet, assets, implants = await _fetch_character_payload(cid, access_token)
    skill_names = await _resolve_skill_names([int(skill["skill_id"]) for skill in skills.get("skills", [])])
    return {
        "character_id": cid,
        "character_name": character.get("name", token_row["character_name"]),
        "scopes": token_row["scopes"].split(),
        "character": character,
        "skills": skills,
        "queue": queue,
        "wallet": wallet,
        "assets": assets,
        "implants": implants,
        "skill_names": skill_names,
    }


async def _fetch_character_payload(character_id: int, access_token: str) -> tuple[Any, Any, Any, Any, Any, Any]:
    async with httpx.AsyncClient(
        base_url=settings.esi_base_url,
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": settings.esi_user_agent},
        timeout=settings.request_timeout_seconds,
    ) as client:
        async def get(path: str, fallback: Any) -> Any:
            try:
                response = await client.get(path)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError:
                return fallback

        character = await get(f"/characters/{character_id}/", {})
        skills = await get(f"/characters/{character_id}/skills/", {"skills": [], "total_sp": 0, "unallocated_sp": 0})
        queue = await get(f"/characters/{character_id}/skillqueue/", [])
        wallet = await get(f"/characters/{character_id}/wallet/", 0)
        assets = await get(f"/characters/{character_id}/assets/", [])
        clones = await get(f"/characters/{character_id}/clones/", {"home_location": {}, "jump_clones": []})
    implants = clones.get("jump_clones", [])
    return character, skills, queue, wallet, assets, implants


async def _resolve_skill_names(skill_ids: list[int]) -> dict[int, str]:
    if not skill_ids:
        return {}
    names: dict[int, str] = {}
    async with httpx.AsyncClient(
        base_url=settings.esi_base_url,
        headers={"User-Agent": settings.esi_user_agent},
        timeout=settings.request_timeout_seconds,
    ) as client:
        for start in range(0, len(skill_ids), 1000):
            response = await client.post("/universe/names/", json=skill_ids[start : start + 1000])
            response.raise_for_status()
            for item in response.json():
                if item.get("category") == "inventory_type":
                    names[int(item["id"])] = item["name"]
    return names


def load_profiles() -> list[dict[str, Any]]:
    profile_dir = Path(__file__).with_name("skill_profiles")
    profiles = []
    for path in sorted(profile_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            profiles.append(json.load(handle))
    profiles.sort(key=lambda item: (item["profile_id"] != "safe_jita_trader", item["display_name"]))
    return profiles


def get_profile(profile_id: str) -> dict[str, Any]:
    for profile in load_profiles():
        if profile["profile_id"] == profile_id:
            return profile
    raise HTTPException(status_code=404, detail="Skill profile not found.")


def _skills_by_id(skills_payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(skill["skill_id"]): skill for skill in skills_payload.get("skills", [])}


def _skill_level(skill: dict[str, Any] | None) -> int:
    if not skill:
        return 0
    return int(skill.get("trained_skill_level", 0))


def _active_skill_level(skill: dict[str, Any] | None) -> int:
    if not skill:
        return 0
    return int(skill.get("active_skill_level", skill.get("trained_skill_level", 0)))


def detect_clone_state(skills_payload: dict[str, Any]) -> dict[str, Any]:
    skills = skills_payload.get("skills", [])
    limited = [skill for skill in skills if _active_skill_level(skill) < _skill_level(skill)]
    total_sp = int(skills_payload.get("total_sp", 0))
    if limited:
        return {
            "state": "Alpha",
            "confidence": "high",
            "reason": "ESI reports at least one trained skill with a lower active level, which usually means Alpha restrictions are active.",
        }
    if total_sp > 5_000_000:
        return {
            "state": "Omega",
            "confidence": "medium",
            "reason": "No inactive trained skills were reported and total SP is above the common Alpha training cap.",
        }
    return {
        "state": "Alpha",
        "confidence": "medium",
        "reason": "No inactive skills were reported, but total SP is within early Alpha range. ESI does not expose account subscription state directly.",
    }


def _training_time_text(current_level: int, target_level: int) -> str:
    hours = sum(TRAINING_HOURS_BY_LEVEL.get(level, 60) for level in range(current_level + 1, target_level + 1))
    if hours < 24:
        return f"{max(1, round(hours))} hours"
    return f"{round(hours / 24, 1)} days"


def _recommendations_for_skills(profile: dict[str, Any], skills_by_id: dict[int, dict[str, Any]], clone_state: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    recommendations = []
    omega_locked = []
    for section, multiplier in (("required_skills", 1.0), ("optional_skills", 0.72), ("omega_only_skills", 0.45)):
        for item in profile.get(section, []):
            skill_id = int(item["skill_id"])
            current = _skill_level(skills_by_id.get(skill_id))
            active = _active_skill_level(skills_by_id.get(skill_id))
            target = int(item["target_level"])
            if current >= target:
                continue
            recommendation = {
                "skill_id": skill_id,
                "skill_name": item["name"],
                "current_level": current,
                "active_level": active,
                "target_level": target,
                "training_time": _training_time_text(current, target),
                "priority": round(float(item.get("priority", 50)) * multiplier),
                "reason": item.get("reason", ""),
                "economic_impact": item.get("economic_impact", ""),
                "omega_only": section == "omega_only_skills",
                "available_after_omega": section == "omega_only_skills" and clone_state == "Alpha",
            }
            if recommendation["available_after_omega"]:
                omega_locked.append(recommendation)
            else:
                recommendations.append(recommendation)
    recommendations.sort(key=lambda item: item["priority"], reverse=True)
    omega_locked.sort(key=lambda item: item["priority"], reverse=True)
    return recommendations, omega_locked


def _roadmap(recommendations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "immediate": recommendations[:3],
        "short_term": recommendations[3:8],
        "medium_term": recommendations[8:15],
    }


def _skill_area_summary(skills_payload: dict[str, Any], profile: dict[str, Any]) -> tuple[list[str], list[str]]:
    skills_by_id = _skills_by_id(skills_payload)
    areas: dict[str, int] = {}
    for item in profile.get("required_skills", []) + profile.get("optional_skills", []):
        current = _skill_level(skills_by_id.get(int(item["skill_id"])))
        areas[item["name"]] = current
    strongest = [name for name, _level in sorted(areas.items(), key=lambda item: item[1], reverse=True)[:4]]
    weakest = [name for name, level in sorted(areas.items(), key=lambda item: item[1]) if level < 3][:4]
    return strongest, weakest


def analyze_character(payload: dict[str, Any], profile_id: str = "safe_jita_trader") -> dict[str, Any]:
    profile = get_profile(profile_id)
    skills_payload = payload["skills"]
    skills_by_id = _skills_by_id(skills_payload)
    clone_state = detect_clone_state(skills_payload)
    recommendations, omega_locked = _recommendations_for_skills(profile, skills_by_id, clone_state["state"])
    strongest, weakest = _skill_area_summary(skills_payload, profile)
    assets = payload.get("assets", [])
    queue = payload.get("queue", [])
    skill_names = payload.get("skill_names", {})
    next_best = recommendations[0] if recommendations else None
    total_sp = int(skills_payload.get("total_sp", 0))
    analysis = (
        f"{payload['character_name']} is best evaluated against the {profile['display_name']} profile. "
        f"The next useful step is {next_best['skill_name']} to level {next_best['target_level']}."
        if next_best
        else f"{payload['character_name']} already meets the main visible requirements for {profile['display_name']}."
    )
    return {
        "character": {
            "character_id": payload["character_id"],
            "name": payload["character_name"],
            "total_sp": total_sp,
            "unallocated_sp": int(skills_payload.get("unallocated_sp", 0)),
            "wallet_balance": float(payload.get("wallet", 0) or 0),
            "asset_count": len(assets),
            "skill_queue_count": len(queue),
            "clone_state": clone_state,
        },
        "profile": profile,
        "strongest_skill_areas": strongest,
        "weakest_skill_areas": weakest,
        "progression_analysis": analysis,
        "recommendations": recommendations,
        "omega_only_recommendations": omega_locked,
        "roadmap": _roadmap(recommendations),
        "warnings": profile.get("warnings", []),
        "next_best_skill": next_best,
        "current_queue": queue,
        "skills": [
            {
                "skill_id": int(skill["skill_id"]),
                "skill_name": skill_names.get(int(skill["skill_id"]), f"Skill {skill['skill_id']}"),
                "trained_skill_level": _skill_level(skill),
                "active_skill_level": _active_skill_level(skill),
                "skillpoints_in_skill": int(skill.get("skillpoints_in_skill", 0)),
            }
            for skill in skills_payload.get("skills", [])
        ],
    }


def session_summary() -> dict[str, Any]:
    return {
        "configured": sso_configured(),
        "callback_url": settings.eve_callback_url,
        "scopes": SCOPES,
        "characters": [dict(row) for row in list_character_tokens()],
    }


def disconnect_character(character_id: int) -> bool:
    return delete_character_token(character_id)


def saved_plans() -> list[dict[str, Any]]:
    return [dict(row) for row in list_saved_plans()]


def save_plan(payload: dict[str, Any]) -> dict[str, Any]:
    row = create_saved_plan(
        character_id=payload.get("character_id"),
        character_name=payload.get("character_name") or "Unknown Character",
        profile_id=payload["profile_id"],
        plan_name=payload["plan_name"],
        notes=payload.get("notes", ""),
    )
    return dict(row)


def remove_plan(plan_id: int) -> bool:
    return delete_saved_plan(plan_id)
