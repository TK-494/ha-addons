# Security

- **Geen secrets in de repo.** Tokens, API-keys en wachtwoorden horen niet in version control.
- **Configuratie via `.env`.** Gebruik `.env.example` als sjabloon; `.env` zelf wordt genegeerd door git.
- **Echte gezondheidsdata blijft offline.** Ruwe exports en parsed data worden nooit gecommit.
- **Meld kwetsbaarheden privé.** Geen publieke issues met gevoelige details of proof-of-concept-data.
- **Beveilig de endpoints.** De upload- en reload-endpoints moeten achter veilige toegang draaien
  (lokaal netwerk of je eigen reverse proxy met authenticatie), nooit onbeveiligd op het open internet.
