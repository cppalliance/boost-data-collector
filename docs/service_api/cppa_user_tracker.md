# cppa_user_tracker.services

**Module path:** `cppa_user_tracker.services`  
**Description:** Identity, profiles, emails, and staging (TmpIdentity, TempProfilieIdentityRelation). Single place for all writes to cppa_user_tracker models.

**Type notation:** Model types refer to `cppa_user_tracker.models` (e.g. `Identity`, `BaseProfile`, `Email`).

---

## Identity

| Function                 | Parameter types                                           | Return type        | Description                                                                             |
| ------------------------ | --------------------------------------------------------- | ------------------ | --------------------------------------------------------------------------------------- |
| `create_identity`        | `display_name: str = ""`, `description: str = ""`         | `Identity`         | Create a new Identity.                                                                  |
| `get_or_create_identity` | `display_name: str = ""`, `description: str = ""`, `defaults: dict \| None = None` | `tuple[Identity, bool]` | Get or create an Identity by `display_name`. `defaults` overrides fields when creating. |

---

## TmpIdentity

| Function              | Parameter types                          | Return type   | Description                     |
| --------------------- | ---------------------------------------- | ------------- | ------------------------------- |
| `create_tmp_identity` | `display_name: str = ""`, `description: str = ""` | `TmpIdentity` | Create a TmpIdentity (staging). |

---

## TempProfilieIdentityRelation

| Function                                | Parameter types                        | Return type                                   | Description                                    |
| --------------------------------------- | -------------------------------------- | --------------------------------------------- | ---------------------------------------------- |
| `add_temp_profile_identity_relation`    | `base_profile: BaseProfile`, `target_identity: TmpIdentity` | `tuple[TempProfilieIdentityRelation, bool]` | Link a BaseProfile to a TmpIdentity (staging). |
| `remove_temp_profile_identity_relation` | `base_profile: BaseProfile`, `target_identity: TmpIdentity` | `None`                                        | Remove the staging relation.                   |

---

## Email

| Function       | Parameter types                                                    | Return type | Description                                                        |
| -------------- | ------------------------------------------------------------------ | ----------- | ------------------------------------------------------------------ |
| `add_email`   | `base_profile: BaseProfile`, `email: str`, `is_primary: bool = False`, `is_active: bool = True` | `Email`     | Add an email to a BaseProfile.                                     |
| `update_email` | `email_obj: Email`, `**kwargs: Any`                                | `Email`     | Update an Email. Allowed keys: `email`, `is_primary`, `is_active`. |
| `remove_email` | `email_obj: Email`                                                 | `None`      | Delete an email.                                                   |

---

## Related

- [Service API index](README.md)
- [Contributing](../Contributing.md)
- [Schema](../Schema.md)
