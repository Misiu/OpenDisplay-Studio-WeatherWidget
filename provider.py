"""Home Assistant data provider owned by the Weather widget package."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from babel.core import UnknownLocaleError
from babel.dates import format_date
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

LOGGER_NAME = "custom_components.opendisplay_studio"
LOGGER = logging.getLogger(LOGGER_NAME)
TRANSLATIONS_DIRECTORY = Path(__file__).with_name("translations")
WEATHER_ICON_BASE_URL = "https://trmnl.com/images/plugins/weather"

WEATHER_CONDITION_ICONS = {
    "clear-night": "wi-night-clear.svg",
    "cloudy": "wi-cloudy.svg",
    "exceptional": "wi-na.svg",
    "fog": "wi-fog.svg",
    "hail": "wi-hail.svg",
    "lightning": "wi-lightning.svg",
    "lightning-rainy": "wi-thunderstorm.svg",
    "partlycloudy": "wi-day-cloudy.svg",
    "pouring": "wi-rain-wind.svg",
    "rainy": "wi-rain.svg",
    "snowy": "wi-snow.svg",
    "snowy-rainy": "wi-rain-mix.svg",
    "sunny": "wi-day-sunny.svg",
    "windy": "wi-strong-wind.svg",
    "windy-variant": "wi-cloudy-windy.svg",
}


def _translation_file(language: str) -> Path:
    """Resolve a validated language name inside this widget package."""
    return TRANSLATIONS_DIRECTORY / f"{language}.json"


def _read_translation_file(path: Path) -> dict[str, str]:
    """Read one flat widget translation resource."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(label) for key, label in value.items() if isinstance(label, str)
    }


def _load_widget_labels(language: str) -> dict[str, str]:
    """Load English, base-language, and exact-locale widget labels."""
    labels = _read_translation_file(_translation_file("en"))
    candidates = [language.partition("-")[0], language]
    for candidate in dict.fromkeys(candidates):
        path = _translation_file(candidate)
        if candidate != "en" and path.is_file():
            labels.update(_read_translation_file(path))
    return labels


@dataclass(frozen=True, slots=True)
class WeatherLocalizer:
    """Localized Weather vocabulary from the widget and Home Assistant."""

    language: str
    labels: dict[str, str]
    condition_labels: dict[str, str]

    @classmethod
    def english(cls) -> WeatherLocalizer:
        """Return the package's deterministic standalone fallback."""
        return cls(language="en", labels=_load_widget_labels("en"), condition_labels={})

    @classmethod
    async def async_create(cls, hass: HomeAssistant, language: str) -> WeatherLocalizer:
        """Load widget labels and reuse Home Assistant's Weather translations."""
        weather_entity, weather_title, labels = await asyncio.gather(
            async_get_translations(
                hass, language, "entity_component", integrations={WEATHER_DOMAIN}
            ),
            async_get_translations(
                hass, language, "title", integrations={WEATHER_DOMAIN}
            ),
            hass.async_add_executor_job(_load_widget_labels, language),
        )
        labels["weather"] = weather_title.get(
            "component.weather.title", labels["weather"]
        )
        attribute_prefix = "component.weather.entity_component._.state_attributes."
        for key in ("temperature", "apparent_temperature", "humidity"):
            labels[key] = weather_entity.get(
                f"{attribute_prefix}{key}.name", labels[key]
            )
        state_prefix = "component.weather.entity_component._.state."
        condition_labels = {
            key.removeprefix(state_prefix): value
            for key, value in weather_entity.items()
            if key.startswith(state_prefix)
        }
        return cls(language=language, labels=labels, condition_labels=condition_labels)

    def condition(self, condition: str) -> str:
        """Return a localized Home Assistant weather condition."""
        return self.condition_labels.get(
            condition,
            condition.replace("-", " ").capitalize()
            if condition
            else self.labels["unavailable"],
        )


def _weather_icon(condition: str) -> str:
    """Map a Home Assistant condition to the widget's weather icon."""
    filename = WEATHER_CONDITION_ICONS.get(condition, "wi-na.svg")
    return f"{WEATHER_ICON_BASE_URL}/{filename}"


def _placeholder(entity_id: str, localizer: WeatherLocalizer) -> dict[str, Any]:
    """Return the complete Weather template contract without live data."""
    return {
        "entity_id": entity_id,
        "name": entity_id or localizer.labels["choose_weather_entity"],
        "condition": "unavailable",
        "condition_label": localizer.labels["unavailable"],
        "icon": _weather_icon("exceptional"),
        "temperature": "—",
        "temperature_unit": "",
        "apparent_temperature": None,
        "humidity": None,
        "updated_at": "",
        "forecast": [],
        "labels": localizer.labels,
    }


