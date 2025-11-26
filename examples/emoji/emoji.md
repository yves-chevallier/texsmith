# Emoji Support

TeXSmith now renders emoji as glyphs (no remote SVG fetch) when you pick a font flavour:

```yaml
press:
  fonts:
    emoji: black   # black | color | twemoji | "Custom Family"
```

- `black` (défaut) : OpenMoji Black (mono, noir et blanc).
- `color` : Noto Color Emoji.
- `twemoji` : passe par le package `twemoji`.
- `artifact` : (héritage) retombe sur les images téléchargées.
- Tout autre nom est utilisé comme famille directe.

Engines :
- LuaLaTeX s’appuie sur `luaotfload` pour ajouter la police emoji en fallback.
- XeLaTeX/Tectonic utilisent `ucharclasses` pour basculer automatiquement sur la police emoji sur la plage U+1F000–U+1FAFF.

Vous pouvez taper les emoji directement dans le Markdown :

| Emoji | Description                    |
| ----- | ------------------------------ |
| 😊    | Smiling face with smiling eyes |
| 🚀    | Rocket                         |
| 🍕    | Pizza                          |
| 🎉    | Party popper                   |
| 🐍    | Snake                          |
| 🌍    | Globe showing Europe-Africa    |
| 💻    | Laptop computer                |
| 📚    | Books                          |
| 🎨    | Artist palette                 |
| 👽    | Alien                          |
| 👋    | Waving hand                    |
| 🤖    | Robot                          |
| 🦄    | Unicorn                        |
| 🧠    | Brain                          |
| 🛸    | Flying saucer                  |
| 🛰️    | Satellite                      |
| 🐙    | Octopus                        |
| 📝    | Memo                           |
| 📋    | Note                           |
| ⭐    | Star                           |
| ✅    | Check mark                     |
| ❌    | Cross mark                     |
| 🧪    | Experiment                     |
| 💡    | Light Bulb                     |
