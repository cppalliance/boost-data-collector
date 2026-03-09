import re
text = """- [2026-01 mailing](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2026/#mailing2026-01)
- [2026-02 pre-Croydon mailing](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2026/#mailing2026-02)
- [2026](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2026/) N5034-N????"""

pattern = re.compile(r'\[([^\]]+)\]\([^#]+#mailing(\d{4}-\d{2})\)')
for m in pattern.finditer(text):
    print(m.groups())