def _uv_label(value: object, labels: dict[str, str]) -> str | None:
    """Convert a numeric UV index into the localized exposure category."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    if value >= 11:
        return labels["uv_extreme"]
    if value >= 8:
        return labels["uv_very_high"]
    if value >= 6:
        return labels["uv_high"]
    if value >= 3:
        return labels["uv_moderate"]
    return labels["uv_low"]


def _forecast_date_label(
    value: object, today: date, localizer: WeatherLocalizer
) -> str:
    """Create a compact localized label for a forecast timestamp."""
    parsed = dt_util.parse_datetime(str(value)) if value else None
    if parsed is None:
        return ""
    local_date = dt_util.as_local(parsed).date()
    offset = (local_date - today).days
    if offset == 0:
        return localizer.labels["today"]
    if offset == 1:
        return localizer.labels["tomorrow"]
    try:
        return format_date(
            local_date, format="EEE", locale=localizer.language.replace("-", "_")
        )
    except UnknownLocaleError, ValueError:
        return local_date.strftime("%a")


@dataclass(frozen=True, slots=True)
class WeatherResult:
    """Resolved values and render language for one compose pass."""

    values: dict[str, dict[str, Any]]
    localizer: WeatherLocalizer


class WeatherDataProvider:
    """Collect and resolve Weather requirements for the generic composer."""

    name = "weather_forecast"

    def new_request(self) -> set[str]:
        """Create an empty deduplicated request."""
        return set()

    def add_request(
        self,
        request: object,
        sources: list[str],
        config: dict[str, Any],
        requirement: dict[str, Any],
    ) -> None:
        """Add selected weather entity IDs."""
        del config, requirement
        cast("set[str]", request).update(sources)

    async def async_resolve(
        self, hass: HomeAssistant, request: object, language: str
    ) -> WeatherResult:
        """Resolve current state, daily forecast, and package translations."""
        localizer = await WeatherLocalizer.async_create(hass, language)
        entity_ids = cast("set[str]", request)
        if not entity_ids:
            return WeatherResult({}, localizer)

        sorted_entity_ids = sorted(entity_ids)
        try:
            response = await hass.services.async_call(
                WEATHER_DOMAIN,
                SERVICE_GET_FORECASTS,
                {"type": "daily"},
                blocking=True,
                target={"entity_id": sorted_entity_ids},
                return_response=True,
            )
        except HomeAssistantError as err:
            LOGGER.warning(
                "Daily weather forecast is unavailable; rendering current "
                "conditions without forecast: %s",
                err,
            )
            response = {}
        forecast_response = response if isinstance(response, dict) else {}
        today = dt_util.now().date()
        result: dict[str, dict[str, Any]] = {}

        for entity_id in sorted_entity_ids:
            state = hass.states.get(entity_id)
            attributes = state.attributes if state is not None else {}
            condition = state.state if state is not None else "unavailable"
            response_item = forecast_response.get(entity_id, {})
            raw_forecasts = (
                response_item.get("forecast", [])
                if isinstance(response_item, dict)
                else []
            )
            forecasts: list[dict[str, Any]] = []
            if isinstance(raw_forecasts, list):
                for item in raw_forecasts:
                    if not isinstance(item, dict):
                        continue
                    forecast_condition = str(item.get("condition") or "exceptional")
                    uv_index = item.get("uv_index")
                    forecasts.append(
                        {
                            "datetime": str(item.get("datetime") or ""),
                            "date_label": _forecast_date_label(
                                item.get("datetime"), today, localizer
                            ),
                            "condition": forecast_condition,
                            "condition_label": localizer.condition(forecast_condition),
                            "icon": _weather_icon(forecast_condition),
                            "temperature": item.get("temperature"),
                            "templow": item.get("templow"),
                            "uv_index": uv_index,
                            "uv_label": _uv_label(uv_index, localizer.labels),
                            "precipitation_probability": item.get(
                                "precipitation_probability"
                            ),
                        }
                    )

            result[entity_id] = {
                "entity_id": entity_id,
                "name": str(attributes.get("friendly_name", entity_id)),
                "condition": condition,
                "condition_label": localizer.condition(condition),
                "icon": _weather_icon(condition),
                "temperature": attributes.get("temperature", "—"),
                "temperature_unit": str(attributes.get("temperature_unit", "")),
                "apparent_temperature": attributes.get("apparent_temperature"),
                "humidity": attributes.get("humidity"),
                "updated_at": (
                    dt_util.as_local(state.last_updated).strftime("%H:%M")
                    if state is not None
                    else ""
                ),
                "forecast": forecasts,
                "labels": localizer.labels,
            }
        return WeatherResult(result, localizer)

    def values(
        self,
        resolved: object,
        sources: list[str],
        config: dict[str, Any],
        requirement: dict[str, Any],
    ) -> list[Any]:
        """Map resolved entities to the requirement's declared cardinality."""
        del config
        weather = cast("WeatherResult", resolved)
        values = [
            {
                **weather.values.get(source, _placeholder(source, weather.localizer)),
                "labels": weather.localizer.labels,
            }
            for source in sources
        ]
        if not values and requirement.get("cardinality") != "many":
            values = [_placeholder("", weather.localizer)]
        return values


PROVIDER = WeatherDataProvider()
