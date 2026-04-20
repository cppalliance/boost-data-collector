# cppa_user_tracker.services

**Module path:** `cppa_user_tracker.services`
**Description:** Identity, profiles (GitHubAccount, SlackUser, MailingListProfile, DiscordProfile, etc.), emails, and staging (TmpIdentity, TempProfileIdentityRelation). Single place for all writes to cppa_user_tracker models.

**Type notation:** Model types refer to `cppa_user_tracker.models` (e.g. `Identity`, `BaseProfile`, `Email`).

---

## Identity

| Function                 | Parameter types                                                                    | Return type             | Description                                                                             |
| ------------------------ | ---------------------------------------------------------------------------------- | ----------------------- | --------------------------------------------------------------------------------------- |
| `create_identity`        | `display_name: str = ""`, `description: str = ""`                                  | `Identity`              | Create a new Identity.                                                                  |
| `get_or_create_identity` | `display_name: str = ""`, `description: str = ""`, `defaults: dict \| None = None` | `tuple[Identity, bool]` | Get or create an Identity by `display_name`. `defaults` overrides fields when creating. |

---

## TmpIdentity

| Function              | Parameter types                                   | Return type   | Description                     |
| --------------------- | ------------------------------------------------- | ------------- | ------------------------------- |
| `create_tmp_identity` | `display_name: str = ""`, `description: str = ""` | `TmpIdentity` | Create a TmpIdentity (staging). |

---

## TempProfileIdentityRelation

| Function                                | Parameter types                                             | Return type                                | Description                                    |
| --------------------------------------- | ----------------------------------------------------------- | ------------------------------------------ | ---------------------------------------------- |
| `add_temp_profile_identity_relation`    | `base_profile: BaseProfile`, `target_identity: TmpIdentity` | `tuple[TempProfileIdentityRelation, bool]` | Link a BaseProfile to a TmpIdentity (staging). |
| `remove_temp_profile_identity_relation` | `base_profile: BaseProfile`, `target_identity: TmpIdentity` | `None`                                     | Remove the staging relation.                   |

---

## MailingListProfile

| Function                             | Parameter types                             | Return type                       | Description                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------ | ------------------------------------------- | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `get_or_create_mailing_list_profile` | `display_name: str = ""`, `email: str = ""` | `tuple[MailingListProfile, bool]` | Get or create a MailingListProfile by display_name and email. Looks up a profile with this display_name and an Email with this address; if found, returns it. Otherwise creates a new profile, adds the email via `add_email`, and returns the new profile. Raises `ValueError` if `display_name` or `email` is missing or empty. |

---

## WG21PaperAuthorProfile

| Function                               | Parameter types                              | Return type                            | Description                                                                                                                                                                                                                                                                                                                                 |
| -------------------------------------- | -------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `get_or_create_wg21_paper_author_profile` | `display_name: str`, `email: str \| None = None` | `tuple[WG21PaperAuthorProfile, bool]` | Resolve by display_name (optional email for disambiguation). If no profile exists, creates one and adds email if provided. If one exists, returns it. If multiple exist and one matches the email, returns that profile. If multiple exist and no email is provided, returns the first. If multiple exist and the supplied email matches none, creates a new profile with that email. **Side effect:** if `email` is supplied and the resolved or created profile does not already have that email, the function associates it with the profile (so existing profiles may be updated). Returns the profile and a boolean indicating creation. Use when linking paper authors so that same name + same email link to the same profile. |

---

## DiscordProfile

| Function                           | Parameter types                                                                                                                      | Return type                     | Description                                                                                                                   |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `get_or_create_discord_profile`    | `discord_user_id: int`, `username: str = ""`, `display_name: str = ""`, `avatar_url: str = ""`, `is_bot: bool = False`, `identity: Identity \| None = None` | `tuple[DiscordProfile, bool]`   | Get or create a DiscordProfile by `discord_user_id`. Updates username, display_name, avatar_url, is_bot if profile exists. |

---

## Email

| Function       | Parameter types                                                                                 | Return type | Description                                                        |
| -------------- | ----------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------ |
| `add_email`    | `base_profile: BaseProfile`, `email: str`, `is_primary: bool = False`, `is_active: bool = True` | `Email`     | Add an email to a BaseProfile.                                     |
| `update_email` | `email_obj: Email`, `**kwargs: Any`                                                             | `Email`     | Update an Email. Allowed keys: `email`, `is_primary`, `is_active`. |
| `remove_email` | `email_obj: Email`                                                                              | `None`      | Delete an email.                                                   |

---

## Related

- [Service API index](README.md)
- [Contributing](../Contributing.md)
- [Schema](../Schema.md)
