# Lyrics

MiraSpeak module. Looks up a song on [LRCLIB](https://lrclib.net) and speaks the lines.

Needs MiraSpeak with module API 1. The lookup uses `httpx`, which MiraSpeak already provides. There is no API key.

## Install

In MiraSpeak, open **Integrations → Modules → Install from GitHub** and paste:

https://github.com/miramocha/MiraSpeak-lyrics

Leave the ref blank for the default branch, or enter `v0.1.0`.

It asks for **speak**, **network**, and **MCP tools**. Python modules are not limited to LRCLIB: granting network means the module runs with the same access as MiraSpeak.

## License

[MIT](LICENSE)
