# AAROHA destination photo credits

The photographs below are genuine views of the named place or region. The site uses local JPEG assets under `app/static/images/destinations/`; the verified working source copies are preserved in its `originals/` subfolder, and no destination photo is loaded from a third party at runtime. Crop and resize derivatives retain the source photograph's attribution and licence. For CC BY-SA derivatives, AAROHA distributes the crops under the same CC BY-SA licence identified below.

| Destination and subject | Photographer | Commons/Pixabay full resolution | Local working copy | Source | Licence |
| --- | --- | --- | --- | --- | --- |
| Hampi — Matanga Hill boulder landscape | Vyacheslav Argenberg | 4032 × 2688 | `originals/hampi-matanga-source.jpg` — 3840 × 2560 | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Hampi_landscape_from_Matanga_Hill,_Hampi,_India.jpg) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Hampi — Virupaksha Temple | Nlgirish | 4928 × 3264 | `originals/hampi-virupaksha-source.jpg` — 3840 × 2543 | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Virupaksha_temple_hampi.jpg) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| Hampi — Vittala Temple stone chariot | Sid Mohanty | 4800 × 3200 | `originals/hampi-vittala-stone-chariot-source.jpg` — 3840 × 2560 | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Stone_Chariot_of_Vitthala_Temple,_Hampi.jpg) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| Anegundi — Anjaneya Hill and hilltop temple | Ingo Mehling | 7008 × 4672 | `originals/anegundi-anjaneya-source.jpg` — 3840 × 2560 | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Anegundi_-_Anjaneya_Hill.jpg) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| Gangavathi — rice fields | sarangib | 4896 × 3264 | `originals/gangavathi-rice-fields-source.jpg` — 1280 × 853 | [Pixabay](https://pixabay.com/photos/rice-fields-gangavati-karnataka-204139/) | [Pixabay Content License](https://pixabay.com/service/license-summary/) |
| Hosapete — Tungabhadra Dam and reservoir | Harvinder Chandigarh | 4032 × 3024 | `originals/hosapete-tungabhadra-dam-gates-source.jpg` — 2560 × 1920 | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:The_Tungabhadra_Dam_02.jpg) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Sanapur — Sanapur Lake and boulder shore | Christopher Soghoian | 1600 × 1200 | `originals/sanapur-lake-source.jpg` — 1600 × 1200 | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Sanapur_lake,_Hampi.jpg) | [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/) |
| Kamalapura — market ruins by Krishna Temple | Ms Sarah Welch | 4032 × 3024 | `originals/kamalapura-krishna-market-source.jpg` — 3840 × 2880 | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:16th-century_traders_market_ruins_facing_Krishna_temple,_Kamalapura_Hampi_Hindu_monuments_Karnataka.jpg) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |

## Local derivatives

Filenames use `{subject}-{width}x{height}.jpg`. Commons originals with sufficient resolution have:

- `1920x900` wide hero crop
- `1200x900` desktop 4:3 card crop
- `800x1000` mobile 4:5 card crop
- `480x360` compact thumbnail

Gangavathi's downloaded source is 1280 × 853, so it has a 1200 × 800 landscape card, a 1200 × 562 wide hero crop, a 682 × 853 portrait crop and a 480 × 360 thumbnail. It is deliberately not upscaled to the nominal 1920px hero or 800 × 1000 mobile targets. The source is a regional rice-field landscape; it is not presented as a particular landmark.

Sanapur's 1600 × 1200 source has a 1600 × 750 hero crop (kept at source resolution), 1200 × 900 desktop card, 800 × 1000 mobile card and 480 × 360 thumbnail. The UI scales it down to the rendered width.

Hosapete uses a 1920 × 900 wide hero crop, 1200 × 900 desktop card, 800 × 1000 mobile card and 480 × 360 thumbnail. Its detail page also has `hosapete-tungabhadra-dam-gates-hero-800x1000.jpg`, a dedicated portrait crop that keeps the dam gates above the overlaid title and actions.

Hampi's Virupaksha and Vittala landmark photographs use the same responsive derivative sizes as the Commons locations above. The desktop/mobile selection is made in `picture` elements; below-the-fold images lazy-load, while the visible home hero is eager and high priority. Failed image requests fall back to the existing forest or ivory surface.

Sources and licenses were checked on the original file pages before downloading. The source files are resized/cropped only; no structures or scenery have been generated or added.
