# Home Assistant weather data contract

The widget requests one Home Assistant `weather` entity through the
`weather_forecast` provider. The provider combines two Home Assistant sources:

- the entity state and current state attributes;
- the daily response from `weather.get_forecasts`.

Configuration fields contain native Home Assistant selector definitions. The
integration can pass their `selector` objects directly to `ha-form`, using the
same UI vocabulary as blueprints. Widget packages never contain executable
Python. Provider names resolve only to implementations registered and reviewed
inside OpenDisplay Studio Integration.

Fixtures model the normalized provider result, not the complete Home Assistant
state object. The Liquid context has this shape:

```yaml
data:
  weather:
    entity_id: weather.home
    name: Home
    condition: partlycloudy
    condition_label: Partly cloudy
    icon: https://example.test/weather/partly-cloudy.svg
    temperature: 18
    temperature_unit: "°C"
    apparent_temperature: 17 # null when unsupported
    humidity: 72              # null when unsupported
    updated_at: 09:30
    forecast:
      - datetime: "2026-08-26T12:00:00+02:00"
        date_label: Today
        condition: rainy
        condition_label: Rain
        icon: https://example.test/weather/rain.svg
        temperature: 20
        templow: 13                    # null when unsupported
        uv_index: 3                    # null when unsupported
        uv_label: Moderate             # null when uv_index is null
        precipitation_probability: 70 # null when unsupported
```

The provider must include every documented key. Unsupported optional values are
represented by `null`; they must not be omitted because widget rendering uses
strict Liquid variables.

Home Assistant guarantees the current temperature and unit for an available
weather entity. Other current attributes are provider-dependent. Daily forecast
items guarantee `datetime` and `temperature`; low temperature, UV index, and
precipitation probability are optional. When UV is unavailable, the widget uses
precipitation probability as the secondary forecast detail.

The normalized fields `name`, `condition_label`, `icon`, `updated_at`,
`date_label`, and `uv_label` are presentation values supplied by the integration.
All other weather values preserve Home Assistant's public field names.

References:

- https://www.home-assistant.io/integrations/weather/
- https://developers.home-assistant.io/docs/core/entity/weather/
