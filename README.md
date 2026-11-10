# Electromaps for Home Assistant

Custom integration that exposes the live status of every connector of a public
charging station listed on [Electromaps](https://map.electromaps.com) as a
Home Assistant sensor.

Not affiliated with or endorsed by Electromaps.

## What you get

- One device per station, one enum sensor per connector:
  `available` / `occupied` / `out_of_service` / `unknown`.
- Attributes: `status_since` (when the connector entered its current status,
  as reported by Electromaps), `plug_type`, `power_kw`, `connector_id`.
- If Electromaps cannot be reached, the sensors become `unavailable`. So
  `unknown` in the history always means Electromaps itself reported it, never
  that the request failed.
- History is kept by the standard Home Assistant recorder.

## Notifications (blueprint)

The integration fires `electromaps_connector_status_changed` once per
connector whose status differs from the previous successful poll. It does not
fire after a restart or when the connection to Electromaps is restored. Event
data: `device_id`, `entity_id`, `location_id`, `location_name`,
`connector_id`, `connector_name`, `from_status`, `to_status`, `from_since`,
`since`.

Events are fired after the sensors have written their new states, so an
automation handling one can read up-to-date sensor states.

Once per poll, for a station where at least one connector changed, it also
fires `electromaps_station_status_changed` with `device_id`, `location_id`,
`location_name`, `free`, `free_before`, `total` and `statuses`
(connector name → status). Use it to detect "no free connector left" without
reading entity states.

The bundled blueprint lets you pick up to three stations (as devices, so all
of their connectors are watched), what to report (a connector becomes free,
occupied or out of service, and/or no free connector is left at a station;
by default: becomes free), the message language and your notification action:

[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Ffttomas%2Fha-electromaps%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Felectromaps%2Fconnector_status_notify.yaml)

The notification action gets `message`, `message_html` (the same text in a
`<pre>` block, monospace in Telegram with `parse_mode: html`) and `title`
variables, for example:

```yaml
action: notify.mobile_app_phone
data:
  message: "{{ message }}"
```

## Footprint

- One GET request to `https://www.electromaps.com/mapi/v2/locations/<id>` per
  interval for the whole station (default 30 s, configurable 30–3600 s), about
  1 KB gzipped, through Home Assistant's shared HTTP session.
- No state writes while nothing changes: the coordinator runs with
  `always_update=False`, and the snapshot it compares holds only the
  connector fields. Ratings, comments and ads are left out.
- On errors the next attempt backs off exponentially (60 → 120 → … up to
  900 s). `Retry-After` is honoured, and 429/503/403 also trigger a back-off.

## Installation

Via the Marketplace (HACS) in Home Assistant 2026.11+:

1. Settings → Marketplace → Add from link → `fttomas/ha-electromaps`
   (type: Integration), then install it.
2. Restart Home Assistant.
3. Settings → Devices & services → Add integration → Electromaps. Enter the
   station ID or its map URL, e.g. `https://map.electromaps.com/en/p/123456`.
4. To change the poll interval, open the integration and click Configure.

Manual install: copy `custom_components/electromaps` into
`<config>/custom_components/` and restart.

## Tests

```
python3 -m unittest discover -s tests
```

The tests cover payload and input parsing on a synthetic fixture, and need no
Home Assistant install.

## API notes

The endpoint is anonymous. Connector statuses used by the Electromaps web app
are `AVAILABLE`, `OCCUPIED`, `OUT_OF_SERVICE` and `UNKNOWN`. Any other value is
mapped to `unknown`. An unknown station ID returns HTTP 403 with
`error_code: LOCATION_NOT_FOUND`.

## License

MIT
