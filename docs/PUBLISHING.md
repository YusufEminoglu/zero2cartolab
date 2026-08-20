# Publishing Notes

## Build the Plugin ZIP

From `C:\Users\YE\PyCharmMiscProject\qgis_plugins`:

```powershell
.\packaging\Build-PluginZip.ps1 -PluginDir planx_cartolab
```

Output:

```text
QGIS_Plugin_Releases\planx_cartolab.zip
```

## Validate Before Push

```powershell
py -3 .\packaging\validate_plugin.py .\planx_cartolab
py -3 .\packaging\full_release_gate.py --plugins planx_cartolab --skip-runtime --skip-geostats-smoke
```

## GitHub Pages

Use the repository settings:

```text
Settings > Pages
Source: Deploy from a branch
Branch: master
Folder: /docs
```

The landing page is `docs/index.html`.

## Release Discipline

- Do not add AI co-author trailers.
- Keep visible plugin UI text in English.
- Keep GitHub showcase files out of the QGIS Plugin Hub ZIP through `.zipignore`.
