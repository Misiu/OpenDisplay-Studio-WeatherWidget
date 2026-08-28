# Home Assistant weather data contract

The widget requests one Home Assistant `weather` entity through the
`weather_forecast` provider. The provider combines two Home Assistant sources:

- the entity state and current state attributes;
- the daily response from `weather.get_forecasts`.

Configuration fields contain native Home Assistant selector definitions. The
integration can pass their `selector` objects directly to `ha-form`, using the
same UI vocabulary as blueprints. This package owns `provider.py`; the
integration only discovers the provider protocol and scopes the exported
provider to this widget. Installing a provider-bearing package means trusting
its Python code. A future public Store must verify package provenance before
installation.

Fixtures model the normalized provider result, not the complete Home Assistant
state object. The Liquid context has this shape:

```yaml
data:
  weather:
    entity_id: weather.home
    name: Home
    condition: partlycloudy
    condition_label: Partly cloudy
    icon: mdi-weather-partly-cloudy
    temperature: 18
    temperature_unit: "°C"
    apparent_temperature: 17 # null when unsupported
    humidity: 72              # null when unsupported
    updated_at: 09:30
    labels:
      weather: Weather
      temperature: Temperature
      right_now: Right now
      # The complete label set is defined by translations/en.json.
    forecast:
      - datetime: "2026-08-26T12:00:00+02:00"
        date_label: Today
        condition: rainy
        condition_label: Rain
        icon: mdi-weather-rainy
        temperature: 20
        templow: 13                    # null when unsupported
        uv_index: 3                    # null when unsupported
        uv_label: Moderate             # null when uv_index is null
        precipitation_probability: 70 # null when unsupported
```

The provider must include every documented key. Unsupported optional values are
represented by `null`; keeping a total provider contract makes CLI and Home
Assistant rendering deterministic.

Home Assistant guarantees the current temperature and unit for an available
weather entity. Other current attributes are provider-dependent. Daily forecast
items guarantee `datetime` and `temperature`; low temperature, UV index, and
precipitation probability are optional. When UV is unavailable, the widget uses
precipitation probability as the secondary forecast detail.

The normalized fields `name`, `condition_label`, `icon`, `updated_at`,
`date_label`, and `uv_label` are presentation values supplied by this package's
provider. Weather conditions and attribute labels reuse Home Assistant's
translations. Widget presentation terms come from `translations/<language>.json`
with English fallback. All other values preserve Home Assistant's public field
names.

`icon` is a local Material Design Icons class name such as
`mdi-weather-rainy`. The template combines it with the global `mdi` class
provided by OpenDisplay Studio Renderer. Weather rendering never downloads
remote images.

References:

- https://www.home-assistant.io/integrations/weather/
- https://developers.home-assistant.io/docs/core/entity/weather/
